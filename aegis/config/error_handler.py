from django.http import HttpResponse
from django.conf import settings

import traceback
import os
import json
import datetime
from datetime import timedelta

from .log import logSend, logError
from .status_collection import *
from .common import str_to_datetime, dt_str, get_api


class BaseMiddleware:
    def __init__(self, get_response):
        # logSend('>>> BaseMiddleware __init__')
        self.get_response = get_response

    def __call__(self, request):
        # logSend('>>> BaseMiddleware __call__: {}'.format(request.get_full_path()))
        # logSend('   request.session: {}'.format([key for key in request.session.keys()]))
        if 'op_id' in request.session.keys() or 'id' in request.session.keys():
            dt_last = str_to_datetime(request.session['dt_last'])
            # logSend('  before: {}'.format(dt_last))
            dt_now = datetime.datetime.now()
            if (dt_now - dt_last).seconds > settings.SESSION_COOKIE_AGE:
                # 쎄션 유지 시간(settings.SESSION_COOKIE_AGE)이 지났으면 로그아웃 처리
                del request.session['op_id']
                del request.session['dt_last']
                del request.session['request.get_full_path()']
                return REG_403_FORBIDDEN.to_json_response()
            # logSend('  request.get_full_path(): {}'.format(request.session['request.get_full_path()']))
            if 'reg' in request.get_full_path() or 'update' in request.get_full_path():
                # 등록 기능은 5초 이내에 다시 요청이 들어왔을 때 걸러낸다.
                if request.session['request.get_full_path()'] == request.get_full_path():
                    if (dt_now - dt_last).seconds < settings.REQUEST_TIME_GAP:
                        logError('Error: {} 5초 이내에 [등록]이나 [수정]요청이 들어왔다. (middleware)'.format(get_api(request)))
                        return REG_409_CONFLICT.to_json_response()
            request.session['dt_last'] = dt_str(dt_now, "%Y-%m-%d %H:%M:%S")
            request.session['request.get_full_path()'] = request.get_full_path()

        return self.get_response(request)


class ProcessExceptionMiddleware(BaseMiddleware):
    def process_exception(self, request, exception):
        # logSend('>>> ProcessExceptionMiddleware: process_exception')
        return exception_handler(request, exception)


def exception_handler(request, exception):
    # logSend('>>> ProcessExceptionMiddleware: exception_handler: function: {}'.format(request.get_full_path()))
    stack_trace = get_traceback_str()
    logError('{}\n{}'.format(get_api(request), stack_trace))
    # response = HttpResponse(json.dumps(
    #     {'message': str(exception),
    #      'stack_trace': stack_trace}
    # ), status=520)
    # my_json = response.content.decode('utf8').replace("'", '"')
    # logSend('  ERROR: {}'.format(my_json))
    # return REG_416_RANGE_NOT_SATISFIABLE.to_json_response()
    return HttpResponse(json.dumps(
        {'message': str(exception),
         'stack_trace': stack_trace}
    ), status=520)


def get_traceback_str():
    # logSend('>>> ProcessExceptionMiddleware: get_traceback_str')
    lines = traceback.format_exc().strip().split('\n')
    rl = [lines[-1]]
    lines = lines[1:-1]
    lines.reverse()
    nstr = ''
    for i in range(len(lines)):
        line = lines[i].strip()
        if line.startswith('File "'):
            eles = lines[i].strip().split('"')
            basename = os.path.basename(eles[1])
            lastdir = os.path.basename(os.path.dirname(eles[1]))
            eles[1] = '%s/%s' % (lastdir, basename)
            rl.append('^\t%s %s' % (nstr, '"'.join(eles)))
            nstr = ''
        else:
            nstr += line
    return '\n'.join(rl)
