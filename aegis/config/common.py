# -*- encoding:utf-8-*-

import random
from Crypto.Hash import SHA256

from .log import logSend, logError
from .status_collection import *
from .secret import AES_DECRYPT_BASE64
import datetime


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


def func_end_log(func_name, message=None):
    """
    호출하는 쪽에서 필수 : import inspect
    """
    log = '<<< ' + func_name
    if message is not None:
        log += ': ' + message
    logSend(log)
    return


def status422(func_name, _message):
    logError(func_name, ' ', _message['message'])
    func_end_log(func_name, _message['message'])
    return REG_422_UNPROCESSABLE_ENTITY.to_json_response(_message)


def hash_SHA256(password):
    add_solt_pw = 'ezcheck_' + password + '_best!'
    hashed = SHA256.new()
    hashed.update(add_solt_pw.encode('utf-8'))
    return hashed.hexdigest()


def no_only_phone_no(phone_no):
    """
    전화번호에서 숫자 외의 문자를 지운다.
    :param phone_no: 010-1111 2222
    :return: 01011112222
    """
    only_no = ''.join(list(filter(str.isdigit, phone_no)))
    if len(only_no) > 3 and only_no[:2] == '82':
        if only_no[2:3] == '0':
            pNo = only_no[2:]
        else:
            pNo = '0' + only_no[2:]
    else:
        pNo = only_no
    return pNo


def phone_format(phone_no):
    """
    숫자만으로된 전화번호를 전화번호 양식으로 바꾸어준다.
    :param phone_no: 01033335555
    :return: 010-3333-5555
    """
    if len(phone_no) < 4:
        return phone_no
    if len(phone_no) < 8:
        return phone_no[:3] + '-' + phone_no[3:]
    formatted_phone_no = phone_no[:3] + '-' + \
                         phone_no[3:len(phone_no)-4] + '-' + \
                         phone_no[len(phone_no)-4:]
    return formatted_phone_no


def dt_null(dt) -> str:
    """
    날짜 시간이 None 값일 때 시간을 표시하지 않고 None 을 표시함
    :param dt:
    :return:
    """
    return None if dt is None else dt.strftime("%Y-%m-%d %H:%M:%S")


def dt_str(dt, dt_format: str) -> str:
    """
    날짜 시간이 None 값일 때 ""(blank)를 표시하고 시간일 때는 양식대로 표시한다.
    :param dt:
    :return:
    """
    return "" if dt is None else dt.strftime(dt_format)


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
        is_decryption_error: True # 암호 해독 에러 여부
        results:[...]   # 에러가 있으면 에러 메세지
        parameter['key']=value,  # 검사가 끝난 파라미터들
    """
    results = {'is_ok': True, 'is_decryption_error': False, 'results': [], 'parameters': {}}
    for key in key_list:
        is_decrypt = '_!' in key
        if is_decrypt:
            key = key.replace('_!', '')
        if key not in rqst:
            # key 가 parameter 에 포함되어 있지 않으면
            results['is_ok'] = False
            results['results'].append('ClientError: parameter \'%s\' 가 없어요\n' % key)
        else:
            if is_decrypt:
                # key 에 '_id' 가 포함되어 있으면 >> 암호화 된 값이면
                plain = AES_DECRYPT_BASE64(rqst[key])
                if plain == '__error':
                    results['is_ok'] = False
                    results['is_decryption_error'] = True
                    results['results'].append('ClientError: parameter \'%s\' 가 정상적인 값이 아니예요.\n' % key)
                else:
                    results['parameters'][key] = plain
            else:
                results['parameters'][key] = rqst[key]
    return results


def str_to_datetime(date_time):
    """
    string to datetime
    - 정해진 양식을 지켜야 한다.
    - 양식 YYYY-MM-DD HH:MM:SS
    - 사용 예
        '2019-05'				2019-05-01 00:00:00
        '2019-05-05'			2019-05-05 00:00:00
        '2019-05-05 17'			2019-05-05 17:00:00
        '2019-05-05 17:30'		2019-05-05 17:30:00
        '2019-05-05 17:30:50'	2019-05-05 17:30:50
    """
    date_time_divide = date_time.split()
    date = date_time_divide[0]
    date_divide = date.split('-')
    if len(date_divide) == 2:
        return datetime.datetime.strptime(date_divide[0] + '-' + date_divide[1]+'-01 00:00:00', "%Y-%m-%d %H:%M:%S")
    if len(date_time_divide) == 1:
        return datetime.datetime.strptime(date + ' 00:00:00', "%Y-%m-%d %H:%M:%S")
    else:
        time = date_time_divide[1]
        time_divide = time.split(':')
        if len(time_divide) == 1:
            return datetime.datetime.strptime(date + ' ' + time + ':00:00', "%Y-%m-%d %H:%M:%S")
        if len(time_divide) == 2:
            return datetime.datetime.strptime(date + ' ' + time + ':00', "%Y-%m-%d %H:%M:%S")
    return datetime.datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S")


def str_to_dt(str_dt):
    """
    "2019/06/04" > 2019-06-04 00:00:00
    :param str_dt:
    :return:
    """
    return datetime.datetime.strptime(str_dt, "%Y/%m/%d")


def str_no(str_no) -> str:
    """
    문자열을 숫자문자로 변경
    A->0
    a->0
    :param str:
    :return:
    """
    result = ''
    for i in range(len(str_no)):
        i_char = ord(str_no[i])
        if i_char < ord('a'):
            no_char = chr(i_char - ord('A') + ord('0'))
        else:
            no_char = chr(i_char - ord('a') + ord('0'))
        result += no_char
    return result


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class Works(object):
    """
    element type: {'id':999, 'begin':'2019/05/01', 'end':'2019/05/30'}
    """
    def __init__(self, x=None):
        self.index = 0
        if x is None:
            self.data = []
        else:
            self.data = x
            self.__del__()

    def __del__(self):
        """
        data 중에 날짜가 지난 항목이 있으면 삭제한다.
        """
        today = datetime.datetime.now()
        for element in self.data:
            logSend(' {} {} {}'.format(element['id'], element['begin'], element['end']))
            if str_to_dt(element['end']) < today:
                self.data.remove(element)

    def add(self, x):
        """
        새로운 업무를 추가한다.
        단, 같은 id 가 있으면 update 한다.
        :return: None or before data
        """
        for element in self.data:
            if element['id'] == x['id']:
                before_x = element
                self.data.remove(element)
                self.data.append(x)
                return before_x
        self.data.append(x)
        return None

    def is_overlap(self, x):
        """
        기간이 겹치는 업무가 있는지 확인한다.
        """
        x_begin = str_to_dt(x['begin'])
        x_end = str_to_dt(x['end'])
        # count_started = 0  # 시작된 업무의 갯수
        # count_reserve = 0  # 시작되지 않은 업무의 갯수
        dt_today = datetime.datetime.now()
        for element in self.data:
            e_begin = str_to_dt(element['begin'])
            e_end = str_to_dt(element['end'])
            # if e_begin < dt_today < e_end:
            #     count_started += 1
            # else:
            #     count_reserve += 1
            if (e_begin < x_begin < e_end) or (e_begin < x_end < e_end):
                return True
        # if count_started > 0:
        #     if count_reserve > 0:
        #         # 시작된 업무와 시작되지 않은 업무 가 각 1개씩 있으면 더 받을 수 없다.
        #         return True
        # elif count_reserve > 1:
        #     # 시작된 업무가 없더라도 시작되지 않은 업무가 2개 있으면 더 받을 수 없다.
        #     return True
        return False

    def work_counter(self, x):
        """
        근무 중인 업무, 요청받은 업무 각각의 갯수
        단, 현재업무는 갯수에서 제외한다.
        """
        count_started = 0  # 시작된 업무의 갯수
        count_reserve = 0  # 시작되지 않은 업무의 갯수
        dt_today = datetime.datetime.now()
        for element in self.data:
            if element['id'] == x:
                continue
            e_begin = str_to_dt(element['begin'])
            e_end = str_to_dt(element['end'])
            if e_begin < dt_today < e_end:
                count_started += 1
            else:
                count_reserve += 1
        return (count_started, count_reserve)
        # if count_started > 0:
        #     if count_reserve > 0:
        #         # 시작된 업무와 시작되지 않은 업무 가 각 1개씩 있으면 더 받을 수 없다.
        #         return True
        # elif count_reserve > 1:
        #     # 시작된 업무가 없더라도 시작되지 않은 업무가 2개 있으면 더 받을 수 없다.
        #     return True
        # return False

    def find(self, work_id):
        """
        work_id 가 있는지 찾는다.
        """
        for self.index in range(len(self.data)):
            if self.data[self.index]['id'] == work_id:
                return True
        return False

    def is_active(self):
        """
        출퇴근이 가능한 업무가 있다. - 업무가 시작되었다.
        """
        today = datetime.datetime.now()
        for self.index in range(len(self.data)):
            if str_to_dt(self.data[self.index]['begin']) < today < str_to_dt(self.data[self.index]['end']):
                return True
        return False

