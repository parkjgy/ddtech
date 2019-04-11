# -*- encoding:utf-8-*-

from Crypto.Hash import SHA256

from .log import logSend
from .status_collection import *


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