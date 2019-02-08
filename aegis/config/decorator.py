from django.http import HttpResponse

from django.views.decorators.csrf import csrf_exempt


def cross_origin_read_allow(function):
    def wrap(request, *args, **kwargs):
        if request.method == 'OPTIONS':
            response = HttpResponse()
        else:
            response = function(request, *args, **kwargs)
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS, POST"
        response["Access-Control-Max-Age"] = "1000"
        response["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type"
        response["Access-Control-Allow-Credentials"] = True
        return response

    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return csrf_exempt(wrap)
