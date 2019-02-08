from django.http import HttpResponse

from django.views.decorators.csrf import csrf_exempt


def cross_origin_read_allow(function):
    """
    Cross-Origin 의 Http 상의 접근을 허용하는 Decorator
    * ORIGIN Header 를 확인하지 못할 경우, Credentials 옵션이 false
    """

    def wrap(request, *args, **kwargs):
        if request.method == 'OPTIONS':
            response = HttpResponse()
        else:
            response = function(request, *args, **kwargs)

        if 'HTTP_ORIGIN' in request.META:
            response["Access-Control-Allow-Origin"] = request.META['HTTP_ORIGIN']
            response["Access-Control-Allow-Credentials"] = 'true'
        else:
            response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS, POST"
        response["Access-Control-Max-Age"] = "1000"
        response["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type"
        return response

    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return csrf_exempt(wrap)
