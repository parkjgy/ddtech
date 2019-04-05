# -*- encoding:utf-8-*-

# Create your views here.

import datetime
import json

import logging
from datetime import timedelta

from django.http import HttpResponse, JsonResponse

from Crypto.Hash import SHA256

from .status_collection import *

# cron 과 충돌
# from Crypto.Cipher import AES

logger_log = logging.getLogger("aegis.log")
logger_error = logging.getLogger("aegis.error.log")
logger_error.setLevel(logging.DEBUG)


def logSend(*args):
    """앱에서 게시물은 요청한다.

    :param: id 게시물의 id 이다

    :returns: json 양식으로 온다. {'S':'0', 'M':'POST 로 와야함'} {'S':'1', 'R':{'tit ... king'}}
    :returns: S: 성공 여부이다. 1: 성공, 0: 실패
    :returns: M: 실패 했을 때 메세지가 실려있다.
    :returns: R: json 양식으로된 게시물이다. {'title': '임신 중 ', 'text': '<!DOCTYPE html><html>...', 'published_date': '2018-10-04', 'author':'Thinking'}
    """
    try:
        str_list = []
        for arg in args:
            str_list.append(str(arg))
        print(''.join(str_list))
        logger_log.debug(''.join(str_list))
    except Exception as e:
        logger_error.error(str(e))
        return


logger_header = logging.getLogger("aegis.header.log")


def logHeader(*args):
    try:
        str_list = []
        for arg in args:
            str_list.append(str(arg))
        print(''.join(str_list))
        logger_header.debug(''.join(str_list))
    except Exception as e:
        logger_log.debug(str(e))
        return


def logError(*args):
    """
    Yields
    ------
    err_code : int
        Non-zero value indicates error code, or zero on success.
    err_msg : str or None
        Human readable error message, or None on success.
    """
    try:
        str_list = []
        for arg in args:
            str_list.append(str(arg))
        print(''.join(str_list))
        logger_error.debug(''.join(str_list))
    except Exception as e:
        logger_error.error(str(e))
        return


# # Cross-Origin Read Allow Rule
# class CRSJsonResponse(JsonResponse):
#     def __init__(self, data, **kwargs):
#         super().__init__(data, **kwargs)
#         self["Access-Control-Allow-Origin"] = "*"
#         self["Access-Control-Allow-Methods"] = "GET, OPTIONS, POST"
#         self["Access-Control-Max-Age"] = "1000"
#         self["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type"
#
#
# class CRSHttpResponse(HttpResponse):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self["Access-Control-Allow-Origin"] = "*"
#         self["Access-Control-Allow-Methods"] = "GET, OPTIONS, POST"
#         self["Access-Control-Max-Age"] = "1000"
#         self["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type"
#
#
# Requests library response redirect
class ReqLibJsonResponse(JsonResponse):
    def __init__(self, req_response, **kwargs):
        super().__init__(req_response.json(), **kwargs)
        self.status_code = req_response.status_code


# #  Requests library response redirect ( For Web.API )
# class CRSReqLibJsonResponse(CRSJsonResponse):
#     def __init__(self, req_response, **kwargs):
#         super().__init__(req_response.json(), **kwargs)
#         self.status_code = req_response.status_code


def ValuesQuerySetToDict(vqs):
    return [item for item in vqs]


def func_begin_log(*args) -> str:
    """
    호출하는 쪽에서 필수 : import inspect
    """
    func_name = ''
    for arg in args:
        func_name = func_name + '/' + arg
    logSend('>>> ' + func_name)
    return func_name


def func_end_log(func_name, message = None):
    """
    호출하는 쪽에서 필수 : import inspect
    """
    log = '<<< ' + func_name
    if message != None:
        log += ' >>> ' + message
    logSend(log)
    return


def status422(func_name, _message):
    func_end_log(func_name, _message['message'])
    return REG_422_UNPROCESSABLE_ENTITY.to_json_response(_message)


def hash_SHA256(password):
    add_solt_pw = 'ezcheck_' + password + '_best!'
    hashed = SHA256.new()
    hashed.update(add_solt_pw.encode('utf-8'))
    return hashed.hexdigest()


def no_only_phone_no(phone_no):
    """
    전화번호에서 '-'와 space 를 제거한다.
    :param phone_no: 010-1111 2222
    :return: 01011112222
    """
    if len(phone_no) > 0:
        phone_no = phone_no.replace('-', '')
        phone_no = phone_no.replace(' ', '')
    return phone_no


def phone_format(phone_no):
    """
    숫자만으로된 전화번호를 전화번호 양식으로 바꾸어준다.
    :param phone_no: 01033335555
    :return: 010-3333-5555
    """
    formated_phone_no = phone_no[:3] + '-' + \
                        phone_no[3:len(phone_no)-4] + '-' + \
                        phone_no[len(phone_no)-4:]
    return formated_phone_no


def dt_null(dt) -> str:
    """
    날짜 시간이 None 값일 때 시간을 표시하지 않고 None 을 표시함
    :param dt:
    :return:
    """
    return None if dt == None else dt.strftime("%Y-%m-%d %H:%M:%S")