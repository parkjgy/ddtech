"""
Customer view

Copyright 2019. DaeDuckTech Corp. All rights reserved.
"""
import os
import random
import requests
import datetime
from datetime import timedelta
import inspect
import re

from django.conf import settings

from config.log import logSend, logError
from config.common import ReqLibJsonResponse
from config.common import status422, is_parameter_ok, id_ok, type_ok, get_client_ip, get_api, str_minute, str2min
# secret import
from config.common import hash_SHA256, no_only_phone_no, phone_format, dt_null, dt_str, str_to_datetime, int_none
from config.secret import AES_ENCRYPT_BASE64, AES_DECRYPT_BASE64
from config.decorator import cross_origin_read_allow, session_is_none_403

# log import
from .models import Customer
from .models import Relationship
from .models import Staff
from .models import Business_Registration
from .models import Work_Place
from .models import Work
from .models import Employee
from .models import Employee_Backup

from config.status_collection import *

# APNs
from config.apns import notification

import xlsxwriter  # json to xlsx
from dateutil.relativedelta import relativedelta


@cross_origin_read_allow
def table_reset_and_clear_for_operation(request):
    """
    <<<운영 서버용>>> 고객 서버 데이터 리셋 & 클리어
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    if AES_DECRYPT_BASE64(rqst['key']) != 'thinking':
        result = {'message': '사용 권한이 없습니다.'}
        logSend(result['message'])

        return REG_403_FORBIDDEN.to_json_response(result)

    Customer.objects.all().delete()
    Relationship.objects.all().delete()
    Business_Registration.objects.all().delete()
    Staff.objects.all().delete()
    Work_Place.objects.all().delete()
    Work.objects.all().delete()
    Employee.objects.all().delete()

    from django.db import connection
    cursor = connection.cursor()
    cursor.execute("ALTER TABLE customer_customer AUTO_INCREMENT = 1")
    cursor.execute("ALTER TABLE customer_relationship AUTO_INCREMENT = 1")
    cursor.execute("ALTER TABLE customer_business_registration AUTO_INCREMENT = 1")
    cursor.execute("ALTER TABLE customer_staff AUTO_INCREMENT = 1")
    cursor.execute("ALTER TABLE customer_work_place AUTO_INCREMENT = 1")
    cursor.execute("ALTER TABLE customer_work AUTO_INCREMENT = 1")
    cursor.execute("ALTER TABLE customer_employee AUTO_INCREMENT = 1")

    result = {'message': 'customer tables deleted == $ python manage.py sqlsequencereset customer'}
    logSend(result['message'])

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def reg_customer_for_operation(request):
    """
    <<<운영 서버용>>> 고객사를 등록한다.
    - 고객사 담당자와 관리자는 처음에는 같은 사람이다.
    - 간단한 내용만 넣어서 등록하고 나머지는 고객사 담당자가 추가하도록 한다.
    * 서버 to 서버 통신 work_id 필요
        주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/reg_customer_for_operation?worker_id=qgf6YHf1z2Fx80DR8o_Lvg&customer_name=주식회사 담&staff_name=박종기&staff_pNo=010-2557-3555&staff_email=parkjgy@daam.co.kr
    POST
        {
            'worker_id': 'cipher_id'  # 운영직원 id
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
        STATUS 541
            {'message':'등록되어있지 않은 업체입니다.'}
        STATUS 543
            {'message', '같은 상호와 담당자 전화번호로 등록된 업체가 있습니다.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    # 운영 서버에서 호출했을 때 - 운영 스텝의 id를 로그에 저장한다.
    worker_id = AES_DECRYPT_BASE64(rqst['worker_id'])
    logSend('   from operation server : operation staff id ', worker_id)

    parameter_check = is_parameter_ok(rqst, ['customer_name', 'staff_name', 'staff_pNo', 'staff_email'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

    customer_name = parameter_check['parameters']['customer_name']
    staff_name = parameter_check['parameters']['staff_name']
    staff_pNo = no_only_phone_no(parameter_check['parameters']['staff_pNo'])
    staff_email = parameter_check['parameters']['staff_email']

    # customer_name = rqst["customer_name"]
    # staff_name = rqst["staff_name"]
    # staff_pNo = no_only_phone_no(rqst["staff_pNo"])
    # staff_email = rqst["staff_email"]

    customers = Customer.objects.filter(corp_name=customer_name, staff_pNo=staff_pNo)
    # 파견기업 등록
    if len(customers) > 0:
        # 파견기업 상호와 담당자 전화번호가 등록되어 있는 경우

        return REG_543_EXIST_TO_SAME_NAME_AND_PHONE_NO.to_json_response()
    else:
        customer = Customer(
            corp_name=customer_name,
            staff_name=staff_name,
            staff_pNo=staff_pNo,
            staff_email=staff_email,
            manager_name=staff_name,
            manager_pNo=staff_pNo,
            manager_email=staff_email,
            is_contractor=True,
            type=11,
        )
        customer.save()

        # 파견업체는 동시에 협력사로 등록 되어 있어야 한다.
        # - 차후 업무에서 업체를 선택할 때 사용할 수 있다.
        relationship = Relationship(
            contractor_id=customer.id,
            type=12,
            corp_id=customer.id,
            corp_name=customer_name,
        )
        relationship.save()

        staff = Staff(
            name=staff_name,
            login_id='temp_' + str(customer.id),
            login_pw=hash_SHA256('happy_day!!!'),
            co_id=customer.id,
            co_name=customer.corp_name,
            pNo=staff_pNo,
            email=staff_email,
            dt_app_login=datetime.datetime.now(),
            dt_login=datetime.datetime.now(),
            is_site_owner=True,
            is_manager=True,
        )
        staff.save()
        customer.staff_id = str(staff.id)
        customer.manager_id = str(staff.id)
        customer.save()
    logSend('staff id = ', staff.id)
    logSend(customer_name, staff_name, staff_pNo, staff_email, staff.login_id, staff.login_pw)
    result = {'message': '정상처리되었습니다.',
              'login_id': staff.login_id
              }

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def sms_customer_staff_for_operation(request):
    """
    <<<운영 서버용>>> 고객사 담당자의 id / pw 를 sms 로 보내기 위해 pw 를 초기화 한다.
    * 서버 to 서버 통신 work_id 필요
        주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/sms_customer_staff_for_operation?worker_id=qgf6YHf1z2Fx80DR8o_Lvg&staff_id=qgf6YHf1z2Fx80DR8o_Lvg
    POST
        {
            'worker_id': 'cipher_id'  # 운영직원 id
            'staff_id': 'cipher_id'  # 암호화된 직원 id
        }
    response
        STATUS 200
            {
                'msg': '정상처리되었습니다.',
                'login_id': staff.login_id,
            }
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    # 운영 서버에서 호출했을 때 - 운영 스텝의 id를 로그에 저장한다.
    worker_id = AES_DECRYPT_BASE64(rqst['worker_id'])
    logSend('   from operation server : operation staff id ', worker_id)

    staffs = Staff.objects.filter(id=AES_DECRYPT_BASE64(rqst['staff_id']))
    if len(staffs) == 0:
        return REG_541_NOT_REGISTERED.to_json_response()
    staff = staffs[0]
    staff.login_pw = hash_SHA256('happy_day!!!')
    staff.save()
    result = {'message': '정상처리되었습니다.',
              'login_id': staff.login_id
              }

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def list_customer_for_operation(request):
    """
    <<<운영 서버용>>> 고객사 리스트를 요청한다.
    * 서버 to 서버 통신 work_id 필요
    http://0.0.0.0:8000/customer/list_customer_for_operation?worker_id=qgf6YHf1z2Fx80DR8o_Lvg&customer_name=대덕테크&staff_name=박종기&staff_pNo=010-2557-3555&staff_email=thinking@ddtechi.com
    GET
        worker_id='AES_256_id' # 운영 서버 직원 id
        customer_name=대덕기공
        staff_name=홍길동
        staff_pNo=010-1111-2222
        staff_email=id@daeducki.com
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "customers": [
                {
                  "id": "qgf6YHf1z2Fx80DR8o_Lvg==",
                  "name": "대덕테크",
                  "contract_no": "",
                  "dt_reg": "2019-01-17 08:09:08",
                  "dt_accept": null,
                  "type": 10,
                  "contractor_name": "",
                  "staff_id": "_w8ZzqmpBf5xvsE2VPY2XzaY9zmregZXSKFBR-4cOts=",
                  "staff_name": "박종기",
                  "staff_pNo": "01025573555",
                  "staff_email": "thinking@ddtechi.com",
                  "manager_name": "이요셉",
                  "manager_pNo": "01024505942",
                  "manager_email": "hello@ddtechi.com",
                  "dt_payment": "2019-02-25 02:24:27"
                },
                ......
              ]
            }
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    # 운영 서버에서 호출했을 때 - 운영 스텝의 id를 로그에 저장한다.
    worker_id = AES_DECRYPT_BASE64(rqst['worker_id'])
    logSend('  --- from operation server : op staff id({})'.format(worker_id))

    customer_name = rqst['customer_name']
    staff_name = rqst['staff_name']
    staff_pNo = no_only_phone_no(rqst['staff_pNo'])
    staff_email = rqst['staff_email']

    customers = Customer.objects.filter(is_contractor=True).values('id', 'corp_name', 'contract_no', 'dt_reg',
                                                                   'dt_accept', 'type', 'staff_id', 'staff_name',
                                                                   'staff_pNo', 'staff_email', 'manager_name',
                                                                   'manager_pNo', 'manager_email', 'dt_payment')
    arr_customer = []
    for customer in customers:
        logSend('id: {}, corp_name: {}'.format(customer['id'], customer['corp_name']))
        customer['id'] = AES_ENCRYPT_BASE64(str(customer['id']))
        customer['dt_reg'] = customer['dt_reg'].strftime("%Y-%m-%d %H:%M:%S")
        customer['dt_accept'] = None if customer['dt_accept'] is None else \
            customer['dt_accept'].strftime("%Y-%m-%d %H:%M:%S")
        customer['dt_payment'] = None if customer['dt_payment'] is None else \
            customer['dt_payment'].strftime("%Y-%m-%d %H:%M:%S")
        customer['staff_id'] = AES_ENCRYPT_BASE64(str(customer['staff_id']))
        customer['staff_pNo'] = phone_format(customer['staff_pNo'])
        customer['manager_pNo'] = phone_format(customer['manager_pNo'])
        arr_customer.append(customer)
    result = {'customers': arr_customer}

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def update_customer(request):
    """
    고객사(협력사, 발주사) 정보 변경 (담당자, 관리자만 가능)
    - 담당자가 담당자를 바꾸면 로그아웃된다.
    - 관리자가 관리자를 바뀌면 바로 로그아웃된다.
    - 관리자가 담당자를 바꾸었을 때는 로그아웃하지 않는다.
    - 담당자나 관리자가 바뀔 때는 다른 값은 바꿀 수 없다.
    	주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
    http://0.0.0.0:8000/customer/update_customer?
    POST
    	{
            'staff_id': '서버에서 받은 암호화된 id', # 담당자를 변경할 때만 (담당자, 관리자만 변경 가능)

            'manager_id': '서버에서 받은 암호화된 id', # 관리자를 변경할 때만 (관리자만 변경 가능)

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
    	    {'message': '담당자가 바뀌어 로그아웃되었습니다.'}
        STATUS 409
            {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
    	STATUS 422
    	    {'message': 'staff_id 가 잘못된 값입니다.'}  # 자신을 선택했을 때 포함
    	    {'message': 'manager_id 가 잘못된 값입니다.'} # 자신을 선택했을 때 포함
    	STATUS 522
    		{'message': '담당자나 관리자만 변경 가능합니다.'}
    		{'message': '관리자만 변경 가능합니다.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    customer = Customer.objects.get(id=worker.co_id)
    logSend('--- corp_name{}, worker_id: {}, staff_id: {}, manager_id: {}'.format(customer.corp_name, worker_id,
                                                                                  customer.staff_id,
                                                                                  customer.manager_id))
    # 담당자(is_site_owner) 나 관리자(is_manager)가 아니면 권한이 없다.
    if not (worker.is_site_owner or worker.is_manager):
        return REG_522_MODIFY_SITE_OWNER_OR_MANAGER_ONLY.to_json_response()
    # 작업자(worker.id) 가 고객사의 담당자(staff_id)나 관리자(staff_id)가 아니면 권한이 없다. - id 로 확인한다.
    if worker.id not in [customer.staff_id, customer.manager_id]:
        return REG_522_MODIFY_SITE_OWNER_OR_MANAGER_ONLY.to_json_response()

    is_logout = False  # 담당자나 관리자가 바뀌면 로그아웃할 flag
    parameter_check = is_parameter_ok(rqst, ['staff_id_!'])
    if parameter_check['is_ok']:
        staff_id = int(parameter_check['parameters']['staff_id'])
        # 기존 담당자(customer.staff_id) 와 새로운 담당자(staff_id)가 같으면 처리할 필요 없다.
        if customer.staff_id != staff_id:
            staffs = Staff.objects.filter(id=staff_id)
            if len(staffs) == 0:
                logError(get_api(request), ' Staff(id:{})가 없어서 담당자가 교체되지 않았다.'.format(staff_id))
            else:
                if len(staffs) > 1:
                    logError(get_api(request), ' Staff(id:{})가 중복되었다.'.format(staff_id))
                staff = staffs[0]
                customer.staff_id = staff.id
                customer.staff_name = staff.name
                customer.staff_pNo = no_only_phone_no(staff.pNo)
                customer.staff_email = staff.email
                customer.save()

                staff.is_site_owner = True
                staff.save()

                is_logout = True

                if customer.manager_id == worker.id:
                    # 관리자가 담당자를 바꾸었기 때문에 로그아웃하지 않는다.
                    is_logout = False

                worker.is_site_owner = False
                worker.is_login = False
                worker.dt_login = datetime.datetime.now()
                worker.save()
    elif parameter_check['is_decryption_error']:
        logError(get_api(request), parameter_check['results'])

        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '이 메세지를 보시면 로그아웃 하십시요.'})

    parameter_check = is_parameter_ok(rqst, ['manager_id_!'])
    if parameter_check['is_ok']:
        manager_id = int(parameter_check['parameters']['manager_id'])
        # 작업자(work_id)가 관리자(customer.manager_id)가 아니면 처리하지 않는다.
        if customer.manager_id == worker_id:
            # 기존 관리자(customer.manager_id)와 새로운 관리자(manager_id)가 같으면 처리하지 않는다.
            if customer.manager_id != manager_id:
                managers = Staff.objects.filter(id=manager_id)
                if len(managers) == 0:
                    logError(get_api(request), ' Staff(id:{})가 없어서 관리자가 교체되지 않았다.'.format(manager_id))
                else:
                    if len(managers) > 1:
                        logError(get_api(request), ' Staff(id:{})가 중복되었다.'.format(manager_id))
                    manager = managers[0]
                    customer.manager_id = manager.id
                    customer.manager_name = manager.name
                    customer.manager_pNo = no_only_phone_no(manager.pNo)
                    customer.manager_email = manager.email
                    customer.save()

                    manager.is_manager = True
                    manager.save()

                    worker.is_manager = False
                    worker.is_login = False
                    worker.dt_login = datetime.datetime.now()
                    worker.save()

                    is_logout = True
    elif parameter_check['is_decryption_error']:
        logError(get_api(request), parameter_check['results'])

        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '이 메세지를 보시면 로그아웃 하십시요.'})

    # 사업자 등록증 내용 변경 or 새로 만들기
    update_business_registration(rqst, customer)

    parameter_check = is_parameter_ok(rqst, ['dt_payment'])
    if parameter_check['is_ok']:
        dt_payment = parameter_check['parameters']['dt_payment']
        dt_payment = datetime.datetime.now().strftime('%Y-%m-') + dt_payment + ' 16:00:00'
        customer.dt_payment = datetime.datetime.strptime(dt_payment, '%Y-%m-%d %H:%M:%S')
        logSend('--- dt_payment: {}'.format(customer.dt_payment))
        customer.save()

    if is_logout:
        # 담당자나 관리자가 바뀌었으면 로그아웃한다.
        del request.session['id']

        return REG_200_SUCCESS.to_json_response({'message': '담당자가 바뀌어 로그아웃되었습니다.'})

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403
def reg_relationship(request):
    """
    고객사의 협력사나 발주사를 등록한다.
    주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
        사업자등록 정보를 넣을 때는 모두 들어와야 한다. - 사업자등록 정보의 상호만 들어오면 안되고 사업자등록번호등 모두가 들어와야한다.
        response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/reg_relationship?type=10&corp_name=(주)티에스엔지&staff_name=홍길동&staff_pNo=010-1111-2222&staff_email=id@daeducki.com
    POST
        {
            'type': 10,      # 10 : 발주사, 12 : 협력사
            'corp_name': '(주)티에스엔지',
            'staff_name': '홍길동',
            'staff_pNo': '010-1111-2222',
            'staff_email': 'id@daeducki.com',

            'manager_name': '유재석',            # 선택
            'manager_pNo': '010-1111-4444',    # 선택
            'manager_email': 'id@daeducki.com' # 선택

            'name':'(주)티에스엔지',		    # 상호 - 선택
            'regNo':'123-000000-12',	    # 사업자등록번호 - 선택
            'ceoName':'홍길동',		 	    # 이름(대표자) - 선택
            'address':'울산시 중구 봉월동 22',   # 사업장소재지 - 선택
            'business_type':'서비스',		    # 업태 - 선택
            'business_item':'정보통신',		# 종목 - 선택
            'dt_reg':'2018-12-05',		 	# 사업자등록일 - 선택
        }
    response
        STATUS 200
        STATUS 409
            {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
        STATUS 544
            {'message', '이미 등록되어 있습니다.'}
        STATUS 422
            {'message': '*** 웹 개발자: type 주세요'}

            {'message': '필수 항목(빨간 별)이 비었습니다.'}
            {'message': '이름은 최소 2자 이상이어야 합니다.'}
            {'message': '전화번호는 국번까지 9자 이상이어야 합니다.'}
            {'message': '이메일 양식이 틀렸습니다.'}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)
    # 등록자 권한 확인 처리
    # if not (worker.is_site_owner or worker.is_manager):
    #     return REG_524_HAVE_NO_PERMISSION_TO_MODIFY.to_json_response({'message': '등록권한이 없습니다.'})

    parameter = is_parameter_ok(rqst, ['corp_name', 'staff_name', 'staff_pNo', 'staff_email'])
    if not parameter['is_ok']:
        return status422(get_api(request), {'message': '필수 항목(빨간 별)이 비었습니다.'})
    corp_name = parameter['parameters']['corp_name']
    staff_name = parameter['parameters']['staff_name']
    staff_pNo = no_only_phone_no(parameter['parameters']['staff_pNo'])
    staff_email = parameter['parameters']['staff_email']

    # if ' ' in corp_name:
    #     return status422(get_api(request), {'message': '회사명에 공백문자가 들어가면 안됩니다.'})
    if len(staff_name) < 2:
        return status422(get_api(request), {'message': '이름은 최소 2자 이상이어야 합니다.'})
    if len(staff_pNo) < 9:
        return status422(get_api(request), {'message': '전화번호는 국번까지 9자 이상이어야 합니다.'})
    check_email = re.compile('^[a-zA-Z0-9+-_.]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
    if check_email.match(staff_email) == None:
        return status422(get_api(request), {'message': '이메일 양식이 틀렸습니다.'})
    """
    import re

    r_p = re.compile('^(?=\S{6,20}$)(?=.*?\d)(?=.*?[a-z])(?=.*?[A-Z])(?=.*?[^A-Za-z\s0-9])')
    this code will validate your password with :

    min length is 6 and max length is 20
    at least include a digit number,
    at least a upcase and a lowcase letter
    at least a special characters

    logint_id = "abCD0123!@#$%^"
    print(r_p.search(logint_id)
    """
    if 'type' not in rqst:
        return status422(get_api(request), {'message': '*** 웹 개발자: type 주세요'})
    type = rqst['type']

    relationships = Relationship.objects.filter(contractor_id=worker.co_id, type=type, corp_name=corp_name)
    if len(relationships) > 0:
        return REG_544_EXISTED.to_json_response()
    corp = Customer(
        corp_name=corp_name,
        staff_name=staff_name,
        staff_pNo=staff_pNo,
        staff_email=staff_email,
        type=type,
    )
    if 'manager_name' in rqst:
        corp.manager_name = rqst['manager_name']
    if 'manager_pNo' in rqst:
        corp.manager_pNo = no_only_phone_no(rqst['manager_pNo'])
    if 'manager_email' in rqst:
        corp.manager_email = rqst['manager_email']
    corp.save()
    # logSend(' new corp: {}'.format({key: corp.__dict__[key] for key in corp.__dict__.keys()}))
    relationship = Relationship(
        contractor_id=worker.co_id,
        type=type,
        corp_id=corp.id,
        corp_name=corp_name
    )
    relationship.save()
    # logSend(' new relationship: {}'.format({key: relationship.__dict__[key] for key in relationship.__dict__.keys()}))

    # 사업자 등록증 처리
    update_business_registration(rqst, corp)

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403
def list_relationship(request):
    """
    발주사, 협력사 리스트를 요청한다.
    http://0.0.0.0:8000/customer/list_relationship?is_partner=YES&is_orderer=YES
    GET
        is_partner=YES  # 협력사 리스트를 가져오는가?
        is_orderer=YES  # 발주사 리스트를 가져오는가?
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "partners": [
                {
                  "name": "주식회사 살구",
                  "id": "ryWQkNtiHgkUaY_SZ1o2uA==",
                  "staff_name": "정소원",
                  "staff_pNo": "010-7620-5918"
                }
              ],
              "orderers": [
                {
                  "name": "대덕기공",
                  "id": "_LdMng5jDTwK-LMNlj22Vw==",
                  "staff_name": "엄원섭",
                  "staff_pNo": "010-3877-4105"
                }
              ]
            }
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    types = []
    if rqst['is_partner'].upper() == 'YES':
        types.append(12)
    if rqst['is_orderer'].upper() == 'YES':
        types.append(10)
    relationships = Relationship.objects.filter(contractor_id=worker.co_id, type__in=types)
    relationship_ids = [relationship.corp_id for relationship in relationships]
    corps = Customer.objects.filter(id__in=relationship_ids).values('id',
                                                                    'staff_name',
                                                                    'staff_pNo')
    corp_dic = {}
    for corp in corps:
        corp_dic[corp['id']] = corp
    partners = []
    orderers = []
    for relationship in relationships:
        corp = {'name': relationship.corp_name,
                'id': AES_ENCRYPT_BASE64(str(relationship.corp_id)),
                'staff_name': corp_dic[relationship.corp_id]['staff_name'],
                'staff_pNo': phone_format(corp_dic[relationship.corp_id]['staff_pNo']),
                'is_editble': False if relationship.contractor_id == relationship.corp_id else True,
                }
        if relationship.type == 12:
            partners.append(corp)
        elif relationship.type == 10:
            orderers.append(corp)
    result = {'partners': partners, 'orderers': orderers}

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def detail_relationship(request):
    """
    발주사, 협력사 상세 정보를 요청한다.
    http://0.0.0.0:8000/customer/detail_relationship?relationship_id=ryWQkNtiHgkUaY_SZ1o2uA
    GET
        relationship_id=ryWQkNtiHgkUaY_SZ1o2uA  # 발주사 협력사 id (암호화 된 값)
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "detail_relationship": {
                "type": 12,
                "type_name": "협력사",
                "corp_id": "ryWQkNtiHgkUaY_SZ1o2uA",
                "corp_name": "주식회사 살구",
                "staff_name": "정소원",
                "staff_pNo": "010-7620-5918",
                "staff_email": "salgoo.ceo@gmail.com",
                "manager_name": "",
                "manager_pNo": "",
                "manager_email": "",
                "name": null,
                "regNo": null,
                "ceoName": null,
                "address": null,
                "business_type": null,
                "business_item": null,
                "dt_reg": null
              }
            }
        STATUS 541
            {'message', '등록된 업체가 없습니다.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    if not 'relationship_id' in rqst:
        logSend('relationship_id << 없음')
    logSend(rqst['relationship_id'])
    logSend(AES_DECRYPT_BASE64(rqst['relationship_id']))
    corps = Customer.objects.filter(id=AES_DECRYPT_BASE64(rqst['relationship_id']))
    if len(corps) == 0:
        return REG_541_NOT_REGISTERED.to_json_response({'message': '등록된 업체가 없습니다.'})
    corp = corps[0]

    detail_relationship = {'type': corp.type,
                           'type_name': '발주사' if corp.type == 10 else '협력사',
                           'corp_id': rqst['relationship_id'],
                           'corp_name': corp.corp_name,
                           'staff_name': corp.staff_name,
                           'staff_pNo': phone_format(corp.staff_pNo),
                           'staff_email': corp.staff_email,
                           'manager_name': corp.manager_name,
                           'manager_pNo': phone_format(corp.manager_pNo),
                           'manager_email': corp.manager_email,
                           }

    business_registrations = Business_Registration.objects.filter(customer_id=corp.id)
    if len(business_registrations) > 0:
        business_registration = business_registrations[0]
        detail_relationship['name'] = business_registration.name  # 상호
        detail_relationship['regNo'] = business_registration.regNo  # 사업자등록번호
        detail_relationship['ceoName'] = business_registration.ceoName  # 성명(대표자)
        detail_relationship['address'] = business_registration.address  # 사업장소재지
        detail_relationship['business_type'] = business_registration.business_type  # 업태
        detail_relationship['business_item'] = business_registration.business_item  # 종목
        detail_relationship[
            'dt_reg'] = None if business_registration.dt_reg is None else business_registration.dt_reg.strftime(
            '%Y-%m-%d')  # 사업자등록일
    else:
        detail_relationship['name'] = None  # 상호
        detail_relationship['regNo'] = None  # 사업자등록번호
        detail_relationship['ceoName'] = None  # # 성명(대표자)
        detail_relationship['address'] = None  # 사업장소재지
        detail_relationship['business_type'] = None  # 업태
        detail_relationship['business_item'] = None  # 종목
        detail_relationship['dt_reg'] = None  # 사업자등록일

    return REG_200_SUCCESS.to_json_response({'detail_relationship': detail_relationship})


@cross_origin_read_allow
@session_is_none_403
def update_relationship(request):
    """
    고객사의 협력사의 정보를 수정한다.
    주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
        사업자등록 정보를 넣을 때는 모두 들어와야 한다. - 사업자등록 정보의 상호만 들어오면 안되고 사업자등록번호등 모두가 들어와야한다.
        response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/update_relationship?corp_id=ryWQkNtiHgkUaY_SZ1o2uA&corp_name=(주)살구&staff_name=정소원&staff_pNo=010-7620-5918&staff_email=salgoo.ceo@gmail.com
    POST
        {
            'corp_id': 'cipher_id',      # 발주사 or 협력사 id 의 암호화된 값
            'corp_name': '(주)티에스엔지',
            'staff_name': '홍길동',
            'staff_pNo': '010-1111-2222',
            'staff_email': 'id@daeducki.com',

            'manager_name': '유재석',            # 선택
            'manager_pNo': '010-1111-4444',    # 선택
            'manager_email': 'id@daeducki.com' # 선택

            'name':'(주)티에스엔지',		    # 상호 - 선택
            'regNo':'123-000000-12',	    # 사업자등록번호 - 선택
            'ceoName':'홍길동',		 	    # 이름(대표자) - 선택
            'address':'울산시 중구 봉월동 22',   # 사업장소재지 - 선택
            'business_type':'서비스',		    # 업태 - 선택
            'business_item':'정보통신',		# 종목 - 선택
            'dt_reg':'2018-12-05',		 	# 사업자등록일 - 선택
        }
    response
        STATUS 200
        STATUS 409
            {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
        STATUS 541
            {'message', '등록된 업체가 없습니다.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    corp_id = rqst['corp_id']
    corps = Customer.objects.filter(id=AES_DECRYPT_BASE64(corp_id))
    if len(corps) == 0:
        return REG_541_NOT_REGISTERED.to_json_response({'message': '등록된 업체가 없습니다.'})
    corp = corps[0]
    is_update_corp = False
    for key in ['corp_name', 'staff_name', 'staff_pNo', 'staff_email', 'manager_name', 'manager_pNo', 'manager_email']:
        # print('key', key)
        if key in rqst:
            # print('     value', rqst[key])
            if len(rqst[key]) > 0:
                corp.__dict__[key] = no_only_phone_no(rqst[key]) if 'pNo' in key else rqst[key]
            else:
                corp.__dict__[key] = ''
            is_update_corp = True
    if is_update_corp:
        # print([(x, corp.__dict__[x]) for x in Customer().__dict__.keys() if not x.startswith('_')])
        corp.save()
        #
        # 영향 받는 곳 update : Relationship, Work_Place, Work
        #
        if 'corp_name' in rqst:
            # Relationship: 협력업체나 발주사 상호가 바뀌면 반영
            relationships = Relationship.objects.filter(corp_id=corp.id)
            if len(relationships) > 0:
                relationship = relationships[0]
                relationship.corp_name = corp.corp_name  # rqst['corp_name']
                relationship.save()
            # Work_Place: 발주사 이름 반영
            work_place_list = Work_Place.objects.filter(order_id=corp.id)
            for work_place in work_place_list:
                work_place.order_name = corp.corp_name
                work_place.save()
            # Work: 협력사 이름 반영
            work_list = Work.objects.filter(contractor_id=corp.id)
            for work in work_list:
                work.contractor_name = corp.corp_name
                work.save()

    # 사업자 등록증 내용 변경 or 새로 만들기
    update_business_registration(rqst, corp)

    return REG_200_SUCCESS.to_json_response()


def update_business_registration(rqst, corp):
    """
    사업자 등록증 신규 등록이나 내용 변경
    :param rqst: 호출 함수의 파라미터
    :param corp: 고객사(수요기업, 파견업체)
    :return: none
    """

    is_update_business_registration = False
    new_business_registration = {}
    for key in ['name', 'regNo', 'ceoName', 'address', 'business_type', 'business_item', 'dt_reg']:
        # logSend('key:', key)
        # print('key', key)
        if key in rqst:
            # print('value:', rqst[key])
            # print('     value', rqst[key])
            if len(rqst[key]) > 0:
                if key == 'dt_reg':
                    # logSend(key, rqst[key])
                    # print(key, rqst[key])
                    dt = rqst[key]
                    new_business_registration[key] = datetime.datetime.strptime(dt[:10],
                                                                                "%Y-%m-%d")  # + datetime.timedelta(hours=9)
                else:
                    new_business_registration[key] = rqst[key]
            else:
                new_business_registration[key] = None
            is_update_business_registration = True
    if is_update_business_registration:
        # print(corp.business_reg_id, new_business_registration)
        # logSend(corp.business_reg_id, new_business_registration)
        if corp.business_reg_id > 0:  # 고객사(수요기업, 파견사)에 사업자 등록정보가 저장되어 있으면
            business_regs = Business_Registration.objects.filter(id=corp.business_reg_id)
            if len(business_regs) > 0:
                business_reg = business_regs[0]
                for key in new_business_registration.keys():
                    business_reg.__dict__[key] = new_business_registration[key]
                # logSend('update',[(x, business_reg.__dict__[x]) for x in Business_Registration().__dict__.keys() if not x.startswith('_')])
                # print('update',[(x, business_reg.__dict__[x]) for x in Business_Registration().__dict__.keys() if not x.startswith('_')])
                business_reg.save()
            else:
                logError('ERROR : 사업자 등록정보 id 가 잘못되었음', corp.name, corp.id, __package__.rsplit('.', 1)[-1],
                         inspect.stack()[0][3])
                # print('사업자 등록정보 id 가 잘못되었음', corp.name, corp.id)
        else:
            business_reg = Business_Registration(customer_id=corp.id,
                                                 dt_reg=None)
            for key in new_business_registration.keys():
                business_reg.__dict__[key] = new_business_registration[key]
            # logSend('new', [(x, business_reg.__dict__[x]) for x in Business_Registration().__dict__.keys() if not x.startswith('_')])
            # print('new', [(x,business_reg.__dict__[x]) for x in Business_Registration().__dict__.keys() if not x.startswith('_')])
            business_reg.save()

            corp.business_reg_id = business_reg.id
            corp.save()

    return


@cross_origin_read_allow
@session_is_none_403
def reg_staff(request):
    """
    고객사 직원을 등록한다.
    - 차후 전화번호 변경 부분과 중복 처리가 필요함.
    - 초기 pw 는 happy_day!!!
        주)	response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/reg_staff?name=이요셉&login_id=hello&login_pw=A~~~8282&position=책임&department=개발&pNo=010-2450-5942&email=hello@ddtechi.com
    POST
        {
            'name': '홍길동',
            'login_id': 'hong_geal_dong',
            'position': '부장',	   # option 비워서 보내도 됨
            'department': '관리부',	# option 비워서 보내도 됨
            'pNo': '010-1111-2222', # '-'를 넣어도 삭제되어 저장 됨
            'email': 'id@daeducki.com',
        }
    response
        STATUS 200
        STATUS 409
            {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
        STATUS 542
            {'message': '다른 사람이 이미 사용하는 아이디입니다.'})
            {'message': '이미 등록되어 있는 전화번호입니다.'}
        STATUS 524
            {'message': '등록권한이 없습니다.'}
        STATUS 422
            {'message': '빨간 별이 있는 항목이 비었습니다.'}
            {'message': '아이디는 영문자, 숫자, 밑줄만 허용되고 6자 이상이어야 합니다.'}
            {'message': '이름은 최소 2자 이상이어야 합니다.'}
            {'message': '전화번호는 국번까지 9자 이상이어야 합니다.'}
            {'message': '이메일 양식이 틀렸습니다.'}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)
    # 등록자 권한 확인 처리
    # if not (worker.is_site_owner or worker.is_manager):
    #     return REG_524_HAVE_NO_PERMISSION_TO_MODIFY.to_json_response({'message': '등록권한이 없습니다.'})

    parameter = is_parameter_ok(rqst, ['login_id', 'name', 'pNo', 'email'])
    if not parameter['is_ok']:
        return status422(get_api(request), {'message': '필수 항목(빨간 별)이 비었습니다.'})
    login_id = parameter['parameters']['login_id']
    name = parameter['parameters']['name']
    pNo = no_only_phone_no(parameter['parameters']['pNo'])
    email = parameter['parameters']['email']

    if len(login_id) < 6 or not login_id.isidentifier():
        return status422(get_api(request), {'message': '아이디는 영문자, 숫자, 밑줄만 허용되고 6자 이상이어야 합니다.'})
    if len(name) < 2:
        return status422(get_api(request), {'message': '이름은 최소 2자 이상이어야 합니다.'})
    if len(pNo) < 9:
        return status422(get_api(request), {'message': '전화번호는 국번까지 9자 이상이어야 합니다.'})
    check_email = re.compile('^[a-zA-Z0-9+-_.]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
    if check_email.match(email) == None:
        return status422(get_api(request), {'message': '이메일 양식이 틀렸습니다.'})
    """
    import re

    r_p = re.compile('^(?=\S{6,20}$)(?=.*?\d)(?=.*?[a-z])(?=.*?[A-Z])(?=.*?[^A-Za-z\s0-9])')
    this code will validate your password with :
    
    min length is 6 and max length is 20
    at least include a digit number,
    at least a upcase and a lowcase letter
    at least a special characters
    
    logint_id = "abCD0123!@#$%^"
    print(r_p.search(logint_id)
    """
    staffs = Staff.objects.filter(login_id=login_id)
    # logSend([staff.name for staff in staffs])
    if len(staffs) > 0:
        return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response({'message': '다른 사람이 이미 사용하는 아이디입니다.'})
    staffs = Staff.objects.filter(pNo=pNo)
    if len(staffs) > 0:
        return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response({'message': '이미 등록되어 있는 전화번호입니다.'})

    new_staff = Staff(
        name=name,
        login_id=login_id,
        login_pw=hash_SHA256('happy_day!!!'),
        co_id=worker.co_id,
        co_name=worker.co_name,
        position=rqst['position'] if 'position' in rqst else "",
        department=rqst['department'] if 'department' in rqst else "",
        dt_app_login=datetime.datetime.now(),
        dt_login=datetime.datetime.now(),
        pNo=pNo,
        email=email
    )
    new_staff.save()
    logSend(' new staff: {}'.format({key: new_staff.__dict__[key] for key in new_staff.__dict__.keys()}))
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def login(request):
    """
    로그인
    - 담당자나 관리자가 아니면 회사 정보 편집이 안되어야한다.
    http://0.0.0.0:8000/customer/login?login_id=temp_1&login_pw=happy_day!!!
    kms / HappyDay365!!!
    POST
        {
            'login_id': 'temp_1
            'login_pw': 'happy_day!!!'
        }
    response
        STATUS 200
        {
          "message": "정상적으로 처리되었습니다.",
          "staff_permission": {
            "is_site_owner": false,
            "is_manager": false
          },
          "company_general": {
            "co_id": '암호화된 소속사 id' # 업무에서 고객사와 협력업체를 선택할 때 사용
            "corp_name": "대덕테크",
            "staff_name": "정소원",
            "staff_pNo": "010-7620-5918",
            "staff_email": "salgoo.ceo@gmail.com",
            "manager_name": "",
            "manager_pNo": "",
            "manager_email": ""
          },
          "business_registration": {
            "name": null,
            "regNo": null,
            "ceoName": null,
            "address": null,
            "business_type": null,
            "business_item": null,
            "dt_reg": null
          }
        }
        STATUS 530
            {'message': '아이디가 없습니다.'}
            {'message': '비밀번호가 틀렸습니다.'}
    	STATUS 200
        {
            'co_id': '암호화된 소속회사 id',
            'br_id': '암호화된 사업자 등록 정보 id',
            'is_site_owner': True,      # 담당자?
            'is_manager': False         # 관리자?
        }
        STATUS 541
            {'message':'등록된 업체가 없습니다.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    login_id = rqst['login_id'].replace(' ', '')
    login_pw = rqst['login_pw'].replace(' ', '')
    logSend('--- login_id: [{}], pw [{}] - [{}]'.format(login_id, login_pw, hash_SHA256(login_pw)))

    staffs = Staff.objects.filter(login_id=login_id)
    if len(staffs) == 0:
        return REG_530_ID_OR_PASSWORD_IS_INCORRECT.to_json_response({'message': '아이디가 없습니다.'})
    elif len(staffs) > 1:
        logError(get_api(request), ' login id: {} 가 중복됩니다.')
    staff = staffs[0]
    logSend('--- server: [{}] vs login [{}]'.format(staff.login_pw, hash_SHA256(login_pw)))
    if staff.login_pw != hash_SHA256(login_pw):
        return REG_530_ID_OR_PASSWORD_IS_INCORRECT.to_json_response({'message': '비밀번호가 틀렸습니다.'})

    # staffs = Staff.objects.filter(login_id=login_id, login_pw=hash_SHA256(login_pw))
    # if len(staffs) == 0:
    #     staffs = Staff.objects.filter(login_id=login_id)
    #     if len(staffs) > 0:
    #         staff = staffs[0]
    #         logSend(hash_SHA256(login_pw), ' vs\n', staff.login_pw)
    #
    # 
    #     return REG_530_ID_OR_PASSWORD_IS_INCORRECT.to_json_response()
    # staff = staffs[0]
    staff.dt_login = datetime.datetime.now()
    staff.is_login = True
    staff.save()
    request.session['id'] = staff.id
    request.session['api_before'] = get_api(request)
    request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request.session.save()

    customers = Customer.objects.filter(id=staff.co_id)
    if len(customers) == 0:
        return REG_541_NOT_REGISTERED.to_json_response({'message': '등록된 업체가 없습니다.'})
    customer = customers[0]
    staff_permission = {'is_site_owner': staff.is_site_owner,  # 담당자인가?
                        'is_manager': staff.is_manager,  # 관리자인가?
                        }
    company_general = {'co_id': AES_ENCRYPT_BASE64(str(customer.id)),
                       'corp_name': customer.corp_name,
                       'staff_name': customer.staff_name,
                       'staff_pNo': phone_format(customer.staff_pNo),
                       'staff_email': customer.staff_email,
                       'manager_name': customer.manager_name,
                       'manager_pNo': phone_format(customer.manager_pNo),
                       'manager_email': customer.manager_email,
                       'dt_payment': None if customer.dt_payment is None else customer.dt_payment.strftime('%d')
                       }

    business_registrations = Business_Registration.objects.filter(customer_id=customer.id)
    if len(business_registrations) > 0:
        business_registration = business_registrations[0]
        business_registration = {'name': business_registration.name,  # 상호
                                 'regNo': business_registration.regNo,  # 사업자등록번호
                                 'ceoName': business_registration.ceoName,  # 성명(대표자)
                                 'address': business_registration.address,  # 사업장소재지
                                 'business_type': business_registration.business_type,  # 업태
                                 'business_item': business_registration.business_item,  # 종목
                                 'dt_reg': None if business_registration.dt_reg is None else business_registration.dt_reg.strftime(
                                     '%Y-%m-%d')  # 사업자등록일
                                 }
    else:
        business_registration = {'name': None,  # 상호
                                 'regNo': None,  # 사업자등록번호
                                 'ceoName': None,  # 성명(대표자)
                                 'address': None,  # 사업장소재지
                                 'business_type': None,  # 업태
                                 'business_item': None,  # 종목
                                 'dt_reg': None  # 사업자등록일
                                 }

    return REG_200_SUCCESS.to_json_response({'staff_permisstion': staff_permission,
                                             'company_general': company_general,
                                             'business_registration': business_registration
                                             })


@cross_origin_read_allow
def logout(request):
    """
    로그아웃
    http://0.0.0.0:8000/customer/logout
    POST
    response
        STATUS 200
    """
    if request.session is None or 'id' not in request.session:
        return REG_200_SUCCESS.to_json_response({'message': '이미 로그아웃되었습니다.'})
    staff = Staff.objects.get(id=request.session['id'])
    staff.is_login = False
    staff.dt_login = datetime.datetime.now()
    staff.save()
    del request.session['id']
    del request.session['dt_last']
    del request.session['api_before']
    # request.session.save()

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403
def update_staff(request):
    """
    직원 정보를 수정한다.
    - 자신의 정보만 수정할 수 있다.
    - 관리자나 담당자는 다른 직원의 정보를 수정할 수 있다.
    - login id, pw 가 바뀌면 로그아웃된다.
    	주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
    		response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/update_staff?before_pw=A~~~8282&login_pw=A~~~8282&name=박종기&position=이사&department=개발&phone_no=010-2557-3555&phone_type=10&push_token=unknown&email=thinking@ddtechi.com
    POST
    	{
    	    'staff_id': 직원의 암호화된 식별 id         # << 추가됨 >> 필수
    	    'new_login_id': '변경하고 싶은 login id',
    		'before_pw': '기존 비밀번호',              # 필수
    		'login_pw': '변경하려는 비밀번호',          # 사전에 비밀번호를 확인할 것
    		'name': '이름',
    		'position': '직책',
    		'department': '부서 or 소속',
    		'phone_no': '전화번호',
    		'email': 'id@ddtechi.com'
    	}
    response
    	STATUS 200
    	STATUS 403  # login id, pw 가 바뀌어 로그아웃처리되었다.
    	    {'message':'로그아웃되었습니다.\n다시 로그인해주세요.'}
    	STATUS 409
    	    {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
    	STATUS 531
    		{'message': '비밀번호가 틀립니다.'}
            {'message': '비밀번호는 6자 이상으로 만들어야 합니다.'}
            {'message': '영문, 숫자가 모두 포합되어야 합니다.'}
    	STATUS 542
    	    {'message':'아이디는 5자 이상으로 만들어야 합니다.'}
    	    {'message':'아이디가 중복됩니다.'}
    	STAUS 422  # 개발자 수정사항
    	    {'message':'ClientError: parameter \'staff_id\' 가 없어요'}
    	    {'message':'ClientError: parameter \'staff_id\' 가 정상적인 값이 아니예요. <암호해독 에러>'}
    	    {'message':'ClientError: parameter \'staff_id\' 본인의 것만 수정할 수 있는데 본인이 아니다.(담당자나 관리자도 아니다.'}
    	    {'message':'ServerError: parameter \'{}\' 의 직원이 없다.'.format(staff_id)}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter_check = is_parameter_ok(rqst, ['staff_id_!'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    staff_id = parameter_check['parameters']['staff_id']

    if int(staff_id) != worker_id:
        # 수정할 직원과 로그인한 직원이 같지 않으면 - 자신의 정보를 자신이 수정할 수는 있지만 관리자가 아니면 다른 사람의 정보 수정이 금지된다.
        if not (worker.is_site_owner or worker.is_manager):
            return status422(get_api(request), {
                'message': 'ClientError: parameter \'staff_id\' 본인의 것만 수정할 수 있는데 본인이 아니다.(담당자나 관리자도 아니다.'})
    staffs = Staff.objects.filter(id=staff_id)
    if len(staffs) == 0:
        return status422(get_api(request), {'message': 'ServerError: staff_id: {} 인 직원이 없다.'.format(staff_id)})
    edit_staff = staffs[0]
    parameter = {}
    for x in rqst.keys():
        parameter[x] = rqst[x]
    logSend(parameter)

    # 비밀번호 확인
    if not ('before_pw' in parameter) or \
            len(parameter['before_pw']) == 0 or \
            hash_SHA256(parameter['before_pw']) != edit_staff.login_pw:
        # 현재 비밀번호가 없거나, 비밀번호를 넣지 않았거나 비밀번호가 다르면

        return REG_531_PASSWORD_IS_INCORRECT.to_json_response({'message': '비밀번호가 틀렸습니다.'})

    # 새로운 id 중복 여부 확인
    if 'new_login_id' in parameter:
        new_login_id = parameter['new_login_id']  # 기존 비밀번호
        if len(new_login_id) < 6:  # id 글자수 6자 이상으로 제한

            return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response({'message': '아이디는 6자 이상으로 만들어야 합니다.'})
        duplicate_staffs = Staff.objects.filter(login_id=new_login_id)
        if len(duplicate_staffs) > 0:
            return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response({'message': '다른 사람이 사용중인 아이디 입니다.'})
        parameter['login_id'] = new_login_id
        del parameter['new_login_id']

    # 새로운 pw 6자 이상, alphabet, number, 특수문자 포함여부 확인
    if 'login_pw' in parameter:
        login_pw = parameter['login_pw']
        if len(login_pw) < 6:  # id 글자수 6자 이상으로 제한

            return REG_531_PASSWORD_IS_INCORRECT.to_json_response({'message': '비밀번호는 8자 이상으로 만들어야 합니다.'})
        #
        # alphabet, number, 특수문자 포함여부 확인
        #
        if not (any(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz' for c in login_pw) and
                any(c in '0123456789' for c in login_pw)):
                #  and any(c in '-_!@#$%^&*(){}[]/?' for c in login_pw)):  # 2020/03/05 특수문자 필수 입력 기능 해제
            return REG_531_PASSWORD_IS_INCORRECT.to_json_response(
                # {'message': '영문, 숫자, 특수문자(-_!@#$%^&*(){}[]/?)가 모두 포합되어야 합니다.'})  # 2020/03/05 특수문자 필수 입력 기능 해제
                {'message': '영문, 숫자가 모두 포합되어야 합니다.'})
        parameter['login_pw'] = hash_SHA256(login_pw)

    logSend(parameter)
    if 'phone_no' in parameter:
        parameter['pNo'] = no_only_phone_no(parameter['phone_no'])
        del parameter['phone_no']
    is_update_worker = False
    for key in ['login_id', 'login_pw', 'name', 'position', 'department', 'pNo', 'email']:
        logSend('key', key)
        if key in parameter:
            logSend('     value', parameter[key])
            edit_staff.__dict__[key] = '' if len(parameter[key]) == 0 else parameter[key]
            is_update_worker = True
    if is_update_worker:
        logSend([(x, worker.__dict__[x]) for x in Staff().__dict__.keys() if not x.startswith('_')])
        if ('login_id' in parameter) or ('login_pw' in parameter):
            edit_staff.is_login = False
            edit_staff.dt_login = datetime.datetime.now()
            edit_staff.save()
        edit_staff.save()
    #
    # 영항 받는 곳 update : Customer, Work_Place, Work - name, pNo, email
    #
    customers = Customer.objects.filter(staff_id=edit_staff.id)
    for customer in customers:
        if 'name' in parameter:
            customer.staff_name = parameter['name']
        if 'pNo' in parameter:
            customer.staff_pNo = parameter['pNo']
        if 'email' in parameter:
            customer.staff_email = parameter['email']
        logSend('--- 파견업체: {}, 담당자: {} {} {}'.format(customer.corp_name, customer.staff_name, customer.staff_pNo,
                                                     customer.staff_email))
        customer.save()

    customers = Customer.objects.filter(manager_id=edit_staff.id)
    for customer in customers:
        if 'name' in parameter:
            customer.manager_name = parameter['name']
        if 'pNo' in parameter:
            customer.manager_pNo = parameter['pNo']
        if 'email' in parameter:
            customer.manager_email = parameter['email']
        logSend('--- 파견업체: {}, 관리자: {} {} {}'.format(customer.corp_name, customer.manager_name, customer.manager_pNo,
                                                     customer.manager_email))
        customer.save()

    work_places = Work_Place.objects.filter(manager_id=edit_staff.id)
    for work_place in work_places:
        if 'name' in parameter:
            work_place.manager_name = parameter['name']
        if 'pNo' in parameter:
            work_place.manager_pNo = parameter['pNo']
        if 'email' in parameter:
            work_place.manager_email = parameter['email']
        logSend('--- 사업장: {}, 관리자: {} {} {}'.format(work_place.name, work_place.manager_name, work_place.manager_pNo,
                                                    work_place.manager_email))
        work_place.save()

    works = Work.objects.filter(staff_id=edit_staff.id)
    for work in works:
        if 'name' in parameter:
            work.staff_name = parameter['name']
        if 'pNo' in parameter:
            work.staff_pNo = parameter['pNo']
        if 'email' in parameter:
            work.staff_email = parameter['email']
        logSend('--- 업무: {}, 담당자: {} {} {}'.format(work.name, work.staff_name, work.staff_pNo, work.staff_email))
        work.save()

    # id, pw 가 변경되었으면 처리가 끝나고 로그아웃
    if ('login_id' in parameter) or ('login_pw' in parameter):
        del request.session['id']

        return REG_403_FORBIDDEN.to_json_response()

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403
def list_staff(request):
    """
    직원 list 요청
    - 차후 검색어 추가
        주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/list_staff
    GET
    response
        STATUS 200
            {'staffs':[{'id', 'name':'...', 'position':'...', 'department':'...', 'pNo':'...', 'pType':'...', 'email':'...', 'login_id'}, ...]}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    staffs = Staff.objects.filter(co_id=worker.co_id).values('id', 'name', 'position', 'department', 'pNo', 'pType',
                                                             'email', 'login_id')
    arr_staff = []
    for staff in staffs:
        staff['id'] = AES_ENCRYPT_BASE64(str(staff['id']))
        staff['pNo'] = phone_format(staff['pNo'])
        arr_staff.append(staff)

    return REG_200_SUCCESS.to_json_response({'staffs': arr_staff})


@cross_origin_read_allow
@session_is_none_403
def reg_work_place(request):
    """
    사업장 등록
        주)	response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/reg_work_place?name=임창베르디안&manager_id=&order_id=
    POST
        {
            'name':'(주)효성 용연 1공장',	# 이름
            'manager_id':'관리자 id',	# 관리자 id (암호화되어 있음)
            'order_id':'발주사 id',	# 발주사 id (암호화되어 있음)
            'address': 사업장 주소,    # 사업장 주소 - beacon 을 설치할 주소
            'latitude': 위도,         # 사업장의 위도 - beacon 을 설치할 위도 (option)
            'longitude': 경도,        # 사업장의 경도 - beacon 을 설치할 경도 (option)
        }
    response
        STATUS 200
        STATUS 409
            {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
        STATUS 416
            {'message': '빈 값은 안 됩니다.'}
            {'message': '숫자로 시작하거나 공백, 특수 문자를 사용하면 안됩니다.'}
            {'message': '3자 이상이어야 합니다.'}
        STATUS 422
            {'message': '사업장 명칭은 최소 4자 이상이어야 합니다.'}
            {'message': '필수 항목(빨간 별)이 비었습니다.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter = is_parameter_ok(rqst, ['name', 'manager_id_!', 'order_id_!'])
    if not parameter['is_ok']:
        return status422(get_api(request), {'message': '필수 항목(빨간 별)이 비었습니다.'})
    name = parameter['parameters']['name']
    manager_id = parameter['parameters']['manager_id']
    order_id = no_only_phone_no(parameter['parameters']['order_id'])

    result = id_ok(name, 3)
    if result is not None:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response(result)
    if 'address' in rqst:
        address = rqst['address']
    if 'latitude' in rqst:
        x = rqst['latitude']
    if 'longitude' in rqst:
        y = rqst['longitude']

    list_work_place = Work_Place.objects.filter(name=name)
    if len(list_work_place) > 0:
        return REG_540_REGISTRATION_FAILED.to_json_response(
            {'message': '같은 이름의 사업장이 있습니다.\n꼭 같은 이름의 사업장이 필요하면\n다른 이름으로 등록 후 이름을 바꾸십시요.'})

    manager = Staff.objects.get(id=manager_id)
    order = Customer.objects.get(id=order_id)
    new_work_place = Work_Place(
        name=name,
        place_name=name,
        contractor_id=worker.co_id,
        contractor_name=worker.co_name,
        manager_id=manager.id,
        manager_name=manager.name,
        manager_pNo=manager.pNo,
        manager_email=manager.email,
        order_id=order.id,
        order_name=order.corp_name
    )
    if 'address' in rqst:
        new_work_place.address = address
    if 'latitude' in rqst:
        new_work_place.x = x
    if 'longitude' in rqst:
        new_work_place.y = y

    new_work_place.save()
    logSend(' new_work_place: {}'.format({key: new_work_place.__dict__[key] for key in new_work_place.__dict__.keys()}))

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403
def update_work_place(request):
    """
    사업장 수정
    - 변경 가능 내용: 사업장 이름, 관리자, 발주사
    - 관리자와 발주사는 선택을 먼저하고 선택된 id 로 변경한다.
    - 값이 비었거나 조회 검색되지 않으면 무시됨
        주)	값이 있는 항목만 수정한다. ('name':'' 이면 사업장 이름을 수정하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/update_work_place?work_place_id=qgf6YHf1z2Fx80DR8o_Lvg&name=&manager_id=&order_id=
    POST
        {
            'work_place_id':'사업장 id' # 수정할 사업장 id (암호화되어 있음)
            'name':'(주)효성 용연 1공장',	# 이름
            'manager_id':'관리자 id',	# 관리자 id (암호화되어 있음)
            'order_id':'발주사 id',	# 발주사 id (암호화되어 있음)
            'address': 사업장 주소,    # 사업장 주소 - beacon 을 설치할 주소
            'latitude': 위도,         # 사업장의 위도 - beacon 을 설치할 위도 (option)
            'longitude': 경도,        # 사업장의 경도 - beacon 을 설치할 경도 (option)
        }
    response
        STATUS 200
            {
             'is_update_manager':is_update_manager,
             'is_update_order':is_update_order,
             'is_update_name':is_update_name
             }
        STATUS 409
            {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
        STATUS 503
            {'message': '사업장을 수정할 권한이 없는 직원입니다.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)
    if 'address' in rqst:
        address = rqst['address']
    if 'latitude' in rqst:
        x = rqst['latitude']
    if 'longitude' in rqst:
        y = rqst['longitude']

    work_place = Work_Place.objects.get(id=AES_DECRYPT_BASE64(rqst['work_place_id']))
    if work_place.contractor_id != worker.co_id:
        logError('ERROR: 발생하면 안되는 에러 - 사업장의 파견사와 직원의 파견사가 틀림', __package__.rsplit('.', 1)[-1], inspect.stack()[0][3])

        return REG_524_HAVE_NO_PERMISSION_TO_MODIFY.to_json_response()

    is_update_manager = False
    if ('manager_id' in rqst) and (len(rqst['manager_id']) > 0):
        managers = Staff.objects.filter(id=AES_DECRYPT_BASE64(rqst['manager_id']))
        if len(managers) == 1:
            manager = managers[0]
            work_place.manager_id = manager.id
            work_place.manager_name = manager.name
            work_place.manager_pNo = manager.pNo
            work_place.manager_email = manager.email
            is_update_manager = True

    is_update_order = False
    if ('order_id' in rqst) and (len(rqst['order_id']) > 0):
        orders = Customer.objects.filter(id=AES_DECRYPT_BASE64(rqst['order_id']))
        if len(orders) == 1:
            order = orders[0]
            work_place.order_id = order.id
            work_place.order_name = order.corp_name
            is_update_order = True

    is_update_name = False
    if ('name' in rqst) and (len(rqst['name']) > 0):
        name = rqst['name']
        work_place.name = name
        work_place.place_name = name
        is_update_name = True
    is_update_address = False
    if 'address' in rqst:
        work_place.address = address
        is_update_address = True
    if 'latitude' in rqst:
        work_place.x = x
        is_update_address = True
    if 'longitude' in rqst:
        work_place.y = y
        is_update_address = True
    #
    # 영항 받는 곳 update : Work
    #
    if ('name' in rqst) and (len(rqst['name']) > 0):
        works = Work.objects.filter(work_place_id=work_place.id)
        for work in works:
            work.work_place_name = rqst['name']
            work.save()
    # beacon 처리가 들어가야 한다.

    work_place.save()

    return REG_200_SUCCESS.to_json_response({'is_update_manager': is_update_manager,
                                             'is_update_order': is_update_order,
                                             'is_update_name': is_update_name,
                                             'is_update_address': is_update_address,
                                             })


@cross_origin_read_allow
@session_is_none_403
def list_work_place(request):
    """
    사업장 목록
    - 빈 값이어도 키는 있어야 한다.
    - 파라미터는 검색에 사용됨으로 "" (빈 문자) 를 사용하고 null 를 사용하지 않는다.
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/list_work_place?name=&manager_name=종기&manager_phone=3555&order_name=대덕
    GET
        name          = (주)효성 용연 1공장	# 이름
        manager_name  = 선호			    # 관리자 이름
        manager_phone = 3832	 	    # 관리자 전화번호
        order_name    = 효성			    # 발주사 이름
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "work_places": [
                {
                  "id": "qgf6YHf1z2Fx80DR8o_Lvg",
                  "name": "대덕테크",
                  "contractor_name": "대덕테크",
                  "place_name": "대덕테크",
                  "manager_id": "qgf6YHf1z2Fx80DR8o_Lvg",
                  "manager_name": "박종기",
                  "manager_pNo": "01025573555",
                  "manager_email": "thinking@ddtechi.com",
                  "order_id": "qgf6YHf1z2Fx80DR8o_Lvg",
                  "order_name": "대덕테크"
                },
                {
                  "id": "ryWQkNtiHgkUaY_SZ1o2uA",
                  "name": "임창베르디안",
                  "contractor_name": "대덕테크",
                  "place_name": "임창베르디안",
                  "manager_id": "qgf6YHf1z2Fx80DR8o_Lvg",
                  "manager_name": "박종기",
                  "manager_pNo": "01025573555",
                  "manager_email": "thinking@ddtechi.com",
                  "order_id": "qgf6YHf1z2Fx80DR8o_Lvg",
                  "order_name": "대덕테크"
                }
              ]
            }
        STATUS 503
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    name = rqst['name']
    manager_name = rqst['manager_name']
    manager_phone = no_only_phone_no(rqst['manager_phone'])
    order_name = rqst['order_name']
    work_places = Work_Place.objects.filter(contractor_id=worker.co_id,
                                            name__contains=name,
                                            manager_name__contains=manager_name,
                                            manager_pNo__contains=manager_phone,
                                            order_name__contains=order_name).values('id',
                                                                                    'name',
                                                                                    'contractor_name',
                                                                                    'place_name',
                                                                                    'manager_id',
                                                                                    'manager_name',
                                                                                    'manager_pNo',
                                                                                    'manager_email',
                                                                                    'order_id',
                                                                                    'order_name')

    arr_work_place = []
    for work_place in work_places:
        work_place['id'] = AES_ENCRYPT_BASE64(str(work_place['id']))
        work_place['manager_id'] = AES_ENCRYPT_BASE64(str(work_place['manager_id']))
        work_place['order_id'] = AES_ENCRYPT_BASE64(str(work_place['order_id']))
        work_place['manager_pNo'] = phone_format(work_place['manager_pNo'])
        arr_work_place.append(work_place)
    result = {'work_places': arr_work_place}

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def reg_work(request):
    """
    사업장 업무 등록
        주)	response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/reg_work?name=비콘교체&work_place_id=1&type=3교대&dt_begin=2019-01-29&dt_end=2019-01-31&staff_id=1
    POST
        {
            'name':         '포장',                  # 생산, 포장, 경비, 미화 등
            'work_place_id':'암호화된 사업장 id',
            'type':         '업무 형태',              # 3교대, 주간, 야간, 2교대 등 (매번 입력하는 걸로)
            'dt_begin':     '2019-01-28',           # 업무 시작 날짜
            'dt_end':       '2019-02-28',           # 업무 종료 날짜
            'staff_id':     '암호화된 현장 소장 id',
            'partner_id':   '암호화된 협력업체 id'
        }
    response
        STATUS 200
        STATUS 409
            {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
        STATUS 416
            {'message': '빈 값은 안 됩니다.'}
            {'message': '숫자로 시작하거나 공백, 특수 문자를 사용하면 안됩니다.'}
            {'message': '3자 이상이어야 합니다.'}
            {'message': '업무 시작 날짜는 오늘 이후여야 합니다.'}
            {'message': '업무 시작 날짜보다 업무 종료 날짜가 더 빠릅니다.'}
        STATUS 544
            {'message': '등록된 업무입니다.\n업무명, 근무형태, 사업장, 담당자, 파견사 가 같으면 등록할 수 없습니다.'}
        STATUS 422
            {'message': '사업장 명칭은 최소 4자 이상이어야 합니다.'}
            {'message': '필수 항목(빨간 별)이 비었습니다.'}
        STATUS 422 # 개발자 수정사항
            {'message': 'ClientError: parameter \'name\' 가 없어요'}
            {'message': 'ClientError: parameter \'work_place_id_\' 가 없어요'}
            {'message': 'ClientError: parameter \'type\' 가 없어요'}
            {'message': 'ClientError: parameter \'dt_begin\' 가 없어요'}
            {'message': 'ClientError: parameter \'dt_begin\' 가 없어요'}
            {'message': 'ClientError: parameter \'dt_end\' 가 없어요'}
            {'message': 'ClientError: parameter \'staff_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'partner_id\' 가 없어요'}

            {'message': 'ClientError: parameter \'work_place_id_\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'staff_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'partner_id\' 가 정상적인 값이 아니예요.'}

            {'message': 'ServerError: Work 에 work_id 이(가) 없거나 중복됨'}

    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter_check = is_parameter_ok(rqst, ['name', 'work_place_id_!', 'type', 'dt_begin', 'dt_end', 'staff_id_!',
                                             'partner_id_!_@'])
    if not parameter_check['is_ok']:
        logSend(get_api(request), {'message': '{}'.format([msg for msg in parameter_check['results']])})
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '필수 항목(빨간 별)이 비었습니다.'})
    name = parameter_check['parameters']['name']
    work_place_id = parameter_check['parameters']['work_place_id']
    type = parameter_check['parameters']['type']
    dt_begin = str_to_datetime(parameter_check['parameters']['dt_begin'])
    dt_end = str_to_datetime(parameter_check['parameters']['dt_end'])
    staff_id = parameter_check['parameters']['staff_id']
    partner_id = parameter_check['parameters']['partner_id']
    if partner_id is None:
        # 협력사가 없이 들어오면 default: 작업자의 회사 id 를 쓴다.
        partner_id = worker.co_id

    result = id_ok(name, 2)
    if result is not None:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '\"업무\"가 {}'.format(result['message'])})
    result = type_ok(type, 2)
    if result is not None:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '\"근무 형태\"가 {}'.format(result['message'])})

    if dt_begin < datetime.datetime.now():
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무 시작 날짜는 오늘 이후여야 합니다.'})
    if dt_end < dt_begin:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무 시작 날짜보다 업무 종료 날짜가 더 빠릅니다.'})

    works = Work.objects.filter(name=name,
                                type=type,
                                work_place_id=work_place_id,
                                staff_id=staff_id,
                                contractor_id=partner_id,
                                )
    for work in works:
        logSend('  existed: {}'.format({x: work.__dict__[x] for x in work.__dict__.keys()}))
    if len(works) > 0:
        return REG_544_EXISTED.to_json_response({'message': '등록된 업무입니다.\n업무명, 근무형태, 사업장, 담당자, 파견사 가 같으면 등록할 수 없습니다.'})

    work_place = Work_Place.objects.get(id=work_place_id)
    staff = Staff.objects.get(id=staff_id)
    contractor = Customer.objects.get(id=partner_id)
    new_work = Work(
        name=name,
        work_place_id=work_place.id,
        work_place_name=work_place.name,
        type=type,
        contractor_id=contractor.id,
        contractor_name=contractor.corp_name,
        dt_begin=dt_begin,  # datetime.datetime.strptime(rqst['dt_begin'], "%Y-%m-%d"),
        dt_end=dt_end,  # datetime.datetime.strptime(rqst['dt_end'], "%Y-%m-%d"),
        staff_id=staff.id,
        staff_name=staff.name,
        staff_pNo=staff.pNo,
        staff_email=staff.email,
    )
    new_work.save()

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403
def update_work(request):
    """
    사업장 업무 수정
    - 업무 항목은 지울 수 없기 때문에 blank("")가 오면 수정하지 않는다.
    - key (예: name) 가 없으면 수정하지 않는다.
    - 사업장의 각 업무는 기간이 지나면 다시 등록해서 사용해야 한다.
        주)	값이 있는 항목만 수정한다. ('name':'' 이면 사업장 이름을 수정하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/update_work?work_id=1&name=비콘교체&work_place_id=1&type=3교대&contractor_id=1&dt_begin=2019-01-21&dt_end=2019-01-26&staff_id=2
    POST
        {
            'work_id':      '암호화된 업무 id',
            'name':         '포장',
            'work_place_id':'암호화된 사업장 id',
            'type':         '업무 형태',
            'dt_begin':     '2019-01-28',           # 업무 시작 날짜
            'dt_end':       '2019-02-28',           # 업무 종료 날짜
            'staff_id':     '암호화된 현장 소장 id',
            'partner_id':   '암호화된 협력업체 id'       # 고객사 id 를 기본으로 한다.
        }
    response
        STATUS 200
        STATUS 409
            {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
        STATUS 416
            {'message': '업무 시작 날짜를 오늘 이전으로 변경할 수 없습니다.'})
            {'message': '업무 시작 날짜가 종료 날짜보다 먼저라서 안됩니다.'})
        STATUS 503
            {'message': '사업장을 수정할 권한이 없는 직원입니다.'}
        STATUS 422 # 개발자 수정사항
            {'message': 'ClientError: parameter \'work_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}

            {'message': 'ServerError: Work 에 work_id 이(가) 없거나 중복됨'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter_check = is_parameter_ok(rqst, ['work_id_!'])
    if not parameter_check['is_ok']:
        return status422(get_api(request),
                         {'message': '{}'.format(''.join([message for message in parameter_check['results']]))})
        # return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    work_id = parameter_check['parameters']['work_id']

    works = Work.objects.filter(id=work_id)
    if len(works) == 0:
        logError(get_api(request), ' work id: {} 없음'.format(work_id))
        return status422(get_api(request), {'message': 'ServerError: Work 에 work_id 이(가) 없거나 중복됨'})
    # if work.contractor_id != worker.co_id:
    #     logError('ERROR: 발생하면 안되는 에러 - 사업장의 파견사와 직원의 파견사가 틀림', __package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    # 
    #     return REG_524_HAVE_NO_PERMISSION_TO_MODIFY.to_json_response()
    work = works[0]

    dt_today = datetime.datetime.now()
    is_update_dt_begin = False
    parameter_check = is_parameter_ok(rqst, ['dt_begin'])
    if parameter_check['is_ok']:
        # 업무가 시작되었으면 업무 시작 날짜를 변경할 수 없다. - 업무 시작 날짜가 들어왔더라도 무시한다.
        if dt_today < work.dt_begin:
            work.dt_begin = str_to_datetime(parameter_check['parameters']['dt_begin'])
            if work.dt_begin < dt_today:
                # 업무 시작 날짜를 오늘 이전으로 설정할 수 없다.

                return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무 시작 날짜를 오늘 이전으로 변경할 수 없습니다.'})
            is_update_dt_begin = True
        else:
            if str_to_datetime(parameter_check['parameters']['dt_begin']) != work.dt_begin:
                return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무가 시작되면 시작 날짜를 변경할 수 없습니다.'})

    is_update_dt_end = False
    parameter_check = is_parameter_ok(rqst, ['dt_end'])
    if parameter_check['is_ok']:
        work.dt_end = str_to_datetime(parameter_check['parameters']['dt_end'])
        is_update_dt_end = True
    if work.dt_end < work.dt_begin:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무 시작 날짜가 종료 날짜보다 먼저라서 안됩니다.'})
    #
    # 근로자 시간 변경
    #
    update_employee_pNo_list = []
    if is_update_dt_begin or is_update_dt_end:
        employees = Employee.objects.filter(work_id=work.id)
        logSend('  - employees = {}'.format([employee.pNo for employee in employees]))
        for employee in employees:
            is_update_employee = False
            if employee.dt_begin < work.dt_begin:
                # 근로자의 업무 시작 날짜가 업무 시작 날짜 보다 빠르면 업무 시작 날짜로 바꾼다.
                employee.dt_begin = work.dt_begin
                is_update_employee = True
                update_employee_pNo_list.append(employee.pNo)
            if work.dt_end < employee.dt_end:
                # 근로자의 업무 종료 날짜가 업무 종료 날짜 보다 느리면 업무 종료 날짜로 바꾼다.
                employee.dt_end = work.dt_end
                is_update_employee = True
                update_employee_pNo_list.append(employee.pNo)
            if is_update_employee:
                employee.save()

    is_update_name = False
    parameter_check = is_parameter_ok(rqst, ['name'])
    if parameter_check['is_ok']:
        work.name = parameter_check['parameters']['name']
        is_update_name = True

    is_update_type = False
    parameter_check = is_parameter_ok(rqst, ['type'])
    if parameter_check['is_ok']:
        work.type = parameter_check['parameters']['type']
        is_update_type = True

    # 업무의 사업장이 변경되었을 때 처리
    is_update_work_place = False
    parameter_check = is_parameter_ok(rqst, ['work_place_id_!'])
    if parameter_check['is_ok']:
        work_place_id = parameter_check['parameters']['work_place_id']
        work_places = Work_Place.objects.filter(id=work_place_id)
        if len(work_places) > 0:
            work_place = work_places[0]
            work.work_place_id = work_place.id
            work.work_place_name = work_place.name
            is_update_work_place = True
    elif parameter_check['is_decryption_error']:
        logError(get_api(request), parameter_check['results'])

        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '이 메세지를 보시면 로그아웃 하십시요.'})

    # 파견업체가 변경되었을 때 처리
    is_update_partner = False
    parameter_check = is_parameter_ok(rqst, ['partner_id_!'])
    if parameter_check['is_ok']:
        partner_id = parameter_check['parameters']['partner_id']
        partners = Customer.objects.filter(id=partner_id)
        if len(partners) > 0:
            partner = partners[0]
            work.contractor_id = partner.id
            work.contractor_name = partner.corp_name
            is_update_partner = True
    elif parameter_check['is_decryption_error']:
        logError(get_api(request), parameter_check['results'])

        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '이 메세지를 보시면 로그아웃 하십시요.'})

    # 업무 담당자가 바뀌었을 때 처리
    is_update_staff = False
    parameter_check = is_parameter_ok(rqst, ['staff_id_!'])
    if parameter_check['is_ok']:
        staff_id = parameter_check['parameters']['staff_id']
        staffs = Staff.objects.filter(id=staff_id)
        if len(staffs) > 0:
            staff = staffs[0]
            work.staff_id = staff.id
            work.staff_name = staff.name
            work.staff_pNo = staff.pNo
            work.staff_email = staff.email
            is_update_staff = True
    elif parameter_check['is_decryption_error']:
        logError(get_api(request), parameter_check['results'])

        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '이 메세지를 보시면 로그아웃 하십시요.'})

    if is_update_dt_begin or is_update_dt_end or is_update_name or is_update_type or is_update_work_place or is_update_partner or is_update_staff:
        work.save()

    is_update_employee = False
    if len(update_employee_pNo_list) > 0:
        update_employee_work_infor = {
            'customer_work_id': work.id,
            'dt_begin_employee': work.dt_begin.strftime('%Y/%m/%d'),
            'dt_end_employee': work.dt_end.strftime('%Y/%m/%d'),
            'update_employee_pNo_list': update_employee_pNo_list,
        }
        r = requests.post(settings.EMPLOYEE_URL + 'update_work_for_customer', json=update_employee_work_infor)
        logSend({'url': r.url, 'POST': update_employee_work_infor, 'STATUS': r.status_code, 'R': r.json()})
        is_update_employee = True if r.status_code == 200 else False

    return REG_200_SUCCESS.to_json_response({'is_update_type': is_update_type,
                                             'is_update_dt_begin': is_update_dt_begin,
                                             'is_update_dt_end': is_update_dt_end,
                                             'is_update_work_place': is_update_work_place,
                                             'is_update_partner': is_update_partner,
                                             'is_update_staff': is_update_staff,
                                             'is_update_name': is_update_name,
                                             'is_update_employee': is_update_employee
                                             })


@cross_origin_read_allow
@session_is_none_403
def list_work_from_work_place(request):
    """
    사업장에 소속된 업무 목록
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/list_work_from_work_place?work_place_id=qgf6YHf1z2Fx80DR8o_Lvg
    GET
        work_place_id   = cipher 사업장 id
        is_active       = YES(1), NO(0) default is NO (호환성을 위해 있어도 되고 없으면 0 으로 처리)
        dt_begin        = 과거 업무를 찾을 때 (optional) 2019/2/20 미구현
        dt_end          = 과거 업무를 찾을 때 (optional)
    response
        STATUS 200
            {
             	"works":
             	[
             		{
             		    "id": 1,
             		    "name": "\ube44\ucf58\uad50\uccb4",
             		    "work_place_id": 1,
             		    "work_place_name": "\ub300\ub355\ud14c\ud06c",
             		    "type": "3\uad50\ub300",
             		    "contractor_id": 1,
             		    "contractor_name": "\ub300\ub355\ud14c\ud06c",
             		    "dt_begin": "2019-01-21 00:00:00",
             		    "dt_end": "2019-01-26 00:00:00",
             		    "staff_id": 2,
             		    "staff_name": "\uc774\uc694\uc149",
             		    "staff_pNo": "01024505942",
             		    "staff_email": "hello@ddtechi.com"
             		},
             		......
             	]
            }
        STATUS 503
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    work_place_id = rqst['work_place_id']
    # if ('dt_begin' in rqst) and ('dt_end' in rqst):
    #     # 추후에 작업
    # if len(str_dt_begin) == 0:
    #     dt_begin = datetime.datetime.now() - timedelta(days=365)
    # else:
    #     dt_begin = datetime.datetime.strptime(str_dt_begin, '%Y-%m-%d')
    # print(dt_begin)
    # str_dt_end = rqst['dt_end']
    # if len(str_dt_end) == 0:
    #     dt_end = datetime.datetime.now() + timedelta(days=365)
    # else:
    #     dt_end = datetime.datetime.strptime(str_dt_end, '%Y-%m-%d')
    # print(dt_end)
    if 'is_active' in rqst and rqst['is_active'] is '1':
        dt_today = datetime.datetime.now()
        works = Work.objects.filter(work_place_id=AES_DECRYPT_BASE64(work_place_id),
                                    dt_end__gte=dt_today,
                                    ).values('id',
                                             'name',
                                             'work_place_id',
                                             'work_place_name',
                                             'type',
                                             'contractor_id',
                                             'contractor_name',
                                             'dt_begin',
                                             'dt_end',
                                             'staff_id',
                                             'staff_name',
                                             'staff_pNo',
                                             'staff_email')
    else:
        works = Work.objects.filter(work_place_id=AES_DECRYPT_BASE64(work_place_id)).values('id',
                                                                                            'name',
                                                                                            'work_place_id',
                                                                                            'work_place_name',
                                                                                            'type',
                                                                                            'contractor_id',
                                                                                            'contractor_name',
                                                                                            'dt_begin',
                                                                                            'dt_end',
                                                                                            'staff_id',
                                                                                            'staff_name',
                                                                                            'staff_pNo',
                                                                                            'staff_email')
    arr_work = []
    for work in works:
        work['id'] = AES_ENCRYPT_BASE64(str(work['id']))
        work['work_place_id'] = AES_ENCRYPT_BASE64(str(work['work_place_id']))
        work['contractor_id'] = AES_ENCRYPT_BASE64(str(work['contractor_id']))
        work['staff_id'] = AES_ENCRYPT_BASE64(str(work['staff_id']))
        work['dt_begin'] = work['dt_begin'].strftime('%Y-%m-%d')
        work['dt_end'] = work['dt_end'].strftime('%Y-%m-%d')
        work['staff_pNo'] = phone_format(work['staff_pNo'])
        arr_work.append(work)
    result = {'works': arr_work}

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def list_work(request):
    """
    사업장 업무 목록
    - 검색 값은 없으면 blank ("")로 보낸다.
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/list_work?name=&manager_name=종기&manager_phone=3555&order_name=대덕
    GET
        name            = 업무 이름
        work_place_name = 사업장 이름
        type            = 업무 형태
        contractor_name = 파견(도급)업체 or 협력업체 이름
        staff_name      = 담당자 이름	    # 담당자가 관리하는 현장 업무를 볼때
        staff_pNo       = 담당자 전화번호   # 담당자가 관리하는 현장 업무를 볼때
        dt_begin        = 해당 날짜에 이후에 시작하는 업무 # 없으면 1년 전부터
        dt_end          = 해당 날짜에 이전에 끝나는 업무  #  없으면 1년 후까지
    response
        STATUS 200
            {
             	"works":
             	[
             		{
             		    "id": 1,
             		    "name": "\ube44\ucf58\uad50\uccb4",
             		    "work_place_id": 1,
             		    "work_place_name": "\ub300\ub355\ud14c\ud06c",
             		    "type": "3\uad50\ub300",
             		    "contractor_id": 1,
             		    "contractor_name": "\ub300\ub355\ud14c\ud06c",
             		    "dt_begin": "2019-01-21 00:00:00",
             		    "dt_end": "2019-01-26 00:00:00",
             		    "staff_id": 2,
             		    "staff_name": "\uc774\uc694\uc149",
             		    "staff_pNo": "01024505942",
             		    "staff_email": "hello@ddtechi.com"
             		},
             		......
             	]
            }
        STATUS 503
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    name = rqst['name']
    work_place_name = rqst['work_place_name']
    type = rqst['type']
    contractor_name = rqst['contractor_name']
    staff_name = rqst['staff_name']
    staff_pNo = no_only_phone_no(rqst['staff_pNo'])
    str_dt_begin = rqst['dt_begin']
    if len(str_dt_begin) == 0:
        dt_begin = datetime.datetime.now() - timedelta(days=365)
    else:
        dt_begin = datetime.datetime.strptime(str_dt_begin, '%Y-%m-%d')
    logSend('  이날짜 이후 업무'.format(dt_begin))
    str_dt_end = rqst['dt_end']
    if len(str_dt_end) == 0:
        dt_end = datetime.datetime.now() + timedelta(days=365)
    else:
        dt_end = datetime.datetime.strptime(str_dt_end, '%Y-%m-%d')
    logSend('  이날짜 까지 업무'.format(dt_end))
    works = Work.objects.filter(name__contains=name,
                                work_place_name__contains=work_place_name,
                                type__contains=type,
                                contractor_name__contains=contractor_name,
                                staff_name__contains=staff_name,
                                staff_pNo__contains=staff_pNo,
                                dt_begin__gt=dt_begin,
                                dt_end__lt=dt_end).values('id',
                                                          'name',
                                                          'work_place_id',
                                                          'work_place_name',
                                                          'type',
                                                          'contractor_id',
                                                          'contractor_name',
                                                          'dt_begin',
                                                          'dt_end',
                                                          'staff_id',
                                                          'staff_name',
                                                          'staff_pNo',
                                                          'staff_email')
    arr_work = []
    for work in works:
        work['id'] = AES_ENCRYPT_BASE64(str(work['id']))
        work['work_place_id'] = AES_ENCRYPT_BASE64(str(work['work_place_id']))
        work['contractor_id'] = AES_ENCRYPT_BASE64(str(work['contractor_id']))
        work['staff_id'] = AES_ENCRYPT_BASE64(str(work['staff_id']))
        work['dt_begin'] = work['dt_begin'].strftime('%Y-%m-%d')
        work['dt_end'] = work['dt_end'].strftime('%Y-%m-%d')
        work['staff_pNo'] = phone_format(work['staff_pNo'])
        arr_work.append(work)
    result = {'works': arr_work}

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def reg_work_v2(request):
    """
    새업무 등록 V2
    - 새업무를 등록한다.
    ? 필수항목 처리
        주)	response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/reg_work_v2
    POST
        {
            'name':             '포장',               # 생산, 포장, 경비, 미화 등
            'work_place_id':    '암호화된 사업장 id',
            'type':             '업무 형태',            # 3교대, 주간, 야간, 2교대 등 (매번 입력하는 걸로)
            'dt_begin':         '2019-01-28',       # 업무 시작 날짜
            'dt_end':           '2019-02-28',       # 업무 종료 날짜
            'staff_id':         '암호화된 현장 소장 id',
            'partner_id':       '암호화된 협력업체 id',

            # 신규 추가 사항
            'time_type':        0,          # 급여형태 0:시급제, 1: 월급제, 2: 교대제, 3: 감시단속직 (급여 계산)
            'week_hours':       40,         # 시간/주 (소정근로시간)
            'month_hours':      209,        # 시간/월 (소정근로시간)
            'working_days':     [1, 2, 4, 5] # 0:일, 1: 월, 2: 화, ... 6: 통)
            'paid_day':         -1,         # 유급휴일 (-1: 수동지정, 0: 일, 1: 월, … 6: 토) 주휴일
            'paid_day':         -1,         # 유급휴일 (-1: 수동지정, 0: 일, 1: 월, … 6: 토) 주휴일
            'is_holiday_work': 1,           # 무급휴일을 휴일근무로 시간계산 하나? 1: 휴무일(휴일 근무), 0: 휴일(연장 근무)
            'work_time_list':               # 근무시간
                [
                    {
                        't_begin': '09:00',  # 근무 시작 시간
                        't_end': '21:00',  # 근무 종료 시간
                        'break_time_type': 0,  # 휴게시간 구분 (0: list, 1: total, 2: none)
                        'beak_time_list':  # 휴게시간이 0 일 때만
                            [
                                {
                                    'bt_begin': '12:00',  # 휴게시간 시작
                                    'bt_end': '13:00'  # 휴게시간 종료
                                },
                                {
                                    'bt_begin': '18:00',  # 휴게시간 시작
                                    'bt_end': '19:00',  # 휴게시간 종
                                }
                            ],
                        'break_time_total': '01:30',  # 휴게시간이 1 일 때만
                    }
                ]
        }
    response
        STATUS 200
        STATUS 409
            {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
        STATUS 416
            {'message': '필수 항목(빨간 별)이 비었습니다.'}
            {'message': '빈 값은 안 됩니다.'}
            {'message': '숫자로 시작하거나 공백, 특수 문자를 사용하면 안됩니다.'}
            {'message': '3자 이상이어야 합니다.'}
            {'message': '업무 시작 날짜는 오늘 이후여야 합니다.'}
            {'message': '업무 시작 날짜보다 업무 종료 날짜가 더 빠릅니다.'}
            {'message': '사업장 id, 관리자 id, 협력사 id 가 잘못되었어요.'}
            {'message': '휴게 시작시간이 출근시간보다 빠르면 안됩니다.'}
            {'message': '휴게 종료시간이 퇴근시간보다 늦으면 안됩니다.'}
        STATUS 544
            {'message': '등록된 업무입니다.\n업무명, 근무형태, 사업장, 담당자, 파견사 가 같으면서 기간이 중복되면 등록할 수 없습니다.'}
        STATUS 422 # 개발자 수정사항
            {'message': 'ClientError: parameter \'name\' 가 없어요'}
            {'message': 'ClientError: parameter \'work_place_id_\' 가 없어요'}
            {'message': 'ClientError: parameter \'type\' 가 없어요'}
            {'message': 'ClientError: parameter \'dt_begin\' 가 없어요'}
            {'message': 'ClientError: parameter \'dt_begin\' 가 없어요'}
            {'message': 'ClientError: parameter \'dt_end\' 가 없어요'}
            {'message': 'ClientError: parameter \'staff_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'partner_id\' 가 없어요'}

            {'message': 'ClientError: parameter \'work_place_id_\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'staff_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'partner_id\' 가 정상적인 값이 아니예요.'}

            {'message': 'ServerError: Work 에 work_id 이(가) 없거나 중복됨'}

            {'message': '근무시간에 출근시간이 없다.'}
            {'message': '근무시간에 퇴근시간이 없다.'}
            {'message': '휴게시간 방식이 없다.'}
            {'message': '휴게시간에 시작시간이 없다.'}
            {'message': '휴게시간에 종료시간이 없다.'}
            {'message': '휴게시간이 시간지정인데 지정시간 리스트가 없다.'}
            {'message': '휴게시간이 총 휴게시간인데 휴게시간이 없다.'}
            {'message': '근무시간에 휴게시간 구분이 범위를 넘었다.'}
            {'message': '근무시간에 휴게시간 방식이 범위를 넘었다.'}

            {'message': '(시급제, 월급제)에 [소정근로일](working_days)이 없어요.'}
            {'message': '(시급제, 월급제)에 [유급휴일](paid_day)이 없어요.'}
            {'message': '(시급제, 월급제)에 [무급휴일규정](is_holiday_work)이 없어요.'}
            {'message': '[유급휴일]이 0 ~ 6 사이의 값이 아닙니다.'}
            {'message': '[유급휴일]이 [소정근로일]이면 안됩니다.'}
            {'message': '(교대제)에 [유급휴일](paid_day)이 없어요.'}
            {'message': '(교대제)에 [무급휴일규정](is_holiday_work)이 없어요.'}
            {'message': '[유급휴일]이 -1 ~ 6 사이의 값이 아닙니다.'}
            {'message': '급여형태: {} 가 범위 초과(0 ~ 3)'.format(int(time_type))}
    """
    return update_work_v2(request)


@cross_origin_read_allow
@session_is_none_403
def update_work_v2(request):
    """
    사업장 업무 수정
    - 업무 항목은 지울 수 없기 때문에 blank("")가 오면 수정하지 않는다.
    - key (예: name) 가 없으면 수정하지 않는다.
    - 사업장의 각 업무는 기간이 지나면 다시 등록해서 사용해야 한다.
        주)	값이 있는 항목만 수정한다. ('name':'' 이면 사업장 이름을 수정하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/update_work?work_id=1&name=비콘교체&work_place_id=1&type=3교대&contractor_id=1&dt_begin=2019-01-21&dt_end=2019-01-26&staff_id=2
    POST
        {
            'work_id':      '암호화된 업무 id',
            'name':         '포장',
            'work_place_id':'암호화된 사업장 id',
            'type':         '업무 형태',
            'dt_begin':     '2019-01-28',           # 업무 시작 날짜
            'dt_end':       '2019-02-28',           # 업무 종료 날짜
            'staff_id':     '암호화된 현장 소장 id',
            'partner_id':   '암호화된 협력업체 id'       # 고객사 id 를 기본으로 한다.

            'time_type':        0,          # 급여형태 0:시급제, 1: 월급제, 2: 교대제, 3: 감시단속직 (급여 계산)
            'week_hours':       40,         # 시간/주 (소정근로시간)
            'month_hours':      209,        # 시간/월 (소정근로시간)
            'working_days':     [1, 2, 4, 5] # << [월, 화, 목, 금] 0:일, 1: 월, 2: 화, ... 6: 통)
            'paid_day':         0,          # << 일요일이 유급휴일 (-1: 수동지정, 0: 일, 1: 월, … 6: 토) 주휴일
            'is_holiday_work': 1,           # 무급휴일을 휴일근무로 시간계산 하나? 1: 휴무일(휴일 근무), 0: 휴일(연장 근무)
            'work_time_list':               # 근무시간
                [
                    {
                        't_begin': '09:00',  # 근무 시작 시간
                        't_end': '21:00',  # 근무 종료 시간
                        'break_time_type': 0,  # 휴게시간 구분 (0: list, 1: total, 2: none)
                        'beak_time_list':  # 휴게시간이 0 일 때만
                            [
                                {
                                    'bt_begin': '12:00',  # 휴게시간 시작
                                    'bt_end': '13:00'  # 휴게시간 종료
                                },
                                {
                                    'bt_begin': '18:00',  # 휴게시간 시작
                                    'bt_end': '19:00',  # 휴게시간 종
                                }
                            ],
                        'break_time_total': '01:30',  # 휴게시간이 1 일 때만
                    }
                ]
        }
    response
        STATUS 200
        STATUS 409
            {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
        STATUS 416
            {'message': '업무 시작 날짜를 오늘 이전으로 변경할 수 없습니다.'})
            {'message': '업무 시작 날짜가 종료 날짜보다 먼저라서 안됩니다.'})
            {'message': '필수 항목(빨간 별)이 비었습니다.'}
            {'message': '빈 값은 안 됩니다.'}
            {'message': '숫자로 시작하거나 공백, 특수 문자를 사용하면 안됩니다.'}
            {'message': '3자 이상이어야 합니다.'}
            {'message': '사업장 id, 관리자 id, 협력사 id 가 잘못되었어요.'}
            {'message': '휴게 시작시간이 출근시간보다 빠르면 안됩니다.'}
            {'message': '휴게 종료시간이 퇴근시간보다 늦으면 안됩니다.'}
        STATUS 503
            {'message': '사업장을 수정할 권한이 없는 직원입니다.'}
        STATUS 422 # 개발자 수정사항
            {'message': 'ClientError: parameter \'work_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}

            {'message': 'ClientError: parameter \'name\' 가 없어요'}
            {'message': 'ClientError: parameter \'work_place_id_\' 가 없어요'}
            {'message': 'ClientError: parameter \'type\' 가 없어요'}
            {'message': 'ClientError: parameter \'dt_begin\' 가 없어요'}
            {'message': 'ClientError: parameter \'dt_begin\' 가 없어요'}
            {'message': 'ClientError: parameter \'dt_end\' 가 없어요'}
            {'message': 'ClientError: parameter \'staff_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'partner_id\' 가 없어요'}

            {'message': 'ClientError: parameter \'work_place_id_\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'staff_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'partner_id\' 가 정상적인 값이 아니예요.'}

            {'message': 'ServerError: Work 에 work_id 이(가) 없거나 중복됨'}

            {'message': '근무시간에 출근시간이 없다.'}
            {'message': '근무시간에 퇴근시간이 없다.'}
            {'message': '휴게시간 방식이 없다.'}
            {'message': '휴게시간에 시작시간이 없다.'}
            {'message': '휴게시간에 종료시간이 없다.'}
            {'message': '휴게시간이 시간지정인데 지정시간 리스트가 없다.'}
            {'message': '휴게시간이 총 휴게시간인데 휴게시간이 없다.'}
            {'message': '근무시간에 휴게시간 구분이 범위를 넘었다.'}
            {'message': '근무시간에 휴게시간 방식이 범위를 넘었다.'}

            {'message': '(시급제, 월급제)에 [소정근로일](working_days)이 없어요.'}
            {'message': '(시급제, 월급제)에 [유급휴일](paid_day)이 없어요.'}
            {'message': '(시급제, 월급제)에 [무급휴일규정](is_holiday_work)이 없어요.'}
            {'message': '[유급휴일]이 0 ~ 6 사이의 값이 아닙니다.'}
            {'message': '[유급휴일]이 [소정근로일]이면 안됩니다.'}
            {'message': '(교대제)에 [유급휴일](paid_day)이 없어요.'}
            {'message': '(교대제)에 [무급휴일규정](is_holiday_work)이 없어요.'}
            {'message': '[유급휴일]이 -1 ~ 6 사이의 값이 아닙니다.'}
            {'message': '급여형태: {} 가 범위 초과(0 ~ 3)'.format(int(time_type))}
    """
    logSend('>>> {}'.format(request.path))
    if "update_work_v2" in request.path:
        is_update = True
    else:
        is_update = False

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    if 'work_id' in rqst and rqst['work_id'] is not None:
        parameter_check = is_parameter_ok(rqst, ['work_id_!'])
        if not parameter_check['is_ok']:
            return status422(get_api(request),
                             {'message': '{}'.format(''.join([message for message in parameter_check['results']]))})
            # return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
        work_id = parameter_check['parameters']['work_id']
    else:
        work_id = -1
    logSend('  > is_reg: {}'.format("YES" if work_id == -1 else "NO"))

    parameter_check = is_parameter_ok(rqst, ['name', 'work_place_id_!', 'type', 'dt_begin', 'dt_end', 'staff_id_!',
                                             'partner_id_!_@', 'time_type', 'week_hours', 'month_hours', 'working_days_@',
                                             'paid_day_@', 'is_holiday_work_@', 'work_time_list'])
    if not parameter_check['is_ok']:
        logSend(get_api(request), {'message': '{}'.format([msg for msg in parameter_check['results']])})
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '필수 항목(빨간 별)이 비었습니다.'})
    name = parameter_check['parameters']['name']
    work_place_id = parameter_check['parameters']['work_place_id']
    work_type = parameter_check['parameters']['type']
    dt_begin = str_to_datetime(parameter_check['parameters']['dt_begin'])
    dt_end = str_to_datetime(parameter_check['parameters']['dt_end'])
    dt_end = dt_end + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
    staff_id = parameter_check['parameters']['staff_id']
    partner_id = parameter_check['parameters']['partner_id']
    time_type = parameter_check['parameters']['time_type']
    week_hours = parameter_check['parameters']['week_hours']
    month_hours = parameter_check['parameters']['month_hours']
    working_days = parameter_check['parameters']['working_days']
    paid_day = parameter_check['parameters']['paid_day']
    is_holiday_work = parameter_check['parameters']['is_holiday_work']
    work_time_list = parameter_check['parameters']['work_time_list']

    if partner_id is None:
        # 협력사가 없이 들어오면 default: 작업자의 회사 id 를 쓴다.
        partner_id = worker.co_id

    result = id_ok(name, 2)
    if result is not None:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '\"업무\"가 {}'.format(result['message'])})
    result = type_ok(work_type, 2)
    if result is not None:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '\"근무 형태\"가 {}'.format(result['message'])})

    if not is_update and dt_begin < datetime.datetime.now():
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무 시작 날짜는 오늘 이후여야 합니다.'})
    if dt_end < dt_begin:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무 시작 날짜보다 업무 종료 날짜가 더 빠릅니다.'})

    # 'time_type': 0,  # 0:시급제, 1: 월급제, 2: 교대제, 3: 감시단속직 (급여 계산)
    if not (0 <= int(time_type) <= 3):
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '급여형태: {} 가 범위 초과(0 ~ 3)'.format(int(time_type))})
    if int(time_type) in [0, 1]:
        # 시급제, 월급제일 경우 working_days, paid_day, is_holiday_work 필수
        # paid_day 는 working_days 에 있는 값을 사용할 수 없다.
        if 'working_days' not in rqst:
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '(시급제, 월급제)에 [소정근로일](working_days)이 없어요.'})
        if 'paid_day' not in rqst:
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '(시급제, 월급제)에 [유급휴일](paid_day)이 없어요.'})
        if 'is_holiday_work' not in rqst:
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '(시급제, 월급제)에 [무급휴일규정](is_holiday_work)이 없어요.'})
        if not (0 <= int(paid_day) <= 6):
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '[유급휴일]이 0 ~ 6 사이의 값이 아닙니다.'})
        if int(paid_day) in working_days:
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '[유급휴일]이 [소정근로일]이면 안됩니다.'})
    elif int(time_type) == 2:
        if 'paid_day' not in rqst:
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '(교대제)에 [유급휴일](paid_day)이 없어요.'})
        if 'is_holiday_work' not in rqst:
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '(교대제)에 [무급휴일규정](is_holiday_work)이 없어요.'})
        if not (-1 <= int(paid_day) <= 6):
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '[유급휴일]이 -1 ~ 6 사이의 값이 아닙니다.'})
    elif int(time_type) != 3:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '급여형태: {} 가 범위 초과(0 ~ 3)'.format(int(time_type))})
    # 'is_holiday_work': 1,  # 무급휴일을 휴일근무로 시간계산 하나? 1: 휴무일(휴일 근무), 0: 휴일(연장 근무)
    # {
    #     't_begin': '09:00',  # 근무 시작 시간
    #     't_end': '21:00',  # 근무 종료 시간
    #     'break_time_type': 0,  # 휴게시간 구분 (0: list, 1: total, 2: none)
    #     'beak_time_list':  # 휴게시간이 0 일 때만
    #         [
    #             {
    #                 'bt_begin': '12:00',  # 휴게시간 시작
    #                 'bt_end': '13:00'  # 휴게시간 종료
    #             },
    #             {
    #                 'bt_begin': '18:00',  # 휴게시간 시작
    #                 'bt_end': '19:00',  # 휴게시간 종
    #             }
    #         ],
    #     'break_time_total': '01:30',  # 휴게시간이 1 일 때만
    # }
    for work_time in work_time_list:
        logSend('work_time: {}'.format(work_time))
        if 't_begin' not in work_time:
            logSend(get_api(request), '근무시간에 출근시간이 없다.')
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '근무시간에 출근시간이 없다.'})
        if 't_end' not in work_time:
            logSend(get_api(request), '근무시간에 퇴근시간이 없다.')
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '근무시간에 퇴근시간이 없다.'})
        t_begin = str_minute(work_time['t_begin'])
        t_end = str_minute(work_time['t_end'])
        if t_end <= t_begin:
            t_end += 24 * 60
        logSend('   t_begin: {}, t_end: {}'.format(t_begin, t_end))
        if 'break_time_type' not in work_time:
            logSend(get_api(request), '휴게시간 방식이 없다.')
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '휴게시간 방식이 없다.'})
        int_break_time_type = int(work_time['break_time_type'])
        if int_break_time_type == 0:  # 휴게시간(들)이 정해져 있을 때
            if 'break_time_list' in work_time:
                break_time_sum = 0
                for break_time in work_time['break_time_list']:
                    if 'bt_begin' not in break_time:
                        logSend(get_api(request), '휴게시간에 시작시간이 없다.')
                        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '휴게시간에 시작시간이 없다.'})
                    # 2020/07/16 기능 정지
                    # bt_begin = str_minute(break_time['bt_begin'])
                    # if bt_begin < t_begin:
                    #     return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '휴게 시작시간이 출근시간보다 빠르면 안됩니다.'})
                    if 'bt_end' not in break_time:
                        logSend(get_api(request), '휴게시간에 종료시간이 없다.')
                        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '휴게시간에 종료시간이 없다.'})
                    # 2020/07/16 기능 정지
                    # bt_end = str_minute(break_time['bt_end'])
                    # if bt_end <= bt_begin:
                    #     bt_end += 24 * 60
                    # if bt_end > t_end:
                    #     return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '휴게 종료시간이 퇴근시간보다 늦으면 안됩니다.'})
                    begin = str2min(break_time['bt_begin'])
                    end = str2min(break_time['bt_end'])
                    time = end - begin
                    if end < begin:
                        time = end + (1440 - begin)
                    break_time_sum = time
                work_time['break_time_total'] = '{0:02d}:{1:02d}'.format((break_time_sum // 60), (break_time_sum % 60))
                logSend('   > break_time_total: {}'.format(work_time['break_time_total']))
            else:
                logSend(get_api(request), '휴게시간이 시간지정인데 지정시간 리스트가 없다.')
                return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '휴게시간이 시간지정인데 지정시간 리스트가 없다.'})
        elif int_break_time_type == 1:  # 휴게시간의 총 시간만 정할 때
            if 'break_time_total' not in work_time:
                logSend(get_api(request), '휴게시간이 총 휴게시간인데 휴게시간이 없다.')
                return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '휴게시간이 총 휴게시간인데 휴게시간이 없다.'})
            work_time['break_time_list'] = []
            # else:  #
            #     bt_total = str_minute(work_time['break_time_total'])
            #     if not (0 <= bt_total <= (t_end - t_begin)/8):  # 4시간당 30분의 휴게시간을 주면 24시간 근무해도 8시간을 초과할 수 없다.
            #         logSend(get_api(request), '휴게시간은 8시간을 초과할 수 없다.')
            #         return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '휴게시간은 8시간을 초과할 수 없다.'})
        elif int_break_time_type > 2:  # 휴게시간을 별도 정하지 않았을 때
            logSend(get_api(request), '휴게시간 방식이 범위를 넘었다.')
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '근무시간에 휴게시간 방식이 범위를 넘었다.'})
        else:
            work_time['break_time_list'] = []
            work_time['break_time_total'] = ''
    time_info = {
        'time_type': time_type,
        'work_time_list': work_time_list,
    }
    logSend('   > time_infor: {}'.format(time_info))
    if 'week_hours' in rqst:
        time_info['week_hours'] = week_hours
    if 'month_hours' in rqst:
        time_info['month_hours'] = month_hours
    if int(time_type) is 0:  # 시급제는 월소정근로일을 0으로
        time_info['month_hours'] = 0
    if 'working_days' in rqst:
        time_info['working_days'] = working_days
    if 'paid_day' in rqst:
        time_info['paid_day'] = int(paid_day)
    if 'is_holiday_work' in rqst:
        time_info['is_holiday_work'] = is_holiday_work

    try:
        work_place = Work_Place.objects.get(id=work_place_id)
        staff = Staff.objects.get(id=staff_id)
        contractor = Customer.objects.get(id=partner_id)
    except Exception as e:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '사업장 id, 관리자 id, 협력사 id 가 잘못되었어요.'})

    if work_id == -1:  # 업무를 새로 만들 때
        works = Work.objects.filter(name=name,
                                    type=work_type,
                                    work_place_id=work_place_id,
                                    staff_id=staff_id,
                                    contractor_id=partner_id,
                                    )
        for work in works:
            logSend('  existed: {}'.format({x: work.__dict__[x] for x in work.__dict__.keys()}))
        if len(works) > 0:
            logSend('  new: {} - {}'.format(dt_begin, dt_end))
            for work in works:
                exist_dt_begin = work.dt_begin
                exist_dt_end = work.dt_end
                logSend('  exist: {} - {}'.format(exist_dt_begin, exist_dt_end))
                if ((exist_dt_begin <= dt_begin <= exist_dt_end) or
                    (exist_dt_begin <= dt_end <= exist_dt_end) or
                    (dt_begin <= exist_dt_begin <= dt_end)):
                    return REG_544_EXISTED.to_json_response({'message': '등록된 업무입니다.\n업무명, 근무형태, 사업장, 담당자, 파견사 가 같으면서 기간이 중복되면 등록할 수 없습니다.'})
        new_work = Work(
            name=name,
            work_place_id=work_place.id,
            work_place_name=work_place.name,
            type=work_type,
            contractor_id=contractor.id,
            contractor_name=contractor.corp_name,
            dt_begin=dt_begin,  # datetime.datetime.strptime(rqst['dt_begin'], "%Y-%m-%d"),
            dt_end=dt_end,  # datetime.datetime.strptime(rqst['dt_end'], "%Y-%m-%d"),
            staff_id=staff.id,
            staff_name=staff.name,
            staff_pNo=staff.pNo,
            staff_email=staff.email,
            enable_post=1,
        )
        new_work.set_time_info(time_info)
        new_work.save()
    else:  # 기존 업무를 업데이트 할 때
        try:
            update_work = Work.objects.get(id = work_id)
        except Exception as e:
            return status422(get_api(request), {'message': '업데이트할 업무({}) 찾을 수 없다. ERROR: {}'.format(work_id, e)})
        update_work.name = name
        update_work.work_place_id = work_place_id
        update_work.work_place_name = work_place.name
        update_work.type = work_type
        update_work.contractor_id = contractor.id
        update_work.contractor_name = contractor.corp_name
        update_work.dt_begin = dt_begin
        update_work.dt_end = dt_end
        update_work.staff_id = staff.id
        update_work.staff_name = staff.name
        update_work.staff_pNo = staff.pNo
        update_work.staff_email = staff.email
        update_work.set_time_info(time_info)
        #
        # 근로자 시간 변경
        #
        update_employee_pNo_list = []
        employees = Employee.objects.filter(work_id=update_work.id)
        logSend('  - employees = {}'.format([employee.pNo for employee in employees]))
        for employee in employees:
            is_update_employee = False
            if employee.dt_begin < update_work.dt_begin:
                # 근로자의 업무 시작 날짜가 업무 시작 날짜 보다 빠르면 업무 시작 날짜로 바꾼다.
                employee.dt_begin = update_work.dt_begin
                is_update_employee = True
                update_employee_pNo_list.append(employee.pNo)
            if update_work.dt_end < employee.dt_end:
                # 근로자의 업무 종료 날짜가 업무 종료 날짜 보다 느리면 업무 종료 날짜로 바꾼다.
                employee.dt_end = update_work.dt_end
                is_update_employee = True
                update_employee_pNo_list.append(employee.pNo)
            if is_update_employee:
                employee.save()

        if len(update_employee_pNo_list) > 0:
            update_employee_work_infor = {
                'customer_work_id': update_work.id,
                'dt_begin_employee': update_work.dt_begin.strftime('%Y/%m/%d'),
                'dt_end_employee': update_work.dt_end.strftime('%Y/%m/%d'),
                'update_employee_pNo_list': update_employee_pNo_list,
            }
            r = requests.post(settings.EMPLOYEE_URL + 'update_work_for_customer', json=update_employee_work_infor)
            logSend({'url': r.url, 'POST': update_employee_work_infor, 'STATUS': r.status_code, 'R': r.json()})
            if r.status_code != 200:
                return r

        update_work.save()

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403
def list_work_from_work_place_v2(request):
    """
    사업장에 소속된 업무 목록
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/list_work_from_work_place?work_place_id=qgf6YHf1z2Fx80DR8o_Lvg
    GET
        work_place_id   = cipher 사업장 id (필수 항목
        is_active       = YES(1), NO(0) default is NO (호환성을 위해 있어도 되고 없으면 0 으로 처리)
        dt_begin        = 과거 업무를 찾을 때 (optional) 2019/2/20 미구현
        dt_end          = 과거 업무를 찾을 때 (optional)
    response
        STATUS 200
            {
             	"works":
             	[
             		{
             		    "id": 1,
             		    "name": "\ube44\ucf58\uad50\uccb4",
             		    "work_place_id": 1,
             		    "work_place_name": "\ub300\ub355\ud14c\ud06c",
             		    "type": "3\uad50\ub300",
             		    "contractor_id": 1,
             		    "contractor_name": "\ub300\ub355\ud14c\ud06c",
             		    "dt_begin": "2019-01-21 00:00:00",
             		    "dt_end": "2019-01-26 00:00:00",
             		    "staff_id": 2,
             		    "staff_name": "\uc774\uc694\uc149",
             		    "staff_pNo": "01024505942",
             		    "staff_email": "hello@ddtechi.com"
             		},
             		......
             	]
            }
        STATUS 409
            {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
        STATUS 416
        STATUS 422 # 개발자 수정사항
            {'message': 'ClientError: parameter \'work_place_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'work_place_id\' 가 정상적인 값이 아니예요.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter_check = is_parameter_ok(rqst, ['work_place_id_!', 'is_active_@'])
    if not parameter_check['is_ok']:
        logSend(get_api(request), {'message': '{}'.format([msg for msg in parameter_check['results']])})
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response()
    work_place_id = parameter_check['parameters']['work_place_id']
    is_active = parameter_check['parameters']['is_active']
    if is_active is '1':
        dt_today = datetime.datetime.now()
        works = Work.objects.filter(work_place_id=work_place_id,
                                    dt_end__gte=dt_today,
                                    )
    else:
        works = Work.objects.filter(work_place_id=work_place_id)
    arr_work = []
    for work in works:
        work_dict = work.get_time_info()
        # 기존에 업무 시간 정보가 없으면 여기서 만들어 넣어야 한다.
        # if len(work_dict) == 0:  # 근무정보가 없는 경우
        work_dict['id'] = AES_ENCRYPT_BASE64(str(work.id))
        work_dict['name'] = work.name
        work_dict['work_place_id'] = AES_ENCRYPT_BASE64(str(work.work_place_id))
        work_dict['work_place_name'] = work.work_place_name
        work_dict['type'] = work.type
        work_dict['contractor_id'] = AES_ENCRYPT_BASE64(str(work.contractor_id))
        work_dict['contractor_name'] = work.contractor_name
        work_dict['dt_begin'] = work.dt_begin.strftime('%Y-%m-%d')
        work_dict['dt_end'] = work.dt_end.strftime('%Y-%m-%d')
        work_dict['staff_id'] = AES_ENCRYPT_BASE64(str(work.staff_id))
        work_dict['staff_name'] = work.staff_name
        work_dict['staff_pNo'] = phone_format(work.staff_pNo)
        work_dict['staff_email'] = work.staff_email
        arr_work.append(work_dict)
    result = {'works': arr_work}

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def list_work_v2(request):
    """
    사업장 업무 목록
    - 필터 항목: 사업장 id, 담당자 id, dt_begin, dt_end
    - 검색 값은 없으면 blank ("")로 보낸다.
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/list_work?name=&manager_name=종기&manager_phone=3555&order_name=대덕
    GET
        name            = 업무 이름
        work_place_name = 사업장 이름
        type            = 업무 형태
        contractor_name = 파견(도급)업체 or 협력업체 이름
        staff_name      = 담당자 이름	    # 담당자가 관리하는 현장 업무를 볼때
        staff_pNo       = 담당자 전화번호   # 담당자가 관리하는 현장 업무를 볼때
        dt_begin        = 해당 날짜에 이후에 시작하는 업무 # 없으면 1년 전부터
        dt_end          = 해당 날짜에 이전에 끝나는 업무  #  없으면 1년 후까지
    response
        STATUS 200
            {
             	"works":
             	[
             		{
             		    "id": 1,
             		    "name": "\ube44\ucf58\uad50\uccb4",
             		    "work_place_id": 1,
             		    "work_place_name": "\ub300\ub355\ud14c\ud06c",
             		    "type": "3\uad50\ub300",
             		    "contractor_id": 1,
             		    "contractor_name": "\ub300\ub355\ud14c\ud06c",
             		    "dt_begin": "2019-01-21 00:00:00",
             		    "dt_end": "2019-01-26 00:00:00",
             		    "staff_id": 2,
             		    "staff_name": "\uc774\uc694\uc149",
             		    "staff_pNo": "01024505942",
             		    "staff_email": "hello@ddtechi.com"
             		},
             		......
             	]
            }
        STATUS 503
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    name = rqst['name']
    work_place_name = rqst['work_place_name']
    work_type = rqst['type']
    contractor_name = rqst['contractor_name']
    staff_name = rqst['staff_name']
    staff_pNo = no_only_phone_no(rqst['staff_pNo'])
    str_dt_begin = rqst['dt_begin']
    if len(str_dt_begin) == 0:
        dt_begin = datetime.datetime.now() - timedelta(days=365)
    else:
        dt_begin = datetime.datetime.strptime(str_dt_begin, '%Y-%m-%d')
    logSend('  이날짜 이후 업무'.format(dt_begin))
    str_dt_end = rqst['dt_end']
    if len(str_dt_end) == 0:
        dt_end = datetime.datetime.now() + timedelta(days=365)
    else:
        dt_end = datetime.datetime.strptime(str_dt_end, '%Y-%m-%d')
    logSend('  이날짜 까지 업무'.format(dt_end))
    works = Work.objects.filter(name__contains=name,
                                work_place_name__contains=work_place_name,
                                type__contains=work_type,
                                contractor_name__contains=contractor_name,
                                staff_name__contains=staff_name,
                                staff_pNo__contains=staff_pNo,
                                dt_begin__gt=dt_begin,
                                dt_end__lt=dt_end)
    arr_work = []
    for work in works:
        work_dict = work.get_time_info()
        # 기존에 업무 시간 정보가 없으면 여기서 만들어 넣어야 한다.
        # if len(work_dict) == 0:  # 근무정보가 없는 경우
        work_dict['id'] = AES_ENCRYPT_BASE64(str(work.id))
        work_dict['name'] = work.name
        work_dict['work_place_id'] = AES_ENCRYPT_BASE64(str(work.work_place_id))
        work_dict['work_place_name'] = work.work_place_name
        work_dict['type'] = work.type
        work_dict['contractor_id'] = AES_ENCRYPT_BASE64(str(work.contractor_id))
        work_dict['contractor_name'] = work.contractor_name
        work_dict['dt_begin'] = work.dt_begin.strftime('%Y-%m-%d')
        work_dict['dt_end'] = work.dt_end.strftime('%Y-%m-%d')
        work_dict['staff_id'] = AES_ENCRYPT_BASE64(str(work.staff_id))
        work_dict['staff_name'] = work.staff_name
        work_dict['staff_pNo'] = phone_format(work.staff_pNo)
        work_dict['staff_email'] = work.staff_email
        arr_work.append(work_dict)
    result = {'works': arr_work}

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def work_dict_from_id(request):
    """
    ((근로자 서버)) 업무 id 에 의한 업무 요청
    http://0.0.0.0:8000/customer/work_dict_from_id?work_id_list=1
    GET
        work_id_list    = 업무 id
    response
        STATUS 200
            {
             	"works":
             	[
             		{
             		    "id": 1,
             		    "name": "\ube44\ucf58\uad50\uccb4",
             		    "work_place_id": 1,
             		    "work_place_name": "\ub300\ub355\ud14c\ud06c",
             		    "type": "3\uad50\ub300",
             		    "contractor_id": 1,
             		    "contractor_name": "\ub300\ub355\ud14c\ud06c",
             		    "dt_begin": "2019-01-21 00:00:00",
             		    "dt_end": "2019-01-26 00:00:00",
             		    "staff_id": 2,
             		    "staff_name": "\uc774\uc694\uc149",
             		    "staff_pNo": "01024505942",
             		    "staff_email": "hello@ddtechi.com"
             		},
             		......
             	]
            }
        STATUS 503
    """

    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        logError(get_api(request), ' 허가되지 않은 ip: {}'.format(get_client_ip(request)))
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    if '-1' in rqst['id_list']:
        work_list = Work.objects.all()
    else:
        work_list = Work.objects.filter(id__in=rqst['id_list'])
    # logSend('  > work_list: {}'.format(work_list))
    all_work_dict = {}
    # arr_work = []
    for work in work_list:
        work_dict = {}
        work_dict['time_info'] = work.get_time_info()
        # 기존에 업무 시간 정보가 없으면 여기서 만들어 넣어야 한다.
        # if len(work_dict) == 0:  # 근무정보가 없는 경우
        # work_dict['id'] = work.id
        work_dict['name'] = work.name
        work_dict['type'] = work.type
        work_dict['work_name_type'] = '{} ({})'.format(work.name, work.type)
        # work_dict['work_place_id'] = work.work_place_id
        work_dict['work_place_name'] = work.work_place_name
        # work_dict['contractor_id'] = work.contractor_id
        # work_dict['contractor_name'] = work.contractor_name
        work_dict['dt_begin'] = work.dt_begin.strftime('%Y/%m/%d')
        work_dict['dt_end'] = work.dt_end.strftime('%Y/%m/%d')
        work_dict['dt_begin_full'] = work.dt_begin.strftime('%Y-%m-%d %H:%M:%S')
        work_dict['dt_end_full'] = work.dt_end.strftime('%Y-%m-%d %H:%M:%S')
        # work_dict['staff_id'] = work.staff_id
        work_dict['staff_name'] = work.staff_name
        work_dict['staff_pNo'] = phone_format(work.staff_pNo)
        work_dict['staff_email'] = work.staff_email
        # arr_work.append(work_dict)
        # del work_dict['id']
        all_work_dict[work.id] = work_dict
    # return REG_200_SUCCESS.to_json_response({'work_list': arr_work})
    # logSend('  > work_dict: {}'.format(all_work_dict))
    return REG_200_SUCCESS.to_json_response({'work_dict': all_work_dict})


@cross_origin_read_allow
@session_is_none_403
def reg_employee(request):
    """
    근로자 등록 - 업무 선택 >> 전화번호 목록 입력 >> [등록 SMS 안내 발송]
    - 업무가 시작되고 나서 추가되는 근로자를 등록하기 위해 "출근 날짜" 추가 - 2019/05/25
    - SMS 를 보내지 못한 전화번호는 근로자 등록을 하지 않는다.
    - response 로 확인된 SMS 못보낸 전화번호에 표시해야 하다.
        주)	response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/reg_employee?work_id=4dnQVYFTi501mmdz6hX6CA&dt_answer_deadline=2019-08-06 19:00:00&dt_begin=2019-08-25&phone_numbers=010-2557-3555
    POST
        {
            'work_id':'사업장 업무 id',
            'dt_answer_deadline':2019-03-01 19:00:00  # 업무 수락/거절 답변 시한
            'dt_begin': 2019-05-25  # 등록하는 근로자의 실제 출근 시작 날짜 (업무의 시작 후에 추가되는 근로자를 위한 날짜)
            'phone_numbers':        # 업무에 배치할 근로자들의 전화번호
            [
                '010-3333-5555', '010-5555-7777', '010-7777-8888', ...
            ]
        }
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "duplicate_pNo": [
                "010-2557-3555",
                "010-3333-99999",
                "010-3333-5555",
                "010-5555-7777",
                "010-7777-9999"
              ],
              "bad_pNo": [
                "010999999",
                "010111199",
                "010222299"
                ]
                ,
              "notification": "html message",
            }
        STATUS 416
            {'message': '종료된 업무에는 근로자를 추가할 수 없습니다.'}
            {'message': '근무 시작 날짜는 오늘보다 늦어야 합니다.'}
            {'message': '답변 시한은 근무 시작 날짜보다 빨라야 합니다.'}
            {'message': '답변 시한은 현재 시각보다 빨라야 합니다.'}
            {'message': '근무 시작 날짜는 업무 시작 날짜보다 같거나 늦어야 합니다.'}
            # {'message': '근무 종료 날짜는 업무 종료 날짜보다 먼저이거나 같아야 합니다.'}
            # {'message': '근무 시작 날짜는 업무 종료 날짜보다 빨라야 합니다.'}
        STATUS 409
            {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'work_id\' 가 없어요'}
            {'message':'ClientError: parameter \'dt_answer_deadline\' 가 없어요'}
            {'message':'ClientError: parameter \'dt_begin\' 이 없어요'}
            {'message':'ClientError: parameter \'phone_numbers\' 가 없어요'}
            {'message':'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Work 에 id={} 가 없다'.format(work_id)}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter_check = is_parameter_ok(rqst, ['work_id_!', 'dt_answer_deadline', 'dt_begin', 'phone_numbers'])
    # parameter_check = is_parameter_ok(rqst, ['work_id_!', 'dt_answer_deadline', 'phone_numbers'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

    work_id = parameter_check['parameters']['work_id']
    dt_answer_deadline = str_to_datetime(parameter_check['parameters']['dt_answer_deadline'])
    dt_begin = str_to_datetime(parameter_check['parameters']['dt_begin'])
    phone_numbers = parameter_check['parameters']['phone_numbers']

    work_list = Work.objects.filter(id=work_id)
    if len(work_list) == 0:
        return status422(get_api(request), {'message': 'ServerError: Work 에 id={} 이(가) 없다'.format(work_id)})
    elif len(work_list) > 1:
        logError(get_api(request), ' Work(id:{})가 중복되었다.'.format(work_id))
    work = work_list[0]
    #
    # 업무 종료 검사
    #
    if work.dt_end < datetime.datetime.now():
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '종료된 업무에는 근로자를 추가할 수 없습니다.'})

    if request.method == 'GET':
        phone_numbers = rqst.getlist('phone_numbers')
    # 전화번호에서 숫자 아닌 문자 지우고 중복된 전화번호도 정리한다.
    phones = []
    seen = set()
    for phone_no in phone_numbers:
        pNo = no_only_phone_no(phone_no)
        if len(pNo) < 8:
            continue
        if pNo not in seen and not seen.add(pNo):
            phones.append(pNo)
    logSend('  - 의미 없는 전화번호 필터링 후 phones: {}'.format(phones))
    #
    # 답변시한 검사
    #
    if dt_begin < work.dt_begin:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근무 시작 날짜는 업무 시작 날짜보다 같거나 늦어야 합니다.'})

    logSend('   > settings.DEBUG: {}'.format(settings.DEBUG))
    if not settings.DEBUG:
        if dt_begin < datetime.datetime.now():
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근무 시작 날짜는 오늘보다 늦어야 합니다.'})

        if dt_begin < dt_answer_deadline:
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '답변 시한은 근무 시작 날짜보다 빨라야 합니다.'})

        if dt_answer_deadline < datetime.datetime.now():
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '답변 시한은 현재 시각보다 빨라야 합니다.'})

        if work.dt_end < dt_end:
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근무 종료 날짜는 업무 종료 날짜보다 먼저이거나 같아야 합니다.'})

        if dt_end < dt_begin:
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근무 시작 날짜는 업무 종료 날짜보다 빨라야 합니다.'})
    #
    # 2019/06/17 기존 근로자가 중복되더라도 새로 업무를 부여할 수 있게 중복번호기능을 중지한다.
    #
    # find_employee_list = Employee.objects.filter(work_id=work.id, pNo__in=phones)
    # duplicate_pNo = [employee.pNo for employee in find_employee_list]
    duplicate_pNo = []
    logSend('  - duplicate phones: {}'.format(duplicate_pNo))
    new_phone_list = [phone for phone in phones if phone not in duplicate_pNo]
    logSend('  - real phones: {}'.format(new_phone_list))
    #
    # 근로자 서버로 근로자의 업무 의사와 답변을 요청
    #
    new_employee_data = {"customer_work_id": work.id,
                         "work_place_name": work.work_place_name,
                         "work_name_type": work.name + ' (' + work.type + ')',
                         "dt_begin": dt_str(dt_begin, '%Y/%m/%d'),  # work.dt_begin.strftime('%Y/%m/%d'),
                         "dt_end": work.dt_end.strftime('%Y/%m/%d'),
                         "staff_name": work.staff_name,
                         "staff_phone": work.staff_pNo,
                         "dt_answer_deadline": rqst['dt_answer_deadline'],
                         "dt_begin_employee": dt_begin.strftime('%Y/%m/%d'),  # 근로자별 업무 시작일
                         "dt_end_employee": work.dt_end.strftime('%Y/%m/%d'),  # 근로자별 업무 종료일 (여기서는 업무종료일과 동일)
                         "is_update": False,
                         "time_info": work.get_time_info(),
                         "phones": new_phone_list,
                         }
    # logSend(new_employee_data)
    response_employee = requests.post(settings.EMPLOYEE_URL + 'reg_employee_for_customer', json=new_employee_data)
    # logSend('   >> result: {}'.format(response_employee.json()['result']))
    if response_employee.status_code != 200:
        return ReqLibJsonResponse(response_employee)

    sms_result = response_employee.json()['result']
    # sms_result = {'01033335555': -101, '01055557777': 5}
    bad_phone_list = []
    bad_condition_list = []
    work_count_over_list = []
    feature_phone_list = []
    #
    # 2019/06/17 기존 근로자가 중복되더라도 새로 업무를 부여할 수 있게 중복번호기능을 중지한다.
    #
    find_employee_list = Employee.objects.filter(work_id=work.id, pNo__in=phones)
    duplicate_pNo = [employee.pNo for employee in find_employee_list]
    for phone in new_phone_list:
        if sms_result[phone] < -100:
            # 잘못된 전화번호 근로자 등록 안함
            bad_phone_list.append(phone_format(phone))
        elif sms_result[phone] < -30:
            # 근로자가 받을 수 있는 요청의 갯수가 넘었다.
            work_count_over_list.append(phone_format(phone))
        elif sms_result[phone] < -20:
            # 피쳐폰은 한개 이상의 업무를 받을 수 없다.
            feature_phone_list.append(phone_format(phone))
        elif sms_result[phone] < -10:
            # 다른 업무와 기간이 겹쳤다.
            bad_condition_list.append(phone_format(phone))
        else:
            # 업무 수락을 기다리는 근로자로 등록
            #
            # 2019/06/17 기존 근로자가 중복되더라도 새로 업무를 부여할 수 있게 중복번호기능을 중지한다.
            #
            if phone in duplicate_pNo:
                for find_employee in find_employee_list:
                    if phone == find_employee.pNo:
                        find_employee.is_accept_work = None
                        find_employee.is_active = 0
                        find_employee.dt_begin = dt_begin
                        find_employee.dt_end = work.dt_end
                        find_employee.dt_answer_deadline = dt_answer_deadline
                        find_employee.save()
            else:
                # logSend('  >> 새로운 근로자 등록 : employee_id: {}'.format(sms_result[phone]))
                new_employee = Employee(
                    employee_id=sms_result[phone],
                    is_accept_work=None,  # 아직 근로자가 결정하지 않았다.
                    is_active=0,  # 근무 중 아님
                    dt_begin=dt_begin,
                    dt_end=work.dt_end,
                    work_id=work.id,
                    pNo=phone,
                    dt_answer_deadline=dt_answer_deadline,
                )
                new_employee.save()
    logSend('  - count bad_phone_list: {}, ',
            'work_count_over_list: {}, ',
            'feature_phone_list: {}, bad_condition_list: {}'.format(len(bad_phone_list),
                                                                    len(work_count_over_list),
                                                                    len(feature_phone_list),
                                                                    len(bad_condition_list)))
    #
    # SMS 가 에러나는 전화번호 표시 html
    #
    if len(bad_phone_list) > 0 or len(bad_condition_list) > 0 or len(work_count_over_list) > 0 or len(
            feature_phone_list) > 0:
        notification = '<html><head><meta charset=\"UTF-8\"></head><body>' \
                       '<h3><span style=\"color: #808080;\">등록할 수 없는 전화번호</span></h3>'
        if len(bad_phone_list) > 0:
            notification += '<p style=\"color: #dd0000;\">문자를 보낼 수 없는 전화번호였습니다.</p>' \
                            '<p style=\"text-align: center; padding-left: 30px; color: #808080;\">'
            for bad_phone in bad_phone_list:
                notification += bad_phone + '<br>'
        if len(bad_condition_list) > 0:
            notification += '<br>' \
                            '<p style=\"color: #dd0000;\">다른 업무가 있는 근로자입니다.</p>' \
                            '<p style=\"text-align: center; padding-left: 30px; color: #808080;\">'
            for bad_condition in bad_condition_list:
                notification += bad_condition + '<br>'
        if len(work_count_over_list) > 0:
            notification += '<br>' \
                            '<p style=\"color: #dd0000;\">업무를 받을 수 있는 한계(2개)가 넘은 근로자입니다.</p>' \
                            '<p style=\"text-align: center; padding-left: 30px; color: #808080;\">'
            for work_count_over in work_count_over_list:
                notification += work_count_over + '<br>'
        if len(feature_phone_list) > 0:
            notification += '<br>' \
                            '<p style=\"color: #dd0000;\">업무 요청이 이미 있는 피처 폰 근로자입니다.</p>' \
                            '<p style=\"text-align: center; padding-left: 30px; color: #808080;\">'
            for feature_phone in feature_phone_list:
                notification += feature_phone + '<br>'
        notification += '</p></body></html>'
    else:
        notification = '<html><head><meta charset=\"UTF-8\"></head><body>' \
                       '<h3><span style=\"color: #808080;\">정상적으로 처리되었습니다.</span></h3>' \
                       '</body></html>'

    return REG_200_SUCCESS.to_json_response(
        {'duplicate_pNo': duplicate_pNo, 'bad_pNo': bad_phone_list, 'bad_condition': bad_condition_list,
         'notification': notification})


@cross_origin_read_allow
def employee_work_accept_for_employee(request):
    """
    <<<근로자 서버용>>> 근로자가 업무 수락/거절했을 때 고객서버가 처리할 일
    * 서버 to 서버 통신 work_id 필요
        주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/employee_work_accept_for_employee?worker_id=qgf6YHf1z2Fx80DR8o_Lvg&staff_id=qgf6YHf1z2Fx80DR8o_Lvg
    POST
        {
            'worker_id': 'cipher_id'  # 운영직원 id
            'work_id':'암호화된 work_id',
            'employee_id': employee id  # 근로자 서버의 근로자 id
            'employee_name':employee.name,
            'employee_pNo':01011112222,
            'is_accept':True
        }
    response
        STATUS 200
            {
                'msg': '정상처리되었습니다.',
                'login_id': staff.login_id,
            }
        STATUS 542
            {'message':'업무 요청이 취소되었습니다.'}
        STATUS 422  # 개발자 수정사항
            {'message': '답변시간이 지났습니다.'}
            {'message': 'ClientError: parameter \'worker_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'employee_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'employee_name\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'employee_pNo\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'is_accept\' 가 정상적인 값이 아니예요.'}

            {'message': 'ServerError: Work 에 work_id 이(가) 없거나 중복됨'}
    """
    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        logError(get_api(request), ' 허가되지 않은 ip: {}'.format(get_client_ip(request)))
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst,
                                      ['worker_id_!', 'work_id', 'employee_id_!', 'employee_name', 'employee_pNo',
                                       'is_accept'])
    if not parameter_check['is_ok']:
        return status422(get_api(request),
                         {'message': '{}'.format(''.join([message for message in parameter_check['results']]))})
    worker_id = parameter_check['parameters']['worker_id']
    work_id = parameter_check['parameters']['work_id']
    employee_id = parameter_check['parameters']['employee_id']
    employee_name = parameter_check['parameters']['employee_name']
    employee_pNo = parameter_check['parameters']['employee_pNo']
    is_accept = parameter_check['parameters']['is_accept']

    # 운영 서버에서 호출했을 때 - 운영 스텝의 id를 로그에 저장한다.
    logSend('   from operation server : operation staff id ', worker_id)

    works = Work.objects.filter(id=work_id)
    if len(works) == 0:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '답변시간이 자났습니다.'})
    work = works[0]

    employees = Employee.objects.filter(work_id=work.id, pNo=employee_pNo)
    if len(employees) == 0:
        return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response({'message': '업무 요청이 취소되었습니다.'})

    employee = employees[0]
    if employee.dt_begin < datetime.datetime.now() and not is_accept:
        employee.is_accept_work = 2  # 답변시한 지남
    else:
        employee.is_accept_work = is_accept
    employee.employee_id = employee_id
    employee.name = employee_name
    employee.dt_accept = datetime.datetime.now()
    employee.save()

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def update_employee_for_employee(request):
    """
    <<<근로자 서버용>>> 근로자 수정
    * 서버 to 서버 통신 work_id 필요
        주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/employee_work_accept_for_employee?worker_id=qgf6YHf1z2Fx80DR8o_Lvg&staff_id=qgf6YHf1z2Fx80DR8o_Lvg
    POST
        {
            'worker_id': 'cipher_id'  # 운영직원 id
            'passer_id': 암호화된 id    # 근로자 서버의 출입자 id >> 고객서버의 employee_id
            'name': 홍길동              # <option> 이름이 바뀔 때만 값이 있다.
            'pNo': 01099993333        # <option> 전화번호가 바뀔 때만 값이 있다.
        }
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
    """
    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        logError(get_api(request), ' 허가되지 않은 ip: {}'.format(get_client_ip(request)))
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    #
    # 운영 서버에서 호출했을 때 - 운영 스텝의 id를 로그에 저장?
    #
    worker_id = AES_DECRYPT_BASE64(rqst['worker_id'])
    if worker_id != 'thinking':
        logError(get_api(request), ' worker_id({}) 가 정상이 아니다.'.format(rqst['worker_id']))

    employees = Employee.objects.filter(employee_id=AES_DECRYPT_BASE64(rqst['passer_id']))

    for employee in employees:
        if 'name' in rqst:
            employee.name = rqst['name']
        if 'pNo' in rqst:
            employee.pNo = rqst['pNo']
        employee.save()
    #
    # backup employee data update?
    #
    return REG_200_SUCCESS.to_json_response({'message': '모두 {}개의 업무에서 근로자 이름이나 전화번호가 변경되었습니다.'.format(len(employees))})


@cross_origin_read_allow
@session_is_none_403
def update_employee(request):
    """
    근로자 수정
     - 근로자가 업무를 거절했거나
     - 응답이 없어 업무에서 배제했거나
     - 업무 예정기간보다 일찍 업무가 끝났을 때
        주)	값이 있는 항목만 수정한다. ('name':'' 이면 사업장 이름을 수정하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/update_employee?
    POST
        {
            'work_id': 업무 id,          # 업무 id (암호화된 값)
            'employee_id':'암호화된 id',  # 필수
            'phone_no':'010-3355-7788', # 전화번호가 잘못되었을 때 변경
            'dt_answer_deadline':2019-03-09 19:00:00,
            'dt_begin':2019-03-09,      # 근무 시작일
            'dt_end':2019-03-31,        # 근로자 한명의 업무 종료일을 변경한다. (업무 인원 전체는 업무에서 변경한다.)
            'is_active':'YES',          # YES: 현재 업무 중, NO: 아직 업무 시작되지 않음
            'message':'업무 종료일이 변경되었거나 업무에 대한 응답이 없어 업무에서 뺐을 때 사유 전달'
            'the_zone_code': '201107002'  # 더존 사원 코드
        }
        업무 시작 전 수정일 때: employee_id, phone_no, dt_begin, dt_end
        업무 시작 후 수정일 때: employee_id, dt_end, is_active, message
    response
        STATUS 200
        STATUS 409
            {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
        STATUS 416
            {'message': '근무 시작 날짜는 오늘보다 늦어야 합니다.'}
            {'message': '답변 시한은 근무 시작 날짜보다 빨라야 합니다.'}
            {'message': '답변 시한은 현재 시각보다 빨라야 합니다.'}
            {'message': '근무 시작 날짜는 업무 시작 날짜보다 같거나 늦어야 합니다.'}
            {'message': '근무 종료 날짜는 업무 종료 날짜보다 먼저이거나 같아야 합니다.'}
            {'message': '근무 시작 날짜는 업무 종료 날짜보다 빨라야 합니다.'}
        STATUS 503
            {'message': '사업장을 수정할 권한이 없는 직원입니다.'}
        STATUS 509
            {"msg": "??? matching query does not exist."} # ??? 을 찾을 수 없다. (op_staff_id, work_id 를 찾을 수 없을 때)
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'employee_id\' 가 없어요'}
            {'message':'ClientError: parameter \'phone_no\' 가 없어요'}
            {'message':'ClientError: parameter \'work_id\' 가 없어요'}
            {'message':'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Employee 에 id={} 이(가) 없다'.format(employee_id)}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['work_id_!', 'employee_id_!', 'dt_end'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    work_id = parameter_check['parameters']['work_id']
    employee_id = parameter_check['parameters']['employee_id']
    dt_end = str_to_datetime(parameter_check['parameters']['dt_end'])

    work = Work.objects.get(id=work_id)
    try:
        employee = Employee.objects.get(id=employee_id)
    except Exception as e:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '해당 근로자가 없습니다.'})
    logSend('  employee: {}'.format(
        {key: employee.__dict__[key] for key in employee.__dict__.keys() if not key.startswith('_')}))

    # 업무에 투입되었는가?
    # if 'is_active' in rqst.keys():
    dt_today = datetime.datetime.now()
    if employee.dt_begin < dt_today:
        #
        # 근로자가 업무에 투입되고 난 다음에 예정된 종료일을 변경할 때 사용
        #
        parameter_check = is_parameter_ok(rqst, ['is_active', 'message_@'])
        if not parameter_check['is_ok']:
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
        is_active = parameter_check['parameters']['is_active']
        message = parameter_check['parameters']['message']

        logSend('  employee.dt_end: {}, dt_end: {}'.format(employee.dt_end, dt_end))
        if employee.dt_end < dt_end:
            # 근무 날짜가 늘어났다.
            logSend('--- employee id: {} 근무날짜: {} > {} '.format(employee.id, employee.dt_end, dt_end))
        else:
            # 근무 날짜가 줄어들었다.
            logSend('--- employee id: {} 근무날짜: {} > {} '.format(employee.id, employee.dt_end, dt_end))
        #
        # 근로자 서버로 근로날짜 변경 전달
        #
        employee.dt_end = dt_end
        employee.is_active = False if employee.dt_end < dt_today else True  # 업무 종료일이 오늘 이전이면 업무 종료
        employee.is_active = True if is_active.upper() == 'YES' else False
        if message is not None and len(message) > 0:
            #
            # to employee server : message,
            #
            logSend('message: {} (아직 처리하지 않는다.)'.format(rqst['message']))
        logSend('  employee: {}'.format(
            {key: employee.__dict__[key] for key in employee.__dict__.keys() if not key.startswith('_')}))
        #
        # 근로기간이 변경되었으면 근로자서버를 업데이트한다.
        #
        employees_infor = {
            'employee_id': AES_ENCRYPT_BASE64(str(employee.employee_id)),
            'work_id': work.id,
            'dt_end': dt_end.strftime("%Y/%m/%d"),
        }
        r = requests.post(settings.EMPLOYEE_URL + 'change_work_period_for_customer', json=employees_infor)
        # {'url': r.url, 'POST': employees_infor, 'STATUS': r.status_code, 'R': r.json()}
        if 'the_zone_code' in rqst:
            only_number = no_only_phone_no(rqst['the_zone_code'])
            if len(only_number) > 0:
                employee.the_zone_code = only_number
                logSend('  > the_zone_code: {}'.format(only_number))
        employee.save()

        return REG_200_SUCCESS.to_json_response()
    #
    # 근로자에게 업무 시작일 전에 업무 투입을 요청할 때 사용
    #
    parameter_check = is_parameter_ok(rqst, ['dt_answer_deadline', 'dt_begin'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    # phone_no = parameter_check['parameters']['phone_no']
    dt_answer_deadline = str_to_datetime(parameter_check['parameters']['dt_answer_deadline'])
    dt_begin = str_to_datetime(parameter_check['parameters']['dt_begin'])

    #
    # 답변 시한 검사
    #
    logSend('  - dt_begin: {}, work.dt_begin: {}, work.dt_end: {}, dt_end: {}, dt_answer_deadline: {}'.format(dt_begin,
                                                                                                              work.dt_begin,
                                                                                                              work.dt_end,
                                                                                                              dt_end,
                                                                                                              dt_answer_deadline))
    # if dt_begin < datetime.datetime.now():
    #     return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근무 시작 날짜는 오늘보다 늦어야 합니다.'})

    if dt_begin < dt_answer_deadline:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '답변 시한은 근무 시작 날짜보다 빨라야 합니다.'})

    # if dt_answer_deadline < datetime.datetime.now():
    #     return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '답변 시한은 현재 시각보다 빨라야 합니다.'})

    if dt_begin < work.dt_begin:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근무 시작 날짜는 업무 시작 날짜보다 같거나 늦어야 합니다.'})

    if work.dt_end < dt_end:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근무 종료 날짜는 업무 종료 날짜보다 먼저이거나 같아야 합니다.'})

    if dt_end < dt_begin:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근무 시작 날짜는 업무 종료 날짜보다 빨라야 합니다.'})
    #
    # 업무 시간 변경 확인
    #
    if dt_begin != employee.dt_begin:
        employee.dt_begin = dt_begin
    # 2019.06.27 최진 대표 요청: 업무 시작하지 않은 근로자는 업무 종료시간을 설정할 수 없다.
    # if dt_end != employee.dt_end:
    #     employee.dt_end = dt_end

    if 'phone_no' in rqst and len(rqst['phone_no']) > 0:
        if 'dt_answer_deadline' not in rqst or len(rqst['dt_answer_deadline']) == 0:
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '전화번호를 바꾸려면 업무 답변 기한을 꼭 넣어야 합니다.'})
        employee.pNo = no_only_phone_no(rqst['phone_no'])
        #
        # 근로자 서버로 근로자의 업무 의사와 답변을 요청
        #
        new_employee_data = {"customer_work_id": work.id,
                             "work_place_name": work.work_place_name,
                             "work_name_type": work.name + ' (' + work.type + ')',
                             "dt_begin": work.dt_begin.strftime('%Y/%m/%d'),
                             "dt_end": work.dt_end.strftime('%Y/%m/%d'),
                             "staff_name": work.staff_name,
                             "staff_phone": work.staff_pNo,
                             "dt_answer_deadline": rqst['dt_answer_deadline'],
                             "dt_begin_employee": employee.dt_begin.strftime('%Y/%m/%d'),  # 개별 근로자의 업무 시작날짜
                             "dt_end_employee": employee.dt_end.strftime('%Y/%m/%d'),  # 개별 근로자의 업무 종료날짜
                             "is_update": "1",  # True
                             "phones": [employee.pNo]
                             }
        # print(new_employee_data)
        response_employee = requests.post(settings.EMPLOYEE_URL + 'reg_employee_for_customer', json=new_employee_data)
        logSend('--- ', response_employee.json())
        if response_employee.status_code != 200:
            return ReqLibJsonResponse(response_employee)
        sms_result = response_employee.json()['result']
        if sms_result[employee.pNo] < -100:
            # 잘못된 전화번호 근로자 등록 안함

            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '잘못된 전화번호입니다.'})
        elif sms_result[employee.pNo] < -30:
            # 업무 요청을 많이 받아서 받을 수 없다.

            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '요청받은 업무가 많아서(2개) 더 요청할 수 없습니다.'})
        elif sms_result[employee.pNo] < -20:
            # 다른 업무 때문에 업무 배정이 안되는 근로자 - 근로자 등록 안함

            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '피쳐폰이라서 업무를 하나밖에 받지 못합니다.'})
        elif sms_result[employee.pNo] < -1:
            # 다른 업무 때문에 업무 배정이 안되는 근로자 - 근로자 등록 안함

            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '근로자의 다른 업무와 기간이 겹칩니다.'})
        employee.employee_id = sms_result[employee.pNo]
    # 2019/06/17 고객웹 > 근로자 > 수정: 답변을 초기화 할 때 사용
    employee.is_accept_work = None
    employee.save()

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403
def list_employee(request):
    """
    << 웹 >> 근로자 목록
      - 업무에 투입된별 근로자 리스트
      - 업무 시작날짜 전이면 업무 수락 여부만 보낸다. (날짜가 무시된다.)
      - 날짜가 없으면 오늘 날짜로 처리한다. (날짜가 없어도 에러처리하지 않는다.)
      - option 에 따라 근로자 근태 내역 추가 (2019
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/list_employee?work_id=1&is_working_history=YES
    GET
        work_id         = 업무 id
        dt              = 2019-07-13 (원하는 날짜)
        is_working_history = 업무 형태 # YES: 근태내역 추가, NO: 근태내역 없음(default) 2019-07-13: 무시
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "enable_post": 1      # 0: [채용 알림] 비 활성화, 1: [채용 알림] 활성화
              "is_recruiting": 1    # 0: 채용 중이 아님 [채용 알림], 1: 현재 채용 상태임 [채용 중지]
              "employees": [
                # 업무 시직 전 응답 - 업무 수락 상태 표시
                {
                  "id": "iZ_rkELjhh18ZZauMq2vQw==",
                  "name": "이순신",
                  "pNo": "010-1111-3555",
                  "dt_begin": "2019-03-08 19:09:30",
                  "dt_end": "2019-03-14 00:00:00",
                  "state": "답변 X",
                  "is_not_begin": "1"
                },
                ......
                # 업무 시작 후 응답 - 출입 시간 표시
                {
                    "id": "45E0n8g8QqeppqJBYkXRHA",
                    "name": "박종기",
                    "pNo": "010-2557-3555",
                    "dt_begin": "2020-02-06 00:00:00",
                    "dt_end": "2020-03-31 00:00:00",
                    "dt_begin_beacon": "",
                    "dt_begin_touch": "17:35",
                    "dt_end_beacon": "",
                    "dt_end_touch": "17:35",
                    "state": "연(월)차",
                    "the_zone_code": "202011003",       # 더존 연동 코드
                    "notification": -1,                 # -1: 알림 없음, 0: 근로자가 확인하지 않은 알림 있음 (이름: 파랑), 2: 근로자가 거절한 알림 임음 (이름 빨강)
                    "week": "화",                        # 요일
                    "day_type": 2,                      # 이날의 근무 형태 0: 유급휴일, 1: 무급휴일, 2: 소정근무일
                    "day_type_description": "소정근무일",  # 근무 형태 설명
                    "is_not_begin": false
                },
                ......
              ]
            }
        STATUS 503
        STATUS 416
            {'message': '근로 내용은 오늘까지만 볼 수 없습니다.'}
            {'message': '업무 시작 날짜 이전 업무 내역은 볼 수 없습니다.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter_check = is_parameter_ok(rqst, ['work_id_!'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    work_id = parameter_check['parameters']['work_id']
    if 'dt' in rqst:
        try:
            dt = str_to_datetime(rqst['dt'])
        except Exception as e:
            dt = datetime.datetime.now()
            logError(get_api(request), ' parameter \'dt\' none or error')
    else:
        dt = datetime.datetime.now()
    work = Work.objects.get(id=work_id)  # 업무 에러 확인용

    # dt_today = datetime.datetime.now()
    dt_today = dt

    if datetime.datetime.now() < dt_today:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근로 내용은 오늘까지만 볼 수 있습니다.'})
    logSend(
        '  work.dt_begin: {}, now: {}, dt_today: {}, work.dt_begin: {}'.format(work.dt_begin, datetime.datetime.now(),
                                                                               dt_today,
                                                                               (work.dt_begin - timedelta(seconds=1))))
    # if work.dt_begin < datetime.datetime.now() and dt_today < work.dt_begin:
    if work.dt_begin < datetime.datetime.now():
        # 업무가 이미 시작되었으면
        if dt_today < (work.dt_begin - datetime.timedelta(seconds=1)):
            # 업무가 시작되었지만 요청한 날짜가 업무 시작 날짜전을 요청하면 에러처리한다.
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무 시작 날짜 이전 업무 내역은 볼 수 없습니다.'})

    s = requests.session()
    work_info = {'staff_id': AES_ENCRYPT_BASE64(str(worker.id)),
                 'work_id': AES_ENCRYPT_BASE64(str(work.id)),
                 }
    employees = []
    if work.dt_begin <= dt_today:
        # 업무가 시작되었다.
        work_info['year_month_day'] = dt_today.strftime("%Y-%m-%d")
        response = s.post(settings.CUSTOMER_URL + 'staff_employees_at_day_v2', json=work_info)
        employee_list = response.json()['employees']
        logSend('  > employoee_list: {}'.format(employee_list))
        for employee in employee_list:
            logSend(' - employee: {}'.format([employee[item] for item in employee.keys()]))
            if str_to_datetime(employee['dt_begin']) < (dt_today + timedelta(days=1)):
                state_dict = {-2: '연(월)차', -1: '조기 퇴근', 0: '',
                              1: '연장 30분', 2: '연장 1시간', 3: '연장 1시간 30분', 4: '연장 2시간', 5: '연장 2시간 30분',
                              6: '연장 3시간', 7: '연장 3시간 30분', 8: '연장 4시간', 9: '연장 4시간 30분', 10: '연장 5시간',
                              11: '연장 5시간 30분', 12: '연장 6시간', 13: '연장 6시간 30분', 14: '연장 7시간',
                              15: '연장 7시간 30분', 16: '연장 8시간', 17: '연장 8시간 30분', 18: '연장 9시간'}
                employee_web = {
                    'id': employee['employee_id'],
                    'name': employee['name'],
                    'pNo': employee['phone'],
                    'dt_begin': employee['dt_begin'],
                    'dt_end': employee['dt_end'],
                    'dt_begin_beacon': "" if employee['dt_begin_beacon'] is None else employee['dt_begin_beacon'][
                                                                                      11:16],
                    'dt_begin_touch': "" if employee['dt_begin_touch'] is None else employee['dt_begin_touch'][11:16],
                    'dt_end_beacon': "" if employee['dt_end_beacon'] is None else employee['dt_end_beacon'][11:16],
                    'dt_end_touch': "" if employee['dt_end_touch'] is None else employee['dt_end_touch'][11:16],
                    'state': state_dict[employee['overtime']],
                    'the_zone_code': "" if employee['the_zone_code'] is None else employee['the_zone_code'],

                    'notification': employee['notification'],
                    'week': employee['week'],
                    'day_type': employee['day_type'],
                    'day_type_description': employee['day_type_description'],

                    'is_not_begin': False,
                }
            else:
                employee_web = {
                    'id': employee['employee_id'],
                    'name': employee['name'],
                    'pNo': employee['phone'],
                    'dt_begin': employee['dt_begin'],
                    'dt_end': employee['dt_end'],
                    'state': employee['is_accept_work'],
                    'the_zone_code': "" if employee['the_zone_code'] is None else employee['the_zone_code'],
                    'is_not_begin': True,
                }
            employees.append(employee_web)
    else:
        # 업무가 아직 시작되지 않았다.
        response = s.post(settings.CUSTOMER_URL + 'staff_employees', json=work_info)
        logSend('  response.json(): {}'.format(response.json()))
        if 'employees' not in response.json():
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근로자가 없습니다.'})
        employee_list = response.json()['employees']
        for employee in employee_list:
            employee_web = {
                'id': employee['employee_id'],
                'name': employee['name'],
                'pNo': employee['phone'],
                'dt_begin': employee['dt_begin'],
                'dt_end': employee['dt_end'],
                'state': employee['is_accept_work'],
                'is_not_begin': True,
            }
            employees.append(employee_web)

    result = {'employees': employees,
              'enable_post': 1 if work.enable_post else 0,
              'is_recruiting': 1 if work.is_recruiting else 0
              }

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def post_employee(request):
    """
    채용 알림: 구직자에게 채용정보를 알림
    - 시험할 때
    http://0.0.0.0:8000/customer/post_employee?work_id=1&is_recruiting=0
    POST
        work_id: 업무 id     # 암호화된 업무 id
        is_recruiting: 1    # 0: 채용이 중지된 상태 [채용 알림], 1: 채용 중인 상태[채용 중지]
    response
        STATUS 200
            "message": "정상적으로 처리되었습니다."
            'message': '변경없는 정상처리입니다.'      # 채용 알림 / 중지 의 변경이 없이 API 가 호출 되었을 때
        STATUS 416
            {'message': '근로 내용은 오늘까지만 볼 수 없습니다.'}
            {'message': '업무 시작 날짜 이전 업무 내역은 볼 수 없습니다.'}
        STATUS 422
            {'message': 파라미터, 파라미터 암호화 에러 등}
            {'message': '해당 업무({}) 없음. {}'.format(work_id, str(e))}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter_check = is_parameter_ok(rqst, ['work_id_!', 'is_recruiting'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    work_id = parameter_check['parameters']['work_id']
    is_recruiting = parameter_check['parameters']['is_recruiting']
    try:
        work = Work.objects.get(id=work_id)  # 업무 에러 확인용
    except Exception as e:
        return status422(get_api(request), {'message': '해당 업무({}) 없음. {}'.format(work_id, str(e))})
    if work.is_recruiting == is_recruiting:
        return REG_200_SUCCESS.to_json_response({'message': '변경없는 정상처리입니다.'})
    #
    # 근로자 서버에 채용 알림 전달
    #
    s = requests.session()
    recruiting_info = {'work_id': rqst['work_id']}      # 나중에 분야별로 나눌 필요가 있다.
    response = s.post(settings.EMPLOYEE_URL + 'alert_recruiting', json=recruiting_info)
    response_dict = response.json()
    logSend('   response: {}'.format(response_dict))
    return ReqLibJsonResponse(response)
    # return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def report_work_place(request):
    """
    보고서: 사업장별
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/report_work_place?is_all=1
    GET
        is_all: 1     # 0: 현재 진행중인 업무, 1: 모든 업무

    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "arr_work_place": [
                {
                  "id": "_LdMng5jDTwK-LMNlj22Vw",
                  "name": "효성용연3공장_필름",
                  "order": "효성용연공장",
                  "manager": "김종민 (010-7290-8113)",
                  "arr_work": [
                    {
                      "id": "_LdMng5jDTwK-LMNlj22Vw",
                      "name_type": "생산 (3조3교대)",
                      "staff": "박상은 (010-6587-7376)",
                      "work": "생산",
                      "type": "3조3교대",
                      "contractor_name": "(주)티에스엔지",
                      "dt_begin": "2019-06-19",
                      "dt_end": "2019-12-31",
                      "time_type": 0,
                      "week_hours": 40,
                      "month_hours": 209,
                      "working_days": [1,2,3,4,5],
                      "paid_day": 0,
                      "is_holiday_work": 1
                    },
                    ......  # 다른 업무
                  ]
                },
                ......  # 다른 사업장
              ]
            }
        STATUS 422
            {'message': 'ClientError: parameter \'is_all\' 가 없어요'}
            {'message': 'ClientError: parameter \'is_all\' 가 정상적인 값이 아니예요.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter_check = is_parameter_ok(rqst, ['is_all'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    is_all = parameter_check['parameters']['is_all']

    work_place_list = Work_Place.objects.filter(contractor_id=worker.co_id)
    arr_work_place = []
    for work_place in work_place_list:
        new_work_place = {'id': AES_ENCRYPT_BASE64(str(work_place.id)),
                          'name': work_place.name,
                          'order': work_place.order_name,
                          'manager': '{} ({})'.format(work_place.manager_name, phone_format(work_place.manager_pNo))
                          }
        if int(is_all) == 1:
            work_list = Work.objects.filter(work_place_id=work_place.id)
        else:
            work_list = Work.objects.filter(work_place_id=work_place.id, dt_end__gt=datetime.datetime.now())
        arr_work = []
        for work in work_list:
            work_time = work.get_time_info()
            new_work = {'id': AES_ENCRYPT_BASE64(str(work.id)),
                        'name_type': '{} ({})'.format(work.name, work.type),
                        'staff': '{} ({})'.format(work.staff_name, phone_format(work.staff_pNo)),
                        'work': work.name,
                        'type': work.type,
                        'contractor_name': work.contractor_name,
                        'dt_begin': dt_str(work.dt_begin, "%Y-%m-%d"),
                        'dt_end': dt_str(work.dt_end, "%Y-%m-%d"),
                        'time_type': work_time['time_type'] if 'time_type' in work_time else "",
                        'week_hours': work_time['week_hours'] if 'week_hours' in work_time else "",
                        'month_hours': work_time['month_hours'] if 'month_hours' in work_time else "",
                        'working_days': work_time['working_days'] if 'working_days' in work_time else "",
                        'paid_day': work_time['paid_day'] if 'paid_day' in work_time else "",
                        'is_holiday_work': work_time['is_holiday_work'] if 'is_holiday_work' in work_time else "",
                        }
            arr_work.append(new_work)
        new_work_place['arr_work'] = arr_work
        arr_work_place.append(new_work_place)
    result = {'arr_work_place': arr_work_place}
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def report_contractor(request):
    """
    보고서: 협력사별
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/report_contractor?is_all=1
    GET
        year_month: 2019-12     # 대상 년 월
        is_all: 0               # 0: 종료된 업무 제외, 1: 종료된 업무도 표시
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "arr_contractor": [
                {
                  "id": "voGxXzbAurv_GvSDv1nciw",
                  "name": "(주)티에스엔지",
                  "arr_work_place": [
                    {
                      "id": "_LdMng5jDTwK-LMNlj22Vw",
                      "name": "효성용연3공장_필름",
                      "order": "효성용연공장",
                      "manager": "김종민 (010-7290-8113)",
                      "arr_work": [
                        {
                          "id": "_LdMng5jDTwK-LMNlj22Vw",
                          "name_type": "생산 (3조3교대)",
                          "staff": "박상은 (010-6587-7376)",
                          "work": "생산",
                          "type": "3조3교대",
                          "contractor_name": "(주)티에스엔지",
                          "dt_begin": "2019-06-19",
                          "dt_end": "2019-12-31",
                          "time_type": 0,
                          "week_hours": 40,
                          "month_hours": 209,
                          "working_days": [1,2,3,4,5],
                          "paid_day": 0,
                          "is_holiday_work": 1
                        },
                        ......  # 다른 업무
                      ]
                    },
                    ......  # 다른 사업장
                  ]
                },
                ......  # 다른 협력사
              ]
            }
        STATUS 422
            {'message': 'ClientError: parameter \'is_all\' 가 없어요'}
            {'message': 'ClientError: parameter \'is_all\' 가 정상적인 값이 아니예요.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter_check = is_parameter_ok(rqst, ['is_all'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    is_all = parameter_check['parameters']['is_all']

    dict_contractor = {}
    work_place_list = Work_Place.objects.filter(contractor_id=worker.co_id)
    for work_place in work_place_list:
        new_work_place = {'id': AES_ENCRYPT_BASE64(str(work_place.id)),
                          'name': work_place.name,
                          'order': work_place.order_name,
                          'manager': '{} ({})'.format(work_place.manager_name, phone_format(work_place.manager_pNo))
                          }
        if int(is_all) == 1:
            work_list = Work.objects.filter(work_place_id=work_place.id)
        else:
            work_list = Work.objects.filter(work_place_id=work_place.id, dt_end__gt=datetime.datetime.now())
        for work in work_list:
            work_time = work.get_time_info()
            new_work = {'id': AES_ENCRYPT_BASE64(str(work.id)),
                        'name_type': '{} ({})'.format(work.name, work.type),
                        'staff': '{} ({})'.format(work.staff_name, phone_format(work.staff_pNo)),
                        'work': work.name,
                        'type': work.type,
                        'contractor_name': work.contractor_name,
                        'dt_begin': dt_str(work.dt_begin, "%Y-%m-%d"),
                        'dt_end': dt_str(work.dt_end, "%Y-%m-%d"),
                        'time_type': work_time['time_type'] if 'time_type' in work_time else "",
                        'week_hours': work_time['week_hours'] if 'week_hours' in work_time else "",
                        'month_hours': work_time['month_hours'] if 'month_hours' in work_time else "",
                        'working_days': work_time['working_days'] if 'working_days' in work_time else "",
                        'paid_day': work_time['paid_day'] if 'paid_day' in work_time else "",
                        'is_holiday_work': work_time['is_holiday_work'] if 'is_holiday_work' in work_time else "",
                        }
            if work.contractor_id in dict_contractor.keys():
                work_place_dict = dict_contractor[work.contractor_id]['work_place_dict']
                if work_place.id in work_place_dict.keys():
                    work_place_list = work_place_dict[work_place.id]['arr_work']
                    work_place_list.append(new_work)
                else:
                    work_place_dict[work_place.id] = new_work_place
                    work_place_dict[work_place.id]['arr_work'] = [new_work]
            else:
                new_work_place['arr_work'] = [new_work]
                dict_contractor[work.contractor_id] = {'id': AES_ENCRYPT_BASE64(str(work.contractor_id)), 'name': work.contractor_name, 'work_place_dict': {work_place.id: new_work_place}}
    arr_contractor = []
    for key in dict_contractor.keys():
        print('>>> {}'.format(dict_contractor[key]))
        work_place_dict = dict_contractor[key]['work_place_dict']
        arr_work_place = []
        for work_place_key in work_place_dict.keys():
            print('  > {}'.format(work_place_dict[work_place_key]))

            work_place = work_place_dict[work_place_key]
            arr_work_place.append(work_place)
        del dict_contractor[key]['work_place_dict']
        contractor = dict_contractor[key]
        contractor['arr_work_place'] = arr_work_place
        arr_contractor.append(contractor)

    result = {'arr_contractor': arr_contractor}
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def report_staff(request):
    """
    보고서: 관리자별
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/report_staff?staff_id=L8IGbbK-19bReE1x3csoGw&is_all=1
    http://0.0.0.0:8000/customer/report_staff?staff_id=gDoPqy_Pea6imtYYzWrEXQ&is_all=1
    GET
        staff_id: 직원 id    # 암호화된 id
        is_all: 1           # 0: 현재 진행중인 업무, 1: 모든 업무

    response
        STATUS 200
            {'message': '관리하는 업무가 없습니다.'}
            {
              "message": "정상적으로 처리되었습니다.",
              "arr_work_place": [
                {
                  "id": "GB-SPRhVjauzMWe7Q83VQg",
                  "name": "바스프화성(식당)",
                  "order": "바스프 화성공장",
                  "manager": "전미숙 (010-5556-0163)",
                  "arr_work": [
                    {
                      "id": "61qvFaTlQIPL7mtfslc5Lg",
                      "name_type": "테스트 (주간)",
                      "staff": "전미숙 (010-5556-0163)",
                      "work": "테스트",
                      "type": "주간",
                      "contractor_name": "(주)대덕에프엔에스",
                      "dt_begin": "2019-08-07",
                      "dt_end": "2019-08-09",
                      "time_type": 0,
                      "week_hours": 40,
                      "month_hours": 209,
                      "working_days": [1,2,3,4,5],
                      "paid_day": 0,
                      "is_holiday_work": 1
                    },
                    ......  # 다른 업무
                  ]
                },
                ......  # 다른 사업장
              ]
            }
        STATUS 422
            {'message': 'ClientError: parameter \'staff_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'staff_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'is_all\' 가 없어요'}
            {'message': 'ClientError: parameter \'is_all\' 가 정상적인 값이 아니예요.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'is_all'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    staff_id = parameter_check['parameters']['staff_id']
    is_all = parameter_check['parameters']['is_all']

    print(staff_id)
    work_place_list = Work_Place.objects.filter(contractor_id=worker.co_id, manager_id=staff_id)
    if len(work_place_list) == 0:
        if int(is_all) == 1:
            work_list = Work.objects.filter(staff_id=staff_id)
        else:
            work_list = Work.objects.filter(staff_id=staff_id, dt_end__gt=datetime.datetime.now())
        if len(work_list) == 0:
            return REG_200_SUCCESS.to_json_response({'message': '관리하는 업무가 없습니다.'})
        work_place_id_list = [work.work_place_id for work in work_list]
        print('  >> {}'.format(work_place_id_list))
        # work_place_list = Work_Place.objects.filter(contractor_id=worker.co_id, id__in=work_place_id_list)
        work_place_list = Work_Place.objects.filter(id__in=work_place_id_list)
        print('  >> {}'.format(len(work_place_list)))
        arr_work_place = []
        for work_place in work_place_list:
            new_work_place = {'id': AES_ENCRYPT_BASE64(str(work_place.id)),
                              'name': work_place.name,
                              'order': work_place.order_name,
                              'manager': '{} ({})'.format(work_place.manager_name, phone_format(work_place.manager_pNo))
                              }
            print('  >> {}'.format(new_work_place))
            arr_work = []
            for work in work_list:
                if work.work_place_id != work_place.id:
                    continue
                work_time = work.get_time_info()
                new_work = {'id': AES_ENCRYPT_BASE64(str(work.id)),
                            'name_type': '{} ({})'.format(work.name, work.type),
                            'staff': '{} ({})'.format(work.staff_name, phone_format(work.staff_pNo)),
                            'work': work.name,
                            'type': work.type,
                            'contractor_name': work.contractor_name,
                            'dt_begin': dt_str(work.dt_begin, "%Y-%m-%d"),
                            'dt_end': dt_str(work.dt_end, "%Y-%m-%d"),
                            'time_type': work_time['time_type'] if 'time_type' in work_time else "",
                            'week_hours': work_time['week_hours'] if 'week_hours' in work_time else "",
                            'month_hours': work_time['month_hours'] if 'month_hours' in work_time else "",
                            'working_days': work_time['working_days'] if 'working_days' in work_time else "",
                            'paid_day': work_time['paid_day'] if 'paid_day' in work_time else "",
                            'is_holiday_work': work_time['is_holiday_work'] if 'is_holiday_work' in work_time else "",
                            }
                arr_work.append(new_work)
            new_work_place['arr_work'] = arr_work
            arr_work_place.append(new_work_place)
        result = {'arr_work_place': arr_work_place}
    else:
        arr_work_place = []
        for work_place in work_place_list:
            new_work_place = {'id': AES_ENCRYPT_BASE64(str(work_place.id)),
                              'name': work_place.name,
                              'order': work_place.order_name,
                              'manager': '{} ({})'.format(work_place.manager_name, phone_format(work_place.manager_pNo))
                              }
            print('  >> {}'.format(new_work_place))
            if is_all:
                work_list = Work.objects.filter(work_place_id=work_place.id)
            else:
                work_list = Work.objects.filter(work_place_id=work_place.id, dt_end__gt=datetime.datetime.now())
            arr_work = []
            for work in work_list:
                work_time = work.get_time_info()
                new_work = {'id': AES_ENCRYPT_BASE64(str(work.id)),
                            'name_type': '{} ({})'.format(work.name, work.type),
                            'staff': '{} ({})'.format(work.staff_name, phone_format(work.staff_pNo)),
                            'work': work.name,
                            'type': work.type,
                            'contractor_name': work.contractor_name,
                            'dt_begin': dt_str(work.dt_begin, "%Y-%m-%d"),
                            'dt_end': dt_str(work.dt_end, "%Y-%m-%d"),
                            'time_type': work_time['time_type'] if 'time_type' in work_time else "",
                            'week_hours': work_time['week_hours'] if 'week_hours' in work_time else "",
                            'month_hours': work_time['month_hours'] if 'month_hours' in work_time else "",
                            'working_days': work_time['working_days'] if 'working_days' in work_time else "",
                            'paid_day': work_time['paid_day'] if 'paid_day' in work_time else "",
                            'is_holiday_work': work_time['is_holiday_work'] if 'is_holiday_work' in work_time else "",
                            }
                arr_work.append(new_work)
            new_work_place['arr_work'] = arr_work
            arr_work_place.append(new_work_place)
        result = {'arr_work_place': arr_work_place}
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def report_employee(request):
    """
    보고서: 근로자별
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/report_employee?name=김미경&is_all=1
    http://0.0.0.0:8000/customer/report_employee?pNo=01023976143&is_all=1
    http://0.0.0.0:8000/customer/report_employee?pNo=01020736959&is_all=1
    GET
        name: 홍길동           # 근로자 이름
        pNo: 01033335555     # 근로자 전화번호
        is_all: 1            # 0: 현재 진행중인 업무, 1: 모든 업무

    response
        STATUS 200
            {'message': '해당 근로자를 찾을 수 없습니다.'}
            {'message': '관리하는 업무가 없습니다.'}
            {
              "message": "정상적으로 처리되었습니다.",
              "employee_info": {
                "id": "ryWQkNtiHgkUaY_SZ1o2uA",
                "pNo": "010-2073-6959",
                "name": "최진(상용)"
              },
              "arr_work_place": [
                {
                  "id": "3EP9Yb9apLUn2Ymof8Mw9A",
                  "name": "test_1",
                  "order": "요셉",
                  "manager": "최진 (010-2073-6959)",
                  "arr_work": [
                    {
                      "id": "3W0uYO_TlmLvE-e_WhMQoA",
                      "name_type": "test_1_4 (주간)",
                      "staff": "최진 (010-2073-6959)",
                      "work": "test_1_4",
                      "type": "주간",
                      "contractor_name": "테스트",
                      "dt_begin": "2019-08-01",
                      "dt_end": "2019-08-30",
                      "time_type": 0,
                      "week_hours": 40,
                      "month_hours": 209,
                      "working_days": [1,2,3,4,5],
                      "paid_day": 0,
                      "is_holiday_work": 1
                    }
                  ]
                },
                {
                  "id": "N--RtSs4MP3qPHBZpxxL8g",
                  "name": "test_4",
                  "order": "대덕INC",
                  "manager": "최진 (010-2073-6959)",
                  "arr_work": [
                    {
                      "id": "YMAoiMsJ00KdriRqYP2wqA",
                      "name_type": "테스트1 (주간)",
                      "staff": "최진 (010-2073-6959)",
                      "work": "테스트1",
                      "type": "주간",
                      "contractor_name": "테스트4",
                      "dt_begin": "2019-09-05",
                      "dt_end": "2019-09-30",
                      "time_type": 0,
                      "week_hours": 40,
                      "month_hours": 209,
                      "working_days": [1,2,3,4,5],
                      "paid_day": 0,
                      "is_holiday_work": 1
                    },
                    {
                      "id": "N-Ef_BUENRMlxjvllS4aCQ",
                      "name_type": "테스트2 (야간)",
                      "staff": "최진 (010-2073-6959)",
                      "work": "테스트2",
                      "type": "야간",
                      "contractor_name": "테스트",
                      "dt_begin": "2019-10-01",
                      "dt_end": "2019-10-31",
                      "time_type": 0,
                      "week_hours": 40,
                      "month_hours": 209,
                      "working_days": [1,2,3,4,5],
                      "paid_day": 0,
                      "is_holiday_work": 1
                    }
                  ]
                }
              ]
            }
        STATUS 416
            {'message': '근로한 업무가 없습니다.'}
        STATUS 422
            {'message': 'ClientError: parameter \'is_all\' 가 없어요'}
            {'message': 'ClientError: parameter \'is_all\' 가 정상적인 값이 아니예요.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    s = requests.session()
    r = s.post(settings.EMPLOYEE_URL + 'tk_employee', json=rqst)
    logSend('  {}'.format({'url': r.url, 'POST': request, 'STATUS': r.status_code, 'R': r.json()}))
    if r.status_code != 200:
        return ReqLibJsonResponse(r)
    result_json = r.json()
    # print('  >> {}'.format(result_json))
    # return REG_200_SUCCESS.to_json_response(result_json)
    if len(r.json()['passers']) == 0:
        return REG_200_SUCCESS.to_json_response({'message': '해당 근로자를 찾을 수 없습니다.'})

    employee = r.json()['passers'][0]
    # print('  >> {}'.format(employee))

    new_employee = {
        'id': AES_ENCRYPT_BASE64(str(employee['id'])),
        'pNo': employee['pNo'],
        'name': employee['name'],
        'work_id_list': [work['id'] for work in employee['works']]
    }
    # print(' >> {}'.format(new_employee))
    if len(new_employee['work_id_list']) == 0:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근로한 업무가 없습니다.'})
    parameter_check = is_parameter_ok(rqst, ['is_all'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    is_all = parameter_check['parameters']['is_all']
    # print(new_employee)
    if int(is_all) == 1:
        work_list = Work.objects.filter(id__in=new_employee['work_id_list'])
    else:
        work_list = Work.objects.filter(id__in=new_employee['work_id_list'], dt_end__gt=datetime.datetime.now())
    if len(work_list) == 0:
        return REG_200_SUCCESS.to_json_response({'message': '관리하는 업무가 없습니다.'})
    work_place_id_list = [work.work_place_id for work in work_list]
    # print('  >> {}'.format(work_place_id_list))
    # work_place_list = Work_Place.objects.filter(contractor_id=worker.co_id, id__in=work_place_id_list)
    work_place_list = Work_Place.objects.filter(id__in=work_place_id_list)
    # print('  >> {}'.format(len(work_place_list)))
    arr_work_place = []
    for work_place in work_place_list:
        new_work_place = {'id': AES_ENCRYPT_BASE64(str(work_place.id)),
                          'name': work_place.name,
                          'order': work_place.order_name,
                          'manager': '{} ({})'.format(work_place.manager_name, phone_format(work_place.manager_pNo))
                          }
        # print('  >> {}'.format(new_work_place))
        arr_work = []
        for work in work_list:
            if work.work_place_id != work_place.id:
                continue
            work_time = work.get_time_info()
            new_work = {'id': AES_ENCRYPT_BASE64(str(work.id)),
                        'name_type': '{} ({})'.format(work.name, work.type),
                        'staff': '{} ({})'.format(work.staff_name, phone_format(work.staff_pNo)),
                        'work': work.name,
                        'type': work.type,
                        'contractor_name': work.contractor_name,
                        'dt_begin': dt_str(work.dt_begin, "%Y-%m-%d"),
                        'dt_end': dt_str(work.dt_end, "%Y-%m-%d"),
                        'time_type': work_time['time_type'],
                        'week_hours': work_time['week_hours'],
                        'month_hours': work_time['month_hours'],
                        'working_days': work_time['working_days'],
                        'paid_day': work_time['paid_day'],
                        'is_holiday_work': work_time['is_holiday_work'],
                        }
            arr_work.append(new_work)
        new_work_place['arr_work'] = arr_work
        arr_work_place.append(new_work_place)
    result = {'employee_info': new_employee,
              'arr_work_place': arr_work_place
              }
    del result['employee_info']['work_id_list']

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def report_detail(request):
    """
    보고서: 업무의 근로자 근태기록
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/report_detail?work_id=YMAoiMsJ00KdriRqYP2wqA&employee_id=ryWQkNtiHgkUaY_SZ1o2uA&year_month=2019-08
    http://0.0.0.0:8000/customer/report_detail?work_id=_LdMng5jDTwK-LMNlj22Vw&year_month=2019-08
    http://0.0.0.0:8000/customer/report_detail?work_id=_LdMng5jDTwK-LMNlj22Vw&employee_id=Rdberb80WBnVt9C81mw4Qw&year_month=2019-08
    GET
        work_id: 업무 id         # 암호화된 id
        employee_id: 근로자 id   # 근로자 id (단, 근로자 한명에 대한 근로내역을 볼 때만 사용)
        year_month: 2019-12    # 요구한 근로 내역
    response
        STATUS 200
            {'message': '관리하는 업무가 없습니다.'}
            {
              "message": "정상적으로 처리되었습니다.",
              "arr_working": [
                {
                  "name": "이영길",        # 이름
                  "break_sum": 0,        # 휴게시간 합계
                  "basic_sum": 180,      # 기본근로시간 합계
                  "night_sum": 0,        # 야간근로시간 합계
                  "overtime_sum": 8,     # 연장근로시간 합계
                  "holiday_sum": 0,      # 휴일근로시간 합계
                  "ho_sum": 0,           # 휴일/연장근로시간 합계
                  "days": {
                    "01": {
                      "01": {                       # 근무한 날짜
                        "dt_in_verify": "06:27",        # 출근시간
                        "dt_out_verify": "15:00",       # 퇴근시간
                        "break": "01:00"                # 휴게시간
                        "basic": "",                    # 기본근로
                        "night": "",                    # 야간근로
                        "overtime": 0,                  # 연장근무
                        "holiday": "",                  # 휴일근로
                        "ho": ""                        # 휴일/연장 근로
                      }
                    },
                    ......
                    "31": {
                      "passer_id": 119,
                      "dt_in_verify": "22:35",
                      "dt_out_verify": "",
                      "overtime": "",
                      "week": "수",
                      "break": "01:00",
                      "basic": "",
                      "night": "",
                      "holiday": "",
                      "ho": ""
                    }
                  },
                },
                ......
              ]
            }
        STATUS 416
            {'message': '업무기간을 벗어났습니다.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'work_id\' 가 없어요'}
            {'message':'ClientError: parameter \'year_month\' 가 없어요'}
            {'message':'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ClientError: parameter \'employee_id\' 가 정상적인 값이 아니예요.'}
            {'message': '업무가 없어요.({})'.format(e)}
            {'message': '해당 근로자가 없어요.({})'.format(e)}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    s = requests.session()
    r = s.post(settings.EMPLOYEE_URL + 'work_report_for_customer', json=rqst)
    logSend('  {}'.format({'url': r.url, 'POST': request, 'STATUS': r.status_code, 'R': r.json()}))
    # result_json = r.json()
    # logSend('  >> {}'.format(result_json))
    if r.status_code != 200:
        return ReqLibJsonResponse(r)
    try:
        working_list = r.json()['arr_working']
    except Exception as e:
        logError('ERROR: {}\n{}'.format(e, r.json()))
    #
    # excel 파일 생성
    #
    make_xlsx(rqst['work_id'], rqst['year_month'], working_list)

    result = {'arr_working': working_list}
    return REG_200_SUCCESS.to_json_response(result)


def make_xlsx(work_id, year_month: str, working_list: list):
    #
    # 1. 양식을 예쁘게 꾸미기
    # 2. 파일이 있는지 확인하고 있을 때 만들어진 날짜가 2개월 이상 지났으면 다시 만들지 않는다.
    #
    data_root = os.path.join(settings.MEDIA_ROOT, 'Data/')
    workbook = xlsxwriter.Workbook('{}{}{}.xlsx'.format(data_root, work_id, year_month))
    worksheet = workbook.add_worksheet()
    # Widen the first column to make the text clearer.
    worksheet.set_column('A:A', 20)

    merge_format = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
    bold = workbook.add_format({'bold': True})
    cell_format = workbook.add_format()
    cell_format.set_pattern(1)
    cell_format.set_bg_color('#eeeeee')
    dt = str_to_datetime(year_month) + relativedelta(months=1) - datetime.timedelta(hours=1)
    last_day = int(dt.strftime("%d"))
    comment_list = ['날짜', '요일', '출근시간', '퇴근시간', '휴게시간', '기본근로', '야간근로', '연장근로', '휴일근로', '휴일/연장']
    row = 0
    for employee in working_list:
        # worksheet.write(row + 0, 0, employee['name'])
        worksheet.merge_range(row + 0, 0, row + 8, 0, employee['name'], merge_format)
        for comment_row in range(0, 9, 1):
            # Write some numbers, with row/column notation.
            worksheet.write(row + comment_row, 1, comment_list[comment_row], cell_format)
        working_list = employee['days']
        # print('   >> working_list: {}'.format(working_list))
        column = 2
        for day in range(1, last_day, 1):
            # print('row: {} column: {} day: {:02}'.format(row, column, day))
            if '{:02}'.format(day) in working_list.keys():
                # Write some numbers, with row/column notation.
                day_info = working_list['{:02}'.format(day)]
                # print('   >> day_info: {}'.format(day_info))
                worksheet.write(row + 0, column, str(day))
                worksheet.write(row + 1, column, day_info['week'])
                worksheet.write(row + 2, column, day_info['dt_in_verify'])
                worksheet.write(row + 3, column, day_info['dt_out_verify'])
                worksheet.write(row + 4, column, day_info['break'])
                worksheet.write(row + 5, column, day_info['basic'])
                worksheet.write(row + 6, column, day_info['night'])
                worksheet.write(row + 7, column, day_info['overtime'])
                worksheet.write(row + 8, column, day_info['holiday'])
                worksheet.write(row + 9, column, day_info['ho'])
            column += 1
        worksheet.write(row + 0, column, '합계')
        worksheet.write(row + 4, column, employee['break_sum'])
        worksheet.write(row + 5, column, employee['basic_sum'])
        worksheet.write(row + 6, column, employee['night_sum'])
        worksheet.write(row + 7, column, employee['overtime_sum'])
        worksheet.write(row + 8, column, employee['holiday_sum'])
        worksheet.write(row + 9, column, employee['ho_sum'])

        row += 9
    workbook.close()
    return


@cross_origin_read_allow
@session_is_none_403
def report_xlsx(request):
    """
    보고서: 엑셀로 저장된 근태기록부 다운로드
    - 업무를 선택하면 자동으로 생성된다.
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/report_xlsx?work_id=YMAoiMsJ00KdriRqYP2wqA&employee_id=ryWQkNtiHgkUaY_SZ1o2uA&year_month=2019-08
    http://0.0.0.0:8000/customer/report_detail?work_id=_LdMng5jDTwK-LMNlj22Vw&year_month=2019-08
    http://0.0.0.0:8000/customer/report_detail?work_id=_LdMng5jDTwK-LMNlj22Vw&employee_id=Rdberb80WBnVt9C81mw4Qw&year_month=2019-08
    GET
        work_id: 업무 id         # 암호화된 id
        employee_id: 근로자 id   # 근로자 id (단, 근로자 한명에 대한 근로내역을 볼 때만 사용)
        year_month: 2019-12    # 요구한 근로 내역
    response
        STATUS 200
            {'message': '관리하는 업무가 없습니다.'}
            {
              "message": "정상적으로 처리되었습니다.",
            }
        STATUS 416
            {'message': '업무기간을 벗어났습니다.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'work_id\' 가 없어요'}
            {'message':'ClientError: parameter \'year_month\' 가 없어요'}
            {'message':'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ClientError: parameter \'employee_id\' 가 정상적인 값이 아니예요.'}
            {'message': '업무가 없어요.({})'.format(e)}
            {'message': '해당 근로자가 없어요.({})'.format(e)}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    data_root = os.path.join(settings.MEDIA_ROOT, 'Data/')
    work_id = rqst['work_id']
    year_month = rqst['year_month']
    file_path = '{}{}{}.xlsx'.format(data_root, work_id, year_month)
    logSend('>>> file_path: {}, is exist: {}'.format(file_path, os.path.isfile(file_path)))
    if os.path.exists(file_path):
        with open(file_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/vnd.ms-excel")
            response['Content-Disposition'] = 'inline; filename=' + os.path.basename(file_path)
            return response
    raise Http404


@cross_origin_read_allow
@session_is_none_403
def report(request):
    """
    현장, 업무별 보고서 (관리자별(X), 요약(X))
      - 요약 보고서
      - 관리자별 보고서
      - 사업장별 보고서
      - 현장별 보고서
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/report?manager_id=&work_place_id=&work_id=
    GET
        manager_id      = 관리자 id    # 없으면 전체
        work_place_id   = 사업장 id    # 없으면 전체
        work_id         = 업무 id     # 없으면 전체

    response
        STATUS 200
            {
            "arr_work_place":
            	[
            	{
            	"id": 1, "name": "\ub300\ub355\ud14c\ud06c", "contractor_name": "\ub300\ub355\ud14c\ud06c", "place_name": "\ub300\ub355\ud14c\ud06c", "manager_name": "\ubc15\uc885\uae30", "manager_pNo": "01025573555", "order_name": "\ub300\ub355\ud14c\ud06c",
            	"arr_work":
            		[
            		{
            			"id": 1, "name": "\ube44\ucf58\uad50\uccb4", "type": "3\uad50\ub300", "staff_name": "\uc774\uc694\uc149", "staff_pNo": "01024505942", "arr_employee":
            			[
            				{
            				"id": 42, "name": "unknown", "pNo": "010-3333-5555", "is_active": true, "dt_begin": "2019-01-30 15:35:39", "dt_end": "2019-02-01 00:00:00"
            				},
            				{"id": 43, "name": "unknown", "pNo": "010-5555-7777", "is_active": false, "dt_begin": "2019-01-30 15:35:39", "dt_end": "2019-01-26 	00:00:00"
            				},
            				{"id": 44, "name": "unknown", "pNo": "010-7777-9999", "is_active": false, "dt_begin": "2019-01-30 15:35:39", "dt_end": "2019-01-26 	00:00:00"
            				}
            			]
            		}
            		]
            	},
            	{
            	"id": 3, "name": "\uc784\ucc3d\ubca0\ub974\ub514\uc548", "contractor_name": "\ub300\ub355\ud14c\ud06c", "place_name": "\uc784\ucc3d\ubca0\ub974\ub514\uc548", "manager_name": "\ubc15\uc885\uae30", "manager_pNo": "01025573555", "order_name": "\ub300\ub355\ud14c\ud06c",
            	"arr_work":
            		[
            		]
            	}
            	]
            }
        STATUS 503
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    # work_id = rqst['work_id']
    # Work.objects.get(id=work_id) # 업무 에러 확인용

    # manager_id = rqst['manager_id']
    # manager = Staff.objects.get(id=manager_id) # 관리자 에러 확인용
    if ('work_place_id' in rqst) and (len(rqst['work_place_id']) > 0):
        # 정해진 사업장 의 정보
        work_places = Work_Place.objects.filter(id=AES_DECRYPT_BASE64(rqst['work_place_id'])
                                                ).values('id',
                                                         'name',
                                                         'contractor_name',
                                                         'place_name',
                                                         'manager_name',
                                                         'manager_pNo',
                                                         'order_name'
                                                         )
    else:
        # 모든 사업장
        work_places = Work_Place.objects.filter(contractor_id=worker.co_id
                                                ).values('id',
                                                         'name',
                                                         'contractor_name',
                                                         'place_name',
                                                         'manager_name',
                                                         'manager_pNo',
                                                         'order_name'
                                                         )
    arr_work_place = []
    for work_place in work_places:
        print('  ', work_place['name'])
        works = Work.objects.filter(work_place_id=work_place['id']
                                    ).values('id',
                                             'name',
                                             'type',
                                             'staff_name',
                                             'staff_pNo'
                                             )
        arr_work = []
        for work in works:
            print('    ', work['name'])
            employees = Employee.objects.filter(work_id=work['id']
                                                ).values('id',
                                                         'name',
                                                         'pNo',
                                                         'is_active',
                                                         'dt_begin',
                                                         'dt_end'
                                                         )
            arr_employee = []
            for employee in employees:
                employee['pNo'] = phone_format(employee['pNo'])
                arr_employee.append(employee)
            work['arr_employee'] = arr_employee
            arr_work.append(work)
            for employee in employees:
                print('      ', employee['pNo'])
        work_place['arr_work'] = arr_work
        arr_work_place.append(work_place)
    result = {'arr_work_place': arr_work_place}

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def report_of_manager(request):
    """
    현장, 관리자별 보고서
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/report?manager_id=
    GET
        manager_id = 관리자 id  # 값이 없으면 모두

    response
        STATUS 200
            {
              "arr_work_place": [
                {
                  "id": 1,
                  "name": "효성용연 1공장",
                  "place_name": "효성용연 1공장 정문 밖",
                  "manager_name": "홍길동",
                  "manager_pNo": "01025573555",
                  "order_name": "(주)효성 1공장",
                  "arr_work": [
                    {
                      "업무": "조립",
                      "형태": "주간",
                      "담당": "유재석",
                      "전화": "01011112222",
                      "인원": "5",
                      "지각": "3",
                      "결근": 1
                    },
                    ......
                  ]
                },
                ......
              ]
            }
        STATUS 503
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    if ('manager_id' in rqst) or (len(rqst['manage_id']) == 0):
        work_places = Work_Place.objects.filter(contractor_id=worker.co_id,
                                                ).values('id',
                                                         'name',
                                                         'place_name',
                                                         'manager_name',
                                                         'manager_pNo',
                                                         'order_name'
                                                         )
    else:
        work_places = Work_Place.objects.filter(conttractor_id=worker.co_id,
                                                manager_id=AES_DECRYPT_BASE64(rqst['manager_id'])
                                                ).values('id',
                                                         'name',
                                                         'place_name',
                                                         'manager_name',
                                                         'manager_pNo',
                                                         'order_name'
                                                         )
    arr_work_place = []
    for work_place in work_places:
        print('  ', work_place['name'])
        work_place['manager_pNo'] = phone_format(work_place['manager_pNo'])
        works = Work.objects.filter(work_place_id=work_place['id']
                                    ).values('id',
                                             'name',
                                             'type',
                                             'staff_name',
                                             'staff_pNo'
                                             )
        arr_work = []
        for work in works:
            work['staff_pNo'] = phone_format(work['staff_pNo'])
            employees = Employee.objects.filter(work_id=work['id'])
            print('    ', work['name'], work['type'], work['type'], work['staff_name'], work['staff_pNo'],
                  len(employees))
            summary = {u'업무': work['name'],
                       u'형태': work['type'],
                       u'담당': work['staff_name'],
                       u'전화': work['staff_pNo'],
                       u'인원': len(employees),
                       u'지각': 3,
                       u'결근': 1,
                       }
            arr_work.append(summary)
        work_place['arr_work'] = arr_work
        arr_work_place.append(work_place)
    result = {'arr_work_place': arr_work_place}

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def report_all(request):
    """
    모든 사업장 현장
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/report?manager_id=&work_place_id=&work_id=
    GET
        manager_id      = 관리자 id    # 없으면 전체
        work_place_id   = 사업장 id    # 없으면 전체
        work_id         = 업무 id     # 없으면 전체

    response
        STATUS 200
            {
              "arr_work_place": [
                {
                  "id": 1,
                  "name": "효성용연 1공장",
                  "place_name": "효성용연 1공장 정문 밖",
                  "manager_name": "홍길동",
                  "manager_pNo": "01025573555",
                  "order_name": "(주)효성 1공장",
                  "summary": {
                    "인원": 99,
                    "지각": 15,
                    "결근": 5
                  }
                },
                ......
              ]
            }
        STATUS 503
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    work_places = Work_Place.objects.filter(contractor_id=worker.co_id
                                            ).values('id',
                                                     'name',
                                                     'place_name',
                                                     'manager_name',
                                                     'manager_pNo',
                                                     'order_name'
                                                     )
    arr_work_place = []
    for work_place in work_places:
        print('  ', work_place['name'])
        work_place['manager_pNo'] = phone_format(work_place['manager_pNo'])
        works = Work.objects.filter(work_place_id=work_place['id']
                                    ).values('id',
                                             'name',
                                             'type',
                                             'staff_name',
                                             'staff_pNo'
                                             )
        no_employees = 0
        no_absent = 0
        no_late = 0
        for work in works:
            work['staff_pNo'] = phone_format(work['staff_pNo'])
            employees = Employee.objects.filter(work_id=work['id'])
            print('    ', work['name'], work['type'], work['type'], work['staff_name'], work['staff_pNo'],
                  len(employees))
            no_employees += len(employees)
            no_late += 3
            no_absent += 1
        work_place['summary'] = {u'인원': no_employees,
                                 u'지각': no_late,
                                 u'결근': no_absent
                                 }
        arr_work_place.append(work_place)
    result = {'arr_work_place': arr_work_place}

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def report_of_staff(request):
    """
    담당자 기준의 업무 보고서 - 담당자가 맡고 있는 업무에 투입된 근로자 리스트
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/report?manager_id=&work_place_id=&work_id=
    GET
        staff_id = 관리자 id # 없으면 로그인 한 사람이 현장 소장인 곳 보고서
    response
        STATUS 200
            {
              "arr_work": [
                {
                  "work_place_name": "효성 1공장",
                  "name": "조립",
                  "contractor_name": "대덕기공",
                  "type": "주간",
                  "staff_name": "홍길동",
                  "staff_pNo": "010-1111-2222",
                  "arr_employee": [
                    {
                      "id": "암호화된 id",
                      "name": "강호동",
                      "pNo": "010-3333-7777",
                      "is_active": "근무중"
                    },
                    ......
                  ]
                },
                ......
              ]
            }
        STATUS 503
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    if ('staff_id' in rqst) or (len(rqst['staff_id']) == 0):
        works = Work.objects.filter(staff_id=worker_id, dt_end__gt=datetime.datetime.now())
    else:
        works = Work.objects.filter(staff_id=AES_ENCRYPT_BASE64(rqst['staff_id']), dt_end__gt=datetime.datetime.now())
    arr_work = []
    for work in works:
        print(work['name'], work['work_place_name'], work['contractor_name'], work['type'], work['staff_name'],
              work['staff_pNo'])
        work = {'work_place_name': work['work_place_name'],
                'name': work['name'],
                'contractor_name': work['contractor_name'],
                'type': work['type'],
                'staff_name': work['staff_name'],
                'staff_pNo': phone_format(work['staff_pNo'])
                }
        employees = Employee.objects.filter(work_id=work['id'],
                                            ).values('id',
                                                     'name',
                                                     'pNo',
                                                     'is_active',
                                                     # 'dt_begin_beacon',
                                                     # 'dt_end_beacon',
                                                     # 'dt_begin_touch',
                                                     # 'dt_begin_touch',
                                                     # 'x',
                                                     # 'y'
                                                     )
        arr_employee = []
        for employee in employees:
            employee['id'] = AES_ENCRYPT_BASE64(str(employee.id))
            employee['is_active'] = '' if employee['is_active'] == 0 else '근무중'
            employee['pNo'] = phone_format(employee['pNo'])
            arr_employee.append(employee)
        work['arr_employee'] = arr_employee
        arr_work.append('arr_employee')
    result = {'arr_work': arr_work}

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def report_of_employee(request):
    """
    근로자의 월별 근태내역
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/report_of_employee?work_id=_LdMng5jDTwK-LMNlj22Vw&employee_id=iZ_rkELjhh18ZZauMq2vQw&year_month=2019-04
    GET
        work_id = 업무 id         # 사업장에서 선택된 업무의 id
        employee_id = 근로자 id    # 업무에서 선택된 근로자의 id
        year_month = "2019-04"   # 근태내역의 연월
    response
        STATUS 200
        {
            "message": "정상적으로 처리되었습니다.",
            "working_days": 26,             # 근로 일수
            "work_type": "주간 오전",         # 근로 조건
            "employee_name": "이순신",        # 근로자 이름
            "working": [                    # 월의 날짜별 근로 내역
              {
                "day": "01",                # 날짜
                "in_hour_min": "08:30",     # 출근 시간
                "out_hour_min": "17:30",    # 퇴근 시간
                "overtime": 0.0,            # 연장근무 시간 (1.5 << 1:30)
                "working_hour": 8,          # 근무시간
                "break_hour": 1             # 근무시간 대비 의무 휴게시
              },
              ...
              ]
        }
        STATUS 503
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'work_id\' 가 없어요'}
            {'message':'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}

            {'message':'ClientError: parameter \'employee_id\' 가 없어요'}
            {'message':'ClientError: parameter \'employee_id\' 가 정상적인 값이 아니예요.'}

            {'message':'ClientError: parameter \'year_month\' 가 없어요'}

            {'message': '업무가 없어요.'}
            {'message': '해당 근로자가 없어요.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter_check = is_parameter_ok(rqst, ['work_id_!', 'employee_id_!', 'year_month'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

    work_id = parameter_check['parameters']['work_id']
    try:
        work = Work.objects.get(id=work_id)
    except Exception as e:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '업무가 없어요.({})'.format(e)})
    employee_id = parameter_check['parameters']['employee_id']
    try:
        employee = Employee.objects.get(id=employee_id)
    except Exception as e:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '해당 근로자가 없어요.({})'.format(e)})
    year_month = parameter_check['parameters']['year_month']
    logSend(work_id, ' ', employee_id)
    # result = {'parameters': [work_id, employee_id, year_month]}
    # return REG_200_SUCCESS.to_json_response(result)

    # employees = Employee.objects.filter(id=employee_id, work_id=work_id)

    parameters = {"employee_id": AES_ENCRYPT_BASE64(str(employee.employee_id)),
                  "dt": year_month,
                  'work_id': work_id
                  }
    s = requests.session()
    r = s.post(settings.EMPLOYEE_URL + 'my_work_histories_for_customer', json=parameters)
    if r.status_code != 200:
        return ReqLibJsonResponse(r)
    month_working = r.json()['working']
    for working in month_working:
        working['day'] = working['year_month_day'][8:10]
        try:
            working['in_hour_min'] = working['dt_begin'][11:16]
            working['out_hour_min'] = working['dt_end'][11:16]
        except Exception as e:
            logSend(get_api(request),
                    ' working data 의 날짜 시간 변경 오류 {} {} {} ({})'.format(working['year_month_day'], working['dt_begin'],
                                                                       working['dt_end'], str(e)))
            working['in_hour_min'] = "08:30"
            working['out_hour_min'] = "17:30"
            # del working
            # continue
        del working['action']
        del working['year_month_day']
        del working['dt_begin']
        del working['dt_end']
    result = {'working': month_working,
              'working_days': len(month_working),
              'work_type': work.type,
              'employee_name': employee.name,
              }

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def staff_version(request):
    """
    [관리자용 앱]:  앱 버전 확인
    - 마지막의 날짜(190111 - 2019.01.11)가 190401 보다 이후이면 업그레이드 메시지 리턴
    http://0.0.0.0:8000/customer/staff_version?v=A.1.0.0.190111
    GET
        v=A.1.0.0.190111

    response
        STATUS 200
        STATUS 551
        {
            'msg': '업그레이드가 필요합니다.'
            'url': 'http://...' # itune, google play update
        }
        STATUS 422 # 개발자 수정사항
            {'message': "ClientError: parameter 'v' 가 없어요'}
            {'message': 'v: A.1.0.0.190111 에서 A 가 잘못된 값이 들어왔어요'}
            {'message': '검사하려는 버전 값이 양식에 맞지 않습니다.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['v'])
    if not parameter_check['is_ok']:
        return status422(get_api(request),
                         {'message': '{}'.format(''.join([message for message in parameter_check['results']]))})
        # return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    version = parameter_check['parameters']['v']

    items = version.split('.')
    phone_type = items[0]
    if phone_type != 'A' and phone_type != 'i':
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': 'v: A.1.0.0.190111 에서 A 가 잘못된 값이 들어왔어요'})
    str_dt_ver = items[len(items) - 1]
    logSend('  version dt: {}'.format(str_dt_ver))
    try:
        dt_version = str_to_datetime('20' + str_dt_ver[:2] + '-' + str_dt_ver[2:4] + '-' + str_dt_ver[4:6])
    except Exception as e:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '검사하려는 버전 값이 양식에 맞지 않습니다.'})
    response_operation = requests.post(settings.OPERATION_URL + 'currentEnv', json={})
    logSend('  current environment', response_operation.status_code, response_operation.json())
    cur_env = response_operation.json()['env_list'][0]
    dt_check = str_to_datetime(
        cur_env['dt_android_mng_upgrade'] if phone_type == 'A' else cur_env['dt_iOS_mng_upgrade'])
    logSend('  DB dt_check: {} vs dt_version: {}'.format(dt_check, dt_version))
    if dt_version < dt_check:
        url_android = "https://play.google.com/store/apps/details?id=com.ddtechi.aegis.manager"
        url_iOS = "https://apps.apple.com/kr/app/keullaesi-obeu-keullaen/id1468894636"
        url_install = ""
        if phone_type == 'A':
            url_install = url_android
        elif phone_type == 'i':
            url_install = url_iOS
        return REG_551_AN_UPGRADE_IS_REQUIRED.to_json_response({'url': url_install  # itune, google play update
                                                                })
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def staff_fg(request):
    """
    [관리자용 앱]:  background to foreground action (push 등의 내용을 가져온다.)
    - session 사용 - 마지막 로그인 후 30분간 계속 세션 유지
    - login_id, login_pw 는 앱 저장한다.
    - 응답에 work list 만 온다.
    - 각 work 의 날짜별 근로자 출퇴근 시간은 staff_employees_at_day 를 이용한다.
    - work 가 아직 시작되지 않았으면 staff_employees 를 이용한다.
    http://0.0.0.0:8000/customer/staff_fg?login_id=think&login_pw=happy_day!!!
    GET
        login_id=abc
        login_pw=password
        token=...
        pType = 10      # 10: 아이폰, 20: 안드로이드
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "staff_id": "암호화된 id"         # 이 값을 가지고 있다가 앱에서 모든 API 에 넣어주어야 한다.
              "works": [                      # 업무
                {
                  "name": "대덕기공 출입시스템 비콘 점검(주간 오전)",    # 업무 이름 : 사업장(대덕기공) + 업무(출입시스템 비콘 점검) + 형식(주간 오전)
                  "work_id": "qgf6YHf1z2Fx80DR8o_Lvg",          # 업무 식별자
                  "staff_name": "이요셉",                         # 업무 담당자 이름 (앱 사용 본인)
                  "staff_phone": "010-2450-5942",               # 업무 담당자 전화번호
                  "dt_begin": "2019-04-02 00:00:00",    # 업무 시작일: 아직 업무 시작 전 상태로 정의한다.
                  "dt_end": "2019-06-02 00:00:00",
                },
                ...  # 다른 work
              ]
            }
        STATUS 530
            {'message': '아이디가 없습니다.'}
            {'message': '비밀번호가 틀렸습니다.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'login_id\' 가 없어요'}
            {'message':'ClientError: parameter \'login_pw\' 가 없어요'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['login_id', 'login_pw', 'token_@', 'pType_@'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

    login_id = parameter_check['parameters']['login_id']
    login_pw = parameter_check['parameters']['login_pw']
    token = parameter_check['parameters']['token']
    pType = parameter_check['parameters']['pType']

    staffs = Staff.objects.filter(login_id=login_id)
    if len(staffs) == 0:
        result = {'message': '아이디가 없습니다.'}
        logError(get_api(request), result['message'])
        return REG_530_ID_OR_PASSWORD_IS_INCORRECT.to_json_response(result)
    elif len(staffs) > 1:
        logError(get_api(request), ' ServerError: \'{}\' 중복된 id'.format(login_id))

    staffs = Staff.objects.filter(login_id=login_id, login_pw=hash_SHA256(login_pw))
    if len(staffs) != 1:
        result = {'message': '비밀번호가 틀렸습니다.'}
        logError(get_api(request), result['message'])
        return REG_530_ID_OR_PASSWORD_IS_INCORRECT.to_json_response(result)

    app_user = staffs[0]
    app_user.is_app_login = True
    app_user.dt_app_login = datetime.datetime.now()
    if token is None or pType is None:
        app_user.push_token = "Staff_token_is_None"
    else:
        app_user.push_token = token
        app_user.pType = pType
    if 'HTTP_AV' in request.META:
        logSend(request.META['HTTP_AV'])
        app_user.app_version = request.META['HTTP_AV']
    app_user.save()
    # request.session['id'] = app_user.id
    # request.session.save()

    logSend('  이름: {}, id: {}, 회사 id: {}'.format(app_user.name, app_user.id, app_user.co_id))
    dt_today = datetime.datetime.now()
    # 업무 추출
    # 사업장 조회 - 사업장을 관리자로 검색해서 있으면 그 사업장의 모든 업무를 볼 수 있게 한다.
    work_places = Work_Place.objects.filter(contractor_id=app_user.co_id, manager_id=app_user.id)
    logSend('  담당 사업장 리스트: {}'.format([work_place.name for work_place in work_places]))
    if len(work_places) > 0:
        arr_work_place_id = [work_place.id for work_place in work_places]
        logSend('  업무 id: {}'.format(arr_work_place_id))
        # 해당 사업장의 모든 업무 조회
        # works = Work.objects.filter(contractor_id=app_user.co_id, work_place_id__in=arr_work_place_id) # 협력업체가 수주하면 못찾음
        # works = Work.objects.filter(work_place_id__in=arr_work_place_id, dt_end__gt=dt_today)
        works = Work.objects.filter(work_place_id__in=arr_work_place_id,
                                    dt_end__gt=(dt_today - datetime.timedelta(days=40)))
    else:
        # works = Work.objects.filter(contractor_id=app_user.co_id, staff_id=app_user.id) # 협력업체가 수주하면 못찾음
        works = Work.objects.filter(staff_id=app_user.id, dt_end__gt=(dt_today - datetime.timedelta(days=3)))
        # works = Work.objects.filter(staff_id=app_user.id)
        logSend('  app_user id: {}'.format(app_user.id))
    logSend('  업무 리스트: {}'.format(
        [(work.staff_name, work.work_place_name + ' ' + work.name + '(' + work.type + ')') for work in works]))
    # 관리자, 현장 소장의 소속 업무 조회 완료
    arr_work = []
    for work in works:
        linefeed = '\n' if len(work.work_place_name) + len(work.name) + len(work.type) > 9 else ' '
        work_dic = {'name': work.work_place_name + linefeed + work.name + '(' + work.type + ')',
                    'work_id': AES_ENCRYPT_BASE64(str(work.id)),
                    'staff_name': work.staff_name,
                    'staff_phone': phone_format(work.staff_pNo),
                    'dt_begin': work.dt_begin.strftime("%Y-%m-%d %H:%M:%S"),
                    'dt_end': work.dt_end.strftime("%Y-%m-%d %H:%M:%S"),
                    'is_start_work': True if work.dt_begin < datetime.datetime.now() else False,
                    }
        # 가상 데이터 생성
        # work_dic = virtual_work(isWorkStart, work_dic)
        arr_work.append(work_dic)
    result = {'staff_id': AES_ENCRYPT_BASE64(str(app_user.id)),
              'works': arr_work
              }

    return REG_200_SUCCESS.to_json_response(result)


def virtual_employee(isWorkStart, employee) -> dict:
    if isWorkStart:
        employee['is_accept_work'] = '수락'
        if random.randint(0, 100) > 90:
            employee['dt_begin'] = (datetime.datetime.now() + datetime.timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
            return employee
        dt_today = datetime.datetime.now().strftime("%Y-%m-%d")
        overtime = random.randint(0, 4) * 30
        employee['overtime'] = str(overtime)
        dt_begin = datetime.datetime.strptime(dt_today + ' 08:35:00', "%Y-%m-%d %H:%M:%S")
        dt_end = datetime.datetime.strptime(dt_today + ' 17:25:00', "%Y-%m-%d %H:%M:%S") + datetime.timedelta(
            minutes=overtime)
        employee['dt_begin_beacon'] = (dt_begin - datetime.timedelta(minutes=random.randint(0, 3) * 5 + 15)).strftime(
            "%Y-%m-%d %H:%M:%S")
        employee['dt_end_beacon'] = (dt_end + datetime.timedelta(minutes=random.randint(0, 3) * 5 + 15)).strftime(
            "%Y-%m-%d %H:%M:%S")
        employee['dt_begin_touch'] = (dt_begin - datetime.timedelta(minutes=random.randint(0, 3) * 5)).strftime(
            "%Y-%m-%d %H:%M:%S")
        employee['dt_end_touch'] = (dt_end + datetime.timedelta(minutes=random.randint(0, 3) * 5 + 15)).strftime(
            "%Y-%m-%d %H:%M:%S")
        employee['x'] = 35.4812 + float(random.randint(0, 100)) / 1000.
        employee['y'] = 129.4230 + float(random.randint(0, 100)) / 1000.
    else:
        t = random.randint(0, 10)
        employee['dt_begin'] = (datetime.datetime.now() + datetime.timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        employee['dt_end'] = (datetime.datetime.now() + datetime.timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
        logSend(t, employee['is_accept_work'])
    return employee


def virtual_work(isWorkStart, work) -> dict:
    if isWorkStart:
        work['dt_begin'] = (datetime.datetime.now() - datetime.timedelta(days=9)).strftime("%Y-%m-%d %H:%M:%S")
    else:
        work['dt_begin'] = (datetime.datetime.now() + datetime.timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    return work


@cross_origin_read_allow
def staff_update_me(request):
    """
    [관리자용 앱]: 자기정보 update
        - 2020/07/07 is_push_touch 만 사
        주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
        response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/staff_update_me?id=&login_id=temp_1&before_pw=A~~~8282&login_pw=&name=박종기&position=이사&department=개발&phone_no=010-2557-3555&phone_type=10&push_token=unknown&email=thinking@ddtechi.com
    POST
        staff_id = 앱 사용자의 식별 id
        is_push_touch = 0          # 0: NO (default) 1: YES

        ----- 이하 아직 사용하지 않는다.
        'id': '암호화된 id',           # 아래 login_id 와 둘 중의 하나는 필수
        'login_id': 'id 로 사용된다.',  # 위 id 와 둘 중의 하나는 필수
        'before_pw': '기존 비밀번호',     # 필수
        'login_pw': '변경하려는 비밀번호',   # 사전에 비밀번호를 확인할 것
        'name': '이름',
        'position': '직책',
        'department': '부서 or 소속',
        'phone_no': '전화번호',
        'phone_type': '전화 종류', # 10:iPhone, 20: Android
        'push_token': 'token',
        'email': 'id@ddtechi.com'
    response
        STATUS 200
        STATUS 422
            {'message': 'ClientError: parameter \'staff_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'work_id\' 가 없어요'}
            {'message': 'is_push_touch 는 0/1 중 하나입니다.'}
            {'message': 'ServerError: 직원으로 등록되어 있지 않거나 중복되었다.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'is_push_touch'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    staff_id = int(parameter_check['parameters']['staff_id'])
    is_push_touch = int(parameter_check['parameters']['is_push_touch'])
    if (is_push_touch < 0) or (1 < is_push_touch):
        return status422(get_api(request), {'message': 'is_push_touch 는 0/1 중 하나입니다.'})

    try:
        staff = Staff.objects.get(id=staff_id)
    except Exception as e:
        message = ' ServerError: Staff 에 staff_id={} 이(가) 없거나 중복됨'.format(staff_id)
        send_slack('customer/staff_update_me', message, channel='#server_bug')
        return status422(get_api(request), {'message': 'ServerError: 직원으로 등록되어 있지 않거나 중복되었다.'})
    staff.is_push_touch = True if (is_push_touch == 1) else False
    # logSend('   > staff.is_push_touch: {}, staff.id:{}, name: {}'.format(staff.is_push_touch, staff.id, staff.name))
    staff.save()

    return REG_200_SUCCESS.to_json_response()

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
        return REG_531_PASSWORD_IS_INCORRECT.to_json_response()

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

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
# @session_is_none_403
def staff_employees_at_day(request):
    """
    출근이 시작된 업무의 날짜별 근로자의 출퇴근 시간 요청
    - 출퇴근 정보 있음
    - 중요 포인트: 출퇴근 시간, 연장근무 여부(연장 근무가 1 이상이면 이름을 파란색으로 표시)
    http://0.0.0.0:8000/customer/staff_employees_at_day?staff_id=ryWQkNtiHgkUaY_SZ1o2uA&work_id=ryWQkNtiHgkUaY_SZ1o2uA&year_month_day=2019-04-23
    POST
        staff_id : 앱 사용자의 식별 id
        work_id : 업무 id
        year_month_day : 2019-04-08   # 근무 내역을 알고 싶은 날짜
    response
        STATUS 200
        {
          "message": "정상적으로 처리되었습니다.",
          "year_month_day":"2019-04-23",
          "employees": [
            {
              "is_accept_work": "수락",
              "employee_id": "iZ_rkELjhh18ZZauMq2vQw",
              "name": "최재환",
              "phone": "010-4871-8362",
              "dt_begin": "2019-03-01 00:00:00",
              "dt_end": "2019-07-31 00:00:00",
              "dt_begin_beacon": "2019-04-23 08:19:00",
              "dt_end_beacon": "2019-04-23 17:43:00",
              "dt_begin_touch": "2019-04-23 08:26:00",
              "dt_end_touch": "2019-04-23 17:39:00",
              "overtime": 0,
              "x": null,
              "y": null,
              "the_zone_code": "202001002",
              "action": 110
            },
            ...... # 다른 근로자 정보
          ]
        }
        STATUS 422 # 개발자 수정사항
            {'message': 'ClientError: parameter \'staff_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'work_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'year_month_day\' 가 없어요'}
            {'message': 'ClientError: parameter \'staff_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}

            {'message': 'ServerError: 직원으로 등록되어 있지 않거나 중복되었다.'}
            {'message': 'ServerError: 업무가 등록되어 있지 않거나 중복되었다.'}
            {'message': '아직 업무가 아직 시직되지 않았습니다. >> staff_employee'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'work_id_!', 'year_month_day'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

    staff_id = parameter_check['parameters']['staff_id']
    work_id = parameter_check['parameters']['work_id']
    year_month_day = parameter_check['parameters']['year_month_day']

    staffs = Work.objects.filter(id=staff_id)
    if len(staffs) == 0:
        logError(get_api(request), ' ServerError: Staff 에 staff_id={} 이(가) 없거나 중복됨'.format(staff_id))
        return status422(get_api(request), {'message': 'ServerError: 직원으로 등록되어 있지 않거나 중복되었다.'})

    works = Work.objects.filter(id=work_id)
    if len(works) == 0:
        logError(get_api(request), ' ServerError: Work 에 work_id={} 이(가) 없거나 중복됨'.format(work_id))
        return status422(get_api(request), {'message': 'ServerError: 업무가 등록되어 있지 않거나 중복되었다.'})
    work = works[0]

    is_work_begin = True if work.dt_begin < datetime.datetime.now() else False
    logSend(work.dt_begin, ' ', datetime.datetime.now(), ' ', is_work_begin)
    if not is_work_begin:
        return status422(get_api(request), {'message': '아직 업무가 시직되지 않음 >> staff_employee'})

    dt_target_day = str_to_datetime(year_month_day)
    employee_list = Employee.objects.filter(work_id=work.id)
    employee_ids = []
    for employee in employee_list:
        if employee.dt_begin < datetime.datetime.now():
            # 업무가 시작된 근로자 중에 응답이 없거나 거절한 근로자 삭제
            if not (employee.is_accept_work == 1):
                # 업무를 수락하지 않은 근로자 제외
                continue
            if employee.dt_end < dt_target_day:
                # 업무 종료된 근로자 표시에서 제외
                # logError(
                #     ' 업무 종료 근로자: {} {} {}'.format(employee.name, employee.pNo, dt_str(employee.dt_end, "%Y-%m-%d")))
                continue
        employee_ids.append(AES_ENCRYPT_BASE64(str(employee.employee_id)))
    # employee_ids = [AES_ENCRYPT_BASE64(str(employee.employee_id)) for employee in employee_list]
    employees_infor = {'employees': employee_ids,
                       'year_month_day': year_month_day,
                       'work_id': AES_ENCRYPT_BASE64(work_id),
                       # 'work_id': AES_ENCRYPT_BASE64('-1'),
                       }
    r = requests.post(settings.EMPLOYEE_URL + 'pass_record_of_employees_in_day_for_customer', json=employees_infor)
    if len(r.json()['fail_list']):
        logError(get_api(request),
                 ' pass_record_of_employees_in_day_for_customer FAIL LIST {}'.format(r.json()['fail_list']))
    pass_records = r.json()['employees']
    fail_list = r.json()['fail_list']
    pass_record_dic = {}
    for pass_record in pass_records:
        employee_id = int(AES_DECRYPT_BASE64(pass_record['passer_id']))
        pass_record_dic[employee_id] = pass_record
    logSend('  - pass record: {}'.format(pass_record_dic))
    arr_employee = []
    for employee in employee_list:
        logSend('  - employee employee_id: {}'.format(employee.employee_id))
        if employee.dt_end < dt_target_day:
            logError(' 업무 종료 근로자: {} {} {}'.format(employee.name, employee.pNo, dt_str(employee.dt_end, "%Y-%m-%d")))
            continue
        employee_dic = {
            'is_accept_work': '응답 X' if employee.is_accept_work is None else '수락' if employee.is_accept_work == 1 else '거절' if employee.is_accept_work == 0 else '답변시한',
            'employee_id': AES_ENCRYPT_BASE64(str(employee.id)),
            'name': employee.name,
            'phone': phone_format(employee.pNo),
            'dt_begin': dt_null(employee.dt_begin),
            'dt_end': dt_null(employee.dt_end),
            # 'dt_begin_beacon': pass_record['dt_in'],
            # 'dt_end_beacon': pass_record['dt_out'],
            # 'dt_begin_touch': pass_record['dt_in_verify'],
            # 'dt_end_touch': pass_record['dt_out_verify'],
            # 'overtime': pass_record['overtime'],
            # 'x': pass_record['x'],
            # 'y': pass_record['y'],
            'the_zone_code': employee.the_zone_code
        }
        try:
            pass_record = pass_record_dic[employee.employee_id]
            employee_dic['dt_begin_beacon'] = pass_record['dt_in']
            employee_dic['dt_end_beacon'] = pass_record['dt_out']
            employee_dic['dt_begin_touch'] = pass_record['dt_in_verify']
            employee_dic['dt_end_touch'] = pass_record['dt_out_verify']
            employee_dic['overtime'] = pass_record['overtime']
            employee_dic['x'] = pass_record['x']
            employee_dic['y'] = pass_record['y']
        except Exception as e:
            logError(get_api(request),
                     ' pass_record_dic[employee.employee_id] - employee_id: {} ({})'.format(employee.employee_id, e))
            employee_dic['dt_begin_beacon'] = None
            employee_dic['dt_end_beacon'] = None
            employee_dic['dt_begin_touch'] = None
            employee_dic['dt_end_touch'] = None
            employee_dic['overtime'] = 0
            employee_dic['x'] = None
            employee_dic['y'] = None

        arr_employee.append(employee_dic)
    result = {'year_month_day': year_month_day,
              'employees': arr_employee,
              'fail_list': fail_list,
              }

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
# @session_is_none_403
def staff_employees_at_day_v2(request):
    """
    출근이 시작된 업무의 날짜별 근로자의 출퇴근 시간 요청
    - 출퇴근 정보 있음
    - 중요 포인트: 출퇴근 시간, 연장근무 여부(연장 근무가 1 이상이면 이름을 파란색으로 표시)
    http://0.0.0.0:8000/customer/staff_employees_at_day_v2?staff_id=ryWQkNtiHgkUaY_SZ1o2uA&work_id=ryWQkNtiHgkUaY_SZ1o2uA&year_month_day=2019-04-23
    POST
        staff_id : 앱 사용자의 식별 id
        work_id : 업무 id
        year_month_day : 2019-04-08   # 근무 내역을 알고 싶은 날짜
    response
        STATUS 200
            {
                "message": "정상적으로 처리되었습니다.",
                "year_month_day": "2020-02-20",
                "employees": [
                    {
                  "is_accept_work": '수락',  # '응답 X', '거절', '답변시한'
                        "employee_id": "45E0n8g8QqeppqJBYkXRHA",
                        "name": "박종기",
                        "phone": "010-2557-3555",
                        "dt_begin": "2020-02-06 00:00:00",
                        "dt_end": "2020-03-31 00:00:00",
                        "the_zone_code": "202011003",
                        "notification": 2,                      # 0: 근로자가 확인하지 않은 알림 있음 (이름: 파랑), 2: 근로자가 거절한 알림 임음 (이름 빨강)
                        "week": "목",                            # 요일
                        "day_type": 2,                          # 이날의 근무 형태 0: 유급휴일, 1: 무급휴일, 2: 소정근무일
                        "day_type_description": "소정근무일",      # 근무 형태 설명
                        "dt_begin_beacon": "2020-02-20 08:32:00",
                        "dt_end_beacon": "2020-02-20 17:32:00",
                        "dt_begin_touch": "2020-02-20 08:29:00",
                        "dt_end_touch": "2020-02-20 17:33:00",
                        "overtime": 0,
                        "x": null,
                        "y": null
                    },
                    ......
                ],
                "fail_list": {
                    "fail_employee_passer_id_list": [
                        262
                    ]
                }
            }
        STATUS 422 # 개발자 수정사항
            {'message': 'ClientError: parameter \'staff_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'work_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'year_month_day\' 가 없어요'}
            {'message': 'ClientError: parameter \'staff_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}

            {'message': 'ServerError: 직원으로 등록되어 있지 않거나 중복되었다.'}
            {'message': 'ServerError: 업무가 등록되어 있지 않거나 중복되었다.'}
            {'message': '아직 업무가 아직 시직되지 않았습니다. >> staff_employee'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'work_id_!', 'year_month_day'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

    staff_id = parameter_check['parameters']['staff_id']
    work_id = parameter_check['parameters']['work_id']
    year_month_day = parameter_check['parameters']['year_month_day']

    staffs = Work.objects.filter(id=staff_id)
    if len(staffs) == 0:
        logError(get_api(request), ' ServerError: Staff 에 staff_id={} 이(가) 없거나 중복됨'.format(staff_id))
        return status422(get_api(request), {'message': 'ServerError: 직원으로 등록되어 있지 않거나 중복되었다.'})

    works = Work.objects.filter(id=work_id)
    if len(works) == 0:
        logError(get_api(request), ' ServerError: Work 에 work_id={} 이(가) 없거나 중복됨'.format(work_id))
        return status422(get_api(request), {'message': 'ServerError: 업무가 등록되어 있지 않거나 중복되었다.'})
    work = works[0]

    is_work_begin = True if work.dt_begin < datetime.datetime.now() else False
    logSend(work.dt_begin, ' ', datetime.datetime.now(), ' ', is_work_begin)
    if not is_work_begin:
        return status422(get_api(request), {'message': '아직 업무가 시직되지 않음 >> staff_employee'})

    dt_target_day = str_to_datetime(year_month_day)
    # employee_list = Employee.objects.filter(work_id=work.id, dt_begin__lt=dt_target_day + timedelta(days=1), dt_end__gt=dt_target_day)
    employee_list = Employee.objects.filter(work_id=work.id, dt_end__gt=dt_target_day)
    logSend('  > employee_list: {}'.format([employee.id for employee in employee_list]))
    employee_ids = []
    for employee in employee_list:
        #
        # 2020-06-17 임시로 업무가 시작되었지만 답변거부, 응답전, 답변시한지남 모두 표시
        #
        # if not (employee.is_accept_work == 1):  # None: 응답 전 상태, 0: 업무를 거부, 1: 업무에 승락, 2: 답변시한 지남
        #     # 업무를 수락하지 않은 근로자를 표시하지 않게 한다.
        #     continue
        employee_ids.append(AES_ENCRYPT_BASE64(str(employee.employee_id)))
    # employee_ids = [AES_ENCRYPT_BASE64(str(employee.employee_id)) for employee in employee_list]
    employees_infor = {'employees': employee_ids,
                       'year_month_day': year_month_day,
                       'work_id': AES_ENCRYPT_BASE64(work_id),
                       # 'work_id': AES_ENCRYPT_BASE64('-1'),
                       }
    r = requests.post(settings.EMPLOYEE_URL + 'work_record_in_day_for_customer', json=employees_infor)
    if len(r.json()['fail_list']):
        logError(get_api(request),
                 ' work_record_in_day_for_customer FAIL LIST {}'.format(r.json()['fail_list']))
    pass_records = r.json()['employees']
    fail_list = r.json()['fail_list']
    logSend('  > fail_list: {}'.format(fail_list))
    pass_record_dic = {}
    for pass_record in pass_records:
        employee_id = int(AES_DECRYPT_BASE64(pass_record['passer_id']))
        pass_record_dic[employee_id] = pass_record
    logSend('  - pass record: {}'.format(pass_record_dic))
    arr_employee = []
    for employee in employee_list:
        logSend('  - employee employee_id: {}, is_accept_work: {}'.format(employee.employee_id, employee.is_accept_work))
        if employee.employee_id not in pass_record_dic.keys():
            logSend('  > 근로자 서버에서 지정한 근로자 근로내역이 없다.: {} {} {}'.format(employee.name, employee.pNo, dt_str(employee.dt_end, "%Y-%m-%d")))
            continue
        if employee.dt_end < dt_target_day:
            logError(' 업무 종료 근로자: {} {} {}'.format(employee.name, employee.pNo, dt_str(employee.dt_end, "%Y-%m-%d")))
            continue
        employee_dic = {
            'is_accept_work': '응답 X' if employee.is_accept_work is None else '수락' if employee.is_accept_work == 1 else '거절' if employee.is_accept_work == 0 else '답변시한',            'employee_id': AES_ENCRYPT_BASE64(str(employee.id)),
            'name': employee.name,
            'phone': phone_format(employee.pNo),
            'dt_begin': dt_null(employee.dt_begin),
            'dt_end': dt_null(employee.dt_end),
            # 'dt_begin_beacon': pass_record['dt_in'],
            # 'dt_end_beacon': pass_record['dt_out'],
            # 'dt_begin_touch': pass_record['dt_in_verify'],
            # 'dt_end_touch': pass_record['dt_out_verify'],
            # 'overtime': pass_record['overtime'],
            # 'x': pass_record['x'],
            # 'y': pass_record['y'],
            'the_zone_code': employee.the_zone_code,
        }
        try:
            pass_record = pass_record_dic[employee.employee_id]
            employee_dic['notification'] = pass_record['notification']
            employee_dic['week'] = pass_record['week']
            employee_dic['day_type'] = pass_record['day_type']
            employee_dic['day_type_description'] = pass_record['day_type_description']

            employee_dic['dt_begin_beacon'] = pass_record['dt_in']
            employee_dic['dt_end_beacon'] = pass_record['dt_out']
            employee_dic['dt_begin_touch'] = pass_record['dt_in_verify']
            employee_dic['dt_end_touch'] = pass_record['dt_out_verify']
            employee_dic['overtime'] = pass_record['overtime']
            employee_dic['x'] = pass_record['x']
            employee_dic['y'] = pass_record['y']
        except Exception as e:
            logError(get_api(request),
                     ' pass_record_dic[employee.employee_id] - employee_id: {} ({})'.format(employee.employee_id, e))
            employee_dic['notification'] = None
            employee_dic['week'] = None
            employee_dic['day_type'] = None
            employee_dic['day_type_description'] = None

            employee_dic['dt_begin_beacon'] = None
            employee_dic['dt_end_beacon'] = None
            employee_dic['dt_begin_touch'] = None
            employee_dic['dt_end_touch'] = None
            employee_dic['overtime'] = 0
            employee_dic['x'] = None
            employee_dic['y'] = None

        arr_employee.append(employee_dic)
    result = {'year_month_day': year_month_day,
              'employees': arr_employee,
              'fail_list': fail_list,
              }
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
# @session_is_none_403
def staff_employees(request):
    """
    요청: 근로자 업무 참여 여부: 업무가 시작되기 전인 근로자
    - 출퇴근 정보 없음
    - 근로자의 응답이 중요 포인트 is_accept_work, name

    http://0.0.0.0:8000/customer/staff_employees?staff_id=ryWQkNtiHgkUaY_SZ1o2uA&work_id=4dnQVYFTi501mmdz6hX6CA
    POST
        staff_id : 앱 사용자의 식별 id
        work_id : 업무 id
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "employees": [
                {
                  "is_accept_work": '응답 X',  # '수락', '거절', '답변시한'
                  "employee_id": "iZ_rkELjhh18ZZauMq2vQw",
                  "name": "-----",
                  "phone": "010-4871-8362",
                  "dt_begin": "2019-04-25 00:00:00",
                  "dt_end": "2019-07-31 00:00:00",
                  "x": null,
                  "y": null
                },
                ...... # 다른 근로자 정보
              ]
            }
        STATUS 422 # 개발자 수정사항
            {'message': 'ClientError: parameter \'staff_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'work_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'staff_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}

            {'message': 'ServerError: 등록되지 않은 관리자 입니다.'}
            {'message': 'ServerError: 등록되지 않은 업무 입니다.'}
            {'message': '이미 업무가 시직되었습니다. >> staff_employees_at_day'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'work_id_!'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    staff_id = int(parameter_check['parameters']['staff_id'])
    work_id = int(parameter_check['parameters']['work_id'])

    staffs = Staff.objects.filter(id=staff_id)
    if len(staffs) == 0:
        logError(get_api(request), ' ServerError: Staff 에 staff_id=[{}] 이(가) 없다'.format(staff_id))
        return status422(get_api(request), {'message': 'ServerError: 등록되지 않은 관리자 입니다.'})

    works = Work.objects.filter(id=work_id)
    if len(works) == 0:
        logError(get_api(request), ' ServerError: Work 에 work_id={} 이(가) 없거나 중복됨'.format(work_id))
        return status422(get_api(request), {'message': 'ServerError: 등록되지 않은 업무 입니다.'})
    work = works[0]

    is_work_begin = True if work.dt_begin < datetime.datetime.now() else False
    if is_work_begin:
        return status422(get_api(request), {'message': '이미 업무가 시직되었습니다. >> staff_employees_at_day'})

    employees = Employee.objects.filter(work_id=work.id)
    arr_employee = []
    for employee in employees:
        employee_dic = {
            'is_accept_work': '응답 X' if employee.is_accept_work is None else '수락' if employee.is_accept_work == 1 else '거절' if employee.is_accept_work == 0 else '답변시한',
            'employee_id': AES_ENCRYPT_BASE64(str(employee.id)),
            'name': employee.name,
            'phone': phone_format(employee.pNo),
            'dt_begin': dt_null(employee.dt_begin),
            'dt_end': dt_null(employee.dt_end),
            # 'dt_begin_beacon': dt_null(employee.dt_begin_beacon),
            # 'dt_end_beacon': dt_null(employee.dt_end_beacon),
            # 'dt_begin_touch': dt_null(employee.dt_begin_touch),
            # 'dt_end_touch': dt_null(employee.dt_end_touch),
            # 'overtime': employee.overtime,
            'x': employee.x,
            'y': employee.y,
        }
        arr_employee.append(employee_dic)
    result = {'employees': arr_employee}

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
# @session_is_none_403
def staff_month_notifications(request):
    """
    요청: 업무의 월 알림 내역
    - 관리자 앱의 날짜를 선택 >> 달력을 보여주고 달력에 알림이 있으면 표시한다.
    http://0.0.0.0:8000/customer/staff_month_notifications?staff_id=ryWQkNtiHgkUaY_SZ1o2uA&work_id=4dnQVYFTi501mmdz6hX6CA
    POST
        staff_id: ryWQkNtiHgkUaY_SZ1o2uA    # 앱 사용자 id
        work_id: ryWQkNtiHgkUaY_SZ1o2uA     # 업무 id
        year_month: 2020-06                 # 년월
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "notification_dict": {
                "01": {
                    "year_month_day": 2020-07-01,   # 년월일
                    "notification_all": 3,          # 알림 갯수: 모든 알림 갯수
                    "notification_before": 1,       # 알림 갯수: 확인 안한 알림
                    "notification_reject": 1,       # 알림 갯수: 거부한 갯수
                    "notification_timeover": 1,     # 알림 갯수: 답변시한이 지난 갯수
                    },
                ......  # 다른 날짜
              }
            }
        STATUS 422 # 개발자 수정사항
            {'message': 'ClientError: parameter \'staff_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'work_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'staff_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}

            {'message': 'ServerError: 등록되지 않은 관리자 입니다.'}
            {'message': 'ServerError: 등록되지 않은 업무 입니다.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'work_id_!', 'year_month'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    staff_id = int(parameter_check['parameters']['staff_id'])
    work_id = int(parameter_check['parameters']['work_id'])

    try:
        staff = Staff.objects.get(id=staff_id)
    except Exception as e:
        return status422(get_api(request), {'message': 'ServerError: 등록되지 않은 관리자 입니다.'})
    try:
        work = Work.objects.filter(id=work_id)
    except Exception as e:
        return status422(get_api(request), {'message': 'ServerError: 등록되지 않은 업무 입니다.'})

    parameters = {
        "work_id": rqst['work_id'],
        "year_month": rqst['year_month']
    }
    s = requests.session()
    r = s.post(settings.EMPLOYEE_URL + 'month_notifications', json=parameters)
    if r.status_code != 200:
        return ReqLibJsonResponse(r)
    return REG_200_SUCCESS.to_json_response({'notification_dict': r.json()['noti_no_dict']})


@cross_origin_read_allow
def staff_bg(request):
    """
    [관리자용 앱]:  foreground to background (서버로 전송할 내용이 있으면 전송하다.)
    - session 으로 처리
    http://0.0.0.0:8000/customer/staff_bg
    POST
    response
        STATUS 200
        STATUS 403
            {'message': '로그아웃되었습니다.\n다시 로그인해주세요.'}
    """

    if (request.session is None) or (not 'id' in request.session):
        return REG_403_FORBIDDEN.to_json_response()

    staff_id = request.session['id']
    app_users = Staff.objects.filter(id=staff_id)
    if len(app_users) != 1:
        logError('ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id))
    app_user = app_users[0]
    app_user.is_app_login = False
    app_user.dt_app_login = datetime.datetime.now()
    app_user.save()

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def staff_background(request):
    """
    [관리자용 앱]:  foreground to background (서버로 전송할 내용이 있으면 전송하다.)
    - 로그인 할때 받았던 id 를 보낸다.
    - id >> staff_id  사용 통일성을 위해 변경
    http://0.0.0.0:8000/customer/staff_background?staff_id=qgf6YHf1z2Fx80DR8o_Lvg
    POST
        staff_id=암호화된 id  # foreground 에서 받은 식별id
    response
        STATUS 200
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'id\' 가 없어요'}
            {'message':'ClientError: parameter \'id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['staff_id_!'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    staff_id = parameter_check['parameters']['staff_id']

    app_users = Staff.objects.filter(id=staff_id)
    if len(app_users) != 1:
        return status422(get_api(request),
                         {'message': 'ServerError: Staff 에 staff_id={} 이(가) 없거나 중복됨'.format(staff_id)})

    app_user = app_users[0]
    app_user.is_app_login = False
    app_user.dt_app_login = datetime.datetime.now()
    app_user.save()

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def staff_employees_from_work(request):
    """
    [관리자용 앱]:  다른 날짜의 근로 내역 요청
    - 담당자(현장 소장, 관리자), 업무, 근로내역 날짜
    - 근로내역 날짜가 업무의 날짜 범위 밖이면 STATUS 416
    - 주) 보낸 날짜의 근로 내역이 없으면 employees:[] 온다.
    http://0.0.0.0:8000/customer/staff_employees_from_work?id=qgf6YHf1z2Fx80DR8o_Lvg&work_id=qgf6YHf1z2Fx80DR8o_Lvg&day=2019-04-12
    POST
        staff_id : 현장관리자 id     # foreground 에서 받은 현장 관리자의 암호화된 식별 id
        work_id : 업무 id     # foreground 에서 받은 업무의 암호화된 식별 id
        day : "2019-04-12"  # 근로내역 날짜
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "dt_work": "2019-04-12"
              "emplyees": [
                {
                  "is_accept_work": '응답 X',  # '수락', '거절', '답변시한'
                  "employee_id": "i52bN-IdKYwB4fcddHRn-g",
                  "name": "근로자",
                  "phone": "010-3333-4444",
                  "dt_begin": "2019-03-10 14:46:04",
                  "dt_end": "2019-05-09 00:00:00",
                  "dt_begin_beacon": "2019-04-14 08:10:00",
                  "dt_end_beacon": "2019-04-14 18:55:00",
                  "dt_begin_touch": "2019-04-14 08:20:00",
                  "dt_end_touch": "2019-04-14 18:45:00",
                  "overtime": "60",
                  "x": 35.5602,
                  "y": 129.446
                },
                ...
              ],
            }
        STATUS 416
            {'message':'업무 날짜 밖의 근로 내역 요청'}  # 앱에서 근로 날짜로 처리해서 나타나지 않게 한다.
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'id\' 가 없어요'}
            {'message':'ClientError: parameter \'work_id\' 가 없어요'}
            {'message':'ClientError: parameter \'day\' 가 없어요'}
            {'message':'ClientError: parameter \'id\' 가 정상적인 값이 아니예요.'}
            {'message':'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)}
            {'message':'ServerError: Work 에 id={} 이(가) 없거나 중복됨'.format(work_id)}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'work_id_!', 'day'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

    staff_id = parameter_check['parameters']['staff_id']
    work_id = parameter_check['parameters']['work_id']
    day = parameter_check['parameters']['day']

    app_users = Staff.objects.filter(id=staff_id)
    if len(app_users) != 1:
        return status422(get_api(request),
                         {'message': 'ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)})
    works = Work.objects.filter(id=work_id)
    if len(works) != 1:
        return status422(get_api(request), {'message': 'ServerError: Work 에 id={} 이(가) 없거나 중복됨'.format(work_id)})
    app_user = app_users[0]
    work = works[0]
    if work.staff_id != app_user.id:
        # 업무 담당자와 요청자가 틀린 경우 - 사업장 담당자 일 수 도 있기 때문에 error 가 아니다.
        logSend('   ! 업무 담당자와 요청자가 틀림 - 사업장 담당자 일 수 도 있기 때문에 error 가 아니다.')
    target_day = datetime.datetime.strptime(day + ' 00:00:00', "%Y-%m-%d %H:%M:%S")
    logSend(target_day, ' ', work.dt_begin)
    if target_day < work.dt_begin:
        # 근로 내역을 원하는 날짜가 업무 시작일 보다 적은 경우 - 아직 업무가 시작되지도 않은 근로 내역을 요청한 경우
        logError(get_api(request), '416 업무 날짜 밖의 근로 내역 요청')
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무 날짜 밖의 근로 내역 요청'})

    employees = Employee.objects.filter(work_id=work.id)
    arr_employee = []
    for employee in employees:
        employee_dic = {
            'is_accept_work': '응답 X' if employee.is_accept_work is None else '수락' if employee.is_accept_work == 1 else '거절' if employee.is_accept_work == 0 else '답변시한',
            'employee_id': AES_ENCRYPT_BASE64(str(employee.employee_id)),
            'name': employee.name,
            'phone': phone_format(employee.pNo),
            'dt_begin': dt_null(employee.dt_begin),
            'dt_end': dt_null(employee.dt_end),
            # 'dt_begin_beacon': dt_null(employee.dt_begin_beacon),
            # 'dt_end_beacon': dt_null(employee.dt_end_beacon),
            # 'dt_begin_touch': dt_null(employee.dt_begin_touch),
            # 'dt_end_touch': dt_null(employee.dt_end_touch),
            # 'overtime': employee.overtime,
            'x': employee.x,
            'y': employee.y,
        }

        # 가상 데이터 생성
        employee_dic = virtual_employee(True, employee_dic)  # isWorkStart = True
        arr_employee.append(employee_dic)
    result = {'emplyees': arr_employee,
              'dt_work': target_day.strftime("%Y-%m-%d")
              }

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def staff_change_time(request):
    """
    [관리자용 앱]: 업무에 투입 중인 근로자 중에서 일부를 선택해서 근무시간(30분 연장, ...)을 변경할 때 호출
    - 담당자(현장 소장, 관리자), 업무, 변경 형태
    - 근로자 명단에서 체크하고 체크한 근로자 만 근무 변경
    - 오늘이 아니면 고칠 수 없음 - 오늘이 아니면 호출하지 말것.
    https://api-dev.aegisfac.com/customer/staff_change_time?id=qgf6YHf1z2Fx80DR8o_Lvg&work_id=_LdMng5jDTwK-LMNlj22Vw&overtime_type=-1
    http://0.0.0.0:8000/customer/staff_change_time?id=qgf6YHf1z2Fx80DR8o_Lvg&work_id=ryWQkNtiHgkUaY_SZ1o2uA&overtime_type=-1&employee_ids=qgf6YHf1z2Fx80DR8o_Lvg
    overtime 설명 (2019-07-21)
        연장 근무( -2: 연차, -1: 업무 끝나면 퇴근, 0: 정상 근무, 1~18: 연장 근무 시간( 1:30분, 2:1시간, 3:1:30, 4:2:00, 5:2:30, 6:3:00 7: 3:30, 8: 4:00, 9: 4:30, 10: 5:00, 11: 5:30, 12: 6:00, 13: 6:30, 14: 7:00, 15: 7:30, 16: 8:00, 17: 8:30, 18: 9:00)
    POST
        staff_id : 현장관리자 id  # foreground 에서 받은 암호화된 식별 id
        work_id : 업무 id
        year_month_day: 2019-05-09 # 처리할 날짜
        overtime_type : 0        # -2: 년차, -1: 업무 완료 조기 퇴근, 0: 표준 근무, 1: 30분 연장 근무, 2: 1시간 연장 근무, 3: 1:30 연장 근무, 4: 2시간 연장 근무, 5: 2:30 연장 근무, 6: 3시간 연장 근무
        employee_ids : [ 근로자_id_1, 근로자_id_2, 근로자_id_3, 근로자_id_4, 근로자_id_5, ...]
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "employees": [
                {
                  "is_accept_work": '응답 X',  # '수락', '거절', '답변시한'
                  "employee_id": "i52bN-IdKYwB4fcddHRn-g",
                  "name": "근로자",
                  "phone": "010-3333-4444",1
                  "dt_begin": "2019-03-10 14:46:04",
                  "dt_end": "2019-05-09 00:00:00",
                  "dt_begin_beacon": "2019-04-14 08:20:00",
                  "dt_end_beacon": "2019-04-14 18:20:00",
                  "dt_begin_touch": "2019-04-14 08:35:00",
                  "dt_end_touch": "2019-04-14 18:25:00",
                  "overtime": "30",
                  "x": 35.5362,
                  "y": 129.444,
                  "overtime_type": -1
                },
                ......
              ]
            }
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'staff_id\' 가 없어요'}
            {'message':'ClientError: parameter \'work_id\' 가 없어요'}
            {'message':'ClientError: parameter \'year_month_day\' 가 없어요'}
            {'message':'ClientError: parameter \'overtime_type\' 가 없어요'}
            {'message':'ClientError: parameter \'employee_ids\' 가 없어요'}
            {'message':'ClientError: parameter \'overtime_type\' 값이 범위(-1 ~ 6)를 넘었습니다.'}
            {'message':'ClientError: parameter \'staff_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)}
            {'message':'ServerError: Work 에 id={} 이(가) 없거나 중복됨'.format(work_id)}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst,
                                      ['staff_id_!', 'work_id_!', 'year_month_day', 'overtime_type', 'employee_ids'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

    staff_id = parameter_check['parameters']['staff_id']
    work_id = parameter_check['parameters']['work_id']
    year_month_day = parameter_check['parameters']['year_month_day']
    overtime_type = int(parameter_check['parameters']['overtime_type'])
    employee_ids = parameter_check['parameters']['employee_ids']

    if overtime_type < -2 or 18 < overtime_type:
        # 초과 근무 형태가 범위를 벗어난 경우
        return status422(get_api(request),
                         {'message': 'ClientError: parameter \'overtime_type\' 값이 범위(-2 ~ 18)를 넘었습니다.'})

    app_users = Staff.objects.filter(id=staff_id)
    if len(app_users) != 1:
        return status422(get_api(request),
                         {'message': 'ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)})
    app_user = app_users[0]
    works = Work.objects.filter(id=work_id)
    if len(works) != 1:
        return status422(get_api(request), {'message': 'ServerError: Work 에 id={} 이(가) 없거나 중복됨'.format(work_id)})
    work = works[0]
    if work.staff_id != app_user.id:
        # 업무 담당자와 요청자가 틀린 경우 - 사업장 담당자 일 수 도 있기 때문에 error 가 아니다.
        logSend('   ! 업무 담당자와 요청자가 틀림 - 사업장 담당자 일 수 도 있기 때문에 error 가 아니다.')

    if request.method == 'GET':
        employee_ids = rqst.getlist('employee_ids')

    # logSend(employee_ids)
    if len(employee_ids) == 0:
        # 연장근무 저장할 근로자 목록이 없다.
        logError(get_api(request), ' 근로자 연장 근무요청을 했는데 선택된 근로자({})가 없다?'.format(employee_ids))

        return REG_200_SUCCESS.to_json_response()
    # 암호화된 employee id 복호화
    employee_id_list = []
    for employee_id in employee_ids:
        if type(employee_id) == dict:
            employee_id_list.append(AES_DECRYPT_BASE64(employee_id['employee_id']))
        else:
            employee_id_list.append(int(AES_DECRYPT_BASE64(employee_id)))
    # logSend(employee_id_list)
    if len(employee_id_list) == 0:
        # 연장근무 저장할 근로자 목록이 없다.
        logError(get_api(request),
                 ' 근로자 연장 근무요청을 했는데 선택된 근로자({})가 없다? (암호화된 근로자 리스트에도 없다.)'.format(employee_id_list))

        return REG_200_SUCCESS.to_json_response()

    # 고객 서버의 employee 에서 요청된 근로자 선정
    employees = Employee.objects.filter(work_id=work.id, id__in=employee_id_list)
    # employee_ids = []
    # for employee in employees:
    #     employee_ids.append(AES_ENCRYPT_BASE64(str(employee.employee_id)))
    #
    # 근로자 서버의 근로자 정보에 연장 시간 변경한다.
    #
    employee_passer_ids = [AES_ENCRYPT_BASE64(str(employee.employee_id)) for employee in employees]
    employees_infor = {'employees': employee_passer_ids,
                       'year_month_day': year_month_day,
                       'work_id': AES_ENCRYPT_BASE64(work_id),
                       'overtime': overtime_type,
                       'overtime_staff_id': AES_ENCRYPT_BASE64(staff_id),
                       }
    r = requests.post(settings.EMPLOYEE_URL + 'pass_record_of_employees_in_day_for_customer', json=employees_infor)
    #
    # 근로자 서버에서 잘못된거 처리해야하는데... 바쁘다! 그래서 실패 내역만 보낸다. (어차피 근로자서버에 로그도 남는데...)
    #
    if len(r.json()['fail_list']):
        logError(get_api(request),
                 ' pass_record_of_employees_in_day_for_customer FAIL LIST {}'.format(r.json()['fail_list']))
    # 그럴리는 없지만 근로자 서버 처리 후 근로자 명단과 고객서버 근로자 명단을 비교처리해야하는데 로그만 남기는 걸로...
    # pass_records = r.json()['employees']
    fail_list = r.json()['fail_list']
    #
    # 근로자 서버의 근로자 처리했으니까 이제 고객 서버 처리하자.
    #
    arr_employee = []
    for employee in employees:
        employee.overtime = overtime_type
        employee.save()
        employee_dic = {
            'is_accept_work': '응답 X' if employee.is_accept_work is None else '수락' if employee.is_accept_work == 1 else '거절' if employee.is_accept_work == 0 else '답변시한',
            'employee_id': AES_ENCRYPT_BASE64(str(employee.employee_id)),
            'name': employee.name,
            'phone': phone_format(employee.pNo),
            'dt_begin': dt_null(employee.dt_begin),
            'dt_end': dt_null(employee.dt_end),
            # 'dt_begin_beacon': dt_null(employee.dt_begin_beacon),
            # 'dt_end_beacon': dt_null(employee.dt_end_beacon),
            # 'dt_begin_touch': dt_null(employee.dt_begin_touch),
            # 'dt_end_touch': dt_null(employee.dt_end_touch),
            # 'overtime': employee.overtime,
            'x': employee.x,
            'y': employee.y,
        }
        arr_employee.append(employee_dic)
    result = {'employees': arr_employee,
              'fail_list': fail_list
              }

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def staff_change_work_v2(request):
    """
    [관리자용 앱]: 업무 중인 근로자의 (근태정보 변경)을 실행한다.
    - 담당자(현장 소장, 관리자), 업무, 변경 형태
    - 근로자 명단에서 체크하고 체크한 근로자 만 근무 변경
    - 오늘부터 3일 전까지만 수정할 수 있다.
    overtime 설명 (2020-03-23)
        연장 근무( -4: 유급휴일 해제, -3: 유급휴일 지정, -2: 연차 휴무, -1: 조기 퇴근, 0: 정상 근무, 1~18: 연장 근무 시간( 1:30분, 2:1시간, 3:1:30, 4:2:00, 5:2:30, 6:3:00 7: 3:30, 8: 4:00, 9: 4:30, 10: 5:00, 11: 5:30, 12: 6:00, 13: 6:30, 14: 7:00, 15: 7:30, 16: 8:00, 17: 8:30, 18: 9:00)
    POST
        staff_id : 현장관리자 id      # foreground 에서 받은 암호화된 식별 id
        work_id : 업무 id           # 암호화된 id
        year_month_day: 2019-05-09 # 처리할 날짜
        overtime_type: 0           # -3: 반차휴무, -2: 연차휴무, -1: 조기 퇴근,
                                   # 0: 표준 근무, 1: 30분 연장 근무, 2: 1시간 연장 근무, ..., 18: 9시간 연장 근무
        employee_ids: [ 근로자_id_1, 근로자_id_2, 근로자_id_3, 근로자_id_4, 근로자_id_5, ...]
        comment: 연차휴무, 조기퇴근, 유급휴가 일 때 사유  # 유급휴일(주휴일)도 사유가 필요한가? 근로자 앱으로 push
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "employees": [
                {
                  "is_accept_work": true,
                  "employee_id": "i52bN-IdKYwB4fcddHRn-g",
                  "name": "근로자",
                  "phone": "010-3333-4444",1
                  "dt_begin": "2019-03-10 14:46:04",
                  "dt_end": "2019-05-09 00:00:00",
                  "dt_begin_beacon": "2019-04-14 08:20:00",
                  "dt_end_beacon": "2019-04-14 18:20:00",
                  "dt_begin_touch": "2019-04-14 08:35:00",
                  "dt_end_touch": "2019-04-14 18:25:00",
                  "overtime": "30",
                  "x": 35.5362,
                  "y": 129.444,
                  "overtime_type": -1
                },
                ......
              ]
            }
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'staff_id\' 가 없어요'}
            {'message':'ClientError: parameter \'work_id\' 가 없어요'}
            {'message':'ClientError: parameter \'year_month_day\' 가 없어요'}
            {'message':'ClientError: parameter \'overtime_type\' 가 없어요'}
            {'message':'ClientError: parameter \'employee_ids\' 가 없어요'}
            {'message':'ClientError: parameter \'overtime_type\' 값이 범위(-3 ~ 18)를 넘었습니다.'}
            {'message':'ClientError: parameter \'staff_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)}
            {'message':'ServerError: Work 에 id={} 이(가) 없거나 중복됨'.format(work_id)}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst,
                                      ['staff_id_!', 'work_id_!', 'year_month_day', 'overtime_type', 'employee_ids', 'comment_@'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

    staff_id = parameter_check['parameters']['staff_id']
    work_id = parameter_check['parameters']['work_id']
    year_month_day = parameter_check['parameters']['year_month_day']
    overtime_type = int(parameter_check['parameters']['overtime_type'])
    employee_ids = parameter_check['parameters']['employee_ids']
    comment = parameter_check['parameters']['comment']

    try:
        app_user = Staff.objects.get(id=staff_id)
    except Exception as e:
        return status422(get_api(request),
                         {'message': 'ServerError: Staff 에 id={} 이(가) 없음'.format(staff_id)})
    try:
        work = Work.objects.get(id=work_id)
    except Exception as e:
        return status422(get_api(request), {'message': 'ServerError: Work 에 id={} 이(가) 없음'.format(work_id)})
    if work.staff_id != app_user.id:
        # 업무 담당자와 요청자가 틀린 경우 - 사업장 담당자 일 수 도 있기 때문에 error 가 아니다.
        logSend('   ! 업무 담당자와 요청자가 틀림 - 사업장 담당자 일 수 도 있기 때문에 error 가 아니다.')
    #
    # 2020/02/28 업무정보(time_info)에 유급휴일(주휴일 paid_day)이 -1 이면 메뉴에 "유급휴일"이 표시되야 한다.
    #
    time_info = work.get_time_info()
    logSend('  > paid_day: {}'.format(time_info['paid_day']))
    if overtime_type < -3 or 18 < overtime_type:
        # 초과 근무 형태가 범위를 벗어난 경우
        return status422(get_api(request),
                         {'message': 'ClientError: parameter \'overtime_type\' 값이 범위(-3 ~ 18)를 넘었습니다.'.format(paid_day)})
    if request.method == 'GET':
        employee_ids = rqst.getlist('employee_ids')

    # logSend(employee_ids)
    if len(employee_ids) == 0:
        # 연장근무 저장할 근로자 목록이 없다.
        logError(get_api(request), ' 근로자 목록({})이 없다?'.format(employee_ids))

        return REG_200_SUCCESS.to_json_response()
    # 암호화된 employee id 복호화
    employee_id_list = []
    for employee_id in employee_ids:
        if type(employee_id) == dict:
            employee_id_list.append(AES_DECRYPT_BASE64(employee_id['employee_id']))
        else:
            employee_id_list.append(int(AES_DECRYPT_BASE64(employee_id)))
    # logSend(employee_id_list)
    if len(employee_id_list) == 0:
        # 연장근무 저장할 근로자 목록이 없다.
        logError(get_api(request),
                 ' 근로자 연장 근무요청을 했는데 선택된 근로자({})가 없다? (암호화된 근로자 리스트에도 없다.)'.format(employee_id_list))

        return REG_200_SUCCESS.to_json_response()

    # 고객 서버의 employee 에서 요청된 근로자 선정
    employees = Employee.objects.filter(work_id=work.id, id__in=employee_id_list)
    # employee_ids = []
    # for employee in employees:
    #     employee_ids.append(AES_ENCRYPT_BASE64(str(employee.employee_id)))
    #
    # 근로자 서버의 근로자 정보에 연장 시간 변경한다.
    #
    employee_passer_ids = [AES_ENCRYPT_BASE64(str(employee.employee_id)) for employee in employees]
    employees_infor = {'employees': employee_passer_ids,
                       'year_month_day': year_month_day,
                       'work_id': AES_ENCRYPT_BASE64(work_id),
                       'overtime': overtime_type,
                       'overtime_staff_id': AES_ENCRYPT_BASE64(staff_id),
                       'comment': comment,
                       }
    r = requests.post(settings.EMPLOYEE_URL + 'pass_record_of_employees_in_day_for_customer_v2', json=employees_infor)
    #
    # 근로자 서버에서 잘못된거 처리해야하는데... 바쁘다! 그래서 실패 내역만 보낸다. (어차피 근로자서버에 로그도 남는데...)
    #
    logSend('  > {}'.format(r.json()))
    if len(r.json()['fail_list']):
        logError(get_api(request),
                 ' pass_record_of_employees_in_day_for_customer_v2 FAIL LIST {}'.format(r.json()['fail_list']))
    # 그럴리는 없지만 근로자 서버 처리 후 근로자 명단과 고객서버 근로자 명단을 비교처리해야하는데 로그만 남기는 걸로...
    # pass_records = r.json()['employees']
    fail_list = r.json()['fail_list']
    #
    # 근로자 서버의 근로자 처리했으니까 이제 고객 서버 처리하자.
    #
    # 2020-03-23: 근로자가 확인하기 전까지 적용시키지 않기 때문에 저장하지 않는다.
    # 관리자가 근로자 정보를 가져올 때 근로자 서버에서 확인 여부를 가져와 표시한다.
    #
    # arr_employee = []
    # for employee in employees:
    #     employee.overtime = overtime_type
    #     employee.save()
    #     employee_dic = {
    #         'is_accept_work': '응답 X' if employee.is_accept_work is None else '수락' if employee.is_accept_work is True else '거절',
    #         'employee_id': AES_ENCRYPT_BASE64(str(employee.employee_id)),
    #         'name': employee.name,
    #         'phone': phone_format(employee.pNo),
    #         'dt_begin': dt_null(employee.dt_begin),
    #         'dt_end': dt_null(employee.dt_end),
    #         # 'dt_begin_beacon': dt_null(employee.dt_begin_beacon),
    #         # 'dt_end_beacon': dt_null(employee.dt_end_beacon),
    #         # 'dt_begin_touch': dt_null(employee.dt_begin_touch),
    #         # 'dt_end_touch': dt_null(employee.dt_end_touch),
    #         # 'overtime': employee.overtime,
    #         'x': employee.x,
    #         'y': employee.y,
    #     }
    #     arr_employee.append(employee_dic)
    # result = {'employees': arr_employee,
    #           'fail_list': fail_list
    #           }
    # return REG_200_SUCCESS.to_json_response(result)
    return REG_200_SUCCESS.to_json_response({'fail_list': fail_list})


@cross_origin_read_allow
def staff_change_day_type(request):
    """
    [관리자용 앱]: 특정일의 휴일, 주휴일, 소정근무일을 변경한다.
    - 근로자 명단에서 체크하고 체크한 근로자 만 근무 변경
    - 오늘부터 3일 전까지만 수정할 수 있다.
    POST
        staff_id : 현장관리자 id      # foreground 에서 받은 암호화된 식별 id
        work_id : 업무 id           # 암호화된 id
        year_month_day: 2019-05-09 # 처리할 날짜
        day_type: 0                 # 근무일 구분 0: 유급휴일, 1: 주휴일(연장 근무), 2: 소정근로일, 3: 휴일(휴일/연장 근무)
        employee_ids: [ 근로자_id_1, 근로자_id_2, 근로자_id_3, 근로자_id_4, 근로자_id_5, ...]
        comment: 근로자에게 전달할 짧은 내용의 글
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "employees": [
                {
                  "is_accept_work": true,
                  "employee_id": "i52bN-IdKYwB4fcddHRn-g",
                  "name": "근로자",
                  "phone": "010-3333-4444",1
                  "dt_begin": "2019-03-10 14:46:04",
                  "dt_end": "2019-05-09 00:00:00",
                  "dt_begin_beacon": "2019-04-14 08:20:00",
                  "dt_end_beacon": "2019-04-14 18:20:00",
                  "dt_begin_touch": "2019-04-14 08:35:00",
                  "dt_end_touch": "2019-04-14 18:25:00",
                  "overtime": "30",
                  "x": 35.5362,
                  "y": 129.444,
                  "overtime_type": -1
                },
                ......
              ]
            }
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'staff_id\' 가 없어요'}
            {'message':'ClientError: parameter \'work_id\' 가 없어요'}
            {'message':'ClientError: parameter \'year_month_day\' 가 없어요'}
            {'message':'ClientError: parameter \'day_type\' 가 없어요'}
            {'message':'ClientError: parameter \'employee_ids\' 가 없어요'}
            {'message':'ClientError: parameter \'day_type\' 값이 범위(0 ~ 3)를 넘었습니다.'}
            {'message':'ClientError: parameter \'staff_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)}
            {'message':'ServerError: Work 에 id={} 이(가) 없거나 중복됨'.format(work_id)}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst,
                                      ['staff_id_!', 'work_id_!', 'year_month_day', 'day_type', 'employee_ids', 'comment_@'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

    staff_id = parameter_check['parameters']['staff_id']
    work_id = parameter_check['parameters']['work_id']
    year_month_day = parameter_check['parameters']['year_month_day']
    day_type = int(parameter_check['parameters']['day_type'])
    employee_ids = parameter_check['parameters']['employee_ids']
    comment = parameter_check['parameters']['comment']

    try:
        app_user = Staff.objects.get(id=staff_id)
    except Exception as e:
        return status422(get_api(request),
                         {'message': 'ServerError: Staff 에 id={} 이(가) 없음'.format(staff_id)})
    try:
        work = Work.objects.get(id=work_id)
    except Exception as e:
        return status422(get_api(request), {'message': 'ServerError: Work 에 id={} 이(가) 없음'.format(work_id)})
    if work.staff_id != app_user.id:
        # 업무 담당자와 요청자가 틀린 경우 - 사업장 담당자 일 수 도 있기 때문에 error 가 아니다.
        logSend('   ! 업무 담당자와 요청자가 틀림 - 사업장 담당자 일 수 도 있기 때문에 error 가 아니다.')
    #
    # 2020/02/28 업무정보(time_info)에 유급휴일(주휴일 paid_day)이 -1 이면 메뉴에 "유급휴일"이 표시되야 한다.
    #
    time_info = work.get_time_info()
    logSend('  > paid_day: {}'.format(time_info['paid_day']))
    if day_type < 0 or 3 < day_type:
        # 초과 근무 형태가 범위를 벗어난 경우
        return status422(get_api(request),
                         {'message': 'ClientError: parameter \'overtime_type\' 값이 범위(0 ~ 3)를 넘었습니다.'.format(paid_day)})
    if request.method == 'GET':
        employee_ids = rqst.getlist('employee_ids')

    # logSend(employee_ids)
    if len(employee_ids) == 0:
        # 연장근무 저장할 근로자 목록이 없다.
        logError(get_api(request), ' 근로자 연장 근무요청을 했는데 선택된 근로자({})가 없다?'.format(employee_ids))

        return REG_200_SUCCESS.to_json_response()
    # 암호화된 employee id 복호화
    employee_id_list = []
    for employee_id in employee_ids:
        if type(employee_id) == dict:
            employee_id_list.append(AES_DECRYPT_BASE64(employee_id['employee_id']))
        else:
            employee_id_list.append(int(AES_DECRYPT_BASE64(employee_id)))
    # logSend(employee_id_list)
    if len(employee_id_list) == 0:
        # 연장근무 저장할 근로자 목록이 없다.
        logError(get_api(request),
                 ' 근로자 연장 근무요청을 했는데 선택된 근로자({})가 없다? (암호화된 근로자 리스트에도 없다.)'.format(employee_id_list))

        return REG_200_SUCCESS.to_json_response()

    # 고객 서버의 employee 에서 요청된 근로자 선정
    employees = Employee.objects.filter(work_id=work.id, id__in=employee_id_list)
    #
    # 근로자 서버에 처리 요청
    #
    employee_passer_ids = [AES_ENCRYPT_BASE64(str(employee.employee_id)) for employee in employees]
    employees_infor = {'employees': employee_passer_ids,
                       'year_month_day': year_month_day,
                       'work_id': AES_ENCRYPT_BASE64(work_id),
                       'day_type': day_type,
                       'day_type_staff_id': AES_ENCRYPT_BASE64(staff_id),
                       'comment': comment,
                       }
    r = requests.post(settings.EMPLOYEE_URL + 'pass_record_of_employees_in_day_for_customer_v2', json=employees_infor)
    logSend('  > {}'.format(r.json()))
    if len(r.json()['fail_list']):
        logError(get_api(request),
                 ' pass_record_of_employees_in_day_for_customer_v2 FAIL LIST {}'.format(r.json()['fail_list']))
    fail_list = r.json()['fail_list']
    return REG_200_SUCCESS.to_json_response({'fail_list': fail_list})


@cross_origin_read_allow
def staff_employee_working(request):
    """
    [관리자용 앱]:  업무에 투입된 근로자의 한달 근로 내역 요청
    - 담당자(현장 소장, 관리자), 업무, 필요한 근로 내역 연월
    http://0.0.0.0:8000/customer/staff_employee_working?id=qgf6YHf1z2Fx80DR8o_Lvg&employee_id=i52bN-IdKYwB4fcddHRn-g&year_month=2019-04
    POST
        staff_id : 현장관리자 id  # foreground 에서 받은 암호화된 식별 id
        work_id : 업무 id
        employee_id : 근로자 id
        year_month : 2019-04   # 근로내역 연월
    response
        STATUS 204 # 일한 내용이 없어서 보내줄 데이터가 없다.
        STATUS 200
        {
            'working':
            [
                { 'action': 10, 'dt_begin': '2018-12-28 12:53:36', 'dt_end': '2018-12-28 12:53:36',
                    'outing':
                    [
                        {'dt_begin': '2018-12-28 12:53:36', 'dt_end': '2018-12-28 12:53:36'}
                    ]
                },
                ......
            ]
        }
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'staff_id\' 가 없어요'}
            {'message':'ClientError: parameter \'employee_id\' 가 없어요'}
            {'message':'ClientError: parameter \'year_month\' 가 없어요'}
            {'message':'ClientError: parameter \'id\' 가 정상적인 값이 아니예요.'}
            {'message':'ClientError: parameter \'employee_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)}
            {'message':'ServerError: Employee 에 id={} 이(가) 없거나 중복됨'.format(employee_id)}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'work_id_!', 'employee_id_!', 'year_month'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    staff_id = parameter_check['parameters']['staff_id']
    work_id = parameter_check['parameters']['work_id']
    employee_id = parameter_check['parameters']['employee_id']
    year_month = parameter_check['parameters']['year_month']

    app_users = Staff.objects.filter(id=staff_id)
    if len(app_users) != 1:
        return status422(get_api(request),
                         {'message': 'ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)})
    employees = Employee.objects.filter(id=employee_id, work_id=work_id)
    if len(employees) != 1:
        return status422(get_api(request), {'message': 'ServerError: Employee 에 '
                                                       'employee_id: {}, '
                                                       'work_id: {} 이(가) 없거나 중복됨'.format(employee_id, work_id)})
    employee = employees[0]

    #
    # 근로자 서버로 근로자의 월 근로 내역을 요청
    #
    employee_info = {
        'employee_id': AES_ENCRYPT_BASE64(str(employee.employee_id)),
        'work_id': employee.work_id,
        'dt': year_month,
    }
    logSend(employee_info)
    response_employee = requests.post(settings.EMPLOYEE_URL + 'my_work_histories_for_customer', json=employee_info)
    logSend(response_employee)
    result = response_employee.json()

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def staff_employee_working_v2(request):
    """
    [관리자용 앱]:  업무에 투입된 근로자의 한달 근로 내역 요청
    - 담당자(현장 소장, 관리자), 업무, 필요한 근로 내역 연월
    http://0.0.0.0:8000/customer/staff_employee_working_v2?id=qgf6YHf1z2Fx80DR8o_Lvg&employee_id=i52bN-IdKYwB4fcddHRn-g&year_month=2019-04
    POST
        staff_id : 현장관리자 id  # foreground 에서 받은 암호화된 식별 id
        work_id : 업무 id
        employee_id : 근로자 id
        year_month : 2019-04   # 근로내역 연월
    response
        STATUS 204 # 일한 내용이 없어서 보내줄 데이터가 없다.
        STATUS 200
            {'message': '근태내역이 없습니다.', "work_dict": {}, "work_day_dict': {} }
            {
                "message": "정상적으로 처리되었습니다.",
                "work_dict": {
                    "68": {
                        "name": "박종기",
                        "break_sum": "18:05",
                        "basic_sum": 209,
                        "night_sum": 0,
                        "overtime_sum": 8,
                        "holiday_sum": 0,
                        "ho_sum": 0
                    }
                },
                "work_day_dict": {
                    "05": {
                        "year_month_day": "2020-06-05",
                        "week": "금",
                        "action": 0,
                        "work_id": "sBEXp67DHY1TpQbybrTBQg",
                        "passer_id": "ryWQkNtiHgkUaY_SZ1o2uA",
                        "begin": "08:00",   # 출근시간
                        "end": "17:00",     # 퇴근시간
                        "break": "60",      # 휴게시간(단위: 분)
                        "break_list": "12:00 ~ 13:00\n15:00 ~ 15:30", # 휴게시간이 여러개일 때 만 있음.
                        "basic": "8",       # 기본근로시간(유급휴일일 때는 주휴시간)
                        "night": "2",       # 야간근로시간
                        "overtime": "0",    # 연장근로시간
                        "holiday": "",      # 휴일근로시간
                        "ho": "",           # 휴일/연장근로시간
                        "remarks": "",
                        "dt_accept": "2020-06-07 14:23:51",
                        "day_type": 2,              # 근무일 구분 0: 유급휴일, 1: 무급휴무일 - 주휴일(연장 근무), 2: 소정근로일, 3: 무급휴일 - 무휴일(휴일/연장 근무)
                        "notification": 2,          # 알림 상태: -1: 없음, 0: 알림 확인전, 1: 알림 확인, 2: 알림 거부, 3: 알림 답변시한 지남
                        "notification_type": -20    # 알림 종류: -30: 새업무 알림,
                                                    # -21: 퇴근시간 수정, -23: 퇴근시간 삭제, -20: 출근시간 수정, -22: 출근시간 삭
                                                    # 근무일 구분 0: 유급휴일, 1: 무급휴무일 - 주휴일(연장 근무), 2: 소정근로일, 3: 무급휴일 - 무휴일(휴일/연장 근무)
                                                    # -13: 휴일(휴일근무), -12: 소정근로일, -11: 주휴일(연장근무), -10: 유급휴일
                                                    # -3: 반차휴가(현재 사용안함9), -2: 연차휴무, -1: 조기퇴근, 0:정상근무, 1~18: 연장근무 시간
                    },
                    ......
                }
            }
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'staff_id\' 가 없어요'}
            {'message':'ClientError: parameter \'employee_id\' 가 없어요'}
            {'message':'ClientError: parameter \'year_month\' 가 없어요'}
            {'message':'ClientError: parameter \'id\' 가 정상적인 값이 아니예요.'}
            {'message':'ClientError: parameter \'employee_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)}
            {'message':'ServerError: Employee 에 id={} 이(가) 없거나 중복됨'.format(employee_id)}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'work_id_!', 'employee_id_!', 'year_month'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    staff_id = parameter_check['parameters']['staff_id']
    work_id = parameter_check['parameters']['work_id']
    employee_id = parameter_check['parameters']['employee_id']
    year_month = parameter_check['parameters']['year_month']

    try:
        staff = Staff.objects.get(id=staff_id)
    except Exception as e:
        return status422(get_api(request),
                         {'message': 'ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)})
    try:
        employee = Employee.objects.get(id=employee_id, work_id=work_id)
    except Exception as e:
        return status422(get_api(request), {'message': 'ServerError: Employee 에 '
                                                       'employee_id: {}, '
                                                       'work_id: {} 이(가) 없거나 중복됨'.format(employee_id, work_id)})
    #
    # 근로자 서버로 근로자의 월 근로 내역을 요청
    #
    employee_info = {
        'passer_id': AES_ENCRYPT_BASE64(str(employee.employee_id)),
        'work_id': rqst['work_id'],
        'dt': year_month,
    }
    response_employee = requests.post(settings.EMPLOYEE_URL + 'my_work_records_v2', json=employee_info)
    return ReqLibJsonResponse(response_employee)

    # if response_employee.status_code != 200:
    #     return ReqLibJsonResponse(response_employee)
    #
    # work_day_dict = {}
    # work_dict = {}
    # arr_working = response_employee.json()['arr_working']
    # for working in arr_working:
    #     days = working['days']
    #     for day_key in days.keys():
    #         day = days[day_key]
    #         day_dict = {
    #             "year_month_day": '{}-{}'.format(year_month, day_key),
    #             "work_id": AES_ENCRYPT_BASE64(str(day['work_id'])),
    #             "action": 110,
    #             "dt_begin": '{}'.format(day['dt_in_verify']),
    #             "dt_end": '{}'.format(day['dt_out_verify']),
    #             "overtime": day['overtime'],
    #             "week": day['week'],
    #             "break": day['break'],
    #             "basic": int_none(day['basic']),
    #             "night": int_none(day['night']),
    #             "holiday": int_none(day['holiday']),
    #             "ho": int_none(day['ho']),
    #         }
    #         work_day_dict[day_key] = day_dict
    #     logSend('  > day: {} - work_id: {}'.format(day_key, day['work_id']))
    #     del working['days']
    #     work_dict[AES_ENCRYPT_BASE64(str(day['work_id']))] = working
    #
    # return REG_200_SUCCESS.to_json_response({'work_dict': work_dict, 'work_day_dict': work_day_dict})


@cross_origin_read_allow
def staff_update_employee(request):
    """
    [관리자용 앱]: 업무에 투입된 근로자의 근무 기간, 연장 근무 변경 요청
    - 담당자(현장 소장, 관리자), 근로자, 근무 기간, 당일의 연장 근무
    - 근로자의 근무 기간은 업무의 기간을 벗아나지 못한다.
    - 값을 넣은 것만 변경한다.
    http://0.0.0.0:8000/customer/staff_update_employee?staff_id=qgf6YHf1z2Fx80DR8o_Lvg&employee_id=iZ_rkELjhh18ZZauMq2vQw&dt_begin=2019-03-01&dt_end=2019-04-30&overtime_type=0
    overtime 설명
        연장 근무 -2: 연차, -1: 업무 끝나면 퇴근, 0: 정상 근무, 1~18: 연장 근무 시간( 1:30분, 2:1시간, 3:1:30, 4:2:00, 5:2:30, 6:3:00 7: 3:30, 8: 4:00, 9: 4:30, 10: 5:00, 11: 5:30, 12: 6:00, 13: 6:30, 14: 7:00, 15: 7:30, 16: 8:00, 17: 8:30, 18: 9:00)
    POST
        staff_id : 현장관리자 id  # foreground 에서 받은 암호화된 식별 id
        work_id : 업무 id
        employee_id : 근로자 id
        dt_begin : 2019-04-01   # 근로 시작 날짜
        dt_end : 2019-04-13     # 근로 종료 날짜
        2020-04-02 아래 overtime_type 은 없어져야 함
        overtime_type : 0       # -1: 업무 완료 조기 퇴근, 0: 표준 근무, 1: 30분 연장 근무, 2: 1시간 연장 근무, 3: 1:30 연장 근무, 4: 2시간 연장 근무, 5: 2:30 연장 근무, 6: 3시간 연장 근무
    response
        STATUS 200
            "working": [
                {
                "year_month_day": "2019-07-01",
                "action": 20,
                "dt_begin": null,
                "dt_end": "2019-07-01 07:01:56",
                "overtime": -1,        # 연장 근무 -2: 연차, -1: 업무 끝나면 퇴근, 0: 정상 근무, 1~18: 연장 근무 시간( 1:30분, 2:1시간, 3:1:30, 4:2:00, 5:2:30, 6:3:00 7: 3:30, 8: 4:00, 9: 4:30, 10: 5:00, 11: 5:30, 12: 6:00, 13: 6:30, 14: 7:00, 15: 7:30, 16: 8:00, 17: 8:30, 18: 9:00)
                "working_hour": 8,
                "break_hour": 0
                },
                ...
            ]
        STATUS 416
            {'message': '업무 시작날짜 이전으로 설정할 수 없습니다.'}
            {'message': '업무 종료날짜 이후로 설정할 수 없습니다.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'staff_id\' 가 없어요'}
            {'message':'ClientError: parameter \'employee_id\' 가 없어요'}
            {'message':'ClientError: parameter \'dt_begin\' 가 없어요'}
            {'message':'ClientError: parameter \'dt_end\' 가 없어요'}
            {'message':'ClientError: parameter \'overtime_type\' 가 없어요'}
            {'message':'ClientError: parameter \'staff_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ClientError: parameter \'employee_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Staff 에 staff_id={} 이(가) 없거나 중복됨'.format(staff_id)}
            {'message':'ServerError: Employee 에 employee_id={} 이(가) 없거나 중복됨'.format(employee_id)}
            {'message':'ClientError: parameter \'dt_begin\'이 업무 시작 날짜 이전입니다.'}
            {'message':'ClientError: parameter \'dt_end\'이 업무 종료 날짜 이후입니다.'}
            {'message':'ClientError: parameter \'overtime_type\'이 범위를 벗어났습니다.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'work_id_!', 'employee_id_!', 'dt_begin', 'dt_end',
                                             'overtime_type_@'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    staff_id = parameter_check['parameters']['staff_id']
    work_id = parameter_check['parameters']['work_id']
    employee_id = parameter_check['parameters']['employee_id']
    str_dt_begin = parameter_check['parameters']['dt_begin']
    str_dt_end = parameter_check['parameters']['dt_end']
    overtime_type = parameter_check['parameters']['overtime_type']

    app_users = Staff.objects.filter(id=staff_id)
    if len(app_users) != 1:
        return status422(get_api(request),
                         {'message': 'ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)})
    employees = Employee.objects.filter(id=employee_id, work_id=work_id)
    if len(employees) != 1:
        return status422(get_api(request),
                         {'message': 'ServerError: Employee 에 id={} 이(가) 없거나 중복됨'.format(employee_id)})
    employee = employees[0]
    # works = Work.objects.filter(id=employee.work_id)
    works = Work.objects.filter(id=work_id)
    if len(works) != 1:
        return status422(get_api(request), {'message': 'ServerError: Work 에 id={} 이(가) 없거나 중복됨'.format(work_id)})
    work = works[0]

    is_update_dt_begin = False
    result = {}
    if not '' == str_dt_begin:
        dt_begin = str_to_datetime(str_dt_begin)
        if dt_begin < work.dt_begin:
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무 시작날짜 이전으로 설정할 수 없습니다.'})
        employee.dt_begin = dt_begin
        is_update_dt_begin = True

    is_update_dt_end = False
    if not '' == str_dt_end:
        dt_end = str_to_datetime(str_dt_end)
        logSend(' str_dt_end: {}, dt_end: {}'.format(str_dt_end, dt_end))
        if work.dt_end < dt_end:
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무 종료날짜 이후로 설정할 수 없습니다.'})
        employee.dt_end = dt_end
        is_update_dt_end = True
    #
    # 근로기간이 변경되었으면 근로자서버를 업데이트한다.
    #
    if is_update_dt_begin or is_update_dt_end:
        employees_infor = {
            'employee_id': AES_ENCRYPT_BASE64(str(employee.employee_id)),
            'work_id': work.id,
        }
        if is_update_dt_begin:
            employees_infor['dt_begin'] = dt_begin.strftime("%Y/%m/%d")
        if is_update_dt_end:
            employees_infor['dt_end'] = dt_end.strftime("%Y/%m/%d")
        logSend(employees_infor)
        r = requests.post(settings.EMPLOYEE_URL + 'change_work_period_for_customer', json=employees_infor)
        result['work_dt_end'] = {'url': r.url, 'POST': employees_infor, 'STATUS': r.status_code, 'R': r.json()}

    if overtime_type is not None:
        if type(overtime_type) is str:
            overtime_type.replace(' ', '')
        if len(overtime_type) > 0:
            if overtime_type < -2 or 18 < overtime_type:
                return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '설정범위를 벗어났습니다.'})
            employee.overtime = overtime_type

    employee.save()
    #
    # employee server 에서 적용시켜야 한다.
    #
    result['update_dt_begin'] = employee.dt_begin.strftime("%Y-%m-%d %H:%M:%S")
    result['update_dt_end'] = employee.dt_end.strftime("%Y-%m-%d %H:%M:%S")
    result['update_overtime'] = employee.overtime_type

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def staff_recognize_employee(request):
    """
    [관리자용 앱]:  근로자의 출퇴근 시간이 잘못되었을 때 현장 소장이 출퇴근 시간을 인정하고 변경하는 기능
    - 담당자(현장 소장, 관리자), 근로자, 출근시간, 퇴근 시간
    - 출근시간과 퇴근시간은 "yyyy-mm-dd hh:mm:ss" 양식으로 보낸다.
    - dt_arrive 와 dt_leave 는 둘중 하나만 온다.
    - 값을 넣은 것만 변경한다.
    http://0.0.0.0:8000/customer/staff_recognize_employee?staff_id=qgf6YHf1z2Fx80DR8o_Lvg&employee_id=iZ_rkELjhh18ZZauMq2vQw&dt_arrive=2019-03-01 08:30:00&dt_end=2019-03-01 17:30:00
    POST
        staff_id : 현장관리자 id  # foreground 에서 받은 암호화된 식별 id
        work_id : 업무 id
        employee_id : 근로자 id
        dt_arrive : 2019-04-01 08:30:00   # 도착 시간 - 출근 시간 (단, 출근시간을 없앨 때는 2019-04-01 25:00:00 을 넣어보낸다.)
        dt_leave : 2019-04-01 17:30:00    # 떠난 시간 - 퇴근 시간 (단, 퇴근시간을 없앨 때는 2019-04-01 25:00:00 을 넣어보낸다.)
    response
        STATUS 200
        STATUS 541
            {'message': '업무 수락이 안되어 있는 근로자 입니다.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'staff_id\' 가 없어요'}
            {'message':'ClientError: parameter \'employee_id\' 가 없어요'}
            {'message':'ClientError: parameter \'dt_arrive\' 가 없어요'}
            {'message':'ClientError: parameter \'dt_leave\' 가 없어요'}
            {'message':'ClientError: parameter \'staff_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ClientError: parameter \'employee_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Staff 에 staff_id={} 이(가) 없거나 중복됨'.format(staff_id)}
            {'message':'ServerError: Employee 에 employee_id={} 이(가) 없거나 중복됨'.format(employee_id)}
            {'message': 'ClientError: parameter \'dt_arrive\' 양식을 확인해주세요.'}
            {'message': 'ClientError: parameter \'dt_leave\' 양식을 확인해주세요.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'work_id_!', 'employee_id_!', 'dt_arrive_@', 'dt_leave_@'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    staff_id = parameter_check['parameters']['staff_id']
    work_id = parameter_check['parameters']['work_id']
    employee_id = parameter_check['parameters']['employee_id']
    str_dt_arrive = parameter_check['parameters']['dt_arrive']
    str_dt_leave = parameter_check['parameters']['dt_leave']

    app_users = Staff.objects.filter(id=staff_id)
    if len(app_users) == 0:
        return status422(get_api(request),
                         {'message': ' ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)})
    employees = Employee.objects.filter(id=employee_id, work_id=work_id)
    logSend('--- employee id {} '.format(employee_id))
    if len(employees) == 0:
        return status422(get_api(request),
                         {'message': 'ServerError: Employee 에 id={} 이(가) 없거나 중복됨'.format(employee_id)})
    employee = employees[0]
    if employee.employee_id == -1:
        return REG_541_NOT_REGISTERED.to_json_response({'message': '업무 수락이 안되어 있는 근로자 입니다.'})
    logSend('--- employee id {} name {} employee_id {}'.format(employee.id, employee.name, employee.employee_id))
    works = Work.objects.filter(id=work_id)
    if len(works) == 0:
        return status422(get_api(request), {'message': 'ServerError: Work 에 id={} 해당 업무가 없습니다.'.format(works)})
    work = works[0]

    #
    # employee server 에서 적용시켜야 한다.
    #
    employees_infor = {'employees': [AES_ENCRYPT_BASE64(str(employee.employee_id))],
                       # 'year_month_day': dt_arrive.strftime('%Y-%m-%d'),
                       'work_id': AES_ENCRYPT_BASE64(str(work.id)),
                       }
    if 'dt_arrive' in rqst and str_dt_arrive is not None:
        if len(str_dt_arrive.split(' ')) == 0:
            return status422(get_api(request), {'message': 'ClientError: parameter \'dt_arrive\' 양식을 확인해주세요.'})
        employees_infor['year_month_day'] = str_dt_arrive[0:10]
        employees_infor['dt_in_verify'] = str_dt_arrive[11:19]
        employees_infor['in_staff_id'] = AES_ENCRYPT_BASE64(staff_id)
        # employee.dt_begin_touch = dt_arrive

    if 'dt_leave' in rqst and str_dt_leave is not None:
        if len(str_dt_leave.split(' ')) == 0:
            return status422(get_api(request), {'message': 'ClientError: parameter \'dt_leave\' 양식을 확인해주세요.'})
        employees_infor['year_month_day'] = str_dt_leave[0:10]
        employees_infor['dt_out_verify'] = str_dt_leave[11:19]
        employees_infor['out_staff_id'] = AES_ENCRYPT_BASE64(staff_id)
        # employee.dt_end_touch = dt_leave

    # employee.save()
    #
    # employee server 에서 적용시켜야 한다.
    #
    r = requests.post(settings.EMPLOYEE_URL + 'pass_record_of_employees_in_day_for_customer_v2', json=employees_infor)
    if len(r.json()['fail_list']):
        logError(get_api(request),
                 ' pass_record_of_employees_in_day_for_customer_v2 FAIL LIST {}'.format(r.json()['fail_list']))
    # pass_records = r.json()['employees']
    # fail_list = r.json()['fail_list']

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def staff_request_certification_no(request):
    """
    [관리자용 앱]:  인증번호 요청(처음 실행)
    SMS 로 인증 문자(6자리)를 보낸다.
    http://0.0.0.0:8000/customer/staff_request_certification_no?phone_no=01025573555
    POST : json
    {
        'phone_no' : '010-1111-2222'
    }
    response
        STATUS 200
        STATUS 605  # 필수 입력 항목이 비었다.
            {'message': '전화번호가 없습니다.'}
        STATUS 606  # 값이 잘못되어 있습니다.
            {'message': '직원등록이 안 되어 있습니다.\n웹에서 전화번호가 틀리지 않았는지 확인해주세요.'}
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    phone_no = rqst['phone_no']
    if len(phone_no) == 0:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '전화번호가 없습니다.'})

    phone_no = phone_no.replace('+82', '0')
    phone_no = phone_no.replace('-', '')
    phone_no = phone_no.replace(' ', '')
    # print(phone_no)
    staffs = Staff.objects.filter(pNo=phone_no)
    if len(staffs) == 0:
        return REG_541_NOT_REGISTERED.to_json_response()

    staff = staffs[0]

    certificateNo = random.randint(100000, 999999)
    staff.push_token = str(certificateNo)
    staff.save()

    rData = {
        'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
        'user_id': 'yuadocjon22',
        'sender': settings.SMS_SENDER_PN,
        'receiver': staff.pNo,
        'msg_type': 'SMS',
        'msg': '이지체크 앱 사용\n'
               '인증번호[' + str(certificateNo) + ']입니다.'
    }

    rSMS = requests.post('https://apis.aligo.in/send/', data=rData)
    print(rSMS.status_code)
    print(rSMS.headers['content-type'])
    print(rSMS.text)
    print(rSMS.json())
    logSend(json.dumps(rSMS.json(), cls=DateTimeEncoder))
    # rJson = rSMS.json()
    # rJson['vefiry_no'] = str(certificateNo)

    # response = HttpResponse(json.dumps(rSMS.json(), cls=DateTimeEncoder))

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def staff_verify_certification_no(request):
    """
    [관리자용 앱]:  인증번호 확인
    근로자 등록 확인 : 문자로 온 SMS 문자로 근로자를 확인하는 기능 (여기서 사업장에 등록된 근로자인지 확인, 기존 등록 근로자인지 확인)
    http://0.0.0.0:8000/employee/verify_employee?phone_no=010-2557-3555&cn=580757&phone_type=A&push_token=token
    POST
        {
            'phone_no' : '010-1111-2222'
            'cn' : '6자리 SMS 인증숫자를 문자로 바꾸어 암호화'
            'phone_type' : 'A' # 안드로이드 폰
            'push_token' : 'push token'
        }
    response
        STATUS 607
            {'message': '인증번호가 틀립니다.'}
        STATUS 200
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    phone_no = rqst['phone_no']
    cipher_cn = rqst['cn']
    phone_type = rqst['phone_type']
    push_token = rqst['push_token']

    if len(phone_type) > 0:
        phone_no = phone_no.replace('-', '')
        phone_no = phone_no.replace(' ', '')

    staff = Staff.objects.get(pNo=phone_no)
    cn = AES_DECRYPT_BASE64(cipher_cn)
    if int(staff.push_token) != int(cn):
        return REG_550_CERTIFICATION_NO_IS_INCORRECT.to_json_response()

    staff.pType = 20 if phone_type == 'A' else 10
    staff.push_token = push_token
    staff.save()

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def staff_reg_my_work(request):
    """
    [관리자용 앱]:  담당 업무 등록 (웹에서...)
    :param request:
    :return:
    """
    return


@cross_origin_read_allow
def staff_update_my_work(request):
    """
    [관리자용 앱]:  담당 업무 내용 수정(웹에서...)
    :param request:
    :return:
    """
    return


@cross_origin_read_allow
def staff_list_my_work(request):
    """
    [관리자용 앱]:  담당 업무 리스트
    http://0.0.0.0:8000/customer/staff_list_my_work?id=ryWQkNtiHgkUaY_SZ1o2uA
    GET
        id= 암호화된 id # 처음이거나 15분 이상 지났으면 login_id, login_pw 를 보낸다.
    response
        STATUS 200
        {
            'work_places':[{'work_place_id':'...', 'work_place_name':'...'}, ...], # 관리자의 경우 사업장
            'works':[{'work_id':'...', 'work_name':'...'}, ...]                     # 현장 소장의 경우 업무(관리자가 겸하는 경우도 있음.)
        }
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    cipher_id = rqst['id']
    app_user = Staff.objects.get(id=AES_DECRYPT_BASE64(cipher_id))

    result = {}
    work_places = Work_Place.objects.filter(contractor_ir=app_user.co_id, manager_id=app_user.id).values('id', 'name')
    if len(work_places) > 0:
        arr_work_place = [work_place for work_place in work_places]
        result['work_places'] = arr_work_place
    works = Work.objects.filter(contractor_ir=app_user.co_id, staff_id=app_user.id).values('id', 'name')
    if len(works) > 0:
        arr_work = [work for work in works]
        result['works'] = arr_work

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def staff_work_list_employee(request):
    """
    [관리자용 앱]:  업무에 근무 중인 근로자 리스트(전일, 당일 근로 내역 포함)
    http://0.0.0.0:8000/customer/staff_work_list_employee?id=ryWQkNtiHgkUaY_SZ1o2uA&work_id=1
    GET
        id= 암호화된 id # 처음이거나 15분 이상 지났으면 login_id, login_pw 를 보낸다.
        work_id= 업무에 근로중인 근로자
    response
        STATUS 200
        {
            'work_places':[{'work_place_id':'...', 'work_place_name':'...'}, ...], # 관리자의 경우 사업장
            'works':[{'work_id':'...', 'work_name':'...'}, ...]                     # 현장 소장의 경우 업무(관리자가 겸하는 경우도 있음.)
        }
    """

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    cipher_id = rqst['id']
    app_user = Staff.objects.get(id=AES_DECRYPT_BASE64(cipher_id))

    result = {}
    work_id = rqst['work_id']
    employees = Employee.objects.filter(work_id=work_id).values('is_active', 'dt_begin', 'dt_end', 'employee_id',
                                                                'name', 'pNo')
    if len(employees) > 0:
        arr_employee = [employee for employee in employees]
        result['employees'] = arr_employee

    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def staff_work_update_employee(request):
    """
    [관리자용 앱]:  업무에 근무 중인 근로자 내용 수정, 추가(지각, 외출, 조퇴, 특이사항)
    	주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
    		response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/staff_work_update_employee?id=&login_id=temp_1&before_pw=A~~~8282&login_pw=&name=박종기&position=이사&department=개발&phone_no=010-2557-3555&phone_type=10&push_token=unknown&email=thinking@ddtechi.com
    POST
    	{
    		'id': '암호화된 id',           # 아래 login_id 와 둘 중의 하나는 필수
    		'login_id': 'id 로 사용된다.',  # 위 id 와 둘 중의 하나는 필수
    		'before_pw': '기존 비밀번호',     # 필수
    		'login_pw': '변경하려는 비밀번호',   # 사전에 비밀번호를 확인할 것
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
    	STATUS 604
    		{'message': '비밀번호가 틀립니다.'}
    """

    if request.method == 'POST':
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
        return REG_531_PASSWORD_IS_INCORRECT.to_json_response()

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

    return REG_200_SUCCESS.to_json_response()


def send_push(push_contents):
    push_result = notification(push_contents)
    logSend('push result: {}'.format(push_result))
    return push_result


@cross_origin_read_allow
def push_from_employee(request):
    """
    << 근로자 서버용 >> 근로자서버에서 고객서버를 이용해 push 롤 보낼 때 사용
    http://0.0.0.0:8000/customer/push_from_employee?name=박종기&dt=2019-09-20 23:00:00&customer_work_id:wG0ueTnPydGK17ktSlOgiA&is_in=0
    GET
        'name': '이순신'               # 근로자 이름
        'dt': '2019-09-20 08:30:00'  # 출퇴근 날짜 시간
        'work_id': 37                # 암호화된 업무 id (2020/02/13 암호화 안함)
        'is_in': True                # 출근인가?
    response
        STATUS 200
            {'message': 'staff is push off'}
        STATUS 403
            {'message':'저리가!!!'}
        STATUS 422
            {'message': 'work of staff mismatch {}'.format(e)}
            {'message': 'none token: {}'.format(staff.push_token)}
    """
    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        logError(get_api(request), ' 허가되지 않은 ip: {}'.format(get_client_ip(request)))
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['name', 'dt', 'work_id', 'is_in'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    name = parameter_check['parameters']['name']
    dt = str_to_datetime(parameter_check['parameters']['dt'])
    work_id = parameter_check['parameters']['work_id']
    is_in = parameter_check['parameters']['is_in']

    # logSend('  - {} {} {} {}'.format(name, dt, work_id, is_in))
    try:
        work = Work.objects.get(id=work_id)
        logSend(work.staff_id, work.staff_name)
        staff = Staff.objects.get(id=work.staff_id)
    except Exception as e:
        logError(get_api(request), ' work or staff mismatch {}'.format(e))
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': 'work of staff mismatch {}'.format(e)})
    if not staff.is_push_touch:
        return REG_200_SUCCESS.to_json_response({'message': 'staff is push off'})

    if len(staff.push_token) < 64:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': 'none token: {}'.format(staff.push_token)})
    # push_contents = {
    #     'target_list': push_list,
    #     'func': 'user',
    #     'isSound': True,
    #     'badge': 1,
    #     'contents': {'title': '(채용정보) {}: {}'.format(work['work_place_name'], work['work_name_type']),
    #                  'subtitle': '{} ~ {}'.format(work['dt_begin'], work['dt_end']),
    #                  'body': {'action': 'NewWork',  # 'NewRecruiting',
    #                           'dt_begin': work['dt_begin'],
    #                           'dt_end': work['dt_end']
    #                           }
    #                  }
    # }
    # send_push(push_contents)
    push_contents = {
        'target_list': [{'id': staff.id, 'token': staff.push_token, 'pType': staff.pType}],
        'func': 'mng',
        'isSound': True,
        'badge': 1,
        'contents': {
            'title': '{}*{}님 {}, 시간: {}'.format(name[:1], name[len(name) - 1:], ("출근" if is_in else "퇴근"),
                                                dt.strftime("%H:%M")),
            'subtitle': '',
            # 'subtitle': '시간: {}'.format(dt.strftime("%H:%M")),
            'body': {'action': 'AlertInOut',
                     'current': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                     },
        }
    }
    response = send_push(push_contents)
    # response = notification(push_contents)

    return REG_200_SUCCESS.to_json_response({'response': json.dumps(response)})


@cross_origin_read_allow
def ddtech_update_syatem(request):
    """
    << 운영 서버용 >> 운영서버에서 고객서버의 변경이 발생했을 때 사용
    http://0.0.0.0:8000/customer/ddtech_update_syatem
    GET
        id= 암호화된 id # 처음이거나 15분 이상 지났으면 login_id, login_pw 를 보낸다.
        work_id= 업무에 근로중인 근로자
    response
        STATUS 200
        STATUS 422
            {'message': '이 기능을 사용할 수 있는 기간(~{})이 지났다.'.format(dt_execute.strftime('%Y-%m-%d %H:%M:%S'))}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    # ---------------------------------------------------------------------------------------
    # Update: Customer Model + is_constractor
    # ---------------------------------------------------------------------------------------
    dt_execute = datetime.datetime.strptime('2019-05-19 09:00:00', '%Y-%m-%d %H:%M:%S')
    dt_today = datetime.datetime.now()
    if dt_execute < dt_today:
        return status422(get_api(request),
                         {'message': '이 기능을 사용할 수 있는 기간(~{})이 지났다.'.format(dt_execute.strftime('%Y-%m-%d %H:%M:%S'))})

    # 협력사 발주사 리스트에서 도급업체 id 를 찾는다.
    list_contractor_id = []
    list_relationship = Relationship.objects.all()
    for relationship in list_relationship:
        if relationship.contractor_id not in list_contractor_id:
            list_contractor_id.append(relationship.contractor_id)
    logSend(list_contractor_id)

    # 고객사 에서 위에서 찾은 업체만 is_contractor 를 True 로 설정한다.
    list_customer = Customer.objects.all()
    for customer in list_customer:
        if customer.id in list_contractor_id:
            customer.is_contractor = True
        else:
            customer.is_contractor = False
        customer.save()

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def tk_check_employees(request):
    """
    [[ 서버 시험]] 근로자를 모두 읽어들여서 전화번호가 중복되는 근로자를 찾고 employee_id 가 다른 경우를 찾는다.
    http://0.0.0.0:8000/customer/tk_check_employees
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
    """

    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    result = []
    s = requests.session()

    # login_data = {"login_id": "thinking",
    #               "login_pw": "parkjong"
    #               }
    # r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    # result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})
    #
    # r = s.post(settings.CUSTOMER_URL + 'logout', json={})
    # result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})

    r = s.post(settings.EMPLOYEE_URL + 'tk_passer_list', json={'key': AES_ENCRYPT_BASE64('thinking')})
    # result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})
    passer_list = r.json()['passers']

    employee_all = Employee.objects.all()
    for employee in employee_all:
        for employee_comp in employee_all:
            if employee.pNo == employee_comp.pNo:
                if employee.id == employee_comp.id:
                    continue
                # if employee.work_id != employee_comp.work_id:
                #     continue
                passer_id = passer_list[employee.pNo] if employee.pNo in passer_list.keys() else ""
                logSend('  employee: {}'.format({employee.pNo: [employee.id, employee_comp.id, passer_id]}))
                result.append({employee.pNo: [employee.id, employee_comp.id, passer_id]})
    logSend(result)

    return REG_200_SUCCESS.to_json_response({'result': result})


@cross_origin_read_allow
def tk_list_employees(request):
    """
    [[ 서버 시험]] 근로자를 모두 읽어들여서 전화번호가 중복되는 근로자를 찾고 employee_id 가 다른 경우를 찾는다.
    http://0.0.0.0:8000/customer/tk_list_employees?work_id=5
    GET
        work_id: 5  # -1 이면 모든 근로자 암호화 되지 않은 값
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
    """

    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    # parameter_check = is_parameter_ok(rqst, ['work_id_!'])
    parameter_check = is_parameter_ok(rqst, ['work_id'])
    if not parameter_check['is_ok']:
        return status422(get_api(request),
                         {'message': '{}'.format(''.join([message for message in parameter_check['results']]))})
    work_id = parameter_check['parameters']['work_id']
    if work_id == -1:
        employee_list = Employee.objects.all()
    else:
        employee_list = Employee.objects.filter(work_id=work_id)
    logSend('  datetime type: {}'.format(type(datetime.datetime.now())))
    employee_dict_list = [
        {x: dt_null(employee.__dict__[x]) if type(employee.__dict__[x]) is datetime.datetime else employee.__dict__[x]
         for x in employee.__dict__.keys() if not x.startswith('_')} for employee in employee_list]
    logSend('  employee_dict_list: {}'.format(employee_dict_list))

    return REG_200_SUCCESS.to_json_response({'employee_list': employee_dict_list})


@cross_origin_read_allow
def tk_complete_employees(request):
    """
    [[ 운영]] 업무가 종료된 근로자를 찾아 별도 저장하고 뺀다.
    - 몇일을 기준으로 완료된 근로자를 백업할지 정한다.
    - 오늘 미만 날짜여야한다.
    http://0.0.0.0:8000/customer/tk_complete_employees?dt_complete=2019-07-31
    GET
        dt_complete: 2019-07-31
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
        STATUS 416
            {'message': '백업할 날짜({})는 오늘({})전이어야 한다..format(dt_complete, dt_today)}
    """

    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    # parameter_check = is_parameter_ok(rqst, ['work_id_!'])
    # parameter_check = is_parameter_ok(rqst, ['work_id'])
    # if not parameter_check['is_ok']:
    #     return status422(get_api(request),
    #                      {'message': '{}'.format(''.join([message for message in parameter_check['results']]))})
    # work_id = parameter_check['parameters']['work_id']
    dt_complete = str_to_datetime(rqst['dt_complete'])
    dt_complete = dt_complete + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
    dt_today = datetime.datetime.strptime(datetime.datetime.now().strftime("%Y-%m-%d ") + "00:00:00",
                                          "%Y-%m-%d %H:%M:%S")

    logSend('  origin: {}, dt_complete: {}, dt_today: {}'.format(rqst['dt_complete'], dt_complete, dt_today))
    if dt_today < dt_complete:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response(
            {'message': '백업할 날짜({})는 오늘({})전이어야 한다.'.format(dt_complete, dt_today)})

    complete_employee_list = Employee.objects.filter(dt_end__lte=dt_complete)

    result = []
    passer_id_list = []
    for employee in complete_employee_list:
        try:
            employee_backup = Employee_Backup(
                name=employee.name,
                pNo=employee.pNo,
                employee_id=employee.employee_id,
                work_id=employee.work_id,
                dt_begin=employee.dt_begin,
                dt_end=employee.dt_end,
            )
            delete_id = employee.id
            employee_backup.save()
            employee.delete()
            result.append({'id': delete_id,
                           'name': employee.name,
                           'SUCCESS': dt_null(employee.dt_end),
                           })
            passer_id_list.append(employee.employee_id)
        except Exception as e:
            result.append({'id': employee.id,
                           'name': employee.name,
                           'ERROR': str(e),
                           })
    """
    Employee 업무 완료 근로자 백업
    
    passer_id_list
    """
    parameter = {"passer_id_list": passer_id_list,
                 "dt_complete": rqst['dt_complete'],
                 }
    s = requests.session()
    r = s.post(settings.EMPLOYEE_URL + 'tk_passer_work_backup', json=parameter)
    result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})

    return REG_200_SUCCESS.to_json_response({'result': result})


@cross_origin_read_allow
def tk_complete_work_backup(request):
    """
    [[ 운영]] 업무가 종료된 근로자를 찾아 별도 저장하고 뺀다.
    - 몇일을 기준으로 완료된 근로자를 백업할지 정한다.
    - 오늘 미만 날짜여야한다.
    http://0.0.0.0:8000/customer/tk_complete_work_backup?dt_complete=2019-07-31
    GET
        dt_complete: 2019-07-31
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
        STATUS 416
            {'message': '백업할 날짜({})는 오늘({})전이어야 한다..format(dt_complete, dt_today)}
    """

    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    # parameter_check = is_parameter_ok(rqst, ['work_id_!'])
    # parameter_check = is_parameter_ok(rqst, ['work_id'])
    # if not parameter_check['is_ok']:
    #     return status422(get_api(request),
    #                      {'message': '{}'.format(''.join([message for message in parameter_check['results']]))})
    # work_id = parameter_check['parameters']['work_id']
    dt_complete = str_to_datetime(rqst['dt_complete'])
    dt_complete = dt_complete + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
    dt_today = datetime.datetime.strptime(datetime.datetime.now().strftime("%Y-%m-%d ") + "00:00:00",
                                          "%Y-%m-%d %H:%M:%S")

    logSend('  origin: {}, dt_complete: {}, dt_today: {}'.format(rqst['dt_complete'], dt_complete, dt_today))
    if dt_today < dt_complete:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response(
            {'message': '백업할 날짜({})는 오늘({})전이어야 한다.'.format(dt_complete, dt_today)})

    complete_work_list = Work.objects.filter(dt_end__lte=dt_complete)
    complete_work_id_list = [x.id for x in complete_work_list]
    complete_employee_list = Employee.objects.filter(work_id__in=complete_work_id_list)

    result = []
    passer_id_list = []
    for employee in complete_employee_list:
        try:
            employee_backup = Employee_Backup(
                name=employee.name,
                pNo=employee.pNo,
                employee_id=employee.employee_id,
                work_id=employee.work_id,
                dt_begin=employee.dt_begin,
                dt_end=employee.dt_end,
            )
            delete_id = employee.id
            employee_backup.save()
            employee.delete()
            result.append({'id': delete_id,
                           'name': employee.name,
                           'SUCCESS': dt_null(employee.dt_end),
                           })
            passer_id_list.append(employee.employee_id)
        except Exception as e:
            result.append({'id': employee.id,
                           'name': employee.name,
                           'ERROR': str(e),
                           })
    """
    Employee 업무 완료 근로자 백업

    passer_id_list
    """
    parameter = {"passer_id_list": passer_id_list,
                 "dt_complete": rqst['dt_complete'],
                 }
    s = requests.session()
    r = s.post(settings.EMPLOYEE_URL + 'tk_passer_work_backup', json=parameter)
    result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})

    return REG_200_SUCCESS.to_json_response({'result': result})


@cross_origin_read_allow
def tk_fix_up_employee_backup(request):
    """
    [[ 운영]] 근로자 전화번호와 이름이 Employee SERVER 내용과 틀린 부분을 바로 잡는다.
    - customer.employee.employee_id > employee.passer_id 잘못된 부분 수정
    http://0.0.0.0:8000/customer/tk_fix_up_employee
    GET
        dt_complete: 2019-07-31
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
        STATUS 416
            {'message': '백업할 날짜({})는 오늘({})전이어야 한다..format(dt_complete, dt_today)}
    """

    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    n = int(rqst['n'])
    # parameter_check = is_parameter_ok(rqst, ['work_id_!'])
    # parameter_check = is_parameter_ok(rqst, ['work_id'])
    # if not parameter_check['is_ok']:
    #     return status422(get_api(request),
    #                      {'message': '{}'.format(''.join([message for message in parameter_check['results']]))})
    # work_id = parameter_check['parameters']['work_id']
    employee_list = Employee.objects.all()
    logSend('  # employee: {}'.format(len(employee_list)))
    employee_compare_list = []
    i = 0
    for employee in employee_list:
        if i >= n:
            break
        i = i + 1
        employee_compare = {'id': employee.id, 'name': employee.name, 'pNo': employee.pNo,
                            'employee_id': employee.employee_id}
        employee_compare_list.append(employee_compare)
    logSend('  # employee: {}'.format(len(employee_compare_list)))

    s = requests.session()

    result = []
    parameter = {
        "employee_compare_list": employee_compare_list,
    }
    r = s.post(settings.EMPLOYEE_URL + 'tk_match_test_for_customer', json=parameter)
    result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})

    # logSend('  result: {}'.format(result))
    # return REG_200_SUCCESS.to_json_response({'employee_compare_list': employee_compare_list})

    fix_up_list = r.json()['miss_match_list']

    fixed_up_list = []
    employee_dict = {x.id: x for x in employee_list}
    for fix_up in fix_up_list:
        employee = employee_dict[fix_up['id']]
        employee.employee_id = fix_up['employee_id']
        if 'name' in fix_up:
            employee.name = fix_up['name']
        # employee.save()
        fixed_up_list.append(
            {'id': employee.id, 'name': employee.name, 'pNo': employee.pNo, 'passer_id': employee.employee_id})
    return REG_200_SUCCESS.to_json_response({'fixed_up_list': fixed_up_list})


@cross_origin_read_allow
def tk_fix_up_employee(request):
    """
    [[ 운영]] 근로자 전화번호와 이름이 Employee SERVER 내용과 틀린 부분을 바로 잡는다.
    - customer.employee.employee_id > employee.passer_id 잘못된 부분 수정
    http://0.0.0.0:8000/customer/tk_fix_up_employee
    GET
        dt_complete: 2019-07-31
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
        STATUS 416
            {'message': '백업할 날짜({})는 오늘({})전이어야 한다..format(dt_complete, dt_today)}
    """

    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    # s = requests.session()
    # r = s.post(settings.EMPLOYEE_URL + 'get_works', json={})
    # # logSend('  > {}'.format({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()}))
    # result_json = r.json()
    # employee_work_dict = result_json['employees_works']

    work_all = Work.objects.all()
    today = datetime.datetime.now()
    work_dict = {work.id: work.dt_end for work in work_all if work.dt_end > today}

    log = []
    employee_all = Employee.objects.all()
    for employee in employee_all:
        if employee.work_id in work_dict.keys():
            if employee.dt_end < work_dict[employee.work_id] and str_to_datetime('2019-12-30 23:59:59') < employee.dt_end:
                log.append('{}({}): {} vs {}'.format(employee.id, employee.name, employee.dt_end, work_dict[employee.work_id]))
                # logSend('  > {}: {} vs {}'.format(employee.id, employee.dt_end, work_dict[employee.work_id]))
                employee.dt_end = str_to_datetime('2020-12-31 23:59:59')
                employee.save()
    return REG_200_SUCCESS.to_json_response({'log': log})


@cross_origin_read_allow
def fix_work_dt_end(request):
    """
    업무의 종료 날짜 시간을 그날의 마지막이 되도록 수정한다.
    http://0.0.0.0:8000/customer/fix_work_dt_end
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
        STATUS 416
            {'message': '백업할 날짜({})는 오늘({})전이어야 한다..format(dt_complete, dt_today)}
    """

    # if get_client_ip(request) not in settings.ALLOWED_HOSTS:
    #     return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    work_list = Work.objects.all()
    result = []
    for work in work_list:
        if dt_str(work.dt_end, "%H:%M:%S") == "00:00:00":
            work.dt_end = work.dt_end + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
            print('  > work: {} - {}'.format(work.name, work.dt_end))
            work.save()
            result.append({'name': work.work_place_name + ':' + work.name + '(' + work.type + ')', 'dt_end': work.dt_end})
    return REG_200_SUCCESS.to_json_response({'result': result})


@cross_origin_read_allow
def temp_update_work_for_employee(request):
    """
    << 임시: 근로자 시험용 >> 업무 날짜 만 수정한다.
    http://0.0.0.0:8000/customer/temp_update_work_for_employee?work_id=68&dt_begin=2020/02/20&dt_end=2020/02/29
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
        STATUS 416
            {'message': '백업할 날짜({})는 오늘({})전이어야 한다..format(dt_complete, dt_today)}
    """

    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['work_id', 'dt_begin_@', 'dt_end_@'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    work_id = parameter_check['parameters']['work_id']
    dt_begin = parameter_check['parameters']['dt_begin']
    dt_end = parameter_check['parameters']['dt_end']

    try:
        work = Work.objects.get(id=work_id)
    except Exception as e:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무: {} 없음'.format(work_id)})
    result = 'work_id: {}'.format(work.id)
    if 'dt_begin' in rqst:
        work.dt_begin = dt_begin
        result += ', dt_begin: {}'.format(work.dt_begin)
    if 'dt_end' in rqst:
        work.dt_end = dt_end
        result += ', dt_end: {}'.format(work.dt_end)
    work.save()
    return REG_200_SUCCESS.to_json_response({'result': result})
