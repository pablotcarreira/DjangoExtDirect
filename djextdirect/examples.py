#-*- coding: utf-8 -*-
# 2014 - Pablo T. Carreira


# In your views.py

from djextdirect import provider

EXT = provider.Provider(name="Ext.app.REMOTING_API", autoadd=False)


# You can use functions in views.
# In the client you would call Namespace.a_function({});
@EXT.register_method("Namespace")
def a_function(request, data):
    result = data['property1'] * data['property2']
    # etc ... etc ...
    return result


class ClassToOrganizeCode(object):
    # You can use staticmethods.
    # In the client you would call ClassToOrganizeCode.a_staticmethod({});
    @staticmethod
    @EXT.register_method("ClassToOrganizeCode")
    def a_staticmethod(request, data):
        result = data['property1'] * data['property2']
        if result > 100:
            raise MyCustomError(result)
        else:
            return result


# It's possible to propagate error messages to the client even in production (DEBUG=False).
# For that you need to define exceptions with a special flag.
class MyCustomError(Exception):
    # This flag tels the app that the error message shoud go to the client even in production moode.
    visible = True

    def __init__(self, value=None):
        self.message = "Value is over 100, it is {}.".format(value)

    def __str__(self):
        return self.message

# In the client you can use the error to display messages:
#
# ClassToOrganizeCode.a_staticmethod({property1: 10, property2: 20},
#     //callback
#     function(result, response, ok){
#         if (ok){
#             console.log(result)
#         }
#         else{
#             console.error(response.message)
#         }
#     }
# );



