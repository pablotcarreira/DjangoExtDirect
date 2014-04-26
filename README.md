

This code was originally created by Michael "Svedrin" Ziegler (https://bitbucket.org/Svedrin/djextdirect).
I made some changes so it's now compatible with ExtJS 4.x (probably ExtJS 5 too) and Django 1.6.

I also implemented some extra features:

 - Improved traceback formating when on debug mode to make it more easily readeable in Chrome or Firefox.
    The python traceback is now a list of strings and it's easy to read in the debug tools.

 - Custom errors messages can be propagated to the client without the traceback when not on debug mode.
    You can create custom exceptions with a special flag. This flag tels the app that the error message shoud
    go to the client even in production mode and without the traceback.
