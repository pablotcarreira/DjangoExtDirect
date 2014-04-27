### Introduction.

This code was originally created by Michael "Svedrin" Ziegler (https://bitbucket.org/Svedrin/djextdirect).
I made some changes so it's now compatible with ExtJS 4.x (probably ExtJS 5 too) and Django 1.6.

I also implemented some extra features:

 - Improved traceback formating when on debug mode to make it more easily readeable in Chrome or Firefox.
    The python traceback is now a list of strings and it's easy to read in the debug tools.

 - Custom errors messages can be propagated to the client without the traceback when not on debug mode.
    You can create custom exceptions with a special flag. This flag tels the app that the error message shoud
    go to the client even in production mode and without the traceback.

### Instalation.

Put the **djextdirect** folder in you PYTHONPATH or in your project tree.

### Usage.

#### First instantiate the provider somewhere, it could be in your views.py

```python

from djextdirect import provider

EXT = provider.Provider(name="Ext.app.REMOTING_API", autoadd=False)

```

#### Then add the line `url(r'^direct/', include(EXT.urls))` to the tuple of URLs,
like that:

```python

from myapp.views import EXT

urlpatterns = patterns('',
                       url(r'^direct/', include(EXT.urls)),
                       # ... other urls ....
                       )
```


#### In you views, decorate your functions to expose them to the client.

You can decorate functions:

```python
@EXT.register_method("Namespace")
def a_function(request, data):
    result = data['property1'] * data['property2']
    # etc ... etc ...
    return result
```

In the client you would call `Namespace.a_function({property1: 10, property2: 10});`

You can also use classes and staticmethods to organize your code:

```python
class ClassToOrganizeCode(object):
    @staticmethod
    @EXT.register_method("ClassToOrganizeCode")
    def a_staticmethod(request, data):
        result = data['property1'] * data['property2']
        if result > 100:
            raise MyCustomError(result)
        else:
            return result
```

In the client you would call `ClassToOrganizeCode.a_staticmethod({property1: 10, property2: 10});`


#### In order to propagate error messages:

It's possible to propagate error messages to the client even in production (DEBUG=False).
For that you need to define exceptions with a special flag.
To flag the exception add the property `visible=True` to the class.

```python

class MyCustomError(Exception):
    # This flag tels the app that the error message shoud go to the client even in production moode.
    visible = True

    def __init__(self, value=None):
        self.message = "Value is over 100, it is {}.".format(value)

    def __str__(self):
        return self.message
```

In the client you can use the error message to display messages to the user, in the example I log to the
console, but you can open a window, or pop up a toast with the error:

```javascript
ClassToOrganizeCode.a_staticmethod({property1: 10, property2: 20},
    //callback
    function(result, response, ok){
        if (ok){
            console.log(result)
        }
        else{
            console.error(response.message)
        }
    }
);
```

If the exception does not have the flag, in the production mode (DEBUG=False),
the provider passes the message "Internal Error".
In the debug mode (DEBUG=True) the provider passes the error message and the traceback for all errors.
