import random
import requests
import datetime
from datetime import timedelta
import inspect

from django.views.decorators.csrf import csrf_exempt  # POST 에서 사용

from django.conf import settings

from config.common import logSend
from config.common import DateTimeEncoder, exceptionError
# from config.common import HttpResponse
from config.common import func_begin_log, func_end_log
# secret import
from config.common import hash_SHA256
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
def reg_customer_for_operation(request):
    """
    <<<운영 서버용>>> 고객사를 등록한다.
    - 고객사 담당자와 관리자는 처음에는 같은 사람이다.
    - 간단한 내용만 넣어서 등록하고 나머지는 고객사 담당자가 추가하도록 한다.
    * 서버 to 서버 통신 work_id 필요
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    # 운영 서버에서 호출했을 때 - 운영 스텝의 id를 로그에 저장한다.
    worker_id = AES_DECRYPT_BASE64(rqst['worker_id'])
    logSend('   from operation server : op staff id ', worker_id)
    print('   from operation server : op staff id ', worker_id)

    customer_name = rqst["customer_name"]
    staff_name = rqst["staff_name"]
    staff_pNo = rqst["staff_pNo"]
    staff_email = rqst["staff_email"]

    customers = Customer.objects.filter(name=customer_name, staff_pNo=staff_pNo)
    # 파견기업 등록
    if len(customers) > 0:
        # 파견기업 상호와 담당자 전화번호가 등록되어 있는 경우
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_543_EXIST_TO_SAME_NAME_AND_PHONE_NO.to_json_response()
    else:
        customer = Customer(
            name=customer_name,
            staff_name=staff_name,
            staff_pNo=staff_pNo,
            staff_email=staff_email,
            manager_name=staff_name,
            manager_pNo=staff_pNo,
            manager_email=staff_email
        )
        customer.save()
        staff = Staff(
            name=staff_name,
            login_id='temp_' + str(customer.id),
            login_pw=hash_SHA256('happy_day!!!'),
            co_id=customer.id,
            co_name=customer.name,
            pNo=staff_pNo,
            email=staff_email,
            is_site_owner=True,
            is_manager=True
        )
        staff.save()
        customer.staff_id = str(staff.id)
        customer.manager_id = str(staff.id)
        customer.save()
    print('staff id = ', staff.id)
    print(customer_name, staff_name, staff_pNo, staff_email, staff.login_id, staff.login_pw)
    result = {'message': '정상처리되었습니다.',
              'login_id': staff.login_id
              }
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def sms_customer_staff_for_operation(request):
    """
    <<<운영 서버용>>> 고객사 담당자의 id / pw 를 sms 로 보내기 위해 pw 를 초기화 한다.
    * 서버 to 서버 통신 work_id 필요
        주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/sms_customer_for_operation?staff_id=&worker_id=
    POST
        {
            'staff_id': 'cipher_id'  # 암호화된 직원 id
            'worker_id': 'cipher_id'  # 운영직원 id
        }
    response
        STATUS 200
            {
                'msg': '정상처리되었습니다.',
                'login_id': staff.login_id,
            }
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    # 운영 서버에서 호출했을 때 - 운영 스텝의 id를 로그에 저장한다.
    worker_id = AES_DECRYPT_BASE64(rqst['worker_id'])
    logSend('   from operation server : op staff id ', worker_id)
    print('   from operation server : op staff id ', worker_id)

    staffs = Staff.objects.filter(id=AES_DECRYPT_BASE64(rqst['staff_id']))
    if len(staffs) == 0:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_541_NOT_REGISTERED.to_json_response()
    staff = staffs[0]
    staff.login_pw = hash_SHA256('happy_day!!!')
    staff.save()
    result = {'message': '정상처리되었습니다.',
              'login_id': staff.login_id
              }
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def list_customer_for_operation(request):
    """
    <<<운영 서버용>>> 고객사 리스트를 요청한다.
    * 서버 to 서버 통신 work_id 필요
    http://0.0.0.0:8000/customer/list_customer?customer_name=대덕테크&staff_name=박종기&staff_pNo=010-2557-3555&staff_email=thinking@ddtechi.com&worker_id=
    GET
        customer_name=대덕기공
        staff_name=홍길동
        staff_pNo=010-1111-2222
        staff_email=id@daeducki.com
        worker_id='AES_256_id' # 운영서버에서 요청할 때만 사용한다.
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "customers": [
                {
                  "id": 1,								 # 고객사 id (보여주지 않는다.)
                  "name": "대덕테크",						 # 고객사 상호
                  "contract_no": "",					 # 계약서 번호 (대덕테크와 고객간 계약서)
                  "dt_reg": "2019-01-17 08:09:08",		 # 등록날짜
                  "dt_accept": null,					 # 등록 승인일
                  "type": 10,   						 # 10 : 발주업체, 11 : 파견업체(도급업체), 12 : 협력업체
                  "contractor_name": "",				 # 파견업체 상호 (협력사일 경우 만 있음)
                  "staff_id":"cipher_id",                # 암호화된 담당자 id (표시하지 않음.) - 담당자 pw 를 reset 할 때 사용
                  "staff_name": "박종기",					 # 담당자
                  "staff_pNo": "01025573555",			 # 담당자 전화번호
                  "staff_email": "thinking@ddtechi.com", # 담당자 이메일
                  "manager_name": "",					 # 관리자
                  "manager_pNo": "",					 # 관리자 전화번호
                  "manager_email": "",					 # 관리자 이메일
                  "dt_payment": null					 # 고객사 결제일
                }
              ]
            }
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    # 운영 서버에서 호출했을 때 - 운영 스텝의 id를 로그에 저장한다.
    worker_id = AES_DECRYPT_BASE64(rqst['worker_id'])
    logSend('   from operation server : op staff id ', worker_id)
    print('   from operation server : op staff id ', worker_id)

    customer_name = rqst['customer_name']
    staff_name = rqst['staff_name']
    staff_pNo = rqst['staff_pNo']
    staff_email = rqst['staff_email']

    customers = Customer.objects.filter().values('id', 'name', 'contract_no', 'dt_reg', 'dt_accept', 'type',
                                                 'contractor_name', 'staff_id', 'staff_name', 'staff_pNo', 'staff_email',
                                                 'manager_name', 'manager_pNo', 'manager_email', 'dt_payment')
    arr_customer = []
    for customer in customers:
        customer['dt_reg'] = customer['dt_reg'].strftime("%Y-%m-%d %H:%M:%S")
        customer['dt_accept'] = None if customer['dt_accept'] is None else customer['dt_accept'].strftime("%Y-%m-%d %H:%M:%S")
        customer['dt_payment'] = None if customer['dt_payment'] is None else customer['dt_payment'].strftime("%Y-%m-%d %H:%M:%S")
        customer['staff_id'] = AES_ENCRYPT_BASE64(str(customer['id']))
        arr_customer.append(customer)
    result = {'customers': arr_customer}
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def update_customer(request):
    """
    고객사(협력사, 발주사) 정보 변경 (담당자, 관리자만 가능)
    - 담당자나 관리자가 바뀌면 바로 로그아웃된다.
    - 담당자나 관리자가 바뀔 때는 다른 값은 바꿀 수 없다.
    	주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
    http://0.0.0.0:8000/customer/update_customer?
    POST
    	{
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
    	STATUS 522
    		{'message': '담당자나 관리자만 변경 가능합니다.'}
    		{'message': '관리자만 변경 가능합니다.'}
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    customer = Customer.objects.get(id=worker.contractor_id)
    print(customer.name)
    print(str(customer.staff_id))
    print(str(customer.manager_id))
    if not(worker.is_site_owner or worker.is_manager):
        print('담당자나 관리자만 변경 가능합니다.')
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_522_MODIFY_SITE_OWNER_OR_MANAGER_ONLY.to_json_response()
    if customer.staff_id != worker.id and customer.manager_id != worker.id:
        print('담당자나 관리자만 변경 가능합니다.')
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_522_MODIFY_SITE_OWNER_OR_MANAGER_ONLY.to_json_response()
    staff_id = rqst['staff_id']
    if len(staff_id) > 0:
        staff_id = AES_DECRYPT_BASE64(staff_id)
        staff = Staff.objects.get(id=staff_id)
        customer.staff_id = staff.id
        customer.staff_name = staff.name
        customer.staff_pNo = staff.pNo
        customer.staff_email = staff.email
        customer.save()
        staff.is_site_owner = True
        staff.save()
        worker.is_site_owner = False
        worker.save()
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_200_SUCCESS.to_json_response({'message': '담당자가 바뀌었습니다.\n로그아웃하십시요.'})
    manager_id = rqst['manager_id']
    if len(manager_id) > 0:
        if worker.is_manager :
            manager_id = AES_DECRYPT_BASE64(manager_id)
            manager = Staff.objects.get(id=manager_id)
            customer.manager_id = manager.id
            customer.manager_name = manager.name
            customer.manager_pNo = manager.pNo
            customer.manager_email = manager.email
            customer.save()
            manager.is_manager = True
            manager.save()
            worker.is_manager = False
            worker.save()
            func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
            return REG_200_SUCCESS.to_json_response({'message': '관리자가 바뀌었습니다.\n로그아웃하십시요.'})
        else:
            func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
            return REG_521_MODIFY_MANAGER_ONLY.to_json_response()
    br_id = rqst['business_reg_id']
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

    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
        STATUS 544
            {'message', '이미 등록되어 있습니다.'}
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    type = rqst['type']
    corp_name = rqst['corp_name']

    relationships = Relationship.objects.filter(contractor_id=worker.co_id, type=type, corp_name=corp_name)
    if len(relationships) > 0:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_544_EXISTED.to_json_response()
    staff_name = rqst['staff_name']
    staff_pNo = rqst['staff_pNo']
    staff_email = rqst['staff_email']
    corp = Customer(
        name=corp_name,
        staff_name=staff_name,
        staff_pNo=staff_pNo,
        staff_email=staff_email,
    )
    if 'manager_name' in rqst:
        corp.manager_name = rqst['manager_name']
    if 'manager_pNo' in rqst:
        corp.manager_pNo = rqst['manager_pNo']
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
    if 'name' in rqst:
        business_registration = Business_Registration(
            name=rqst['name'],
            regNo=rqst['regNo'],
            ceoName=rqst['ceoName'],
            address=rqst['address'],
            business_type=rqst['business_type'],
            business_item=rqst['business_item'],
            dt_reg=rqst['dt_reg'],
            customer_id=corp.id
        )
        business_registration.save()
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
                  "name": "(주)티에스엔지",	 # 협력사 상호
                  "id": "cipher_id",	 # 협력사 id (협력사 정보 수정시 사용)
                },
                ...
              ]
              "orderers": [
                {
                  "name": "(주)효성 용연공장",	# 발주사 상호
                  "id": "cipher_id",		# 발주사 id (발주사 정보 수정시 사용)
                },
                ...
              ]
            }
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    types = []
    if rqst['is_partner']:
        types.append(12)
    if rqst['is_orderer']:
        types.append(10)
    relationships = Relationship.objects.filter(contractor_id = worker.co_id, type__in = types)
    partners = []
    orderers = []
    for relationship in relationships:
        corp = {'name':relationship.corp_name,
                'id':AES_ENCRYPT_BASE64(str(relationship.corp_id))
                }
        if relationship.type == 12:
            partners.append(corp)
        elif relationship.type == 10:
            orderers.append(corp)
    result = {'partners':partners, 'orderers':orderers}
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def detail_relationship(request):
    """
    발주사, 협력사 상세 정보를 요청한다.
    http://0.0.0.0:8000/customer/detail_relationship?corp_id=ryWQkNtiHgkUaY_SZ1o2uA
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    corp_id = rqst['corp_id']
    corps = Customer.objects.filter(id=AES_DECRYPT_BASE64(corp_id))
    if len(corps) == 0:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_541_NOT_REGISTERED.to_json_response({'message':'등록된 업체가 없습니다.'})
    corp = corps[0]

    detail_relationship = {'type':corp.type,
                           'type_name': '발주사' if corp.type == 10 else '협력사',
                           'corp_id':corp_id,
                           'corp_name':corp.name,
                           'staff_name': corp.staff_name,
                           'staff_pNo': corp.staff_pNo,
                           'staff_email': corp.staff_email,
                           'manager_name': corp.manager_name,
                           'manager_pNo': corp.manager_pNo,
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
        detail_relationship['dt_reg'] = business_registration.dt_reg  # 사업자등록일
    else:
        detail_relationship['name'] = None  # 상호
        detail_relationship['regNo'] = None  # 사업자등록번호
        detail_relationship['ceoName'] = None  # # 성명(대표자)
        detail_relationship['address'] = None  # 사업장소재지
        detail_relationship['business_type'] = None  # 업태
        detail_relationship['business_item'] = None  # 종목
        detail_relationship['dt_reg'] = None  # 사업자등록일

    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
        STATUS 541
            {'message', '등록된 업체가 없습니다.'}
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    corp_id = rqst['corp_id']
    corps = Customer.objects.filter(id=AES_DECRYPT_BASE64(corp_id))
    if len(corps) == 0:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_541_NOT_REGISTERED.to_json_response({'message':'등록된 업체가 없습니다.'})
    corp = corps[0]
    update = False
    if 'corp_name' in rqst:
        corp.name = rqst['corp_name']
        update = True
    if 'staff_name' in rqst:
        corp.staff_name = rqst['staff_name']
        update = True
    if 'staff_pNo' in rqst:
        corp.staff_pNo = rqst['staff_pNo']
        update = True
    if 'staff_email' in rqst:
        corp.staff_email = rqst['staff_email']
        update = True
    if 'manager_name' in rqst:
        corp.manager_name = rqst['manager_name']
        update = True
    if 'manager_pNo' in rqst:
        corp.manager_pNo = rqst['manager_pNo']
        update = True
    if 'manager_email' in rqst:
        corp.manager_email = rqst['manager_email']
        update = True
    if update:
        corp.save()

    if 'name' in rqst:
        business_registrations = Business_Registration.objects.filter(customer_id=corp.id)
        if len(business_registrations) == 0:
            business_registration = Business_Registration(
                name=rqst['name'],
                regNo=rqst['regNo'],
                ceoName=rqst['ceoName'],
                address=rqst['address'],
                business_type=rqst['business_type'],
                business_item=rqst['business_item'],
                dt_reg=rqst['dt_reg'],
                customer_id=corp.id
            )
            business_registration.save()
        else:
            business_registration = business_registrations[0]
            if 'name' in rqst:
                business_registration.name = rqst['name']
            if 'regNo' in rqst:
                business_registration.regNo = rqst['regNo']
            if 'ceoName' in rqst:
                business_registration.ceoName = rqst['ceoName']
            if 'address' in rqst:
                business_registration.address = rqst['address']
            if 'business_type' in rqst:
                business_registration.business_type = rqst['business_type']
            if 'business_item' in rqst:
                business_registration.business_item = rqst['business_item']
            if 'dt_reg' in rqst:
                business_registration.dt_reg = rqst['dt_reg']
            if 'customer_id' in rqst:
                business_registration.customer_id = rqst['customer_id']
            business_registration.save()

    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403
def reg_staff(request):
    """
    고객사 직원을 등록한다.
    - 차후 전화번호 변경 부분과 중복 처리가 필요함.
    - 초기 pw 는 HappyDay365!!
        주)	response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/reg_staff?name=이요셉&login_id=hello&login_pw=A~~~8282&position=책임&department=개발&pNo=010-2450-5942&email=hello@ddtechi.com
    POST
        {
            'name': '홍길동',
            'login_id': 'hong_geal_dong',
            'position': '부장',	   # option 비워서 보내도 됨
            'department': '관리부',	# option 비원서 보내도 됨
            'pNo': '010-1111-2222', # '-'를 넣어도 삭제되어 저장 됨
            'email': 'id@daeducki.com',
        }
    response
        STATUS 200
        STATUS 542
            {'message':'전화번호나 아이디가 중복되었습니다.'}
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    name = rqst['name']
    login_id = rqst['login_id']
    position = rqst['position']
    department = rqst['department']
    phone_no = rqst['pNo']
    email = rqst['email']

    phone_no = phone_no.replace('-', '')
    phone_no = phone_no.replace(' ', '')

    staffs = Staff.objects.filter(pNo=phone_no, login_id=id)
    if len(staffs) > 0:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response()
    new_staff = Staff(
        name=name,
        login_id=login_id,
        login_pw=hash_SHA256('HappyDay365!!!'),
        co_id=worker.co_id,
        co_name=worker.co_name,
        position=position,
        department=department,
        pNo=phone_no,
        email=email
    )
    new_staff.save()
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
              "staff_permisstion": {
                "is_site_owner": false,
                "is_manager": false
              },
              "company_general": {
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
            {'message':'아이디나 비밀번호가 틀립니다.'}
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    login_id = rqst['login_id']
    login_pw = rqst['login_pw']
    print(login_id, login_pw, hash_SHA256(login_pw))
    staff = Staff.objects.get(id=1)
    print(staff.login_id, staff.login_pw)
    staffs = Staff.objects.filter(login_id=login_id, login_pw=hash_SHA256(login_pw))
    if len(staffs) == 0:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_530_ID_OR_PASSWORD_IS_INCORRECT.to_json_response()
    staff = staffs[0]
    staff.dt_login = datetime.datetime.now()
    staff.is_login = True
    staff.save()
    request.session['id'] = staff.id
    request.session.save()

    customers = Customer.objects.filter(id=staff.co_id)
    if len(customers) == 0:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_541_NOT_REGISTERED.to_json_response({'message':'등록된 업체가 없습니다.'})
    customer = customers[0]
    staff_permission = {'is_site_owner': staff.is_site_owner,  # 담당자인가?
                        'is_manager': staff.is_manager,  # 관리자인가?
                        }
    company_general = {'corp_name': customer.name,
                       'staff_name': customer.staff_name,
                       'staff_pNo': customer.staff_pNo,
                       'staff_email': customer.staff_email,
                       'manager_name': customer.manager_name,
                       'manager_pNo': customer.manager_pNo,
                       'manager_email': customer.manager_email,
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
                                 'dt_reg': business_registration.dt_reg.strftime('%Y-%m-%d')  # 사업자등록일
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

    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.session is None or 'id' not in request.session:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_200_SUCCESS.to_json_response({'message': '이미 로그아웃되었습니다.'})
    staff = Staff.objects.get(id=request.session['id'])
    staff.is_login = False
    staff.dt_login = datetime.datetime.now()
    staff.save()
    del request.session['id']
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403
def update_staff(request):
    """
    직원 정보를 수정한다.
    - 자신의 정보만 수정할 수 있다.
    	주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
    		response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/update_staff?before_pw=A~~~8282&login_pw=A~~~8282&name=박종기&position=이사&department=개발&phone_no=010-2557-3555&phone_type=10&push_token=unknown&email=thinking@ddtechi.com
    POST
    	{
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
    	STATUS 503
    		{'message': '비밀번호가 틀립니다.'}
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    print(worker_id)
    worker = Staff.objects.get(id=worker_id)

    before_pw = rqst['before_pw']  # 기존 비밀번호
    login_pw = rqst['login_pw']  # 변경하려는 비밀번호
    name = rqst['name']  # 이름
    position = rqst['position']  # 직책
    department = rqst['department']  # 부서 or 소속
    phone_no = rqst['phone_no']  # 전화번호
    phone_type = rqst['phone_type']  # 전화 종류	10:iPhone, 20: Android
    push_token = rqst['push_token']  # token
    email = rqst['email']  # id@ddtechi.co
    print(before_pw, login_pw, name, position, department, phone_no, phone_type, push_token, email)

    if len(phone_no) > 0:
        phone_no = phone_no.replace('-', '')
        phone_no = phone_no.replace(' ', '')
        print(phone_no)

    if hash_SHA256(before_pw) != worker.login_pw:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_531_PASSWORD_IS_INCORRECT.to_json_response()

    if len(login_pw) > 0:
        worker.login_pw = hash_SHA256(login_pw)
    if len(name) > 0:
        worker.name = name
    if len(position) > 0:
        worker.position = position
    if len(department) > 0:
        worker.department = department
    if len(phone_no) > 0:
        worker.pNo = phone_no
    if len(phone_type) > 0:
        worker.pType = phone_type
    if len(push_token) > 0:
        worker.push_token = push_token
    if len(email) > 0:
        worker.email = email
    worker.save()
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    staffs = Staff.objects.filter(co_id=worker.co_id).values('id', 'name', 'position', 'department', 'pNo', 'pType', 'email', 'login_id')
    arr_staff = []
    for staff in staffs:
        staff['id'] = AES_ENCRYPT_BASE64(str(staff['id']))
        arr_staff.append(staff)
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
        }
    response
        STATUS 200
        STATUS 422
            {'message':'사업장 이름, 관리자, 발주사 중 어느 하나도 빠지면 안 됩니다.'}
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    name = rqst['name']
    manager_id = rqst['manager_id']
    order_id = rqst['order_id']
    if len(name) == 0 or len(manager_id) == 0 or len(order_id) == 0:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':'사업장 이름, 관리자, 발주사 중 어느 하나도 빠지면 안 됩니다.'})

    manager = Staff.objects.get(id=AES_DECRYPT_BASE64(manager_id))
    order = Customer.objects.get(id=AES_DECRYPT_BASE64(order_id))
    new_work_place = Work_Place(
        name = name,
        place_name = name,
        contractor_id = worker.co_id,
        contractor_name = worker.co_name,
        manager_id = manager.id,
        manager_name = manager.name,
        manager_pNo = manager.pNo,
        manager_email = manager.email,
        order_id = order.id,
        order_name = order.name
    )
    new_work_place.save()
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403
def update_work_place(request):
    """
    사업장 수정
    - 변경 가능 내용: 사업장 이름, 관리자, 발주사
    - 관리자와 발주사는 선택을 먼저하고 선택된 id 로 변경한다.
        주)	값이 있는 항목만 수정한다. ('name':'' 이면 사업장 이름을 수정하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/update_work_place?work_place_id=qgf6YHf1z2Fx80DR8o_Lvg&name=&manager_id=&order_id=
    POST
        {
            'work_place_id':'사업장 id' # 수정할 사업장 id (암호화되어 있음)
            'name':'(주)효성 용연 1공장',	# 이름
            'manager_id':'관리자 id',	# 관리자 id (암호화되어 있음)
            'order_id':'발주사 id',	# 발주사 id (암호화되어 있음)
        }
    response
        STATUS 200
        STATUS 503
            {'message': '사업장을 수정할 권한이 없는 직원입니다.'}
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    # staff_id = AES_DECRYPT_BASE64(rqst['staff_id'])
    # staff = Staff.objects.get(id=staff_id)
    work_place_id = rqst['work_place_id']
    work_place = Work_Place.objects.get(id=work_place_id)
    if work_place.contractor_id != worker.co_id:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_524_HAVE_NO_PERMISSION_TO_MODIFY.to_json_response()

    manager_id = rqst['manager_id']
    if len(manager_id) > 0:
        manager = Staff.objects.get(id=AES_DECRYPT_BASE64(manager_id))
        work_place.manager_id = manager.id
        work_place.manager_name = manager.name
        work_place.manager_pNo = manager.pNo
        work_place.manager_email = manager.email

    order_id = rqst['order_id']
    if len(order_id) > 0:
        order = Customer.objects.get(id=AES_DECRYPT_BASE64(order_id))
        work_place.order_id = order.id
        work_place.order_name = order.name

    name = rqst['name']
    if len(name) > 0:
        work_place.name = name
        work_place.place_name = name

    work_place.save()
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403
def list_work_place(request):
    """
    사업장 목록
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    name = rqst['name']
    manager_name = rqst['manager_name']
    manager_phone = rqst['manager_phone']
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
        arr_work_place.append(work_place)
    result = {'work_places': arr_work_place}
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
            'name':'포장',
            'work_place_id':1,        # 사업장 id
            'type':'업무 형태',
            'dt_begin':'2019-01-28',  # 업무 시작 날짜
            'dt_end':'2019-02-28',    # 업무 종료 날짜
            'staff_id':2,             # 현장 소장
        }
    response
        STATUS 200
        STATUS 509
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    work_place_id = rqst['work_place_id']
    work_place = Work_Place.objects.get(id=work_place_id)
    staff_id = rqst['staff_id']
    staff = Staff.objects.get(id=staff_id)
    name = rqst['name']
    type = rqst['type']
    dt_begin = datetime.datetime.strptime(rqst['dt_begin'], "%Y-%m-%d")
    dt_end = datetime.datetime.strptime(rqst['dt_end'], "%Y-%m-%d")
    print(dt_begin, dt_end)
    new_work = Work(
        name=name,
        work_place_id=work_place.id,
        work_place_name=work_place.name,
        type=type,
        contractor_id=staff.co_id,
        contractor_name=staff.co_name,
        dt_begin=dt_begin,
        dt_end=dt_end,
        staff_id=staff.id,
        staff_name=staff.name,
        staff_pNo=staff.pNo,
        staff_email=staff.email,
    )
    new_work.save()
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403
def update_work(request):
    """
    사업장 업무 수정
        주)	값이 있는 항목만 수정한다. ('name':'' 이면 사업장 이름을 수정하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/update_work?work_id=1&name=비콘교체&work_place_id=1&type=3교대&contractor_id=1&dt_begin=2019-01-21&dt_end=2019-01-26&staff_id=2
    POST
        {
            'op_staff_id':'암호화된 id',  # 업무처리하는 직원
            'work_id':10,               # 업무 id
            'name':'포장',
            'work_place_id':1,        # 사업장 id
            'type':'업무 형태',
            'contractor_id':'파견업체(도급업체) id',
            'dt_begin':'2019-01-28',  # 업무 시작 날짜
            'dt_end':'2019-02-28',    # 업무 종료 날짜
            'staff_id':2,
        }
    response
        STATUS 200
        STATUS 503
            {'message': '사업장을 수정할 권한이 없는 직원입니다.'}
        STATUS 509
            {"msg": "??? matching query does not exist."} # ??? 을 찾을 수 없다.(op_staff_id, work_id 를 찾을 수 없을 때)
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    work_id = rqst['work_id']
    work = Work.objects.get(id=work_id)

    name = rqst['name']
    if len(name) > 0:
        work.name = name

    work_place_id = rqst['work_place_id']
    if len(work_place_id) > 0:
        work_place = Work_Place.objects.get(id=work_place_id)
        work.work_place_id = work_place.id
        work.work_place_name = work_place.name

    type = rqst['type']
    if len(type) > 0:
        work.type = type

    contractor_id = rqst['contractor_id']
    if len(contractor_id) > 0:
        contractor = Customer.objects.get(id=contractor_id)
        work.contractor_id = contractor.id
        work.contractor_name = contractor.name

    dt_begin = rqst['dt_begin']
    if len(dt_begin) > 0:
        work.dt_begin = datetime.datetime.strptime(dt_begin, "%Y-%m-%d")
        print(dt_begin, work.dt_begin)
        #
        # 근로자 시간 변경?
        #

    dt_end = rqst['dt_end']
    if len(dt_end) > 0:
        work.dt_end = datetime.datetime.strptime(dt_end, "%Y-%m-%d")
        print(dt_end, work.dt_end)
        #
        # 근로자 시간 변경?
        #

    staff_id = rqst['staff_id']
    if len(staff_id) > 0:
        staff = Staff.objects.get(id=staff_id)
        work.staff_id=staff.id
        work.staff_name=staff.name
        work.staff_pNo=staff.pNo
        work.staff_email=staff.email

    work.save()
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403
def list_work(request):
    """
    사업장 업무 목록
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/list_work?name=&manager_name=종기&manager_phone=3555&order_name=대덕
    GET
        work_place_name = 사업장 이름
        type            = 업무 형태
        contractor_name = 파견(도급)업체 이름
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    work_id = rqst['work_id']
    work = Work.objects.get(id=work_id)

    name = rqst['name']
    work_place_name = rqst['work_place_name']
    type = rqst['type']
    contractor_name = rqst['contractor_name']
    staff_name = rqst['staff_name']
    staff_pNo = rqst['staff_pNo']
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
    arr_work = [work for work in works]
    result = {'works': arr_work}
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@session_is_none_403
def reg_employee(request):
    """
    근로자 등록 - 업무별 전화번호 목록을 넣는 방식
        주)	response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/reg_employee?work_id=1&phone_numbers=010-3333-5555&phone_numbers=010-5555-7777&phone_numbers=010-7777-9999
    POST
        {
            'work_id':'사업장 업무 id',
            'phone_numbers':   # 업무에 배치할 근로자들의 전화번호
            [
                '010-3333-5555', '010-5555-7777', '010-7777-8888', ...
            ]
        }
    response
        STATUS 200
        STATUS 509
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    work_id = rqst['work_id']
    work = Work.objects.get(id=work_id)

    phones = rqst.getlist('phone_numbers')
    print(phones)
    for phone in phones:
        new_employee = Employee(
            is_active = 0, # 근무 중 아님
            dt_begin = work.dt_begin,
            dt_end = work.dt_end,
            work_id = work.id,
            work_name = work.name,
            work_place_name = work.work_place_name,
            pNo = phone
        )
        new_employee.save()
    #
    # 근로자 서버로 근로자의 업무 의사와 답변을 요청
    #
    # request = http://...
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403
def update_employee(request):
    """
    근로자 수정
     - 근로자가 업무를 거부했거나
     - 응답이 없어 업무에서 배제했거나
     - 업무 예정기간보다 일찍 업무가 끌났을 때
        주)	값이 있는 항목만 수정한다. ('name':'' 이면 사업장 이름을 수정하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/update_employee?
    POST
        {
            'employee_id':5,            # 필수
            'dt_end':2019-02-01,        # 근로자 한명의 업무 종료일을 변경한다. (업무 인원 전체는 업무에서 변경한다.)
            'is_active':'YES',          # YES: 업무 배정, NO: 업무 배제
            'message':'업무 종료일이 변경되었거나 업무에 대한 응답이 없어 업무에서 뺐을 때 사유 전달'
        }
    response
        STATUS 200
        STATUS 503
            {'message': '사업장을 수정할 권한이 없는 직원입니다.'}
        STATUS 509
            {"msg": "??? matching query does not exist."} # ??? 을 찾을 수 없다. (op_staff_id, work_id 를 찾을 수 없을 때)
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    employee_id = rqst['employee_id']
    employee = Employee.objects.get(id=employee_id)

    dt_end = rqst['dt_end']
    if len(dt_end) > 0:
        employee.dt_end = datetime.datetime.strptime(dt_end, "%Y-%m-%d")
        employee.is_active = 0 if employee.dt_end < datetime.datetime.now() else 1  # 업무 종료일이 오늘 이전이면 업무 종료
        print(dt_end, employee.dt_end, datetime.datetime.now(), employee.is_active)
        #
        # to employee server : message,
        #

    is_active = rqst['is_active']
    if is_active.upper() == 'YES':
        employee.is_active = 1
    elif is_active.upper() == 'NO':
        employee.is_active = 0

    message = rqst['message']
    #
    # to employee server : message,
    #
    employee.save()
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403
def list_employee(request):
    """
    근로자 목록
      - 업무별 리스트
      - option 에 따라 근로자 근태 내역 추가
        주)	값이 있는 항목만 검색에 사용한다. ('name':'' 이면 사업장 이름으로는 검색하지 않는다.)
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/customer/list_employee?work_id=1&is_working_history=YES
    GET
        work_id         = 업무 id
        is_working_history = 업무 형태 # YES: 근태내역 추가, NO: 근태내역 없음(default)
    response
        STATUS 200
            {
            	"employees":
            	[
            		{
            		    "id":42,
            			"is_active": false,
            			"dt_begin": "2019-01-30 15:35:39",
            			"dt_end": "2019-01-26 00:00:00",
            			"work_id": 1,
            			"work_name": "비콘교체",
            			"work_place_name": "대덕테크",
            			"employee_id": -1,
            			"name": "unknown",
            			"pNo": "010-3333-5555"
            		},
            		......
            	]
            }
    STATUS 503
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    worker = Staff.objects.get(id=worker_id)

    work_id = rqst['work_id']
    Work.objects.get(id=work_id) # 업무 에러 확인용

    employees = Employee.objects.filter(work_id=work_id).values('id',
                                                                'is_active',
                                                                'dt_begin',
                                                                'dt_end',
                                                                'work_id',
                                                                'work_name',
                                                                'work_place_name',
                                                                'employee_id',
                                                                'name',
                                                                'pNo')
    arr_employee = [employee for employee in employees]
    if rqst['is_working_history'].upper() == 'YES':
        print('   >>> request: working history')
        #
        #
        # 근로자 서버에 근태 내역 요청
        #
    result = {'employees': arr_employee}
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response(result)


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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
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
    work_place_id = rqst['work_place_id']
    print(work_place_id)
    if len(work_place_id) == 0:
        work_places = Work_Place.objects.filter(contractor_id=worker.co_id).values('id', 'name', 'contractor_name', 'place_name', 'manager_name', 'manager_pNo', 'order_name')
    else :
        work_places = Work_Place.objects.filter(id=work_place_id).values('id', 'name', 'contractor_name', 'place_name', 'manager_name', 'manager_pNo', 'order_name')
    arr_work_place = []
    for work_place in work_places:
        print('  ', work_place['name'])
        works = Work.objects.filter(work_place_id=work_place['id']).values('id', 'name', 'type', 'staff_name', 'staff_pNo')
        arr_work = []
        for work in works:
            print('    ', work['name'])
            employees = Employee.objects.filter(work_id=work['id']).values('id', 'name', 'pNo', 'is_active', 'dt_begin', 'dt_end')
            arr_employee = [employee for employee in employees]
            work['arr_employee'] = arr_employee
            arr_work.append(work)
            for employee in employees:
                print('      ', employee['pNo'])
        work_place['arr_work'] = arr_work
        arr_work_place.append(work_place)
    result = {'arr_work_place': arr_work_place}
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def staff_version(request):
    """
    현장 소장 - 앱 버전 확인
    http://0.0.0.0:8000/customer/staff_version?v=A.1.0.0.190111
    GET
        v=A.1.0.0.190111

    response
        STATUS 200
        STATUS 503
        {
            'message': '업그레이드가 필요합니다.'
            'url': 'http://...' # itune, google play update
        }
        STATUS 509
        {'message': '검사하려는 버전 값이 양식에 맞지 않습니다.'}
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    version = rqst['v']
    items = version.split('.')
    if len(items[4]) == 0:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '버전값의 양식이 틀립니다.'})
    ver_dt = items[4]
    dt_version = datetime.datetime.strptime('20' + ver_dt[:2] + '-' + ver_dt[2:4] + '-' + ver_dt[4:6] + ' 00:00:00',
                                            '%Y-%m-%d %H:%M:%S')
    dt_check = datetime.datetime.strptime('2019-01-12 00:00:00', '%Y-%m-%d %H:%M:%S')
    print(dt_version)
    if dt_version < dt_check:
        print('dt_version < dt_check')
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_551_AN_UPGRADE_IS_REQUIRED.to_json_response({'url': 'http://...'})
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def staff_foreground(request):
    """
    현장 소장 - background to foreground action (push 등의 내용을 가져온다.)
    - 로그인을 했었으면 id 로 로그인을 한다. (15분 후에는 login_id, login_pw 같이 보내야 한다.)
    - 처음 로그인하면 id 는 비우고 login_id, login_pw 를 암호화 해서 보낸다.
    - id, login_id, login_pw 는 앱 저장한다.
    http://0.0.0.0:8000/customer/staff_foreground?v=A.1.0.0.190111
    GET
        id= 암호화된 id # 처음이거나 15분 이상 지났으면 login_id, login_pw 를 보낸다.
        login_id=abc # 암호화 할 것
        login_pw=password # 암호화 한 것
    response
        STATUS 200
        {
            'id':'암호화 된 id', # 처음 로그인할 때 한번만 온다.
            'work_places':[{'work_place_id':'...', 'work_place_name':'...'}, ...], # 관리자의 경우 사업장
            'works':[{'work_id':'...', 'work_name':'...'}, ...]                     # 현장 소장의 경우 업무(관리자가 겸하는 경우도 있음.)
        }
        STATUS 603
            {'message': '로그인 아이디나 비밀번호가 틀립니다.'}
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    cipher_id = rqst['id']
    cipher_login_id = rqst['login_id']
    cipher_login_pw = rqst['login_pw']
    result = {}
    if len(cipher_id) > 0:
        app_user = Staff.objects.get(id = AES_DECRYPT_BASE64(cipher_id))
        if  datetime.datetime.now() > app_user.dt_app_login + datetime.timedelta(minutes=15):
            if app_user.login_id != int(AES_DECRYPT_BASE64(cipher_login_id)) or app_user.login_pw != cipher_login_pw:
                func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
                return REG_530_ID_OR_PASSWORD_IS_INCORRECT.to_json_response()
    else:
        app_user = Staff.objects.get(login_id=AES_DECRYPT_BASE64(cipher_login_id), login_pw=cipher_login_pw)
        result['id'] = AES_ENCRYPT_BASE64(str(app_user.id))

    work_places = Work_Place.objects.filter(contractor_ir=app_user.co_id, manager_id=app_user.id).values('id', 'name')
    if len(work_places) > 0:
        arr_work_place = [work_place for work_place in work_places]
        result['work_places'] = arr_work_place
    works = Work.objects.filter(contractor_ir=app_user.co_id, staff_id=app_user.id).values('id', 'name')
    if len(works) > 0:
        arr_work = [work for work in works]
        result['works'] = arr_work
    app_user.is_app_login = True
    app_user.dt_app_login = datetime.datetime.now()
    app_user.save()
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def staff_background(request):
    """
    현장 소장 - foreground to background (서버로 전송할 내용이 있으면 전송하다.)
    http://0.0.0.0:8000/customer/staff_background?v=A.1.0.0.190111
    POST
        id=암호화된 id
    response
        STATUS 200
        STATUS 604
            {'message': 'id 가 틀립니다.'}
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    cipher_id = rqst['id']
    if len(cipher_id) == 0:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_532_ID_IS_WRONG
    app_user = Staff.objects.get(id = AES_DECRYPT_BASE64(cipher_id))
    app_user.is_app_login = False
    app_user.dt_login = datetime.datetime.now()
    app_user.save()

    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def staff_update_me(request):
    """
    현장 소장 - 자기정보 update
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
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
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def staff_request_certification_no(request):
    """
    현장 소장 - 인증번호 요청(처음 실행)
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    phone_no = rqst['phone_no']
    if len(phone_no) == 0:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '전화번호가 없습니다.'})

    phone_no = phone_no.replace('+82', '0')
    phone_no = phone_no.replace('-', '')
    phone_no = phone_no.replace(' ', '')
    # print(phone_no)
    staffs = Staff.objects.filter(pNo=phone_no)
    if len(staffs) == 0:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def staff_verify_certification_no(request):
    """
    현장 소장 - 인증번호 확인
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
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
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_550_CERTIFICATION_NO_IS_INCORRECT.to_json_response()

    staff.pType = 20 if phone_type == 'A' else 10
    staff.push_token = push_token
    staff.save()

    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def staff_reg_my_work(request):
    """
    현장 소장 - 담당 업무 등록 (웹에서...)
    :param request:
    :return:
    """
    return


@cross_origin_read_allow
def staff_update_my_work(request):
    """
    현장 소장 - 담당 업무 내용 수정(웹에서...)
    :param request:
    :return:
    """
    return


@cross_origin_read_allow
def staff_list_my_work(request):
    """
    현장 소장 - 담당 업무 리스트
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

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
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def staff_work_list_employee(request):
    """
    현장 소장 - 업무에 근무 중인 근로자 리스트(전일, 당일 근로 내역 포함)
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    cipher_id = rqst['id']
    app_user = Staff.objects.get(id = AES_DECRYPT_BASE64(cipher_id))

    result = {}
    work_id=rqst['work_id']
    employees = Employee.objects.filter(work_id=work_id).values('is_active', 'dt_begin', 'dt_end', 'employee_id', 'name', 'pNo')
    if len(employees) > 0:
        arr_employee = [employee for employee in employees]
        result['employees'] = arr_employee
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def staff_work_update_employee(request):
    """
    현장 소장 - 업무에 근무 중인 근로자 내용 수정, 추가(지각, 외출, 조퇴, 특이사항)
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])        
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
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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

    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()
