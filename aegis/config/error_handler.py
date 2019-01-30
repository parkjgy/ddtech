from django.http import HttpResponse
import traceback
import os
import json
from .common import logSend, logError


class BaseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)


class ProcessExceptionMiddleware(BaseMiddleware):
    def process_exception(self, request, exception):
        stack_trace = get_traceback_str()
        print(stack_trace)
        logError(stack_trace)
        return HttpResponse(json.dumps(
            {'message': str(exception),
             'stack_trace': stack_trace}
        ), status=503)


def get_traceback_str():
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
