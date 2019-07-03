"""
Customer view

Copyright 2019. DaeDuckTech Corp. All rights reserved.
"""
import random
import requests
import datetime
from datetime import timedelta
import inspect

from django.conf import settings

from config.log import logSend, logError
from config.common import ReqLibJsonResponse
from config.common import func_begin_log, func_end_log, status422, is_parameter_ok, get_client_ip
# secret import
from config.common import hash_SHA256, no_only_phone_no, phone_format, dt_null, dt_str, str_to_datetime
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

from config.status_collection import *


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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    if AES_DECRYPT_BASE64(rqst['key']) != 'thinking':
        result = {'message':'사용 권한이 없습니다.'}
        logSend(result['message'])
        func_end_log(func_name)
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
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    # 운영 서버에서 호출했을 때 - 운영 스텝의 id를 로그에 저장한다.
    worker_id = AES_DECRYPT_BASE64(rqst['worker_id'])
    logSend('   from operation server : operation staff id ', worker_id)

    parameter_check = is_parameter_ok(rqst, ['customer_name', 'staff_name', 'staff_pNo', 'staff_email'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

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
        func_end_log(func_name)
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
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    # 운영 서버에서 호출했을 때 - 운영 스텝의 id를 로그에 저장한다.
    worker_id = AES_DECRYPT_BASE64(rqst['worker_id'])
    logSend('   from operation server : operation staff id ', worker_id)

    staffs = Staff.objects.filter(id=AES_DECRYPT_BASE64(rqst['staff_id']))
    if len(staffs) == 0:
        func_end_log(func_name)
        return REG_541_NOT_REGISTERED.to_json_response()
    staff = staffs[0]
    staff.login_pw = hash_SHA256('happy_day!!!')
    staff.save()
    result = {'message': '정상처리되었습니다.',
              'login_id': staff.login_id
              }
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    # 운영 서버에서 호출했을 때 - 운영 스텝의 id를 로그에 저장한다.
    worker_id = AES_DECRYPT_BASE64(rqst['worker_id'])
    logSend('  --- from operation server : op staff id '.format(AES_DECRYPT_BASE64(worker_id)))

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
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])
    # logSend('  before func: {} now: {} vs last: {}'.format(request.session['func_name'], datetime.datetime.now(), request.session['dt_last']))
    if (request.session['func_name'] == func_name) and \
            (datetime.datetime.strptime(request.session['dt_last'], "%Y-%m-%d %H:%M:%S") + \
             datetime.timedelta(seconds=settings.REQUEST_TIME_GAP) > datetime.datetime.now()):
        logError('Error: {} 5초 이내에 [등록]이나 [수정]요청이 들어왔다.'.format(func_name))
        func_end_log(func_name)
        return REG_409_CONFLICT.to_json_response()
    request.session['func_name'] = func_name
    request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request.session.save()

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    customer = Customer.objects.get(id=worker.co_id)
    logSend('--- corp_name{}, worker_id: {}, staff_id: {}, manager_id: {}'.format(customer.corp_name, worker_id, customer.staff_id,
                                                                                customer.manager_id))
    # 담당자(is_site_owner) 나 관리자(is_manager)가 아니면 권한이 없다.
    if not(worker.is_site_owner or worker.is_manager):
        func_end_log(func_name)
        return REG_522_MODIFY_SITE_OWNER_OR_MANAGER_ONLY.to_json_response()
    # 작업자(worker.id) 가 고객사의 담당자(staff_id)나 관리자(staff_id)가 아니면 권한이 없다. - id 로 확인한다.
    if worker.id not in [customer.staff_id, customer.manager_id]:
        func_end_log(func_name)
        return REG_522_MODIFY_SITE_OWNER_OR_MANAGER_ONLY.to_json_response()

    is_logout = False  # 담당자나 관리자가 바뀌면 로그아웃할 flag
    parameter_check = is_parameter_ok(rqst, ['staff_id_!'])
    if parameter_check['is_ok']:
        staff_id = int(parameter_check['parameters']['staff_id'])
        # 기존 담당자(customer.staff_id) 와 새로운 담당자(staff_id)가 같으면 처리할 필요 없다.
        if customer.staff_id != staff_id:
            staffs = Staff.objects.filter(id=staff_id)
            if len(staffs) == 0:
                logError(func_name, ' Staff(id:{})가 없어서 담당자가 교체되지 않았다.'.format(staff_id))
            else:
                if len(staffs) > 1:
                    logError(func_name, ' Staff(id:{})가 중복되었다.'.format(staff_id))
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
        logError(func_name, parameter_check['results'])
        func_end_log(func_name)
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
                    logError(func_name, ' Staff(id:{})가 없어서 관리자가 교체되지 않았다.'.format(manager_id))
                else:
                    if len(managers) > 1:
                        logError(func_name, ' Staff(id:{})가 중복되었다.'.format(manager_id))
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
        logError(func_name, parameter_check['results'])
        func_end_log(func_name)
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
        func_end_log(func_name)
        return REG_200_SUCCESS.to_json_response({'message': '담당자가 바뀌어 로그아웃되었습니다.'})

    func_end_log(func_name)
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
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])
    # logSend('  before func: {} now: {} vs last: {}'.format(request.session['func_name'], datetime.datetime.now(), request.session['dt_last']))
    if (request.session['func_name'] == func_name) and \
            (datetime.datetime.strptime(request.session['dt_last'], "%Y-%m-%d %H:%M:%S") + \
             datetime.timedelta(seconds=settings.REQUEST_TIME_GAP) > datetime.datetime.now()):
        logError('Error: {} 5초 이내에 [등록]이나 [수정]요청이 들어왔다.'.format(func_name))
        func_end_log(func_name)
        return REG_409_CONFLICT.to_json_response()
    request.session['func_name'] = func_name
    request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request.session.save()

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    type = rqst['type']
    corp_name = rqst['corp_name']

    relationships = Relationship.objects.filter(contractor_id=worker.co_id, type=type, corp_name=corp_name)
    if len(relationships) > 0:
        func_end_log(func_name)
        return REG_544_EXISTED.to_json_response()
    staff_name = rqst['staff_name']
    staff_pNo = no_only_phone_no(rqst['staff_pNo'])
    staff_email = rqst['staff_email']
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
    relationship = Relationship(
        contractor_id=worker.co_id,
        type=type,
        corp_id=corp.id,
        corp_name=corp_name
    )
    relationship.save()

    # 사업자 등록증 처리
    update_business_registration(rqst, corp)

    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
        corp = {'name':relationship.corp_name,
                'id':AES_ENCRYPT_BASE64(str(relationship.corp_id)),
                'staff_name':corp_dic[relationship.corp_id]['staff_name'],
                'staff_pNo':phone_format(corp_dic[relationship.corp_id]['staff_pNo']),
                'is_editble': False if relationship.contractor_id == relationship.corp_id else True,
                }
        if relationship.type == 12:
            partners.append(corp)
        elif relationship.type == 10:
            orderers.append(corp)
    result = {'partners':partners, 'orderers':orderers}
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    if not 'relationship_id' in rqst:
        logSend('relationship_id << 없음')
    logSend(rqst['relationship_id'])
    logSend(AES_DECRYPT_BASE64(rqst['relationship_id']))
    corps = Customer.objects.filter(id=AES_DECRYPT_BASE64(rqst['relationship_id']))
    if len(corps) == 0:
        func_end_log(func_name)
        return REG_541_NOT_REGISTERED.to_json_response({'message':'등록된 업체가 없습니다.'})
    corp = corps[0]

    detail_relationship = {'type':corp.type,
                           'type_name': '발주사' if corp.type == 10 else '협력사',
                           'corp_id':rqst['relationship_id'],
                           'corp_name':corp.corp_name,
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
        detail_relationship['dt_reg'] =  None if business_registration.dt_reg is None else business_registration.dt_reg.strftime('%Y-%m-%d')  # 사업자등록일
    else:
        detail_relationship['name'] = None  # 상호
        detail_relationship['regNo'] = None  # 사업자등록번호
        detail_relationship['ceoName'] = None  # # 성명(대표자)
        detail_relationship['address'] = None  # 사업장소재지
        detail_relationship['business_type'] = None  # 업태
        detail_relationship['business_item'] = None  # 종목
        detail_relationship['dt_reg'] = None  # 사업자등록일

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'detail_relationship':detail_relationship})


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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])
    # logSend('  before func: {} now: {} vs last: {}'.format(request.session['func_name'], datetime.datetime.now(), request.session['dt_last']))
    if (request.session['func_name'] == func_name) and \
            (datetime.datetime.strptime(request.session['dt_last'], "%Y-%m-%d %H:%M:%S") + \
             datetime.timedelta(seconds=settings.REQUEST_TIME_GAP) > datetime.datetime.now()):
        logError('Error: {} 5초 이내에 [등록]이나 [수정]요청이 들어왔다.'.format(func_name))
        func_end_log(func_name)
        return REG_409_CONFLICT.to_json_response()
    request.session['func_name'] = func_name
    request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request.session.save()

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    corp_id = rqst['corp_id']
    corps = Customer.objects.filter(id=AES_DECRYPT_BASE64(corp_id))
    if len(corps) == 0:
        func_end_log(func_name)
        return REG_541_NOT_REGISTERED.to_json_response({'message':'등록된 업체가 없습니다.'})
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

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()


def update_business_registration(rqst, corp):
    """
    사업자 등록증 신규 등록이나 내용 변경
    :param rqst: 호출 함수의 파라미터
    :param corp: 고객사(수요기업, 파견업체)
    :return: none
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
                    new_business_registration[key] = datetime.datetime.strptime(dt[:10], "%Y-%m-%d") # + datetime.timedelta(hours=9)
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
                logError('ERROR : 사업자 등록정보 id 가 잘못되었음', corp.name, corp.id, __package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
    func_end_log(func_name)
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
            {'message':'전화번호나 아이디가 중복되었습니다.'}
        STATUS 532
            {'message':'아이디에는 공백문자(SPACE)를 사용할 수 없습니다.'}
            {'message':'아이디에는 줄바꿈을 사용할 수 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])
    # logSend('  before func: {} now: {} vs last: {}'.format(request.session['func_name'], datetime.datetime.now(), request.session['dt_last']))
    if (request.session['func_name'] == func_name) and \
            (datetime.datetime.strptime(request.session['dt_last'], "%Y-%m-%d %H:%M:%S") + \
             datetime.timedelta(seconds=settings.REQUEST_TIME_GAP) > datetime.datetime.now()):
        logError('Error: {} 5초 이내에 [등록]이나 [수정]요청이 들어왔다.'.format(func_name))
        func_end_log(func_name)
        return REG_409_CONFLICT.to_json_response()
    request.session['func_name'] = func_name
    request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request.session.save()

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    login_id = rqst['login_id']
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
    # login_id = login_id.replace(' ', '')
    # login_id = login_id.replace('\n', '')

    if login_id.find(' ') > -1:
        logError(func_name, ' 로그인 id에 space 들어왔다. \"{}\"'.format(login_id))
        login_id = login_id.replace(' ', '')
        # func_end_log(func_name)
        # return REG_532_ID_IS_WRONG.to_json_response({'message':'아이디에는 공백문자(SPACE)를 사용할 수 없습니다.'})
    if login_id.find('\n') > -1:
        logError(func_name, ' 로그인 id에 line feed 들어왔다. \"{}\"'.format(login_id))
        login_id = login_id.replace('\n', '')
    if login_id.find('\x0D') > -1:
        logError(func_name, ' 로그인 id에 carriage return 들어왔다. \"{}\"'.format(login_id))
        login_id = login_id.replace('\x0D', '')
    logSend('   login_id = \"{}\"'.format(login_id))

    phone_no = no_only_phone_no(rqst['pNo'])
    # staffs = Staff.objects.filter(pNo=phone_no, login_id=login_id)
    # logSend([staff.name for staff in staffs])
    staffs = Staff.objects.filter(login_id=login_id)
    # logSend([staff.name for staff in staffs])
    if len(staffs) > 0:
        func_end_log(func_name)
        return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response({'message': '다른 사람이 이미 사용하는 아이디입니다.'})
    staffs = Staff.objects.filter(pNo=phone_no)
    # logSend([staff.name for staff in staffs])
    if len(staffs) > 0:
        func_end_log(func_name)
        return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response({'message': '이미 등록되어 있는 전화번호입니다.'})

    name = rqst['name']
    position = rqst['position']
    department = rqst['department']
    email = rqst['email']
    new_staff = Staff(
        name=name,
        login_id=login_id,
        login_pw=hash_SHA256('happy_day!!!'),
        co_id=worker.co_id,
        co_name=worker.co_name,
        position=position,
        department=department,
        dt_app_login=datetime.datetime.now(),
        dt_login=datetime.datetime.now(),
        pNo=phone_no,
        email=email
    )
    new_staff.save()
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    login_id = rqst['login_id'].replace(' ', '')
    login_pw = rqst['login_pw'].replace(' ', '')
    logSend('--- login_id: [{}], pw [{}] - [{}]'.format(login_id, login_pw, hash_SHA256(login_pw)))

    staffs = Staff.objects.filter(login_id=login_id)
    if len(staffs) == 0:
        func_end_log(func_name)
        return REG_530_ID_OR_PASSWORD_IS_INCORRECT.to_json_response({'message': '아이디가 없습니다.'})
    elif len(staffs) > 1:
        logError(func_name, ' login id: {} 가 중복됩니다.')
    staff = staffs[0]
    logSend('--- server: [{}] vs login [{}]'.format(staff.login_pw, hash_SHA256(login_pw)))
    if staff.login_pw != hash_SHA256(login_pw):
        func_end_log(func_name)
        return REG_530_ID_OR_PASSWORD_IS_INCORRECT.to_json_response({'message': '비밀번호가 틀렸습니다.'})

    # staffs = Staff.objects.filter(login_id=login_id, login_pw=hash_SHA256(login_pw))
    # if len(staffs) == 0:
    #     staffs = Staff.objects.filter(login_id=login_id)
    #     if len(staffs) > 0:
    #         staff = staffs[0]
    #         logSend(hash_SHA256(login_pw), ' vs\n', staff.login_pw)
    #
    #     func_end_log(func_name)
    #     return REG_530_ID_OR_PASSWORD_IS_INCORRECT.to_json_response()
    # staff = staffs[0]
    staff.dt_login = datetime.datetime.now()
    staff.is_login = True
    staff.save()
    request.session['id'] = staff.id
    request.session['func_name'] = func_name
    request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request.session.save()

    customers = Customer.objects.filter(id=staff.co_id)
    if len(customers) == 0:
        func_end_log(func_name)
        return REG_541_NOT_REGISTERED.to_json_response({'message':'등록된 업체가 없습니다.'})
    customer = customers[0]
    staff_permission = {'is_site_owner': staff.is_site_owner,  # 담당자인가?
                        'is_manager': staff.is_manager,  # 관리자인가?
                        }
    company_general = {'co_id':AES_ENCRYPT_BASE64(str(customer.id)),
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
                                 'dt_reg': None if business_registration.dt_reg is None else business_registration.dt_reg.strftime('%Y-%m-%d') # 사업자등록일
                                 }
    else:
        business_registration = {'name':None,  # 상호
                                 'regNo':None,  # 사업자등록번호
                                 'ceoName':None,  # 성명(대표자)
                                 'address':None,  # 사업장소재지
                                 'business_type':None,  # 업태
                                 'business_item':None,  # 종목
                                 'dt_reg':None  # 사업자등록일
                                 }

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'staff_permisstion':staff_permission,
                                             'company_general':company_general,
                                             'business_registration':business_registration
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.session is None or 'id' not in request.session:
        func_end_log(func_name)
        return REG_200_SUCCESS.to_json_response({'message': '이미 로그아웃되었습니다.'})
    staff = Staff.objects.get(id=request.session['id'])
    staff.is_login = False
    staff.dt_login = datetime.datetime.now()
    staff.save()
    del request.session['id']
    del request.session['dt_last']
    del request.session['func_name']
    request.session.save()

    func_end_log(func_name)
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
            {'message': '비밀번호는 8자 이상으로 만들어야 합니다.'}
            {'message': '영문, 숫자, 특수문자가 모두 포합되어야 합니다.'}
    	STATUS 542
    	    {'message':'아이디는 5자 이상으로 만들어야 합니다.'}
    	    {'message':'아이디가 중복됩니다.'}
    	STAUS 422  # 개발자 수정사항
    	    {'message':'ClientError: parameter \'staff_id\' 가 없어요'}
    	    {'message':'ClientError: parameter \'staff_id\' 가 정상적인 값이 아니예요. <암호해독 에러>'}
    	    {'message':'ClientError: parameter \'staff_id\' 본인의 것만 수정할 수 있는데 본인이 아니다.(담당자나 관리자도 아니다.'}
    	    {'message':'ServerError: parameter \'{}\' 의 직원이 없다.'.format(staff_id)}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])
    # logSend('  before func: {} now: {} vs last: {}'.format(request.session['func_name'], datetime.datetime.now(), request.session['dt_last']))
    if (request.session['func_name'] == func_name) and \
            (datetime.datetime.strptime(request.session['dt_last'], "%Y-%m-%d %H:%M:%S") + \
             datetime.timedelta(seconds=settings.REQUEST_TIME_GAP) > datetime.datetime.now()):
        logError('Error: {} 5초 이내에 [등록]이나 [수정]요청이 들어왔다.'.format(func_name))
        func_end_log(func_name)
        return REG_409_CONFLICT.to_json_response()
    request.session['func_name'] = func_name
    request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request.session.save()

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter_check = is_parameter_ok(rqst, ['staff_id_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    staff_id = parameter_check['parameters']['staff_id']

    if int(staff_id) != worker_id:
        # 수정할 직원과 로그인한 직원이 같지 않으면 - 자신의 정보를 자신이 수정할 수는 있지만 관리자가 아니면 다른 사람의 정보 수정이 금지된다.
        if not (worker.is_site_owner or worker.is_manager):
            return status422(func_name, {'message':'ClientError: parameter \'staff_id\' 본인의 것만 수정할 수 있는데 본인이 아니다.(담당자나 관리자도 아니다.'})
    staffs = Staff.objects.filter(id=staff_id)
    if len(staffs) == 0:
        return status422(func_name, {'message': 'ServerError: staff_id: {} 인 직원이 없다.'.format(staff_id)})
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
        func_end_log(func_name)
        return REG_531_PASSWORD_IS_INCORRECT.to_json_response({'message': '비밀번호가 틀렸습니다.'})

    # 새로운 id 중복 여부 확인
    if 'new_login_id' in parameter:
        new_login_id = parameter['new_login_id']  # 기존 비밀번호
        if len(new_login_id) < 5: # id 글자수 5자 이상으로 제한
            func_end_log(func_name)
            return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response({'message': '아이디는 5자 이상으로 만들어야 합니다.'})
        duplicate_staffs = Staff.objects.filter(login_id=new_login_id)
        if len(duplicate_staffs) > 0:
            func_end_log(func_name)
            return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response({'message': '다른 사람이 사용중인 아이디 입니다.'})
        parameter['login_id'] = new_login_id
        del parameter['new_login_id']

    # 새로운 pw 8자 이상, alphabet, number, 특수문자 포함여부 확인
    if 'login_pw' in parameter:
        login_pw = parameter['login_pw']
        if len(login_pw) < 8:  # id 글자수 8자 이상으로 제한
            func_end_log(func_name)
            return REG_531_PASSWORD_IS_INCORRECT.to_json_response({'message': '비밀번호는 8자 이상으로 만들어야 합니다.'})
        #
        # alphabet, number, 특수문자 포함여부 확인
        #
        if not (any(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz' for c in login_pw) and
                any(c in '0123456789' for c in login_pw) and
                any(c in '-_!@#$%^&*(){}[]/?' for c in login_pw)):
            func_end_log(func_name)
            return REG_531_PASSWORD_IS_INCORRECT.to_json_response({'message':'영문, 숫자, 특수문자(-_!@#$%^&*(){}[]/?)가 모두 포합되어야 합니다.'})
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
        logSend('--- 파견업체: {}, 담당자: {} {} {}'.format(customer.corp_name, customer.staff_name, customer.staff_pNo, customer.staff_email))
        customer.save()

    customers = Customer.objects.filter(manager_id=edit_staff.id)
    for customer in customers:
        if 'name' in parameter:
            customer.manager_name = parameter['name']
        if 'pNo' in parameter:
            customer.manager_pNo = parameter['pNo']
        if 'email' in parameter:
            customer.manager_email = parameter['email']
        logSend('--- 파견업체: {}, 관리자: {} {} {}'.format(customer.corp_name, customer.manager_name, customer.manager_pNo, customer.manager_email))
        customer.save()

    work_places = Work_Place.objects.filter(manager_id=edit_staff.id)
    for work_place in work_places:
        if 'name' in parameter:
            work_place.manager_name = parameter['name']
        if 'pNo' in parameter:
            work_place.manager_pNo = parameter['pNo']
        if 'email' in parameter:
            work_place.manager_email = parameter['email']
        logSend('--- 사업장: {}, 관리자: {} {} {}'.format(work_place.name, work_place.manager_name, work_place.manager_pNo, work_place.manager_email))
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
        func_end_log(func_name)
        return REG_403_FORBIDDEN.to_json_response()
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    staffs = Staff.objects.filter(co_id=worker.co_id).values('id', 'name', 'position', 'department', 'pNo', 'pType', 'email', 'login_id')
    arr_staff = []
    for staff in staffs:
        staff['id'] = AES_ENCRYPT_BASE64(str(staff['id']))
        staff['pNo'] = phone_format(staff['pNo'])
        arr_staff.append(staff)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'staffs':arr_staff})


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
        STATUS 422
            {'message':'사업장 이름, 관리자, 발주사 중 어느 하나도 빠지면 안 됩니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])
    # logSend('  before func: {} now: {} vs last: {}'.format(request.session['func_name'], datetime.datetime.now(), request.session['dt_last']))
    if (request.session['func_name'] == func_name) and \
            (datetime.datetime.strptime(request.session['dt_last'], "%Y-%m-%d %H:%M:%S") + \
             datetime.timedelta(seconds=settings.REQUEST_TIME_GAP) > datetime.datetime.now()):
        logError('Error: {} 5초 이내에 [등록]이나 [수정]요청이 들어왔다.'.format(func_name))
        func_end_log(func_name)
        return REG_409_CONFLICT.to_json_response()
    request.session['func_name'] = func_name
    request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request.session.save()

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    name = rqst['name']
    manager_id = rqst['manager_id']
    order_id = rqst['order_id']
    if 'address' in rqst:
        address = rqst['address']
    if 'latitude' in rqst:
        x = rqst['latitude']
    if 'longitude' in rqst:
        y = rqst['longitude']
    if len(name) == 0 or len(manager_id) == 0 or len(order_id) == 0:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':'사업장 이름, 관리자, 발주사 중 어느 하나도 빠지면 안 됩니다.'})

    list_work_place = Work_Place.objects.filter(name=name)
    if len(list_work_place) > 0:
        func_end_log(func_name)
        return REG_540_REGISTRATION_FAILED.to_json_response({'message':'같은 이름의 사업장이 있습니다.\n꼭 같은 이름의 사업장이 필요하면\n다른 이름으로 등록 후 이름을 바꾸십시요.'})

    manager = Staff.objects.get(id=AES_DECRYPT_BASE64(manager_id))
    order = Customer.objects.get(id=AES_DECRYPT_BASE64(order_id))
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
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])
    # logSend('  before func: {} now: {} vs last: {}'.format(request.session['func_name'], datetime.datetime.now(), request.session['dt_last']))
    if (request.session['func_name'] == func_name) and \
            (datetime.datetime.strptime(request.session['dt_last'], "%Y-%m-%d %H:%M:%S") + \
             datetime.timedelta(seconds=settings.REQUEST_TIME_GAP) > datetime.datetime.now()):
        logError('Error: {} 5초 이내에 [등록]이나 [수정]요청이 들어왔다.'.format(func_name))
        func_end_log(func_name)
        return REG_409_CONFLICT.to_json_response()
    request.session['func_name'] = func_name
    request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request.session.save()

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
        func_end_log(func_name)
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
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
    func_end_log(func_name)
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
            {'message': '업무 시작 날짜는 오늘 이후여야 합니다.'}
            {'message': '업무 시작 날짜보다 업무 종료 날짜가 더 빠릅니다.'}
        STATUS 544
            {'message': '등록된 업무입니다.\n업무명, 근무형태, 사업장, 담당자, 파견사 가 같으면 등록할 수 없습니다.'}
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])
    # logSend('  before func: {} now: {} vs last: {}'.format(request.session['func_name'], datetime.datetime.now(), request.session['dt_last']))
    if (request.session['func_name'] == func_name) and \
            (datetime.datetime.strptime(request.session['dt_last'], "%Y-%m-%d %H:%M:%S") + \
             datetime.timedelta(seconds=settings.REQUEST_TIME_GAP) > datetime.datetime.now()):
        logError('Error: {} 5초 이내에 [등록]이나 [수정]요청이 들어왔다.'.format(func_name))
        func_end_log(func_name)
        return REG_409_CONFLICT.to_json_response()
    request.session['func_name'] = func_name
    request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request.session.save()

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter_check = is_parameter_ok(rqst, ['name', 'work_place_id_!', 'type', 'dt_begin', 'dt_end', 'staff_id_!', 'partner_id_!'])
    if not parameter_check['is_ok']:
        return status422(func_name, {'message': '{}'.format(''.join([message for message in parameter_check['results']]))})
        # func_end_log(func_name)
        # return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    name = parameter_check['parameters']['name']
    work_place_id = parameter_check['parameters']['work_place_id']
    type = parameter_check['parameters']['type']
    dt_begin = str_to_datetime(parameter_check['parameters']['dt_begin'])
    dt_end = str_to_datetime(parameter_check['parameters']['dt_end'])
    staff_id = parameter_check['parameters']['staff_id']
    partner_id = parameter_check['parameters']['partner_id']
    if dt_begin < datetime.datetime.now():
        func_end_log(func_name)
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무 시작 날짜는 오늘 이후여야 합니다.'})
    if dt_end < dt_begin:
        func_end_log(func_name)
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무 시작 날짜보다 업무 종료 날짜가 더 빠릅니다.'})

    works = Work.objects.filter(name=name,
                                type=type,
                                work_place_id=work_place_id,
                                staff_id=staff_id,
                                contractor_id=partner_id,
                                )
    # is_empty = False
    # blanks = []
    # for key in ['name', 'work_place_id', 'type', 'dt_begin', 'dt_end', 'staff_id', 'partner_id']:
    #     if key in rqst:
    #         if len(rqst[key]) == 0:
    #             blanks.append(key)
    #             is_empty = True
    #     else:
    #         blanks.append(key)
    #         is_empty = True
    # if is_empty:
    #     func_end_log(func_name)
    #     return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '모든 항목은 어느 하나도 빠지면 안 됩니다.'})
    # works = Work.objects.filter(name=rqst['name'],
    #                             type=rqst['type'],
    #                             work_place_id=AES_DECRYPT_BASE64(rqst['work_place_id']),
    #                             staff_id=AES_DECRYPT_BASE64(rqst['staff_id']),
    #                             contractor_id=AES_DECRYPT_BASE64(rqst['partner_id']),
    #                             )
    if len(works) > 0:
        func_end_log(func_name)
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
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])
    # logSend('  before func: {} now: {} vs last: {}'.format(request.session['func_name'], datetime.datetime.now(), request.session['dt_last']))
    if (request.session['func_name'] == func_name) and \
            (datetime.datetime.strptime(request.session['dt_last'], "%Y-%m-%d %H:%M:%S") + \
             datetime.timedelta(seconds=settings.REQUEST_TIME_GAP) > datetime.datetime.now()):
        logError('Error: {} 5초 이내에 [등록]이나 [수정]요청이 들어왔다.'.format(func_name))
        func_end_log(func_name)
        return REG_409_CONFLICT.to_json_response()
    request.session['func_name'] = func_name
    request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request.session.save()

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter_check = is_parameter_ok(rqst, ['work_id_!'])
    if not parameter_check['is_ok']:
        return status422(func_name, {'message': '{}'.format(''.join([message for message in parameter_check['results']]))})
        # func_end_log(func_name)
        # return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    work_id = parameter_check['parameters']['work_id']

    works = Work.objects.filter(id=work_id)
    if len(works) == 0:
        logError(func_name, ' work id: {} 없음'.format(work_id))
        return status422(func_name, {'message': 'ServerError: Work 에 work_id 이(가) 없거나 중복됨'})
    # if work.contractor_id != worker.co_id:
    #     logError('ERROR: 발생하면 안되는 에러 - 사업장의 파견사와 직원의 파견사가 틀림', __package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    #     func_end_log(func_name)
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
                func_end_log(func_name)
                return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무 시작 날짜를 오늘 이전으로 변경할 수 없습니다.'})
            is_update_dt_begin = True
        else:
            if str_to_datetime(parameter_check['parameters']['dt_begin']) != work.dt_begin:
                func_end_log(func_name)
                return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무가 시작되면 시작 날짜를 변경할 수 없습니다.'})

    is_update_dt_end = False
    parameter_check = is_parameter_ok(rqst, ['dt_end'])
    if parameter_check['is_ok']:
        work.dt_end = str_to_datetime(parameter_check['parameters']['dt_end'])
        is_update_dt_end = True
    if work.dt_end < work.dt_begin:
        func_end_log(func_name)
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
        logError(func_name, parameter_check['results'])
        func_end_log(func_name)
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
        logError(func_name, parameter_check['results'])
        func_end_log(func_name)
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
        logError(func_name, parameter_check['results'])
        func_end_log(func_name)
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '이 메세지를 보시면 로그아웃 하십시요.'})

    if is_update_dt_begin or is_update_dt_end or is_update_name or is_update_type or is_update_work_place or is_update_partner or is_update_staff:
        work.save()

    update_employee_work_infor = {
        'customer_work_id': AES_ENCRYPT_BASE64(str(work.id)),
        'work_place_name': work.work_place_name,
        'work_name_type': '{} ({})'.format(work.name, work.type),
        'begin': work.dt_begin.strftime('%Y/%m/%d'),
        'end': work.dt_end.strftime('%Y/%m/%d'),
        'staff_name': work.staff_name,
        'staff_pNo': work.staff_pNo,
        'update_employee_pNo_list': update_employee_pNo_list,
    }
    r = requests.post(settings.EMPLOYEE_URL + 'update_work_for_customer', json=update_employee_work_infor)
    logSend({'url': r.url, 'POST': update_employee_work_infor, 'STATUS': r.status_code, 'R': r.json()})
    is_update_employee = True if r.status_code == 200 else False

    func_end_log(func_name)
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
    사업장 업무 목록
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/list_work?work_place_id
    GET
        work_place_id   = cipher 사업장 id
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
    dt_today = datetime.datetime.now()
    works = Work.objects.filter(work_place_id=AES_DECRYPT_BASE64(work_place_id),
                                # dt_end=None,
                                dt_end__gte=dt_today).values('id',
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
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
    print(dt_begin)
    str_dt_end = rqst['dt_end']
    if len(str_dt_end) == 0:
        dt_end = datetime.datetime.now() + timedelta(days=365)
    else:
        dt_end = datetime.datetime.strptime(str_dt_end, '%Y-%m-%d')
    print(dt_end)
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
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def reg_employee(request):
    """
    근로자 등록 - 업무 선택 >> 전화번호 목록 입력 >> [등록 SMS 안내 발송]
    - 업무가 시작되고 나서 추가되는 근로자를 등록하기 위해 "출근 날짜" 추가 - 2019/05/25
    - SMS 를 보내지 못한 전화번호는 근로자 등록을 하지 않는다.
    - response 로 확인된 SMS 못보낸 전화번호에 표시해야 하다.
        주)	response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/reg_employee?work_id=qgf6YHf1z2Fx80DR8o_Lvg&dt_answer_deadline=2019-03-01 19:00:00&phone_numbers=010-3333-5555&phone_numbers=010-5555-7777&phone_numbers=010-7777-9999
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])
    # logSend('  before func: {} now: {} vs last: {}'.format(request.session['func_name'], datetime.datetime.now(), request.session['dt_last']))
    if (request.session['func_name'] == func_name) and \
            (datetime.datetime.strptime(request.session['dt_last'], "%Y-%m-%d %H:%M:%S") + \
             datetime.timedelta(seconds=settings.REQUEST_TIME_GAP) > datetime.datetime.now()):
        logError('Error: {} 5초 이내에 [등록]이나 [수정]요청이 들어왔다.'.format(func_name))
        func_end_log(func_name)
        return REG_409_CONFLICT.to_json_response()
    request.session['func_name'] = func_name
    request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request.session.save()

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter_check = is_parameter_ok(rqst, ['work_id_!', 'dt_answer_deadline', 'dt_begin', 'phone_numbers'])
    # parameter_check = is_parameter_ok(rqst, ['work_id_!', 'dt_answer_deadline', 'phone_numbers'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    work_id = parameter_check['parameters']['work_id']
    dt_answer_deadline = str_to_datetime(parameter_check['parameters']['dt_answer_deadline'])
    dt_begin = str_to_datetime(parameter_check['parameters']['dt_begin'])
    phone_numbers = parameter_check['parameters']['phone_numbers']

    work_list = Work.objects.filter(id=work_id)
    if len(work_list) == 0:
        return status422(func_name, {'message': 'ServerError: Work 에 id={} 이(가) 없다'.format(work_id)})
    elif len(work_list) > 1:
        logError(func_name, ' Work(id:{})가 중복되었다.'.format(work_id))
    work = work_list[0]

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
    if dt_begin < datetime.datetime.now():
        func_end_log(func_name)
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근무 시작 날짜는 오늘보다 늦어야 합니다.'})

    if dt_begin < dt_answer_deadline:
        func_end_log(func_name)
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '답변 시한은 근무 시작 날짜보다 빨라야 합니다.'})

    if dt_answer_deadline < datetime.datetime.now():
        func_end_log(func_name)
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '답변 시한은 현재 시각보다 빨라야 합니다.'})

    if dt_begin < work.dt_begin:
        func_end_log(func_name)
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근무 시작 날짜는 업무 시작 날짜보다 같거나 늦어야 합니다.'})

    # if work.dt_end < dt_end:
    #     func_end_log(func_name)
    #     return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근무 종료 날짜는 업무 종료 날짜보다 먼저이거나 같아야 합니다.'})
    #
    # if dt_end < dt_begin:
    #     func_end_log(func_name)
    #     return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근무 시작 날짜는 업무 종료 날짜보다 빨라야 합니다.'})
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
    new_employee_data = {"customer_work_id": AES_ENCRYPT_BASE64(str(work.id)),
                         "work_place_name": work.work_place_name,
                         "work_name_type": work.name + ' (' + work.type + ')',
                         "dt_begin": work.dt_begin.strftime('%Y/%m/%d'),
                         "dt_end": work.dt_end.strftime('%Y/%m/%d'),
                         "staff_name": work.staff_name,
                         "staff_phone": work.staff_pNo,
                         "dt_answer_deadline": rqst['dt_answer_deadline'],
                         "dt_begin_employee": dt_begin.strftime('%Y/%m/%d'),   # 근로자별 업무 시작일
                         "dt_end_employee": work.dt_end.strftime('%Y/%m/%d'),  # 근로자별 업무 종료일 (여기서는 업무종료일과 동일)
                         "is_update": False,
                         "phones": new_phone_list,
                         }
    # logSend(new_employee_data)
    response_employee = requests.post(settings.EMPLOYEE_URL + 'reg_employee_for_customer', json=new_employee_data)
    # logSend(response_employee)
    if response_employee.status_code != 200:
        func_end_log(func_name)
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
                        find_employee.save()
            else:
                new_employee = Employee(
                    employee_id=sms_result[phone],
                    is_accept_work=None,  # 아직 근로자가 결정하지 않았다.
                    is_active=0,  # 근무 중 아님
                    dt_begin=dt_begin,
                    dt_end=work.dt_end,
                    work_id=work.id,
                    pNo=phone,
                )
                new_employee.save()
    logSend('  - count bad_phone_list: {}, work_count_over_list: {}, feature_phone_list: {}, bad_condition_list: {}'.format(len(bad_phone_list),
                                                                                                                        len(work_count_over_list),
                                                                                                                        len(feature_phone_list),
                                                                                                                        len(bad_condition_list)))
    #
    # SMS 가 에러나는 전화번호 표시 html
    #
    if len(bad_phone_list) > 0 or len(bad_condition_list) > 0 or len(work_count_over_list) > 0 or len(feature_phone_list) > 0:
        notification = '<html><head><meta charset=\"UTF-8\"></head><body>' \
                       '<h3><span style=\"color: #808080;\">등록되지 않은 전화번호</span></h3>'
        if len(bad_phone_list) > 0:
            notification += '<p style=\"color: #dd0000;\">문자를 보낼 수 없는 전화번호였습니다.</p>' \
                            '<p style=\"text-align: center; padding-left: 30px; color: #808080;\">'
            for bad_phone in bad_phone_list:
                notification += bad_phone + '<br>'
        if len(bad_condition_list) > 0:
            notification += '<br>' \
                            '<p style=\"color: #dd0000;\">다른 업무와 기간이 겹치는 전화번호입니다.</p>' \
                            '<p style=\"text-align: center; padding-left: 30px; color: #808080;\">'
            for bad_condition in bad_condition_list:
                notification += bad_condition + '<br>'
        if len(work_count_over_list) > 0:
            notification += '<br>' \
                            '<p style=\"color: #dd0000;\">업무를 받을 수 있는 한계(2개)가 넘은 전화번호입니다.</p>' \
                            '<p style=\"text-align: center; padding-left: 30px; color: #808080;\">'
            for work_count_over in work_count_over_list:
                notification += work_count_over + '<br>'
        if len(feature_phone_list) > 0:
            notification += '<br>' \
                            '<p style=\"color: #dd0000;\">업무 요청이 이미 있는 피처 폰 전화번호입니다.</p>' \
                            '<p style=\"text-align: center; padding-left: 30px; color: #808080;\">'
            for feature_phone in feature_phone_list:
                notification += feature_phone + '<br>'
        notification += '</p></body></html>'
    else:
        notification = '<html><head><meta charset=\"UTF-8\"></head><body>' \
                       '<h3><span style=\"color: #808080;\">정상적으로 처리되었습니다.</span></h3>' \
                       '</body></html>'
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'duplicate_pNo': duplicate_pNo, 'bad_pNo': bad_phone_list, 'bad_condition': bad_condition_list, 'notification': notification})


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
            {'message':'파견사 측에 근로자 정보가 없습니다.'}
        STATUS 422  # 개발자 수정사항
            {'message':'업무 참여 시간이 종료되었습니다.'}
            {'message': 'ClientError: parameter \'worker_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'employee_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'employee_name\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'employee_pNo\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: parameter \'is_accept\' 가 정상적인 값이 아니예요.'}

            {'message': 'ServerError: Work 에 work_id 이(가) 없거나 중복됨'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['worker_id_!', 'work_id_!', 'employee_id_!', 'employee_name', 'employee_pNo', 'is_accept'])
    if not parameter_check['is_ok']:
        return status422(func_name, {'message': '{}'.format(''.join([message for message in parameter_check['results']]))})
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
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
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '업무 참여 시간이 종료되었습니다.'})
    work = works[0]

    employees = Employee.objects.filter(work_id=work.id, pNo=employee_pNo)
    if len(employees) == 0:
        func_end_log(func_name)
        return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response({'message': '파견사 측에 근로자 정보가 없습니다.'})

    employee = employees[0]
    if employee.dt_begin < datetime.datetime.now() and not is_accept:
        employee.delete()
    else:
        employee.employee_id = employee_id
        employee.name = employee_name
        employee.is_accept_work = is_accept
        employee.save()

    func_end_log(func_name)
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
            'employee_pNo':01011112222,
            'new_name':name,
            'new_pNo':pNo
        }
    response
        STATUS 200
            {
                'msg': '정상처리되었습니다.',
                'login_id': staff.login_id,
            }
        STATUS 409
            {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
        STATUS 542
            {'message':'파견사 측에 근로자 정보가 없습니다.'}
        STATUS 422  # 개발자 수정사항
            {'message':'업무 참여 시간이 종료되었습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])
    #
    # 서버 to 서버 에 적용할 수 없어 삭제 2019-05-17
    #
    # logSend('  before func: {} now: {} vs last: {}'.format(request.session['func_name'], datetime.datetime.now(), request.session['dt_last']))
    # if (request.session['func_name'] == func_name) and \
    #         (datetime.datetime.strptime(request.session['dt_last'], "%Y-%m-%d %H:%M:%S") + \
    #          datetime.timedelta(seconds=settings.REQUEST_TIME_GAP) > datetime.datetime.now()):
    #     logError('Error: {} 5초 이내에 [등록]이나 [수정]요청이 들어왔다.'.format(func_name))
    #     func_end_log(func_name)
    #     return REG_409_CONFLICT.to_json_response()
    # request.session['func_name'] = func_name
    # request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # request.session.save()

    # 운영 서버에서 호출했을 때 - 운영 스텝의 id를 로그에 저장한다.
    worker_id = AES_DECRYPT_BASE64(rqst['worker_id'])
    logSend('   from employee server : operation staff id ', worker_id)

    logSend(rqst['employee_pNo'])
    logSend(rqst['new_name'])
    logSend(rqst['new_pNo'])

    employees = Employee.objects.filter(pNo=rqst['employee_pNo'])

    for employee in employees:
        employee.name = rqst['new_name']
        employee.pNo = rqst['new_pNo']
        employee.save()

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()


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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])
    # logSend('  before func: {} now: {} vs last: {}'.format(request.session['func_name'], datetime.datetime.now(), request.session['dt_last']))
    if (request.session['func_name'] == func_name) and \
            (datetime.datetime.strptime(request.session['dt_last'], "%Y-%m-%d %H:%M:%S") + \
             datetime.timedelta(seconds=settings.REQUEST_TIME_GAP) > datetime.datetime.now()):
        logError('Error: {} 5초 이내에 [등록]이나 [수정]요청이 들어왔다.'.format(func_name))
        func_end_log(func_name)
        return REG_409_CONFLICT.to_json_response()
    request.session['func_name'] = func_name
    request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request.session.save()

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter_check = is_parameter_ok(rqst, ['work_id_!', 'employee_id_!', 'dt_end'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    work_id = parameter_check['parameters']['work_id']
    employee_id = parameter_check['parameters']['employee_id']
    dt_end = str_to_datetime(parameter_check['parameters']['dt_end'])

    work = Work.objects.get(id=work_id)
    employee = Employee.objects.get(id=employee_id)
    logSend('  employee: {}'.format({key: employee.__dict__[key] for key in employee.__dict__.keys() if not key.startswith('_')}))

    # 업무에 투입되었는가?
    # if 'is_active' in rqst.keys():
    dt_today = datetime.datetime.now()
    if employee.dt_begin < dt_today:
        #
        # 근로자가 업무에 투입되고 난 다음에 예정된 종료일을 변경할 때 사용
        #
        parameter_check = is_parameter_ok(rqst, ['is_active', 'message'])
        if not parameter_check['is_ok']:
            func_end_log(func_name)
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
        if len(message) > 0:
            #
            # to employee server : message,
            #
            logSend('message: {} (아직 처리하지 않는다.)'.format(rqst['message']))
        employee.save()
        logSend('  employee: {}'.format(
            {key: employee.__dict__[key] for key in employee.__dict__.keys() if not key.startswith('_')}))
        #
        # 근로기간이 변경되었으면 근로자서버를 업데이트한다.
        #
        employees_infor = {
            'employee_id': AES_ENCRYPT_BASE64(str(employee.employee_id)),
            'work_id': AES_ENCRYPT_BASE64(str(work.id)),
            'dt_end': dt_end.strftime("%Y/%m/%d"),
        }
        r = requests.post(settings.EMPLOYEE_URL + 'change_work_period_for_customer', json=employees_infor)
        result['work_dt_end'] = {'url': r.url, 'POST': employees_infor, 'STATUS': r.status_code, 'R': r.json()}

        func_end_log(func_name)
        return REG_200_SUCCESS.to_json_response()
    #
    # 근로자에게 업무 시작일 전에 업무 투입을 요청할 때 사용
    #
    parameter_check = is_parameter_ok(rqst, ['dt_answer_deadline', 'dt_begin'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    # phone_no = parameter_check['parameters']['phone_no']
    dt_answer_deadline = str_to_datetime(parameter_check['parameters']['dt_answer_deadline'])
    dt_begin = str_to_datetime(parameter_check['parameters']['dt_begin'])

    #
    # 답변 시한 검사
    #
    logSend('  - dt_begin: {}, work.dt_begin: {}, work.dt_end: {}, dt_end: {}, dt_answer_deadline: {}'.format(dt_begin, work.dt_begin, work.dt_end, dt_end, dt_answer_deadline))
    if dt_begin < datetime.datetime.now():
        func_end_log(func_name)
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근무 시작 날짜는 오늘보다 늦어야 합니다.'})

    if dt_begin < dt_answer_deadline:
        func_end_log(func_name)
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '답변 시한은 근무 시작 날짜보다 빨라야 합니다.'})

    if dt_answer_deadline < datetime.datetime.now():
        func_end_log(func_name)
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '답변 시한은 현재 시각보다 빨라야 합니다.'})

    if dt_begin < work.dt_begin:
        func_end_log(func_name)
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근무 시작 날짜는 업무 시작 날짜보다 같거나 늦어야 합니다.'})

    if work.dt_end < dt_end:
        func_end_log(func_name)
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '근무 종료 날짜는 업무 종료 날짜보다 먼저이거나 같아야 합니다.'})

    if dt_end < dt_begin:
        func_end_log(func_name)
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
            func_end_log(func_name)
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '전화번호를 바꾸려면 업무 답변 기한을 꼭 넣어야 합니다.'})
        employee.pNo = no_only_phone_no(rqst['phone_no'])
        #
        # 근로자 서버로 근로자의 업무 의사와 답변을 요청
        #
        new_employee_data = {"customer_work_id": AES_ENCRYPT_BASE64(str(work.id)),
                             "work_place_name": work.work_place_name,
                             "work_name_type": work.name + ' (' + work.type + ')',
                             "dt_begin": work.dt_begin.strftime('%Y/%m/%d'),
                             "dt_end": work.dt_end.strftime('%Y/%m/%d'),
                             "staff_name": work.staff_name,
                             "staff_phone": work.staff_pNo,
                             "dt_answer_deadline": rqst['dt_answer_deadline'],
                             "dt_begin_employee": employee.dt_begin.strftime('%Y/%m/%d'),  # 개별 근로자의 업무 시작날짜
                             "dt_end_employee": employee.dt_end.strftime('%Y/%m/%d'),      # 개별 근로자의 업무 종료날짜
                             "is_update": False,
                             "phones": [employee.pNo]
                             }
        # print(new_employee_data)
        response_employee = requests.post(settings.EMPLOYEE_URL + 'reg_employee_for_customer', json=new_employee_data)
        logSend('--- ', response_employee.json())
        if response_employee.status_code != 200:
            func_end_log(func_name)
            return ReqLibJsonResponse(response_employee)
        sms_result = response_employee.json()['result']
        if sms_result[employee.pNo] < -100:
            # 잘못된 전화번호 근로자 등록 안함
            func_end_log(func_name)
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '잘못된 전화번호입니다.'})
        elif sms_result[employee.pNo] < -30:
            # 업무 요청을 많이 받아서 받을 수 없다.
            func_end_log(func_name)
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '요청받은 업무가 많아서(2개) 더 요청할 수 없습니다.'})
        elif sms_result[employee.pNo] < -20:
            # 다른 업무 때문에 업무 배정이 안되는 근로자 - 근로자 등록 안함
            func_end_log(func_name)
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '피쳐폰이라서 업무를 하나밖에 받지 못합니다.'})
        elif sms_result[employee.pNo] < -1:
            # 다른 업무 때문에 업무 배정이 안되는 근로자 - 근로자 등록 안함
            func_end_log(func_name)
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '근로자의 다른 업무와 기간이 겹칩니다.'})
        employee.employee_id = sms_result[employee.pNo]

    # 2019/06/17 고객웹 > 근로자 > 수정: 답변을 초기화 할 때 사용
    employee.is_accept_work = None
    employee.save()

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403
def list_employee(request):
    """
    근로자 목록
      - 업무별 리스트
      -
      - option 에 따라 근로자 근태 내역 추가 (2019
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/list_employee?work_id=1&is_working_history=YES
    GET
        work_id         = 업무 id
        is_working_history = 업무 형태 # YES: 근태내역 추가, NO: 근태내역 없음(default)
    response
        STATUS 200
            # 업무 시직 전 응답 - 업무 수락 상태 표시
            {
              "message": "정상적으로 처리되었습니다.",
              "employees": [
                {
                  "id": "iZ_rkELjhh18ZZauMq2vQw==",
                  "name": "이순신",
                  "pNo": "010-1111-3555",
                  "dt_begin": "2019-03-08 19:09:30",
                  "dt_end": "2019-03-14 00:00:00",
                  "state": "답변 X",
                  "is_not_begin": "1"
                },
                {
                  "id": "gDoPqy_Pea6imtYYzWrEXQ==",
                  "name": "양만춘",
                  "pNo": "010-1111-2222",
                  "dt_begin": "2019-03-08 19:09:30",
                  "dt_end": "2019-03-14 00:00:00",
                  "state": "거절",
                  "is_not_begin": "1"
                },
                {
                  "id": "ox9fRbgDQ-PxgCiqoDLYhQ==",
                  "name": "강감찬",
                  "pNo": "010-4444-5555",
                  "dt_begin": "2019-03-08 19:09:30",
                  "dt_end": "2019-03-14 00:00:00",
                  "state": "수락",
                  "is_not_begin": "1"
                },
                {
                  "id": "PTs37nITB5mJAWFwUQKixQ==",
                  "name": "-----",
                  "pNo": "010-33-3344",
                  "dt_begin": "2019-03-10 13:15:29",
                  "dt_end": "2019-03-14 00:00:00",
                  "state": "잘못된 전화번호",
                  "is_not_begin": "1"
                }
              ]
            }
            # 업무 시작 후 응답 - 출입 시간 표시
            {
              "message": "정상적으로 처리되었습니다.",
              "employees": [
                {
                  "id": "ox9fRbgDQ-PxgCiqoDLYhQ==",
                  "name": "강감찬",
                  "pNo": "010-4444-5555",
                  "dt_begin_beacon": "08:20",
                  "dt_begin_touch": "08:31",
                  "dt_end_beacon": "17:48",
                  "dt_end_touch": "17:38",
                  "state": "",
                  "is_not_begin": "0"
                },
                {
                  "id": "voGxXzbAurv_GvSDv1nciw==",
                  "name": "안중근",
                  "pNo": "010-3333-4444",
                  "dt_begin_beacon": "",
                  "dt_begin_touch": "08:31",
                  "dt_end_beacon": "",
                  "dt_end_touch": "17:31",
                  "state": "SMS",
                  "is_not_begin": "0"
                },
                {
                  "id": "ox9fRbgDQ-PxgCiqoDLYhQ==", # 업무가 시작되었지만 아직 업무에 투입되지 않은 근로자 처리
                  "name": "강감찬",
                  "pNo": "010-4444-5555",
                  "dt_begin": "2019-03-08 19:09:30",
                  "dt_end": "2019-03-14 00:00:00",
                  "state": "수락",
                  "is_not_begin": "1"
                },
                {
                  "id": "dMNzyCm2k_hGaqkDrFojAA==",
                  "name": "이순신",
                  "pNo": "010-1111-3333",
                  "dt_begin_beacon": "08:16",
                  "dt_begin_touch": "08:27",
                  "dt_end_beacon": "17:50",
                  "dt_end_touch": "17:33",
                  "state": "",
                  "is_not_begin": "0"
                }
              ]
            }
        STATUS 503
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    work_id = AES_DECRYPT_BASE64(rqst['work_id'])
    work = Work.objects.get(id=work_id)  # 업무 에러 확인용
    dt_today = datetime.datetime.now()

    s = requests.session()
    work_info = {'staff_id': AES_ENCRYPT_BASE64(str(worker.id)),
                 'work_id': AES_ENCRYPT_BASE64(str(work.id)),
                 }
    employees = []
    if work.dt_begin < dt_today:
        # 업무가 시작되었다.
        work_info['year_month_day'] = dt_today.strftime("%Y-%m-%d")
        response = s.post(settings.CUSTOMER_URL + 'staff_employees_at_day', json=work_info)
        employee_list = response.json()['employees']
        for employee in employee_list:
            logSend(' - employee: {}'.format([employee[item] for item in employee.keys()]))
            if str_to_datetime(employee['dt_begin']) < dt_today:
                employee_web = {
                    'id': employee['employee_id'],
                    'name': employee['name'],
                    'pNo': employee['phone'],
                    'dt_begin': employee['dt_begin'],
                    'dt_end': employee['dt_end'],
                    'dt_begin_beacon': "" if employee['dt_begin_beacon'] is None else employee['dt_begin_beacon'][11:16],
                    'dt_begin_touch': "" if employee['dt_begin_touch'] is None else employee['dt_begin_touch'][11:16],
                    'dt_end_beacon': "" if employee['dt_end_beacon'] is None else employee['dt_end_beacon'][11:16],
                    'dt_end_touch': "" if employee['dt_end_touch'] is None else employee['dt_end_touch'][11:16],
                    'state': "",
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
                    'is_not_begin': True,
                }
            employees.append(employee_web)
    else:
        # 업무가 아직 시작되지 않았다.
        response = s.post(settings.CUSTOMER_URL + 'staff_employees', json=work_info)
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

    result = {'employees': employees}
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)

    # employees = Employee.objects.filter(work_id=work_id)
    # arr_employee = []
    # today = datetime.datetime.now()
    # # print('--- ', work.dt_begin.strftime("%Y-%m-%d %H:%M:%S"), today.strftime("%Y-%m-%d %H:%M:%S"))
    # # if False:
    # if today < work.dt_begin:
    #     # print('--- 업무 시작 전')
    #     # 업무가 시작되기 전 근로자에게 SMS 를 보내고 답변 상태를 표시
    #     for employee in employees:
    #         state = "잘못된 전화번호"
    #         if employee.employee_id != -101:
    #             if employee.is_accept_work is None:
    #                 state = "답변 X"
    #             elif employee.is_accept_work:
    #                 state = "수락"
    #             else:
    #                 state = "거절"
    #         view_employee = {'id': AES_ENCRYPT_BASE64(str(employee.id)),
    #                          'name': employee.name,
    #                          'pNo': phone_format(employee.pNo),
    #                          'dt_begin': employee.dt_begin.strftime("%Y-%m-%d %H:%M:%S"),
    #                          'dt_end': employee.dt_end.strftime("%Y-%m-%d %H:%M:%S"),
    #                          'state': state,
    #                          'is_not_begin': True,
    #                          }
    #         arr_employee.append(view_employee)
    # else:
    #     # print('--- 업무 시작 후')
    #     # 업무가 시작되었으면 당일의 근태내역을 표시
    #     # 근로자 서버에서 가져오나?
    #     # employees_infor = {
    #     #     'employees': [],
    #     #     'year_month_day': rqst['dt'],
    #     #     'work_id': rqst['dt'],
    #     # }
    #     # r = requests.post(settings.EMPLOYEE_URL + 'pass_record_of_employees_in_day_for_customer', json=employees_infor)
    #     # employees = r.json()['employees']
    #     for employee in employees:
    #         # 주석처리된 부분은 임시 데이터를 만드는 부분
    #         # today_str = today.strftime("%Y-%m-%d ")
    #         # employee.dt_begin_beacon = datetime.datetime.strptime(today_str + "08:" + str(random.randint(0,10) + 15) + ":00", "%Y-%m-%d %H:%M:%S")
    #         # employee.dt_begin_touch = datetime.datetime.strptime(today_str + "08:" + str(random.randint(0,10) + 25) + ":00", "%Y-%m-%d %H:%M:%S")
    #         # employee.dt_end_touch = datetime.datetime.strptime(today_str + "17:" + str(random.randint(0,10) + 30) + ":00", "%Y-%m-%d %H:%M:%S")
    #         # employee.dt_end_beacon = datetime.datetime.strptime(today_str + "17:" + str(random.randint(0,10) + 40) + ":00", "%Y-%m-%d %H:%M:%S")
    #         # print(employee.dt_begin_beacon, employee.dt_begin_touch, employee.dt_end_touch, employee.dt_end_beacon)
    #         # state = ""
    #         # if employee.pNo == '01033334444':
    #         #     state = "SMS"
    #         #     employee.dt_begin_beacon = None
    #         #     employee.dt_end_beacon = None
    #         # print(employee.dt_begin_beacon, employee.dt_begin_touch, employee.dt_end_touch, employee.dt_end_beacon)
    #         if today < employee.dt_begin:
    #             if employee.is_accept_work is None:
    #                 state = "답변 X"
    #             elif employee.is_accept_work:
    #                 state = "수락"
    #             else:
    #                 state = "거절"
    #             view_employee = {'id': AES_ENCRYPT_BASE64(str(employee.id)),
    #                              'name': employee.name,
    #                              'pNo': phone_format(employee.pNo),
    #                              'dt_begin': employee.dt_begin.strftime("%Y-%m-%d %H:%M:%S"),
    #                              'dt_end': employee.dt_end.strftime("%Y-%m-%d %H:%M:%S"),
    #                              'state': state,
    #                              'is_not_begin': True,
    #                              }
    #         else:
    #             if employee.is_accept_work is None or not employee.is_accept_work:
    #                 # 업무가 시작되었어도 답변이 없거나 거절한 근로자 삭제
    #                 logSend('  - accept is none or reject: {}'.format(employee.pNo))
    #                 employee.delete()
    #                 continue
    #             view_employee = {'id': AES_ENCRYPT_BASE64(str(employee.id)),
    #                              'name': employee.name,
    #                              'pNo': phone_format(employee.pNo),
    #                              'dt_begin_beacon': dt_str(employee.dt_begin_beacon, "%H:%M"),  # "%Y-%m-%d %H:%M:%S"),
    #                              'dt_begin_touch': dt_str(employee.dt_begin_touch, "%H:%M"),  # "%Y-%m-%d %H:%M:%S"),
    #                              'dt_end_beacon': dt_str(employee.dt_end_beacon, "%H:%M"),  # "%Y-%m-%d %H:%M:%S"),
    #                              'dt_end_touch': dt_str(employee.dt_end_touch, "%H:%M"),  # "%Y-%m-%d %H:%M:%S"),
    #                              'state': "",
    #                              'is_not_begin': False,
    #                              }
    #         arr_employee.append(view_employee)
    # if rqst['is_working_history'].upper() == 'YES':
    #     logSend('   *** request: working history')
    #     #
    #     #
    #     # 근로자 서버에 근태 내역 요청
    #     #
    # result = {'employees': arr_employee}
    # func_end_log(func_name)
    # return REG_200_SUCCESS.to_json_response(result)


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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
    else :
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
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
            print('    ', work['name'], work['type'], work['type'], work['staff_name'], work['staff_pNo'], len(employees))
            summary = {u'업무':work['name'],
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
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
            print('    ', work['name'], work['type'], work['type'], work['staff_name'], work['staff_pNo'], len(employees))
            no_employees += len(employees)
            no_late += 3
            no_absent += 1
        work_place['summary'] = {u'인원':no_employees,
                                 u'지각':no_late,
                                 u'결근':no_absent
                                 }
        arr_work_place.append(work_place)
    result = {'arr_work_place': arr_work_place}
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    if ('staff_id' in rqst) or (len(rqst['staff_id']) == 0):
        works = Work.objects.filter(staff_id=worker_id, dt_end__gt=datetime.datetime.now())
    else:
        works = Work.objects.filter(staff_id=AES_ENCRYPT_BASE64(rqst['staff_id']), dt_end__gt=datetime.datetime.now())
    arr_work = []
    for work in works:
        print(work['name'], work['work_place_name'], work['contractor_name'], work['type'], work['staff_name'], work['staff_pNo'])
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
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    parameter_check = is_parameter_ok(rqst, ['work_id_!', 'employee_id_!', 'year_month'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

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
    # func_end_log(func_name)
    # return REG_200_SUCCESS.to_json_response(result)

    # employees = Employee.objects.filter(id=employee_id, work_id=work_id)

    parameters = {"employee_id": AES_ENCRYPT_BASE64(str(employee.employee_id)),
                  "dt": year_month
                  }
    s = requests.session()
    r = s.post(settings.EMPLOYEE_URL + 'my_work_histories_for_customer', json=parameters)
    if r.status_code != 200:
        func_end_log(func_name)
        return ReqLibJsonResponse(r)
    month_working = r.json()['working']
    for working in month_working:
        working['day'] = working['year_month_day'][8:10]
        try:
            working['in_hour_min'] = working['dt_begin'][11:16]
            working['out_hour_min'] = working['dt_end'][11:16]
        except Exception as e:
            logSend(func_name, ' working data 의 날짜 시간 변경 오류 {} {} {} ({})'.format(working['year_month_day'], working['dt_begin'], working['dt_end'], str(e)))
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
    func_end_log(func_name)
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
            'message': '업그레이드가 필요합니다.',
            'url': 'http://...' # itune, google play update
        }
        STATUS 520
        {'message': '검사하려는 버전 값이 양식에 맞지 않습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    version = rqst['v']
    items = version.split('.')
    ver_dt = items[len(items) - 1]
    print(ver_dt)
    if len(ver_dt) < 6:
        func_end_log(func_name)
        return REG_520_UNDEFINED.to_json_response({'message': '검사하려는 버전 값이 양식에 맞지 않습니다.'})

    dt_version = datetime.datetime.strptime('20' + ver_dt[:2] + '-' + ver_dt[2:4] + '-' + ver_dt[4:6] + ' 00:00:00',
                                            '%Y-%m-%d %H:%M:%S')
    dt_check = datetime.datetime.strptime('2019-04-01 00:00:00', '%Y-%m-%d %H:%M:%S')
    print(dt_version)
    if dt_version < dt_check:
        print('dt_version < dt_check')
        func_end_log(func_name)
        return REG_551_AN_UPGRADE_IS_REQUIRED.to_json_response({'url': 'http://...'})

    func_end_log(func_name)
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
    http://0.0.0.0:8000/customer/staff_fg?login_id=think&login_pw=parkjong
    GET
        login_id=abc
        login_pw=password
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['login_id', 'login_pw'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    login_id = parameter_check['parameters']['login_id']
    login_pw = parameter_check['parameters']['login_pw']

    staffs = Staff.objects.filter(login_id=login_id)
    if len(staffs) == 0:
        result = {'message': '아이디가 없습니다.'}
        func_end_log(func_name, result['message'])
        return REG_530_ID_OR_PASSWORD_IS_INCORRECT.to_json_response(result)
    elif len(staffs) > 1:
        logError(func_name, ' ServerError: \'{}\' 중복된 id'.format(login_id))

    staffs = Staff.objects.filter(login_id=login_id, login_pw=hash_SHA256(login_pw))
    if len(staffs) != 1:
        result = {'message': '비밀번호가 틀렸습니다.'}
        func_end_log(func_name, result['message'])
        return REG_530_ID_OR_PASSWORD_IS_INCORRECT.to_json_response(result)

    app_user = staffs[0]
    app_user.is_app_login = True
    app_user.dt_app_login = datetime.datetime.now()
    app_user.save()
    # request.session['id'] = app_user.id
    # request.session.save()

    logSend(app_user.name, app_user.id, app_user.co_id)
    dt_today = datetime.datetime.now()
    # 업무 추출
    # 사업장 조회 - 사업장을 관리자로 검색해서 있으면 그 사업장의 모든 업무를 볼 수 있게 한다.
    work_places = Work_Place.objects.filter(contractor_id=app_user.co_id, manager_id=app_user.id)
    logSend([work_place.name for work_place in work_places])
    if len(work_places) > 0:
        arr_work_place_id = [work_place.id for work_place in work_places]
        logSend(arr_work_place_id)
        # 해당 사업장의 모든 업무 조회
        # works = Work.objects.filter(contractor_id=app_user.co_id, work_place_id__in=arr_work_place_id) # 협력업체가 수주하면 못찾음
        works = Work.objects.filter(work_place_id__in=arr_work_place_id, dt_end__gt=dt_today)
    else:
        # works = Work.objects.filter(contractor_id=app_user.co_id, staff_id=app_user.id) # 협력업체가 수주하면 못찾음
        works = Work.objects.filter(staff_id=app_user.id, dt_end__gt=dt_today)
    logSend([work.staff_name for work in works])
    # 관리자, 현장 소장의 소속 업무 조회 완료
    arr_work = []
    for work in works:
        linefeed = '\n' if len(work.work_place_name) + len(work.name) + len(work.type) > 9 else ' '
        work_dic = {'name':work.work_place_name + linefeed + work.name + '(' + work.type + ')',
                    'work_id':AES_ENCRYPT_BASE64(str(work.id)),
                    'staff_name':work.staff_name,
                    'staff_phone':phone_format(work.staff_pNo),
                    'dt_begin':work.dt_begin.strftime("%Y-%m-%d %H:%M:%S"),
                    'dt_end':work.dt_end.strftime("%Y-%m-%d %H:%M:%S"),
                    'is_start_work': True if work.dt_begin < datetime.datetime.now() else False,
                    }
        # 가상 데이터 생성
        # work_dic = virtual_work(isWorkStart, work_dic)
        arr_work.append(work_dic)
    result = {'staff_id': AES_ENCRYPT_BASE64(str(app_user.id)),
              'works': arr_work
              }

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)


def virtual_employee(isWorkStart, employee) -> dict:
    if isWorkStart:
        employee['is_accept_work'] = '수락'
        if random.randint(0,100) > 90:
            employee['dt_begin'] = (datetime.datetime.now() + datetime.timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
            return employee
        dt_today = datetime.datetime.now().strftime("%Y-%m-%d")
        overtime = random.randint(0, 4) * 30
        employee['overtime'] = str(overtime)
        dt_begin = datetime.datetime.strptime(dt_today + ' 08:35:00', "%Y-%m-%d %H:%M:%S")
        dt_end = datetime.datetime.strptime(dt_today + ' 17:25:00', "%Y-%m-%d %H:%M:%S") + datetime.timedelta(minutes=overtime)
        employee['dt_begin_beacon'] = (dt_begin - datetime.timedelta(minutes=random.randint(0,3)*5 + 15)).strftime("%Y-%m-%d %H:%M:%S")
        employee['dt_end_beacon'] = (dt_end + datetime.timedelta(minutes=random.randint(0,3)*5 + 15)).strftime("%Y-%m-%d %H:%M:%S")
        employee['dt_begin_touch'] = (dt_begin - datetime.timedelta(minutes=random.randint(0,3)*5)).strftime("%Y-%m-%d %H:%M:%S")
        employee['dt_end_touch'] = (dt_end + datetime.timedelta(minutes=random.randint(0,3)*5 + 15)).strftime("%Y-%m-%d %H:%M:%S")
        employee['x'] = 35.4812 + float(random.randint(0,100)) / 1000.
        employee['y'] = 129.4230 + float(random.randint(0,100)) / 1000.
    else:
        t = random.randint(0,10)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'work_id_!', 'year_month_day'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    staff_id = parameter_check['parameters']['staff_id']
    work_id = parameter_check['parameters']['work_id']
    year_month_day = parameter_check['parameters']['year_month_day']

    staffs = Work.objects.filter(id=staff_id)
    if len(staffs) == 0:
        logError(func_name, ' ServerError: Staff 에 staff_id={} 이(가) 없거나 중복됨'.format(staff_id))
        return status422(func_name, {'message': 'ServerError: 직원으로 등록되어 있지 않거나 중복되었다.'})

    works = Work.objects.filter(id=work_id)
    if len(works) == 0:
        logError(func_name, ' ServerError: Work 에 work_id={} 이(가) 없거나 중복됨'.format(work_id))
        return status422(func_name, {'message': 'ServerError: 업무가 등록되어 있지 않거나 중복되었다.'})
    work = works[0]

    is_work_begin = True if work.dt_begin < datetime.datetime.now() else False
    logSend(work.dt_begin, ' ', datetime.datetime.now(), ' ', is_work_begin)
    if not is_work_begin:
        func_end_log(func_name)
        return status422(func_name, {'message': '아직 업무가 시직되지 않음 >> staff_employee'})

    employee_list = Employee.objects.filter(work_id=work.id)
    for employee in employee_list:
        if employee.dt_begin < datetime.datetime.now():
            # 업무가 시작된 근로자 중에
            if employee.is_accept_work is None or not employee.is_accept_work:
                employee.delete()
    employee_ids = [AES_ENCRYPT_BASE64(str(employee.employee_id)) for employee in employee_list]
    employees_infor = {'employees': employee_ids,
                       'year_month_day': year_month_day,
                       'work_id': AES_ENCRYPT_BASE64(work_id),
                       # 'work_id': AES_ENCRYPT_BASE64('-1'),
                       }
    r = requests.post(settings.EMPLOYEE_URL + 'pass_record_of_employees_in_day_for_customer', json=employees_infor)
    if len(r.json()['fail_list']):
        logError(func_name, ' pass_record_of_employees_in_day_for_customer FAIL LIST {}'.format(r.json()['fail_list']))
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
        employee_dic = {
            'is_accept_work': '응답 X' if employee.is_accept_work is None else '수락' if employee.is_accept_work is True else '거절',
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
            logError(func_name, ' pass_record_dic[employee.employee_id] - employee_id: {} ({})'.format(employee.employee_id, e))
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
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
# @session_is_none_403
def staff_employees(request):
    """
    업무가 시작되기 전인 업무의 근로자 참여 여부 요청
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
                  "is_accept_work": "응답 X",
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('   ', key, ' - ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'work_id_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    staff_id = int(parameter_check['parameters']['staff_id'])
    work_id = int(parameter_check['parameters']['work_id'])

    staffs = Staff.objects.filter(id=staff_id)
    if len(staffs) == 0:
        logError(func_name, ' ServerError: Staff 에 staff_id=[{}] 이(가) 없다'.format(staff_id))
        return status422(func_name, {'message': 'ServerError: 등록되지 않은 관리자 입니다.'})

    works = Work.objects.filter(id=work_id)
    if len(works) == 0:
        logError(func_name, ' ServerError: Work 에 work_id={} 이(가) 없거나 중복됨'.format(work_id))
        return status422(func_name, {'message': 'ServerError: 등록되지 않은 업무 입니다.'})
    work = works[0]

    is_work_begin = True if work.dt_begin < datetime.datetime.now() else False
    if is_work_begin:
        func_end_log(func_name)
        return status422(func_name, {'message': '이미 업무가 시직되었습니다. >> staff_employees_at_day'})

    employees = Employee.objects.filter(work_id=work.id)
    arr_employee = []
    for employee in employees:
        employee_dic = {
            'is_accept_work': '응답 X' if employee.is_accept_work is None else '수락' if employee.is_accept_work is True else '거절',
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
        # 가상 데이터 생성
        # employee_dic = virtual_employee(isWorkStart, employee_dic)
        # employee_dic = employee_day_working_from_employee(employee_dic, year_month_day)
        # employee['is_accept_work'] = '응답 X' if employee.is_accept_work == None else '수락' if employee.is_accept_work == True else '거절'
        arr_employee.append(employee_dic)
    result = {'employees': arr_employee}
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)


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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])

    if (request.session is None) or (not 'id' in request.session):
        func_end_log(func_name)
        return REG_403_FORBIDDEN.to_json_response()

    staff_id = request.session['id']
    app_users = Staff.objects.filter(id=staff_id)
    if len(app_users) != 1:
        logError('ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id))
    app_user = app_users[0]
    app_user.is_app_login = False
    app_user.dt_app_login = datetime.datetime.now()
    app_user.save()

    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['staff_id_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    staff_id = parameter_check['parameters']['staff_id']

    app_users = Staff.objects.filter(id=staff_id)
    if len(app_users) != 1:
        return status422(func_name, {'message':'ServerError: Staff 에 staff_id={} 이(가) 없거나 중복됨'.format(staff_id)})

    app_user = app_users[0]
    app_user.is_app_login = False
    app_user.dt_app_login = datetime.datetime.now()
    app_user.save()

    func_end_log(func_name)
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
                  "is_accept_work": true,
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'work_id_!', 'day'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

    staff_id = parameter_check['parameters']['staff_id']
    work_id = parameter_check['parameters']['work_id']
    day = parameter_check['parameters']['day']

    app_users = Staff.objects.filter(id=staff_id)
    if len(app_users) != 1:
        return status422(func_name, {'message': 'ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)})
    works = Work.objects.filter(id=work_id)
    if len(works) != 1:
        return status422(func_name, {'message': 'ServerError: Work 에 id={} 이(가) 없거나 중복됨'.format(work_id)})
    app_user = app_users[0]
    work = works[0]
    if work.staff_id != app_user.id:
        # 업무 담당자와 요청자가 틀린 경우 - 사업장 담당자 일 수 도 있기 때문에 error 가 아니다.
        logSend('   ! 업무 담당자와 요청자가 틀림 - 사업장 담당자 일 수 도 있기 때문에 error 가 아니다.')
    target_day = datetime.datetime.strptime(day + ' 00:00:00', "%Y-%m-%d %H:%M:%S")
    logSend(target_day, ' ', work.dt_begin)
    if target_day < work.dt_begin:
        # 근로 내역을 원하는 날짜가 업무 시작일 보다 적은 경우 - 아직 업무가 시작되지도 않은 근로 내역을 요청한 경우
        func_end_log(func_name, '416 업무 날짜 밖의 근로 내역 요청')
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무 날짜 밖의 근로 내역 요청'})

    employees = Employee.objects.filter(work_id=work.id)
    arr_employee = []
    for employee in employees:
        employee_dic = {'is_accept_work': '응답 X' if employee.is_accept_work is None else '수락' if employee.is_accept_work is True else '거절',
                        'employee_id': AES_ENCRYPT_BASE64(str(employee.employee_id)),
                        'name': employee.name,
                        'phone': phone_format(employee.pNo),
                        'dt_begin': dt_null(employee.dt_begin),
                        'dt_end': dt_null(employee.dt_end),
                        'dt_begin_beacon': dt_null(employee.dt_begin_beacon),
                        'dt_end_beacon': dt_null(employee.dt_end_beacon),
                        'dt_begin_touch': dt_null(employee.dt_begin_touch),
                        'dt_end_touch': dt_null(employee.dt_end_touch),
                        'overtime': employee.overtime,
                        'x': employee.x,
                        'y': employee.y,
                        }

        # 가상 데이터 생성
        employee_dic = virtual_employee(True, employee_dic)  # isWorkStart = True
        arr_employee.append(employee_dic)
    result = {'emplyees': arr_employee,
              'dt_work': target_day.strftime("%Y-%m-%d")
              }

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def staff_change_time(request):
    """
    [관리자용 앱]: 업무에 투입 중인 근로자 중에서 일부를 선택해서 근무시간(30분 연장, ...)을 변경할 때 호출
    - 담당자(현장 소장, 관리자), 업무, 변경 형태
    - 근로자 명단에서 체크하고 체크한 근로자 만 근무 변경
    - 오늘이 아니면 고칠 수 없음 - 오늘이 아니면 호출하지 말것.
    https://api-dev.aegisfac.com/apiView/customer/staff_change_time?id=qgf6YHf1z2Fx80DR8o_Lvg&work_id=_LdMng5jDTwK-LMNlj22Vw&overtime_type=-1
    http://0.0.0.0:8000/apiView/customer/staff_change_time?id=qgf6YHf1z2Fx80DR8o_Lvg&work_id=ryWQkNtiHgkUaY_SZ1o2uA&overtime_type=-1&employee_ids=qgf6YHf1z2Fx80DR8o_Lvg
    POST
        staff_id : 현장관리자 id  # foreground 에서 받은 암호화된 식별 id
        work_id : 업무 id
        year_month_day: 2019-05-09 # 처리할 날짜
        overtime_type : 0        # -1: 업무 완료 조기 퇴근, 0: 표준 근무, 1: 30분 연장 근무, 2: 1시간 연장 근무, 3: 1:30 연장 근무, 4: 2시간 연장 근무, 5: 2:30 연장 근무, 6: 3시간 연장 근무
        employee_ids : [ 근로자_id_1, 근로자_id_2, 근로자_id_3, 근로자_id_4, 근로자_id_5, ...]
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "employees": [
                {
                  "is_accept_work": true,
                  "employee_id": "i52bN-IdKYwB4fcddHRn-g",
                  "name": "근로자",
                  "phone": "010-3333-4444",
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'work_id_!', 'year_month_day', 'overtime_type', 'employee_ids'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    staff_id = parameter_check['parameters']['staff_id']
    work_id = parameter_check['parameters']['work_id']
    year_month_day = parameter_check['parameters']['year_month_day']
    overtime_type = int(parameter_check['parameters']['overtime_type'])
    employee_ids = parameter_check['parameters']['employee_ids']

    if overtime_type < -1 or 6 < overtime_type:
        # 초과 근무 형태가 범위를 벗어난 경우
        return status422(func_name, {'message':'ClientError: parameter \'overtime_type\' 값이 범위(-1 ~ 6)를 넘었습니다.'})

    app_users = Staff.objects.filter(id=staff_id)
    if len(app_users) != 1:
        return status422(func_name, {'message':'ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)})
    app_user = app_users[0]
    works = Work.objects.filter(id=work_id)
    if len(works) != 1:
        return status422(func_name, {'message':'ServerError: Work 에 id={} 이(가) 없거나 중복됨'.format(work_id) })
    work = works[0]
    if work.staff_id != app_user.id:
        # 업무 담당자와 요청자가 틀린 경우 - 사업장 담당자 일 수 도 있기 때문에 error 가 아니다.
        logSend('   ! 업무 담당자와 요청자가 틀림 - 사업장 담당자 일 수 도 있기 때문에 error 가 아니다.')

    if request.method == 'GET':
        employee_ids = rqst.getlist('employee_ids')

    # logSend(employee_ids)
    if len(employee_ids) == 0:
        # 연장근무 저장할 근로자 목록이 없다.
        logError(func_name, ' 근로자 연장 근무요청을 했는데 선택된 근로자({})가 없다?'.format(employee_ids))
        func_end_log(func_name)
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
        logError(func_name, ' 근로자 연장 근무요청을 했는데 선택된 근로자({})가 없다? (암호화된 근로자 리스트에도 없다.)'.format(employee_id_list))
        func_end_log(func_name)
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
        logError(func_name, ' pass_record_of_employees_in_day_for_customer FAIL LIST {}'.format(r.json()['fail_list']))
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
        employee_dic = {'is_accept_work': '응답 X' if employee.is_accept_work is None else '수락' if employee.is_accept_work is True else '거절',
                        'employee_id': AES_ENCRYPT_BASE64(str(employee.employee_id)),
                        'name': employee.name,
                        'phone': phone_format(employee.pNo),
                        'dt_begin': dt_null(employee.dt_begin),
                        'dt_end': dt_null(employee.dt_end),
                        'dt_begin_beacon': dt_null(employee.dt_begin_beacon),
                        'dt_end_beacon': dt_null(employee.dt_end_beacon),
                        'dt_begin_touch': dt_null(employee.dt_begin_touch),
                        'dt_end_touch': dt_null(employee.dt_end_touch),
                        'overtime': employee.overtime,
                        'x': employee.x,
                        'y': employee.y,
                        }
        arr_employee.append(employee_dic)
    result = {'employees': arr_employee,
              'fail_list': fail_list
              }

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)


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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'work_id_!', 'employee_id_!', 'year_month'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    staff_id = parameter_check['parameters']['staff_id']
    work_id = parameter_check['parameters']['work_id']
    employee_id = parameter_check['parameters']['employee_id']
    year_month = parameter_check['parameters']['year_month']

    app_users = Staff.objects.filter(id=staff_id)
    if len(app_users) != 1:
        return status422(func_name, {'message': 'ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)})
    employees = Employee.objects.filter(id=employee_id, work_id=work_id)
    if len(employees) != 1:
        return status422(func_name, {'message': 'ServerError: Employee 에 '
                                                'employee_id: {}, '
                                                'work_id: {} 이(가) 없거나 중복됨'.format(employee_id, work_id)})
    employee = employees[0]

    #
    # 근로자 서버로 근로자의 월 근로 내역을 요청
    #
    employee_info = {
            'employee_id': AES_ENCRYPT_BASE64(str(employee.employee_id)),
            'work_id': AES_ENCRYPT_BASE64(str(employee.work_id)),
            'dt': year_month,
        }
    logSend(employee_info)
    response_employee = requests.post(settings.EMPLOYEE_URL + 'my_work_histories_for_customer', json=employee_info)
    logSend(response_employee)
    result = response_employee.json()

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def staff_update_employee(request):
    """
    [관리자용 앱]:  업무에 투입된 근로자의 근무 기간, 연장 근무 변경 요청
    - 담당자(현장 소장, 관리자), 근로자, 근무 기간, 당일의 연장 근무
    - 근로자의 근무 기간은 업무의 기간을 벗아나지 못한다.
    - 값을 넣은 것만 변경한다.
    http://0.0.0.0:8000/customer/staff_update_employee?staff_id=qgf6YHf1z2Fx80DR8o_Lvg&employee_id=iZ_rkELjhh18ZZauMq2vQw&dt_begin=2019-03-01&dt_end=2019-04-30&overtime_type=0
    POST
        staff_id : 현장관리자 id  # foreground 에서 받은 암호화된 식별 id
        work_id : 업무 id
        employee_id : 근로자 id
        dt_begin : 2019-04-01   # 근로 시작 날짜
        dt_end : 2019-04-13     # 근로 종료 날짜
        overtime_type : 0       # -1: 업무 완료 조기 퇴근, 0: 표준 근무, 1: 30분 연장 근무, 2: 1시간 연장 근무, 3: 1:30 연장 근무, 4: 2시간 연장 근무, 5: 2:30 연장 근무, 6: 3시간 연장 근무
    response
        STATUS 200
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'work_id_!', 'employee_id_!', 'dt_begin', 'dt_end', 'overtime_type'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    staff_id = parameter_check['parameters']['staff_id']
    work_id = parameter_check['parameters']['work_id']
    employee_id = parameter_check['parameters']['employee_id']
    str_dt_begin = parameter_check['parameters']['dt_begin']
    str_dt_end = parameter_check['parameters']['dt_end']
    overtime_type = parameter_check['parameters']['overtime_type']

    app_users = Staff.objects.filter(id=staff_id)
    if len(app_users) != 1:
        return status422(func_name, {'message': 'ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)})
    employees = Employee.objects.filter(id=employee_id, work_id=work_id)
    if len(employees) != 1:
        return status422(func_name, {'message': 'ServerError: Employee 에 id={} 이(가) 없거나 중복됨'.format(employee_id)})
    employee = employees[0]
    # works = Work.objects.filter(id=employee.work_id)
    works = Work.objects.filter(id=work_id)
    if len(works) != 1:
        return status422(func_name, {'message': 'ServerError: Work 에 id={} 이(가) 없거나 중복됨'.format(work_id)})
    work = works[0]

    is_update_dt_begin = False
    result = {}
    if not '' == str_dt_begin:
        dt_begin = str_to_datetime(str_dt_begin)
        if dt_begin < work.dt_begin:
            func_end_log(func_name)
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무 시작날짜 이전으로 설정할 수 없습니다.'})
        employee.dt_begin = dt_begin
        is_update_dt_begin = True

    is_update_dt_end = False
    if not '' == str_dt_end:
        dt_end = str_to_datetime(str_dt_end)
        if work.dt_end < dt_end:
            func_end_log(func_name)
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무 종료날짜 이후로 설정할 수 없습니다.'})
        employee.dt_end = dt_end
        is_update_dt_end = True
    #
    # 근로기간이 변경되었으면 근로자서버를 업데이트한다.
    #
    if is_update_dt_begin or is_update_dt_end:
        employees_infor = {
            'employee_id': AES_ENCRYPT_BASE64(str(employee.employee_id)),
            'work_id': AES_ENCRYPT_BASE64(str(work.id)),
        }
        if is_update_dt_begin:
            employees_infor['dt_begin'] = dt_begin.strftime("%Y/%m/%d")
        if is_update_dt_end:
            employees_infor['dt_end'] = dt_end.strftime("%Y/%m/%d")
        logSend(employees_infor)
        r = requests.post(settings.EMPLOYEE_URL + 'change_work_period_for_customer', json=employees_infor)
        result['work_dt_end'] = {'url': r.url, 'POST': employees_infor, 'STATUS': r.status_code, 'R': r.json()}

    if not '' == overtime_type:
        if overtime_type < -1 or 6 < overtime_type:
            func_end_log(func_name)
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '설정범위를 벗어났습니다.'})
        employee.overtime = overtime_type

    employee.save()
    #
    # employee server 에서 적용시켜야 한다.
    #
    result['update_dt_begin'] = employee.dt_begin.strftime("%Y-%m-%d %H:%M:%S")
    result['update_dt_end'] = employee.dt_end.strftime("%Y-%m-%d %H:%M:%S")
    result['update_overtime'] = employee.overtime

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def staff_recognize_employee(request):
    """
    [관리자용 앱]:  근로자의 출퇴근 시간이 잘못되었을 때 현장 소장이 출퇴근 시간을 인정하고 변경하는 기능
    - 담당자(현장 소장, 관리자), 근로자, 출근시간, 퇴근 시간
    - 출근시간과 퇴근시간은 "yyyy-mm-dd hh:mm:ss" 양식으로 보낸다.
    - 값을 넣은 것만 변경한다.
    http://0.0.0.0:8000/customer/staff_recognize_employee?staff_id=qgf6YHf1z2Fx80DR8o_Lvg&employee_id=iZ_rkELjhh18ZZauMq2vQw&dt_arrive=2019-03-01 08:30:00&dt_end=2019-03-01 17:30:00
    POST
        staff_id : 현장관리자 id  # foreground 에서 받은 암호화된 식별 id
        work_id : 업무 id
        employee_id : 근로자 id
        dt_arrive : 2019-04-01 08:30:00   # 도착 시간 - 출근 시간
        dt_leave : 2019-04-01 17:30:00    # 떠난 시간 - 퇴근 시간
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['staff_id_!', 'work_id_!', 'employee_id_!', 'dt_arrive', 'dt_leave'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    staff_id = parameter_check['parameters']['staff_id']
    work_id = parameter_check['parameters']['work_id']
    employee_id = parameter_check['parameters']['employee_id']
    str_dt_arrive = parameter_check['parameters']['dt_arrive']
    str_dt_leave = parameter_check['parameters']['dt_leave']

    app_users = Staff.objects.filter(id=staff_id)
    if len(app_users) == 0:
        return status422(func_name, {'message': ' ServerError: Staff 에 id={} 이(가) 없거나 중복됨'.format(staff_id)})
    employees = Employee.objects.filter(id=employee_id, work_id=work_id)
    logSend('--- employee id {} '.format(employee_id))
    if len(employees) == 0:
        return status422(func_name, {'message': 'ServerError: Employee 에 id={} 이(가) 없거나 중복됨'.format(employee_id)})
    employee = employees[0]
    if employee.employee_id == -1:
        func_end_log(func_name)
        return REG_541_NOT_REGISTERED.to_json_response({'message': '업무 수락이 안되어 있는 근로자 입니다.'})
    logSend('--- employee id {} name {} employee_id {}'.format(employee.id, employee.name, employee.employee_id))
    works = Work.objects.filter(id=work_id)
    if len(works) == 0:
        return status422(func_name, {'message': 'ServerError: Work 에 id={} 해당 업무가 없습니다.'.format(works)})
    work = works[0]

    #
    # employee server 에서 적용시켜야 한다.
    #
    employees_infor = {'employees': [AES_ENCRYPT_BASE64(str(employee.employee_id))],
                       # 'year_month_day': dt_arrive.strftime('%Y-%m-%d'),
                       'work_id': AES_ENCRYPT_BASE64(str(work.id)),
                       }
    if not '' == str_dt_arrive:
        if len(str_dt_arrive.split(' ')) == 0:
            return status422(func_name, {'message': 'ClientError: parameter \'dt_arrive\' 양식을 확인해주세요.'})
        dt_arrive = datetime.datetime.strptime(str_dt_arrive, "%Y-%m-%d %H:%M:%S")
        employee.dt_begin_touch = dt_arrive
        employees_infor['year_month_day'] = dt_arrive.strftime('%Y-%m-%d')
        employees_infor['dt_in_verify'] = dt_arrive.strftime('%H:%M')
        employees_infor['in_staff_id'] = AES_ENCRYPT_BASE64(staff_id)

    if not '' == str_dt_leave:
        if len(str_dt_leave.split(' ')) == 0:
            return status422(func_name, {'message': 'ClientError: parameter \'dt_leave\' 양식을 확인해주세요.'})
        dt_leave = datetime.datetime.strptime(str_dt_leave, "%Y-%m-%d %H:%M:%S")
        employee.dt_end_touch = dt_leave
        employees_infor['year_month_day'] = dt_leave.strftime('%Y-%m-%d')
        employees_infor['dt_out_verify'] = dt_leave.strftime('%H:%M')
        employees_infor['out_staff_id'] = AES_ENCRYPT_BASE64(staff_id)

    employee.save()
    #
    # employee server 에서 적용시켜야 한다.
    #
    r = requests.post(settings.EMPLOYEE_URL + 'pass_record_of_employees_in_day_for_customer', json=employees_infor)
    if len(r.json()['fail_list']):
        logError(func_name, ' pass_record_of_employees_in_day_for_customer FAIL LIST {}'.format(r.json()['fail_list']))
    pass_records = r.json()['employees']
    fail_list = r.json()['fail_list']

    result = {'update_dt_arrive': dt_null(employee.dt_begin_touch),
              'update_dt_leave': dt_null(employee.dt_end_touch)
              }

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def staff_update_me(request):
    """
    [관리자용 앱]:  자기정보 update (사용 보류)
    	주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
    		response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/staff_update_me?id=&login_id=temp_1&before_pw=A~~~8282&login_pw=&name=박종기&position=이사&department=개발&phone_no=010-2557-3555&phone_type=10&push_token=unknown&email=thinking@ddtechi.com
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
        func_end_log(func_name)
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
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    phone_no = rqst['phone_no']
    if len(phone_no) == 0:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '전화번호가 없습니다.'})

    phone_no = phone_no.replace('+82', '0')
    phone_no = phone_no.replace('-', '')
    phone_no = phone_no.replace(' ', '')
    # print(phone_no)
    staffs = Staff.objects.filter(pNo=phone_no)
    if len(staffs) == 0:
        func_end_log(func_name)
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
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
        func_end_log(func_name)
        return REG_550_CERTIFICATION_NO_IS_INCORRECT.to_json_response()

    staff.pType = 20 if phone_type == 'A' else 10
    staff.push_token = push_token
    staff.save()

    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    cipher_id = rqst['id']
    app_user = Staff.objects.get(id = AES_DECRYPT_BASE64(cipher_id))

    result = {}
    work_places = Work_Place.objects.filter(contractor_ir=app_user.co_id, manager_id=app_user.id).values('id', 'name')
    if len(work_places) > 0:
        arr_work_place = [work_place for work_place in work_places]
        result['work_places'] = arr_work_place
    works = Work.objects.filter(contractor_ir=app_user.co_id, staff_id=app_user.id).values('id', 'name')
    if len(works) > 0:
        arr_work = [work for work in works]
        result['works'] = arr_work
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    cipher_id = rqst['id']
    app_user = Staff.objects.get(id = AES_DECRYPT_BASE64(cipher_id))

    result = {}
    work_id=rqst['work_id']
    employees = Employee.objects.filter(work_id=work_id).values('is_active', 'dt_begin', 'dt_end', 'employee_id', 'name', 'pNo')
    if len(employees) > 0:
        arr_employee = [employee for employee in employees]
        result['employees'] = arr_employee
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def staff_work_update_employee(request):
    """
    [관리자용 앱]:  업무에 근무 중인 근로자 내용 수정, 추가(지각, 외출, 조퇴, 특이사항)
    	주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
    		response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/staff_update_me?id=&login_id=temp_1&before_pw=A~~~8282&login_pw=&name=박종기&position=이사&department=개발&phone_no=010-2557-3555&phone_type=10&push_token=unknown&email=thinking@ddtechi.com
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
        func_end_log(func_name)
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

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()


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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    # ---------------------------------------------------------------------------------------
    # Update: Customer Model + is_constractor
    # ---------------------------------------------------------------------------------------
    dt_execute = datetime.datetime.strptime('2019-05-19 09:00:00', '%Y-%m-%d %H:%M:%S')
    dt_today = datetime.datetime.now()
    if dt_execute < dt_today:
        return status422(func_name, {'message': '이 기능을 사용할 수 있는 기간(~{})이 지났다.'.format(dt_execute.strftime('%Y-%m-%d %H:%M:%S'))})

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

    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        return REG_403_FORBIDDEN.to_json_response({'result': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result': result})


@cross_origin_read_allow
def tk_list_employees(request):
    """
    [[ 서버 시험]] 근로자를 모두 읽어들여서 전화번호가 중복되는 근로자를 찾고 employee_id 가 다른 경우를 찾는다.
    http://0.0.0.0:8000/customer/tk_list_employees
    GET
        work_id: 5
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        return REG_403_FORBIDDEN.to_json_response({'result': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    result = []
    # parameter_check = is_parameter_ok(rqst, ['work_id_!'])
    parameter_check = is_parameter_ok(rqst, ['work_id'])
    if not parameter_check['is_ok']:
        return status422(func_name, {'message': '{}'.format(''.join([message for message in parameter_check['results']]))})
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    work_id = parameter_check['parameters']['work_id']

    employee_list = Employee.objects.filter(work_id=work_id).values('id', 'is_accept_work', 'is_active', 'dt_begin', 'dt_end', 'work_id', 'employee_id', 'name', 'pNo', 'dt_begin_beacon', 'dt_end_beacon', 'dt_begin_touch', 'dt_end_touch', 'overtime', 'x', 'y')
    json_employee_list = [employee for employee in employee_list]
    logSend('  employee_list: {}'.format(json_employee_list))
    result.append({'employee_list': json_employee_list})
    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result': result})
