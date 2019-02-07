import json
from django.conf import settings

from config.common import logSend, logError
from config.common import DateTimeEncoder, ValuesQuerySetToDict, exceptionError
from config.common import CRSHttpResponse, CRSReqLibJsonResponse
from config.common import hash_SHA256
# secret import
from config.secret import AES_ENCRYPT_BASE64, AES_DECRYPT_BASE64

from .models import Staff
from .models import Work_Place
from .models import Beacon

import requests
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from config.status_collection import *

from config.error_handler import *
# from config.settings.base import CUSTOMER_URL

# Operation
# 1) request.method ='OPTIONS'
# 서버에서 Cross-Site 관련 옵션들을 확인
# 2) request.method == REAL_METHOD:
# 실제 사용할 데이터를 전송

# try: 다음에 code = 'argument incorrect'

import inspect


def reg_staff(request):
    """
    운영 직원 등록
    - 파라미터가 빈상태를 검사하지 않는다. (호출하는 쪽에서 검사)
    http://0.0.0.0:8000/operation/reg_staff?pNo=010-2557-3555&id=thinking&pw=a~~~8282
    POST
        {
            'pNo': '010-1111-2222',
            'id': 'thinking',
            'pw': 'a~~~8282'    # SHA256
        }
    response
        STATUS 200
    """
    try:
        func_name = inspect.stack()[0][3]
        app_name = __package__.rsplit('.', 1)[-1]
        print('>>> ' + app_name + '/' + func_name)
        print(get_traceback_str())
        if request.method == 'OPTIONS':
            return CRSHttpResponse()
        elif request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        phone_no = rqst['pNo']
        id_ = rqst['id']
        pw = rqst['pw']

        phone_no = phone_no.replace('-', '')
        phone_no = phone_no.replace(' ', '')
        print(phone_no)

        staffs = Staff.objects.filter(pNo=phone_no, login_id=id_)
        if len(staffs) > 0:
            # r = {'link':'http://'}
            #
            # print('...')
            # response = REG_611_DUPLICATE_PHONE_NO_OR_ID
            # print(response.status, response.message)
            # r = response.to_json_response()
            # print(r.status, r.message)
            # return r
            return REG_611_DUPLICATE_PHONE_NO_OR_ID.to_json_response()
        new_staff = Staff(
            login_id=id,
            login_pw=hash_SHA256(pw),
            pNo=phone_no
        )
        new_staff.save()
        response = CRSHttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('reg_staff', '509', e)


def login(request):
    """
    로그인
    http://0.0.0.0:8000/operation/login?id=thinking&pw=a~~~8282
    POST
        {
            'id': 'thinking',
            'pw': 'a~~~8282'
        }
    response
        STATUS 200
            { 'you': '넌 이거야?'}
        STATUS 401
            {'message':'id 나 비밀번호가 틀립니다.'}
    """
    try:
        if request.method == 'OPTIONS':
            return CRSHttpResponse()
        elif request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        id = rqst['id']
        pw = rqst['pw']

        staffs = Staff.objects.filter(login_id=id, login_pw=pw)
        if len(staffs) == 0:
            result = {'message': 'id 나 비밀번호가 틀립니다.'}
            response = CRSHttpResponse(json.dumps(result, cls=DateTimeEncoder))
            response.status_code = 503
            return response
        staff = staffs[0]

        request.session['id'] = staff.id
        result = {}
        response = CRSHttpResponse(json.dumps(result, cls=DateTimeEncoder))
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('login', '509', e)


def update_staff(request):
    """
    직원 정보를 수정한다.
        주)    항목이 비어있으면 수정하지 않는 항목으로 간주한다.
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/operation/update_staff?login_id=thinking&before_pw=a~~~8282&login_pw=A~~~8282&name=박종기&position=이사&department=개발&phone_no=&phone_type=10&push_token=unknown&email=thinking@ddtechi.com
    POST
        {
            'login_id': 'id 로 사용된다.',  # 위 id 와 둘 중의 하나는 필수
            'before_pw': '기존 비밀번호',     # 필수
            'login_pw': '변경하려는 비밀번호',
            'name': '이름',
            'position': '직책',
            'department': '부서 or 소속',
            'phone_no': '전화번호',
            'phone_type': '전화 종류', # 10:iPhone, 20: Android
            'push_token': 'token',
            'email': 'id@ddtechi.com'
        }
    response
        STATUS 200
        STATUS 503
            {
                'err': {
                    'code': 301,
                    'message': '기존 비밀번호가 틀립니다.'
                }
            }
    """
    try:
        if request.method == 'OPTIONS':
            return CRSHttpResponse()
        elif request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        print(request.session['id'])
        _id = request.session['id']  # 암호화된 id
        login_id = rqst['login_id']  # id 로 사용
        before_pw = rqst['before_pw']  # 기존 비밀번호
        login_pw = rqst['login_pw']  # 변경하려는 비밀번호
        name = rqst['name']  # 이름
        position = rqst['position']  # 직책
        department = rqst['department']  # 부서 or 소속
        phone_no = rqst['phone_no']  # 전화번호
        phone_type = rqst['phone_type']  # 전화 종류    10:iPhone, 20: Android
        push_token = rqst['push_token']  # token
        email = rqst['email']  # id@ddtechi.co
        print(_id, login_id, before_pw, login_pw, name, position, department, phone_no, phone_type, push_token, email)

        if len(phone_no) > 0:
            phone_no = phone_no.replace('-', '')
            phone_no = phone_no.replace(' ', '')
            print(phone_no)

        if len(_id) > 0:
            staff = Staff.objects.get(id=_id)
        else:
            staff = Staff.objects.get(login_id=login_id)
        if before_pw != staff.login_pw:
            result = {'message': '비밀번호가 틀립니다.'}
            response = CRSHttpResponse(json.dumps(result, cls=DateTimeEncoder))
            response.status_code = 503
            return response

        if len(login_pw) > 0:
            staff.login_pw = login_pw
        if len(name) > 0:
            staff.name = name
        if len(position) > 0:
            staff.position = position
        if len(department) > 0:
            staff.department = department
        if len(phone_no) > 0:
            staff.phone_no = phone_no
        if len(phone_type) > 0:
            staff.phone_type = phone_type
        if len(push_token) > 0:
            staff.push_token = push_token
        if len(email) > 0:
            staff.email = email
        staff.save()
        response = CRSHttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('update_staff', '509', e)


def list_staff(request):
    """
    직원 list 요청
        주)    항목이 비어있으면 수정하지 않는 항목으로 간주한다.
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/operation/list_staff?id=&login_id=thinking&login_pw=A~~~8282
    GET
        id = 요청직원 id
        login_id = 요청직원 id
        login_pw = 요청직원 pw
    response
        STATUS 200
            [{'name':'...', 'position':'...', 'department':'...', 'pNo':'...', 'pType':'...', 'email':'...'}, ...]
        STATUS 503
            {'message': '직원이 아닙니다.'}
    """
    try:
        if request.method == 'OPTIONS':
            return CRSHttpResponse()
        elif request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        print(request.session.keys())
        for key in request.session.keys():
            print(key, ':', request.session[key])

        id = rqst['id']  # 암호화된 id
        login_id = rqst['login_id']  # 암호화된 id
        login_pw = rqst['login_pw']  # 암호화된 id
        print(id, login_id)

        if len(id) > 0:
            staff = Staff.objects.get(id=AES_DECRYPT_BASE64(id))
        else:
            staff = Staff.objects.get(login_id=login_id)
        if login_pw != staff.login_pw:
            result = {'message': '직원이 아닙니다.'}
            response = CRSHttpResponse(json.dumps(result, cls=DateTimeEncoder))
            response.status_code = 503
            return response

        staffs = Staff.objects.filter().values('name', 'position', 'department', 'pNo', 'pType', 'email')
        arr_staffs = [staff for staff in staffs]
        response = CRSHttpResponse(json.dumps(arr_staffs, cls=DateTimeEncoder))
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('update_staff', '509', e)


@csrf_exempt
def reg_customer(request):
    """
    고객사를 등록한다.
    - 간단한 내용만 넣어서 등록하고 나머지는 고객사 담당자가 추가하도록 한다.
    - 입력한 전화번호로 SMS 에 id 와 pw 를 보낸다. (회사 이름과 전화번호가 동일해야한다.)
        주) 항목이 비어있으면 수정하지 않는 항목으로 간주한다.
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/operation/reg_customer?re_sms=NO&customer_name=대덕테크&staff_name=박종기&staff_pNo=010-2557-3555&staff_email=thinking@ddtechi.com
    POST
        {
            're_sms': 'YES', # 문자 재요청인지 여부 (YES : SMS 재요청, NO : 신규 등록)
            'customer_name': '대덕기공',    # 문자 재전송 필수
            'staff_name': '홍길동',
            'staff_pNo': '010-1111-2222',   # 문자 재전송 필수
            'staff_email': 'id@daeducki.com'
        }
    response
        STATUS 200
    """
    logSend('>>> operation/reg_customer')
    print(">>> operation/reg_customer")
    if request.method == 'OPTIONS':
        return CRSHttpResponse()
    elif request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    re_sms = rqst['re_sms']
    customer_name = rqst["customer_name"]
    staff_name = rqst["staff_name"]
    staff_pNo = rqst["staff_pNo"]
    staff_email = rqst["staff_email"]

    new_customer_data = {
        're_sms': re_sms,
        'customer_name': customer_name,
        'staff_name': staff_name,
        'staff_pNo': staff_pNo,
        'staff_email': staff_email
    }
    response_customer = requests.post(settings.CUSTOMER_URL + 'reg_customer', json=new_customer_data)
    print('status', response_customer.status_code, response_customer.json())
    if response_customer.status_code == 200:
        response_customer_json = response_customer.json()
        print('아이디 ' + response_customer_json['login_id'] + '\n' + '비밀번호 ' + response_customer_json['login_pw'])
        rData = {
            'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
            'user_id': 'yuadocjon22',
            'sender': settings.SMS_SENDER_PN,
            'receiver': staff_pNo,  # '01025573555',
            'msg_type': 'SMS',
            'msg': '반갑습니다.\n'
                   '\'이지체크\'예요~~\n'
                   '아이디 ' + response_customer_json['login_id'] + '\n'
                   '비밀번호 ' + AES_DECRYPT_BASE64(response_customer_json['login_pw'])
        }
        r = requests.post('https://apis.aligo.in/send/', data=rData)
        print(r.json())
    else:
        response_json = response_customer.json()
        response = CRSHttpResponse(json.dumps(response_json, cls=DateTimeEncoder))
        response.status_code = response_customer.status_code

    logSend('<<< operation/reg_customer')
    print('<<< operation/reg_customer')
    return CRSReqLibJsonResponse(response_customer)


@csrf_exempt
def list_customer(request):
    """
    고객사 리스트를 요청한다.
    http://0.0.0.0:8000/operation/list_customer?customer_name=대덕테크&staff_name=박종기&staff_pNo=010-2557-3555&staff_email=thinking@ddtechi.com
    GET
        customer_name=대덕기공
        staff_name=홍길동
        staff_pNo=010-1111-2222
        staff_email=id@daeducki.com
    response
        STATUS 200
    """
    if request.method == 'OPTIONS':
        return CRSHttpResponse()
    elif request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    customer_name = rqst['customer_name']
    staff_name = rqst['staff_name']
    staff_pNo = rqst['staff_pNo']
    staff_email = rqst['staff_email']

    json_data = {
        'customer_name': customer_name,
        'staff_name': staff_name,
        'staff_pNo': staff_pNo,
        'staff_email': staff_email
    }
    # print(json_data, settings.CUSTOMER_URL)
    response_customer = requests.get(settings.CUSTOMER_URL + 'list_customer', params=json_data)
    # response_customer = requests.get('http://0.0.0.0:8000/customer/list_customer', params=json_data)
    # print(response_customer.status_code, response_customer.json())
    return CRSReqLibJsonResponse(response_customer)


def update_work_place(request):
    """
    사업장 내용을 수정한다.
        주)    항목이 비어있으면 수정하지 않는 항목으로 간주한다.
            response 는 추후 추가될 예정이다.
    POST
        {
            'id': '암호화된 id',
            'major': (비콘 major 번호),
            'staff_name': '박종기',
            'staff_pNo': '010-2557-3555',

            'place_name': '효성 용연2공장',
            'contractor_name': '대덕기공',

            'manager_name': '홍길동',
            'manager_pNo': '010-1111-2222',
            'manager_email': 'id@daeducki.com',

            'order_name': '(주)효성',
            'order_staff_name': '제갈공명',
            'order_staff_pNo': '010-2222-3333',
            'order_staff_email': 'id@company.com',
        }
    response
        STATUS 200
        STATUS 503
            {
                'err': {
                    'code': 401,
                    'msg': 'id가 틀립니다.'
                }
            }
    """
    response = HttpResponse()
    response.status_code = 200
    return response


def update_beacon(request):
    """
    비콘 내용을 수정한다.
        주)    항목이 비어있으면 수정하지 않는 항목으로 간주한다.
            response 는 추후 추가될 예이다.
    POST
        {
            'id': '암호화된 id',
            'uuid': '12345678-0000-0000-123456789012', # 8-4-4-4-12
            'major': 12001, # 앞 2자리 지역, 뒷 3자리 일련번호 (max 65536)
            'minor': 10001, # 앞 2자리 사용 방법(10: 출입, 20:위험지역, 30:통제구역), 뒷 3자리 일련번호
            'dt_last': '2018-12-28 12:53:36', # 최종 인식 날짜
            'dt_battery': '2018-12-28 12:53:36', # 최종 밧데리 변경 날짜
            'work_place_id': -1 # 사업장 id
        }
    response
        STATUS 200
        STATUS 503
            {
                'err': {
                    'code': 401,
                    'msg': 'id가 틀립니다.'
                }
            }
    """
    response = HttpResponse()
    response.status_code = 200
    return response


def list_work_place(request):
    """
    사업장 정보 리스트를 요청한다.
    GET
        cust_type=10 # 10 : 발주업체, 11 : 파견업체, 12 : 협력업체
        area=10 # 10 : 울산, 11 : 부산, 12 : 경남, 20 : 대구, 경북, 30 : 광주, 전남
    response
        STATUS 200
            {
                'no': 20
                'list': [
                    {
                        'id': '암호화된 id',
                        'major':'10001',
                        'staff_name':'한국인',
                        'staff_pNo':'010-1111-2222',

                        'place_name':'(주)효성 용연2공장',
                        'contractor_name':'대덕기공',

                        'manager_name':'홍길동',
                        'manager_pNo':'010-2222-3333',
                        'manager_email':'id@daeducki.com',

                        'order_name':'(주)효성',
                        'order_staff_name':'제갈공명',
                        'order_staff_pNo':'010-3333-4444',
                        'order_staff_email':'id@company.com',
                    },
                    ......
                ]
            }
    """

    response = HttpResponse()
    response.status_code = 200
    return response


def list_beacon(request):
    """
    beacon 정보 리스트를 요청한다.
    GET
        cust_type=10 # 10 : 발주업체, 11 : 파견업체, 12 : 협력업체
        area=10 # 10 : 울산, 11 : 부산, 12 : 경남, 20 : 대구, 경북, 30 : 광주, 전남
        staff_phone_no=010-1111-2222 # blank to all
        is_problem=y # 문제가 있는 비콘 사업장만 표시
    response
        STATUS 200
            {
                'no': 20
                'list': [
                    {
                        'id': '암호화된 id',
                        'major':'10001',
                        'staff_name':'한국인',
                        'staff_pNo':'010-1111-2222',

                        'place_name':'(주)효성 용연2공장',
                        'contractor_name':'대덕기공',

                        'manager_name':'홍길동',
                        'manager_pNo':'010-2222-3333',
                        'manager_email':'id@daeducki.com',

                        'order_name':'(주)효성',
                        'order_staff_name':'제갈공명',
                        'order_staff_pNo':'010-3333-4444',
                        'order_staff_email':'id@company.com',
                    },
                    ......
                ]
            }
    """
    response = HttpResponse()
    response.status_code = 200
    return response


def detail_beacon(request):
    """
    beacon 정보 리스트를 요청한다.
    GET
        cust_type=10 # 10 : 발주업체, 11 : 파견업체, 12 : 협력업체
        area=10 # 10 : 울산, 11 : 부산, 12 : 경남, 20 : 대구, 경북, 30 : 광주, 전남
        staff_phone_no=010-1111-2222 # blank to all
        is_problem=y # 문제가 있는 비콘 사업장만 표시
    response
        STATUS 200
            {
                'no': 20
                'list': [
                    {
                        'id': '암호화된 id',
                        'major':'10001',
                        'staff_name':'한국인',
                        'staff_pNo':'010-1111-2222',

                        'place_name':'(주)효성 용연2공장',
                        'contractor_name':'대덕기공',

                        'manager_name':'홍길동',
                        'manager_pNo':'010-2222-3333',
                        'manager_email':'id@daeducki.com',

                        'order_name':'(주)효성',
                        'order_staff_name':'제갈공명',
                        'order_staff_pNo':'010-3333-4444',
                        'order_staff_email':'id@company.com',

                        'no_inout': 10,
                        'no_err': 1,
                        'dt_last': '2018-12-28 12:53:36',
                    },
                    ......
                ]
            }
    """

    response = HttpResponse()
    response.status_code = 200
    return response
