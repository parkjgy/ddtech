import datetime
from datetime import timedelta

from django.views.decorators.csrf import csrf_exempt  # POST 에서 사용

import json
from django.conf import settings

from config.common import logSend, logError
from config.common import DateTimeEncoder, ValuesQuerySetToDict, exceptionError
from config.common import CRSHttpResponse, CRSReqLibJsonResponse
# secret import
from config.secret import AES_ENCRYPT_BASE64, AES_DECRYPT_BASE64

# log import
from .models import Customer
from .models import Staff
from .status_collection import *


@csrf_exempt
def reg_customer(request):
    """
    /customer/reg_customer
    고객사를 등록한다.
    간단한 내용만 넣어서 등록하고 나머지는 고객사 담당자가 추가하도록 한다.
    입력한 전화번호로 SMS 에 id 와 pw 를 보낸다.
        주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/reg_customer?customer_name=대덕테크&staff_name=박종기&staff_pNo=010-2557-3555&staff_email=thinking@ddtechi.com
    POST
        {
            'customer_name': '대덕기공',
            'staff_name': '홍길동',
            'staff_pNo': '010-1111-2222',
            'staff_email': 'id@daeducki.com'
        }
    response
        STATUS 200
    """
    try:
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        customer_name = rqst["customer_name"]
        staff_name = rqst["staff_name"]
        staff_pNo = rqst["staff_pNo"]
        staff_email = rqst["staff_email"]

        print(customer_name, staff_name, staff_pNo, staff_email)
        customers = Customer.objects.filter(name=customer_name, staff_name=staff_name)
        if len(customers) > 0:
            staff = Staff.objects.get(id=customers[0].staff_id)
            return REG_400_CUSTOMER_STAFF_ALREADY_REGISTERED.to_response()
        customer = Customer(
            name=customer_name,
            staff_name=staff_name,
            staff_pNo=staff_pNo,
            staff_email=staff_email
        )
        customer.save()
        staff = Staff(
            name=staff_name,
            login_id='temp_' + str(customer.id),
            login_pw='happy_day!!!',
            co_id=customer.id,
            co_name=customer.name,
            pNo=staff_pNo,
            email=staff_email
        )
        staff.save()
        print('staff id = ', staff.id)
        customer.staff_id = staff.id

        print(customer_name, staff_name, staff_pNo, staff_email)
        customer.save()

        result = {'msg': '정상처리되었습니다.',
                  'login_id': staff.login_id,
                  'login_pw': staff.login_pw}
        return CRSHttpResponse(json.dumps(result, cls=DateTimeEncoder))
    except Exception as e:
        return exceptionError('reg_customer', 503, e)


@csrf_exempt
def list_customer(request):
    """
    고객사 리스트를 요청한다.
    http://0.0.0.0:8000/customer/list_customer?customer_name=대덕테크&staff_name=박종기&staff_pNo=010-2557-3555&staff_email=thinking@ddtechi.com
    GET
        customer_name=대덕기공
        staff_name=홍길동
        staff_pNo=010-1111-2222
        staff_email=id@daeducki.com
    response
        STATUS 200
    """
    print('--- /customer/list_customer')
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

    customers = Customer.objects.filter().values('name', 'contract_no', 'dt_reg', 'dt_accept', 'type',
                                                 'contractor_name', 'staff_name', 'staff_pNo', 'staff_email',
                                                 'manager_name', 'manager_pNo', 'manager_email', 'dt_payment')
    arr_customer = [customer for customer in customers]
    result = {'customers': arr_customer}
    response = HttpResponse(json.dumps(result, cls=DateTimeEncoder))
    response.status_code = 200
    return CRSHttpResponse(response)


def reg_staff(request):
    """
    고객사 직원을 등록한다.
        주)	response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/reg_staff?staff_id=qgf6YHf1z2Fx80DR8o/Lvg&name=이요셉&login_id=hello&login_pw=A~~~8282&position=책임&department=개발&pNo=010-2450-5942&email=hello@ddtechi.com
    POST
        {
            'staff_id':'암호화된 id',
            'name': '홍길동',
            'login_id': 'hong_geal_dong',
            'position': '부장',	   # option 비워서 보내도 됨
            'department': '관리부',	# option 비원서 보내도 됨
            'pNo': '010-1111-2222', # '-'를 넣어도 삭제되어 저장 됨
            'email': 'id@daeducki.com',
        }
    response
        STATUS 200
    """
    try:
        if request.method == 'OPTIONS':
            return CRSHttpResponse()
        elif request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        staff_id = AES_DECRYPT_BASE64(rqst['staff_id'])
        staff = Staff.objects.get(id=staff_id)

        name = rqst['name']
        login_id = rqst['login_id']
        position = rqst['position']
        department = rqst['department']
        phone_no = rqst['pNo']
        email = rqst['email']

        phone_no = phone_no.replace('-', '')
        phone_no = phone_no.replace(' ', '')
        print(phone_no)

        staffs = Staff.objects.filter(pNo=phone_no, login_id=id)
        if len(staffs) > 0:
            result = {'message': '전화번호나 id 가 중복됩니다.'}
            response = CRSHttpResponse(json.dumps(result, cls=DateTimeEncoder))
            response.status_code = 503
            return response
        new_staff = Staff(
            name=name,
            login_id=login_id,
            login_pw='aaa',
            co_id=staff.co_id,
            co_name=staff.co_name,
            position=position,
            department=department,
            pNo=phone_no,
            email=email
        )
        new_staff.save()
        print('--- save')
        response = CRSHttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('reg_staff', '509', e)


def login(request):
    """
    로그인
    http://0.0.0.0:8000/customer/login?id=thinking&pw=A~~~8282
    POST
        {
            'id': 'thinking',
            'pw': 'a~~~8282'
        }
    response
        STATUS 200
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
        print('---', id, pw)

        staffs = Staff.objects.filter(login_id=id, login_pw=pw)
        if len(staffs) == 0:
            result = {'message': 'id 나 비밀번호가 틀립니다.'}
            response = CRSHttpResponse(json.dumps(result, cls=DateTimeEncoder))
            response.status_code = 503
            return response
        response = CRSHttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('login', '509', e)


def update_staff(request):
    """
    직원 정보를 수정한다.
        주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/update_staff?id=&login_id=temp_1&before_pw=A~~~8282&login_pw=&name=박종기&position=이사&department=개발&phone_no=010-2557-3555&phone_type=10&push_token=unknown&email=thinking@ddtechi.com
    POST
        {
            'id': '암호화된 id',           # 아래 login_id 와 둘 중의 하나는 필수
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
            {'message': '비밀번호가 틀립니다.'}
    """
    try:
        if request.method == 'OPTIONS':
            return CRSHttpResponse()
        elif request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        id = rqst['id']  # 암호화된 id
        login_id = rqst['login_id']  # id 로 사용
        before_pw = rqst['before_pw']  # 기존 비밀번호
        login_pw = rqst['login_pw']  # 변경하려는 비밀번호
        name = rqst['name']  # 이름
        position = rqst['position']  # 직책
        department = rqst['department']  # 부서 or 소속
        phone_no = rqst['phone_no']  # 전화번호
        phone_type = rqst['phone_type']  # 전화 종류	10:iPhone, 20: Android
        push_token = rqst['push_token']  # token
        email = rqst['email']  # id@ddtechi.co
        print(id, login_id, before_pw, login_pw, name, position, department, phone_no, phone_type, push_token, email)

        if len(phone_no) > 0:
            phone_no = phone_no.replace('-', '')
            phone_no = phone_no.replace(' ', '')
            print(phone_no)

        if len(id) > 0:
            staff = Staff.objects.get(id=AES_DECRYPT_BASE64(id))
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
            staff.pNo = phone_no
        if len(phone_type) > 0:
            staff.pType = phone_type
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
        주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/list_staff?id=&login_id=temp_1&login_pw=A~~~8282
    GET
        id = 요청직원 id
        login_id = 요청직원 id
        login_pw = 요청직원 pw
    response
        STATUS 200
            [{'name':'...', 'position':'...', 'department':'...', 'pNo':'...', 'pType':'...', 'email':'...', 'login_id'}, ...]
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

        staffs = Staff.objects.filter().values('name', 'position', 'department', 'pNo', 'pType', 'email', 'login_id')
        arr_staffs = [staff for staff in staffs]
        response = CRSHttpResponse(json.dumps(arr_staffs, cls=DateTimeEncoder))
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('update_staff', '509', e)
