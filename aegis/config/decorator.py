import json

from importlib import import_module

from django.http import HttpResponse

from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from .error_handler import exception_handler
from .status_collection import REG_403_FORBIDDEN
from .log import logSend, logError, logHeader
from .common import get_api, AES_DECRYPT_BASE64

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
            try:
                header = '\n'
                header += '>>> {}'.format(get_api(request))
                # logHeader('>>> {}'.format(get_api(request)))  # 함수 시작 표시
                # logSend('>>> {}'.format(get_api(request)))  # 함수 시작 표시
                if request.method == 'POST':
                    if len(request.body) == 0:
                        rqst = {}
                    else:
                        rqst = json.loads(request.body.decode("utf-8"))
                else:
                    rqst = request.GET
                # 함수 파라미터 표시
                for key in rqst.keys():
                    plain_text = ''
                    if '_id' in key:
                        plain_text = AES_DECRYPT_BASE64(str(rqst[key]))
                        if plain_text == '__error':
                            plain_text = ''
                    # if '_id' in key and 'n_id' not in key and '_id_' not in key:
                    #     # 'n_id': login_id 는 암호화된 값이 아니기 때문에 제외한다.
                    #     # '_id_':
                    #     if rqst[key] is not None and len(rqst[key]) > 20:  # AES 암호화 된 값이면 22자가 최소임 - 즉 암호화된 값
                    #         plain_text = AES_DECRYPT_BASE64(rqst[key])
                    #         if plain_text == '__error':
                    #             plain_text = ''
                    header += '\n^  {}: {} {}'.format(key, rqst[key], plain_text)
                    # logHeader('^  {}: {} {}'.format(key, rqst[key], plain_text))
                    # logSend('^  {}: {} {}'.format(key, rqst[key], plain_text))
                # logHeader(header)
                logSend(header)
                response = function(request, *args, **kwargs)
                # logHeader('<<< {}'.format(get_api(request)))  # 함수 끝 표시
                # logSend('<<< {}'.format(get_api(request)))  # 함수 끝 표시
            except Exception as e:
                # 해당 Decorator 를 사용하는 View 에서 오류 발생 시, 똑같은 오류처리
                # logSend('ERROR > {}'.format(get_api(request)))
                response = exception_handler(request, e)
        # logSend('<<< {}: {}\n^ {}'.format(get_api(request), response.status_code, response.content))
        # logSend('v {} {}'.format(resp.status_code, response_body['message']))
        # json_content = json.loads(response.content)
        # logSend('\nv {} {}\n<<< {}\n'.format(response.status_code, json_content['message'], get_api(request)))
        logSend('\nv {}\n<<< {}\n'.format(response.status_code, get_api(request)))

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
        # logSend('  cross_origin_read_allow: response: {}'.format(response))
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
            # print(request.META['HTTP_TOKEN'])
            request.session = SessionStore(session_key=request.META['HTTP_TOKEN'])
        response = function(request, *args, **kwargs)
        return response

    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap


def session_is_none_403(function):
    """
    session 의 id 가 None 일 경우 혹, session 자체가 없는 경우 404 오류
    - session 의 id 가 없는 경우 403 오류를 내는 decorator 정의
    웹에서는 Header 의 Token 값을 선행 조건으로 사용하기 때문에, session_is_none_403 보다 선행적으로 cross_origin_read_allow 가 정의 되어야함.

    EX )
    올바른 예)
    @cross_origin_read_allow
    @session_is_none_403
    def view_name(request):
        ....

    웹에 사용되지 않을 경우엔 cross_origin_read_allow 가 선행이 되지 않아도 무방.
    """

    def wrap(request, *args, **kwargs):
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET
        if ('worker_id' not in rqst) and (
                (request.session is None) or ('id' not in request.session) or (request.session['id'] is None)):
            return REG_403_FORBIDDEN.to_json_response()
        response = function(request, *args, **kwargs)
        return response

    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap


def session_is_none_403_with_operation(function):
    """
    session 의 id 가 None 일 경우 혹, session 자체가 없는 경우 404 오류
    - session 의 id 가 없는 경우 403 오류를 내는 decorator 정의
    웹에서는 Header 의 Token 값을 선행 조건으로 사용하기 때문에, session_is_none_403 보다 선행적으로 cross_origin_read_allow 가 정의 되어야함.

    EX )
    올바른 예)
    @cross_origin_read_allow
    @session_is_none_403
    def view_name(request):
        ....

    웹에 사용되지 않을 경우엔 cross_origin_read_allow 가 선행이 되지 않아도 무방.
    """

    def wrap(request, *args, **kwargs):
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET
        if ('worker_id' not in rqst) and (
                request.session is None or 'op_id' not in request.session or request.session['op_id'] is None):
            return REG_403_FORBIDDEN.to_json_response()
        response = function(request, *args, **kwargs)
        return response

    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap

