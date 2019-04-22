# -*- encoding:utf-8-*-

import random
from Crypto.Hash import SHA256

from .log import logSend
from .status_collection import *
from .secret import AES_DECRYPT_BASE64


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

def rMin(min) -> int:
    """
    min 값을 기준으로 위 아래 5분 값을 랜덤으로 준다.
    :param min:
    :return:
    """
    random_value = random.randint(0, 10)
    return min - 5 + random_value

def is_parameter_ok(rqst, key_list) -> dict:
    """
    API 의 파라미터를 검사
    - key_list 의 key에 '_!' 가 붙어 있으면 암호환된 값을 복호화 한다. ex) key_! << 키는 key 이고 복호화 해서 정상인지 확인한다는 뜻
    :param rqst:
    :param key_list:
    :return:
        is_ok: True     # 에러 발생 여부
        results:[...]   # 에러가 있으면 에러 메세지
        parameter['key']=value,  # 검사가 끝난 파라미터들
    """
    results = {'is_ok':True, 'results':[], 'parameters':{}}
    for key in key_list:
        is_decrypt = '_!' in key
        if is_decrypt:
            key = key.replace('_!', '')
        if not key in rqst:
            # key 가 parameter 에 포함되어 있지 않으면
            results['is_ok'] = False
            results['results'].append('ClientError: parameter \'%s\' 가 없어요\n' % key)
        else:
            if is_decrypt:
                # key 에 '_id' 가 포함되어 있으면 >> 암호화 된 값이면
                plain = AES_DECRYPT_BASE64(rqst[key])
                if plain == '__error':
                    results['is_ok'] = False
                    results['results'].append('ClientError: parameter \'%s\' 가 정상적인 값이 아니예요.\n' % key)
                else:
                    results['parameters'][key] = plain
            else:
                results['parameters'][key] = rqst[key]
    return results


