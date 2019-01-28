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
from .models import Business_Registration
from .models import Work_Place
from .models import Work
from .models import Employee

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
            'is_not_first': 'YES',
            'customer_name': '대덕기공',
            'staff_name': '홍길동',
            'staff_pNo': '010-1111-2222',
            'staff_email': 'id@daeducki.com'
        }
    response
        STATUS 200
            {
                'msg': '정상처리되었습니다.',
                'login_id': staff.login_id,
                'login_pw': staff.login_pw
            }
        STATUS 503
            {'msg': '등록되지 않았습니다.'}
    """
    try:
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        is_not_first = rqst['is_not_first']
        customer_name = rqst["customer_name"]
        staff_name = rqst["staff_name"]
        staff_pNo = rqst["staff_pNo"]
        staff_email = rqst["staff_email"]

        print(customer_name, staff_name, staff_pNo, staff_email)
        customers = Customer.objects.filter(name=customer_name, staff_name=staff_name)
        if is_not_first.upper() == 'YES':
            if len(customers) == 0:
                result = {'msg': '등록되지 않았습니다.'}
                response = HttpResponse(json.dumps(result, cls=DateTimeEncoder))
                response.status_code = 503
                return CRSHttpResponse(response)
            customer = customers[0]
            staff = Staff.objects.get(id=customer.staff_id)
        else:
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
            customer.staff_id = str(staff.id)
            customer.save()
        print('staff id = ', staff.id)
        print(customer_name, staff_name, staff_pNo, staff_email, staff.login_id, staff.login_pw)

        result = {'msg': '정상처리되었습니다.',
                  'login_id': staff.login_id,
                  'login_pw': staff.login_pw}
        return CRSHttpResponse(json.dumps(result, cls=DateTimeEncoder))
    except Exception as e:
        return exceptionError('reg_customer', 503, e)


def update_customer(request):
    """
    고객사(협력사, 발주사) 정보 변경 (담당자, 관리자만 가능)
    	주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
    	    id(staff_id, manager_id, ...) 가 잘못되면 ERROR 처리한다.
    	    담당자와 관리자가 바뀌면 로그아웃 한다.
    	    담당자나 관리자가 바뀔 때는 다른 값은 바꿀 수 없다.
    http://0.0.0.0:8000/customer/update_customer?id=&login_id=temp_1&before_pw=A~~~8282&login_pw=&name=박종기&position=이사&department=개발&phone_no=010-2557-3555&phone_type=10&push_token=unknown&email=thinking@ddtechi.com
    POST
    	{
    		'id': '암호화된 id',           # 처리 직원 id 아래 login_id 와 둘 중의 하나는 필수
    		'login_id': 'id 로 사용된다.',  # 위 id 와 둘 중의 하나는 필수
    		'login_pw': '비밀번호',     # 필수
    		'co_id': '암호화된 소속사 id', # 로그인 할 때 받음

            'staff_id': '서버에서 받은 암호화된 id', # 담당자를 변경할 때만 (담당자, 관리자만 변경 가능)

            'manager_id': '서버에서 받은 암호화된 id', # 관리자를 변경할 때만 (관리자만 변경 가능)

            'business_reg_id': '서버에서 받은 암호화된 id', # 사업자 등록 정보 (담당자, 관리자만 변경 가능)

            'name': '상호',
            'regNo': '123-00-12345', # 사업자등록번호
            'ceoName': '대표자', # 성명
            'address': '사업장 소재지',
            'business_type': '업태',
            'business_item': '종목',
            'dt_reg': '2018-03-01', # 사업자등록일

            'dt_payment': '25', # 유료고객의 결제일 (5, 10, 15, 20, 25 중 에서 선택) 담당자, 관리자만 변경 가능
    	}
    response
    	STATUS 200
    	STATUS 503
    		{'message': '비밀번호가 틀립니다.'}
    		{'message': '담당자나 관리자만 변경 가능합니다.'}
    		{'message': '관리자만 변경 가능합니다.'}
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
        login_pw = rqst['login_pw']  # 비밀번호
        co_id = rqst['co_id']  # 소속사 id
        print(id, login_id, login_pw, co_id)

        customer = Customer.objects.get(id=AES_DECRYPT_BASE64(co_id))
        # id 가 틀리면 위에서 에러가 나야한다.
        id = AES_DECRYPT_BASE64(id)
        print(id)
        print(str(customer.staff_id.id))
        print(str(customer.manager_id))
        if customer.staff_id != id and customer.manager_id != id:
            print('담당자나 관리자만 변경 가능합니다.')
            result = {'message': '담당자나 관리자만 변경 가능합니다.'}
            response = CRSHttpResponse(json.dumps(result, cls=DateTimeEncoder))
            response.status_code = 503
            return response
        staff_id = rqst['staff_id']
        if len(staff_id) > 0:
            staff_id = AES_DECRYPT_BASE64(staff_id)
            staff = Staff.objects.get(id=staff_id)
            customer.staff_id = staff.id
            customer.staff_name = staff.name
            customer.staff_pNo = staff.pNo
            customer.staff_email = staff.email
            customer.save()
            result = {'message': '담당자가 바뀌었습니다.\n로그아웃하십시요.'}
            response = CRSHttpResponse(json.dumps(result, cls=DateTimeEncoder))
            response.status_code = 200
            return response
        manager_id = rqst['manager_id']
        if len(manager_id) > 0:
            if customer.manager_id != id:
                manager_id = AES_DECRYPT_BASE64(manager_id)
                manager = Staff.objects.get(id=manager_id)
                customer.manager_id = manager.id
                customer.manager_name = manager.name
                customer.manager_pNo = manager.pNo
                customer.manager_email = manager.email
                customer.save()
                result = {'message': '관리자가 바뀌었습니다.\n로그아웃하십시요.'}
                response = CRSHttpResponse(json.dumps(result, cls=DateTimeEncoder))
                response.status_code = 200
                return response
            else:
                result = {'message': '관리자만 변경 가능합니다.'}
                response = CRSHttpResponse(json.dumps(result, cls=DateTimeEncoder))
                response.status_code = 200
                return response
        br_id.name = rqst['business_reg_id']
        if len(br_id) > 0:
            br_id = AES_DECRYPT_BASE64(rqst['business_reg_id'])
            buss_regs = Business_Registration.objects.filter(id=br_id)
            if len(buss_regs) > 0:
                buss_reg = buss_regs[0]
                if len(rqst.rqst['name']) > 0:
                    buss_reg.name = rqst['name']
                if len(rqst.rqst['regNo']) > 0:
                    buss_reg.regNo = rqst['regNo']
                if len(rqst.rqst['ceoName']) > 0:
                    buss_reg.ceoName = rqst['ceoName']
                if len(rqst.rqst['address']) > 0:
                    buss_reg.address = rqst['address']
                if len(rqst.rqst['business_type']) > 0:
                    buss_reg.business_type = rqst['business_type']
                if len(rqst.rqst['business_item']) > 0:
                    buss_reg.business_item = rqst['business_item']
                if len(rqst.rqst['dt_reg']) > 0:
                    buss_reg.dt_reg = rqst['dt_reg']
                buss_reg.save()
        dt_payment = rqst['dt_payment']
        if len(dt_payment) > 0:
            str_dt_now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(str_dt_now)
            str_dt_now = str_dt_now[:8] + dt_payment + str_dt_now[10:]
            print(str_dt_now)
            customer.dt_payment = datetime.datetime.strptime(str_dt_now, '%Y-%m-%d %H:%M:%S')
        customer.save()

        response = CRSHttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('update_customer', '509', e)


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
    http://0.0.0.0:8000/customer/login?id=temp_1&pw=A~~~8282
    POST
        {
            'id': 'thinking',
            'pw': 'a~~~8282'
        }
    response
        STATUS 200
        STATUS 401
            {'message':'id 나 비밀번호가 틀립니다.'}
    	STATUS 200
        {
            'co_id': '암호화된 소속회사 id',
            'br_id': '암호화된 사업자 등록 정보 id',
            'is_staff': 'YES', # 담당자?
            'is_manage': 'NO' # 관리자?
        }
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
        staff = staffs[0]
        customer = Customer.objects.get(id=staff.co_id)
        result = {
            'co_id': AES_ENCRYPT_BASE64(str(staff.co_id)),   # 소속회사 id
            'br_id': AES_ENCRYPT_BASE64(str(customer.business_reg_id)),  # 사업자 등록 정보
            'is_staff': 'YES' if staff.id == customer.staff_id else 'NO',    # 담당자?
            'is_manage': 'YES' if staff.id == customer.manager_id else 'NO'    # 관리자?
        }
        response = CRSHttpResponse(json.dumps(result, cls=DateTimeEncoder))
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


def reg_work_place(request):
    """
    사업장 등록
        주)	response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/reg_work_place?staff_id=qgf6YHf1z2Fx80DR8o_Lvg&name=임창베르디안&manager_id=1&order_id=1
    POST
        {
            'staff_id':'암호화된 id', # 업무처리하는 직원
            'name':'(주)효성 용연 1공장',	# 이름
            'manager_id':'8382',	# 관리자 id
            'order_id':'1899',	# 발주사 id
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

        manager_id = rqst['manager_id']
        manager = Staff.objects.get(id=manager_id)
        order_id = rqst['order_id']
        order = Customer.objects.get(id=order_id)
        name = rqst['name']
        new_work_place = Work_Place(
            name = name,
            place_name = name,
            contractor_id = staff.co_id,
            contractor_name = staff.co_name,
            manager_id = manager.id,
            manager_name = manager.name,
            manager_pNo = manager.pNo,
            manager_email = manager.email,
            order_id = order.id,
            order_name = order.name
        )
        new_work_place.save()
        response = CRSHttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('reg_work_place', '509', e)


def update_work_place(request):
    """
    사업장 수정
        주)	값이 있는 항목만 수정한다. ('name':'' 이면 사업장 이름을 수정하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/update_work_place?staff_id=qgf6YHf1z2Fx80DR8o_Lvg&work_place_id=10&name=&manager_id=&order_id=
    POST
        {
            'staff_id':'암호화된 id', # 업무처리하는 직원
            'work_place_id':'사업장 id' # 수정할 사업장 id
            'name':'(주)효성 용연 1공장',	# 이름
            'manager_id':'8382',	# 관리자 id
            'order_id':'1899',	# 발주사 id
        }
    response
        STATUS 200
        STATUS 503
            {'message': '사업장을 수정할 권한이 없는 직원입니다.'}
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
        work_place_id = rqst['work_place_id']
        work_place = Work_Place.objects.get(id=work_place_id)
        if work_place.contractor_id != staff.co_id:
            result = {'message': '사업장을 수정할 권한이 없는 직원입니다.'}
            response = CRSHttpResponse(json.dumps(result, cls=DateTimeEncoder))
            response.status_code = 503
            return response

        manager_id = rqst['manager_id']
        if len(manager_id) > 0:
            manager = Staff.objects.get(id=manager_id)
            work_place.manager_id = manager.id
            work_place.manager_name = manager.name
            work_place.manager_pNo = manager.pNo
            work_place.manager_email = manager.email

        order_id = rqst['order_id']
        if len(order_id) > 0:
            order = Customer.objects.get(id=order_id)
            work_place.order_id = order.id
            work_place.order_name = order.name

        name = rqst['name']
        if len(name) > 0:
            work_place.name = name
            work_place.place_name = name

        work_place.save()
        response = CRSHttpResponse()
        response.status_code = 200
        print('<<< update_work_place', work_place.name)
        return response
    except Exception as e:
        return exceptionError('update_work_place', '509', e)


def list_work_place(request):
    """
    사업장 목록
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/list_work_place?staff_id=qgf6YHf1z2Fx80DR8o_Lvg&name=&manager_name=종기&manager_phone=3555&order_name=대덕
    GET
        staff_id      = 암호화된 id	 	# 업무처리하는 직원
        name          = (주)효성 용연 1공장	# 이름
        manager_name  = 선호			    # 관리자 이름
        manager_phone = 3832	 	    # 관리자 전화번호
        order_name    = 효성			    # 발주사 이름
    response
        STATUS 200
        {
            "work_places":
                [ {"name": "대덕테크", "contractor_id": 1, "contractor_name": "대덕테크", "place_name": "대덕테크", "manager_id": 1, "manager_name": "박종기", "manager_pNo": "01025573555", "manager_email": "thinking@ddtechi.com", "order_id": 1, "order_name": "대덕기공"}
                  ......
                ]}
        STATUS 503
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
        manager_name = rqst['manager_name']
        manager_phone = rqst['manager_phone']
        order_name = rqst['order_name']
        work_places = Work_Place.objects.filter(contractor_id=staff.co_id,
                                                name__contains=name,
                                                manager_name__contains=manager_name,
                                                manager_pNo__contains=manager_phone,
                                                order_name__contains=order_name).values('name',
                                                                                        'contractor_id',
                                                                                        'contractor_name',
                                                                                        'place_name',
                                                                                        'manager_id',
                                                                                        'manager_name',
                                                                                        'manager_pNo',
                                                                                        'manager_email',
                                                                                        'order_id',
                                                                                        'order_name')

        arr_work_place = [work_place for work_place in work_places]
        result = {'work_places': arr_work_place}
        response = CRSHttpResponse(json.dumps(result, cls=DateTimeEncoder))
        response.status_code = 200
        print('<<< list_work_place')
        return response
    except Exception as e:
        return exceptionError('list_work_place', '509', e)


def reg_work(request):
    """
    사업장 업무 등록
        주)	response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/reg_work?staff_id=qgf6YHf1z2Fx80DR8o_Lvg&name=임창베르디안&manager_id=1&order_id=1
    POST
        {
            'op_staff_id':'암호화된 id',   # 업무처리하는 직원
            'name':'포장',
            'work_place_id':1,        # 사업장 id
            'type':'업무 형태',
            'dt_begin':'2019-01-28',  # 업무 시작 날짜
            'dt_end':'2019-02-28',    # 업무 종료 날짜
            'staff_id':2,
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

        op_staff_id = AES_DECRYPT_BASE64(rqst['op_staff_id'])
        staff = Staff.objects.get(id=op_staff_id)

        work_place_id = rqst['work_place_id']
        work_place = Work_Place.objects.get(id=work_place_id)
        staff_id = rqst['staff_id']
        staff = Staff.objects.get(id=staff_id)
        name = rqst['name']
        type = rqst['type']
        # dt_begin = datetime.datetime.strptime(rqst['dt_begin'], "%Y-%m-%d %H:%M:%S")
        # dt_end = datetime.datetime.strptime(rqst['dt_end'], "%Y-%m-%d %H:%M:%S")
        dt_begin = datetime.datetime.strptime(rqst['dt_begin'], "%Y-%m-%d")
        dt_end = datetime.datetime.strptime(rqst['dt_end'], "%Y-%m-%d")
        print(dt_begin, dt_end)
        # new_work = Work(
        #     name = name,
        #     place_name = name,
        #     contractor_id = staff.co_id,
        #     contractor_name = staff.co_name,
        #     manager_id = manager.id,
        #     manager_name = manager.name,
        #     manager_pNo = manager.pNo,
        #     manager_email = manager.email,
        #     order_id = order.id,
        #     order_name = order.name
        # )
        # new_work_place.save()
        response = CRSHttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('reg_work', '509', e)


def update_work(request):
    """
    사업장 업무 수정
    :param request:
    :return:
    """
    return


def list_work(request):
    """
    사업장 업무 목록
    :param request:
    :return:
    """
    return


def reg_employee(request):
    """
    근로자 등록
    :param request:
    :return:
    """
    return


def update_employee(request):
    """
    근로자 수정
    :param request:
    :return:
    """
    return


def list_employee(request):
    """
    근로자 목록
    :param request:
    :return:
    """
    return


def report(request):
    """
    현장, 업무별 보고서
    :param request:
    :return:
    """
    return
