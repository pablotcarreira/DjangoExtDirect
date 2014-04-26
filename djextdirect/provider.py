# -*- coding: utf-8 -*-

"""
 *  Copyright (C) 2010, Michael "Svedrin" Ziegler <diese-addy@funzt-halt.net>
 *
 *  djExtDirect is free software; you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation; either version 2 of the License, or
 *  (at your option) any later version.
 *
 *  This package is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 ----------------------------------------------------------------------------------------

 Modified 2014 - Pablo Torres Carreira
 - Now working with Django 1.6 and ExtJS 4.
 - Improved traceback formating when on debug mode to make it more easily readeable in Chrome or Firefox.
 - Custom errors messages can be propagated to the client without the traceback when not on debug mode.



"""

import json as simplejson
import inspect
import functools
import traceback
from sys import stderr

from django.http import HttpResponse
from django.conf import settings
from django.conf.urls import patterns
from django.core.urlresolvers import reverse
from django.utils.datastructures import MultiValueDictKeyError
from django.core.serializers.json import DjangoJSONEncoder
import sys


def getname(cls_or_name):
    """ If cls_or_name is not a string, return its __name__. """
    if type(cls_or_name) not in (str, unicode):
        return cls_or_name.__name__
    return cls_or_name


class Provider(object):
    """ Provider for Ext.Direct. This class handles building API information and
        routing requests to the appropriate functions, and serializing their
        response and exceptions - if any.

        Instantiation:

        >>> EXT_JS_PROVIDER = Provider( [name="Ext.app.REMOTING_API", autoadd=True] )

        If autoadd is True, the api.js will include a line like such::

            Ext.Direct.addProvider( Ext.app.REMOTING_API );

        After instantiating the Provider, register functions to it like so:

        >>> @EXT_JS_PROVIDER.register_method("myclass")
        ... def myview( request, possibly, some, other, arguments ):
        ...    " does something with all those args and returns something "
        ...    return 13.37

        Note that those views **MUST NOT** return an HttpResponse but simply
        the plain result, as the Provider will build a response from whatever
        your view returns!

        To be able to access the Provider, include its URLs in an arbitrary
        URL pattern, like so:

        >>> from views import EXT_JS_PROVIDER # import our provider instance
        >>> urlpatterns = patterns(
        ...     # other patterns go here
        ...     ( r'api/', include(EXT_DIRECT_PROVIDER.urls) ),
        ... )

        This way, the Provider will define the URLs "api/api.js" and "api/router".

        If you then access the "api/api.js" URL, you will get a response such as::

            Ext.app.REMOTING_API = { # Ext.app.REMOTING_API is from Provider.name
                "url": "/mumble/api/router",
                "type": "remoting",
                "actions": {"myclass": [{"name": "myview", "len": 4}]}
                }

        You can then use this code in ExtJS to define the Provider there.
    """

    def __init__(self, name="Ext.app.REMOTING_API", autoadd=True):
        self.name = name
        self.autoadd = autoadd
        self.classes = {}

    def register_method(self, cls_or_name, flags=None):
        """ Return a function that takes a method as an argument and adds that
            to cls_or_name.

            The flags parameter is a dictionary for additional information, e.g. formHandler=True.

            Note: This decorator does not replace the method by a new function,
            it returns the original function as-is.
        """
        return functools.partial(self._register_method, cls_or_name, flags=flags)

    def _register_method(self, cls_or_name, method, flags=None):
        """ Actually registers the given function as a method of cls_or_name. """
        clsname = getname(cls_or_name)
        if clsname not in self.classes:
            self.classes[clsname] = {}
        if flags is None:
            flags = {}
        self.classes[clsname][method.__name__] = method
        method.EXT_argnames = inspect.getargspec(method)[0][1:]
        method.EXT_len = len(method.EXT_argnames)
        method.EXT_flags = flags
        return method

    def build_api_dict(self):
        actdict = {}
        for clsname in self.classes:
            actdict[clsname] = []
            for methodname in self.classes[clsname]:
                methinfo = {
                    "name": methodname,
                    "len": self.classes[clsname][methodname].EXT_len
                }
                methinfo.update(self.classes[clsname][methodname].EXT_flags)
                actdict[clsname].append(methinfo)

        return actdict

    def get_api_plain(self, request):
        """ Introspect the methods and get a JSON description of only the API. """
        return HttpResponse(simplejson.dumps({
                                                 "url": reverse(self.request),
                                                 "type": "remoting",
                                                 "actions": self.build_api_dict()
                                             }, cls=DjangoJSONEncoder), mimetype="application/json")

    def get_api(self, request):
        """ Introspect the methods and get a javascript description of the API
            that is meant to be embedded directly into the web site.
        """
        request.META["CSRF_COOKIE_USED"] = True
        lines = ["%s = %s;" % ( self.name, simplejson.dumps({
                                                                "url": reverse(self.request),
                                                                "type": "remoting",
                                                                "actions": self.build_api_dict()
                                                            }, cls=DjangoJSONEncoder))]

        if self.autoadd:
            lines.append(
                """Ext.Ajax.on("beforerequest", function(conn, options){"""
                """    if( !options.headers )"""
                """        options.headers = {};"""
                """    options.headers["X-CSRFToken"] = Ext.util.Cookies.get("csrftoken");"""
                """});"""
            )
            lines.append("Ext.Direct.addProvider( %s );" % self.name)

        return HttpResponse("\n".join(lines), mimetype="text/javascript")

    def request(self, request):
        """ Implements the Router part of the Ext.Direct specification.

            It handles decoding requests, calling the appropriate function (if
            found) and encoding the response / exceptions.
        """
        request.META["CSRF_COOKIE_USED"] = True
        # First try to use request.POST, if that doesn't work check for req.raw_post_data.
        # The other way round this might make more sense because the case that uses
        # raw_post_data is way more common, but accessing request.POST after raw_post_data
        # causes issues with Django's test client while accessing raw_post_data after
        # request.POST does not.
        # [Pablo] - Changed request.raw_post_data to request.body in Django 1.6.


        try:
            jsoninfo = {
                'action': request.POST['extAction'],
                'method': request.POST['extMethod'],
                'type': request.POST['extType'],
                'upload': request.POST['extUpload'],
                'tid': request.POST['extTID'],
            }
        except (MultiValueDictKeyError, KeyError), err:
            try:
                rawjson = simplejson.loads(request.body)
            except getattr(simplejson, "JSONDecodeError", ValueError):
                return HttpResponse(simplejson.dumps({
                                                         'type': 'exception',
                                                         'message': 'malformed request',
                                                         'where': err.message,
                                                         "tid": None,  # dunno
                                                     }, cls=DjangoJSONEncoder), mimetype="application/json")
            else:
                return self.process_normal_request(request, rawjson)
        else:
            return self.process_form_request(request, jsoninfo)

    def process_normal_request(self, request, rawjson):
        """ Process standard requests (no form submission or file uploads). """
        if not isinstance(rawjson, list):
            rawjson = [rawjson]

        responses = []

        for reqinfo in rawjson:
            cls, methname, data, rtype, tid = (reqinfo['action'],
                                               reqinfo['method'],
                                               reqinfo['data'],
                                               reqinfo['type'],
                                               reqinfo['tid'])

            if cls not in self.classes:
                responses.append({
                    'type': 'exception',
                    'message': 'no such action',
                    'where': cls,
                    "tid": tid,
                })
                continue

            if methname not in self.classes[cls]:
                responses.append({
                    'type': 'exception',
                    'message': 'no such method',
                    'where': methname,
                    "tid": tid,
                })
                continue

            func = self.classes[cls][methname]

            if func.EXT_len and len(data) == 1 and type(data[0]) == dict:
                # data[0] seems to contain a dict with params. check if it does, and if so, unpack
                args = []
                for argname in func.EXT_argnames:
                    if argname in data[0]:
                        args.append(data[0][argname])
                    else:
                        args = None
                        break
                if args:
                    data = args

            if data is not None:
                datalen = len(data)
            else:
                datalen = 0

            if datalen != len(func.EXT_argnames):
                responses.append({
                    'type': 'exception',
                    'tid': tid,
                    'message': 'invalid arguments',
                    'where': 'Expected %d, got %d' % ( len(func.EXT_argnames), len(data) )
                })
                continue

            try:
                if data:
                    result = func(request, *data)
                else:
                    result = func(request)

            except Exception as error:
                errinfo = {
                    'type': 'exception',
                    "tid": tid,
                }
                if settings.DEBUG:
                    traceback.print_exc(file=stderr)
                    errinfo['message'] = error.__str__()
                    errinfo['where'] = traceback.format_tb(sys.exc_traceback)
                else:
                    if hasattr(error, "visible"):
                        errinfo['message'] = error.__str__()
                    else:
                        errinfo['message'] = 'Erro Interno.'
                    errinfo['where'] = ''
                responses.append(errinfo)

            else:
                responses.append({
                    "type": rtype,
                    "tid": tid,
                    "action": cls,
                    "method": methname,
                    "result": result
                })

        if len(responses) == 1:
            return HttpResponse(simplejson.dumps(responses[0], cls=DjangoJSONEncoder), mimetype="application/json")
        else:
            return HttpResponse(simplejson.dumps(responses, cls=DjangoJSONEncoder), mimetype="application/json")

    def process_form_request(self, request, reqinfo):
        """ Router for POST requests that submit form data and/or file uploads. """
        cls, methname, rtype, tid = (reqinfo['action'],
                                     reqinfo['method'],
                                     reqinfo['type'],
                                     reqinfo['tid'])

        if cls not in self.classes:
            response = {
                'type': 'exception',
                'message': 'no such action',
                'where': cls,
                "tid": tid,
            }

        elif methname not in self.classes[cls]:
            response = {
                'type': 'exception',
                'message': 'no such method',
                'where': methname,
                "tid": tid,
            }

        else:
            func = self.classes[cls][methname]
            try:
                result = func(request)

            except Exception, err:
                result = None
                errinfo = {
                    'type': 'exception',
                    "tid": tid,
                }
                if settings.DEBUG:
                    traceback.print_exc(file=stderr)
                    errinfo['message'] = err.message
                    errinfo['where'] = traceback.format_exc()
                else:
                    errinfo['message'] = 'The socket packet pocket has an error to report.'
                    errinfo['where'] = ''
                response = errinfo

            else:
                response = {
                    "type": rtype,
                    "tid": tid,
                    "action": cls,
                    "method": methname,
                    "result": result
                }

        if reqinfo['upload'] == "true":
            response = {'type': rtype, 'tid': tid, 'action': cls,
                        'method': methname, 'result': result, 'success': True}
            return HttpResponse(simplejson.dumps(response, cls=DjangoJSONEncoder), mimetype="text/html")
        else:
            return HttpResponse(simplejson.dumps(response, cls=DjangoJSONEncoder), mimetype="application/json")

    def get_urls(self):
        """ Return the URL patterns. """
        pat = patterns('',
                       (r'api.json$', self.get_api_plain ),
                       (r'api.js$', self.get_api ),
                       (r'router/?', self.request ),
        )
        return pat

    urls = property(get_urls)
