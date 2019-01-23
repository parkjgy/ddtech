# -*- encoding:utf-8-*-

# Create your views here.

import datetime
import json
import logging
from datetime import timedelta

from django.http import HttpResponse, JsonResponse

# cron 과 충돌
# from Crypto.Cipher import AES

logger_log = logging.getLogger("aegis.log")
logger_error = logging.getLogger("aegis.error.log")
logger_error.setLevel(logging.DEBUG)


def logSend(message):
    """앱에서 게시물은 요청한다.

    :param: id 게시물의 id 이다

    :returns: json 양식으로 온다. {'S':'0', 'M':'POST 로 와야함'} {'S':'1', 'R':{'tit ... king'}}
    :returns: S: 성공 여부이다. 1: 성공, 0: 실패
    :returns: M: 실패 했을 때 메세지가 실려있다.
    :returns: R: json 양식으로된 게시물이다. {'title': '임신 중 ', 'text': '<!DOCTYPE html><html>...', 'published_date': '2018-10-04', 'author':'Thinking'}
    """
    try:
        logger_log.debug(message)
    except Exception as e:
        logger_error.error(str(e))
        return


logger_header = logging.getLogger("aegis.header.log")


def logHeader(message):
    try:
        logger_header.debug(message)
    except Exception as e:
        logger_log.debug(str(e))
        return


def logError(message):
    """
    Yields
    ------
    err_code : int
        Non-zero value indicates error code, or zero on success.
    err_msg : str or None
        Human readable error message, or None on success.
    """
    try:
        logger_error.debug(message)
    except Exception as e:
        logger_error.error(str(e))
        return


# Cross-Origin Read Allow Rule
class CRSJsonResponse(JsonResponse):
    def __init__(self, data, **kwargs):
        super().__init__(data, **kwargs)
        self["Access-Control-Allow-Origin"] = "*"
        self["Access-Control-Allow-Methods"] = "GET, OPTIONS, POST"
        self["Access-Control-Max-Age"] = "1000"
        self["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type"


class CRSHttpResponse(HttpResponse):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self["Access-Control-Allow-Origin"] = "*"
        self["Access-Control-Allow-Methods"] = "GET, OPTIONS, POST"
        self["Access-Control-Max-Age"] = "1000"
        self["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type"


# Requests library response redirect
class ReqLibJsonResponse(JsonResponse):
    def __init__(self, req_response, **kwargs):
        super().__init__(req_response.json(), **kwargs)
        self.status_code = req_response.status_code


#  Requests library response redirect ( For Web.API )
class CRSReqLibJsonResponse(CRSJsonResponse):
    def __init__(self, req_response, **kwargs):
        super().__init__(req_response.json(), **kwargs)
        self.status_code = req_response.status_code


def ValuesQuerySetToDict(vqs):
    return [item for item in vqs]


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            if obj.utcoffset() is not None:
                obj = obj - obj.utcoffset() + timedelta(0, 0, 0, 0, 0, 9)
                # logSend('DateTimeEncoder >>> utcoffset() = ' + str(obj.utcoffset()) + ', obj = ' + str(obj))
            encoded_object = obj.strftime('%Y-%m-%d %H:%M:%S')
            # logSend('DateTimeEncoder >>> is YES >>>' + str(encoded_object))
        else:
            encoded_object = json.JSONEncoder.default(self, obj)
            # logSend('DateTimeEncoder >>> is NO >>>' + str(encoded_object))
        return encoded_object


def exceptionError(funcName, code, e):
    print(funcName + ' >>> ' + code + ' ERROR: ' + str(e))
    logError(funcName + ' >>> ' + code + ' ERROR: ' + str(e))
    logSend(funcName + ' >>> ' + code + ' ERROR: ' + str(e))
    result = {'message': str(e)}
    response = HttpResponse(json.dumps(result, cls=DateTimeEncoder))
    print(response)
    response.status_code = 503
    print(response.content)
    return response
