from importlib import import_module

from django.http import HttpResponse

from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

SessionStore = import_module(settings.SESSION_ENGINE).SessionStore


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
            response["Access-Control-Expose-Headers"] = "Token"
            response["Access-Control-Allow-Credentials"] = 'true'
        else:
            response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS, POST"
        response["Access-Control-Max-Age"] = "3600"
        response["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type, Token"
        if request.session.session_key:
            response['Token'] = request.session.session_key
        return response

    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return csrf_exempt(token_to_session(wrap))


def token_to_session(function):
    """
    Web Client 에서 Header 에서 받은 Token 값으로 Session 으로 치환하는 Decorator
    """
    def wrap(request, *args, **kwargs):
        if 'HTTP_TOKEN' in request.META:
            print(request.META['HTTP_TOKEN'])
            request.session = SessionStore(session_key=request.META['HTTP_TOKEN'])
        response = function(request, *args, **kwargs)
        return response

    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap
