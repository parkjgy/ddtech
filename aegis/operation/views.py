from django.shortcuts import render

import json

from django.http import HttpResponse
from django.http import HttpRequest
from django.http import JsonResponse

from django.views.decorators.csrf import csrf_exempt

# log import
from config.common import logSend
from config.common import logHeader
from config.common import logError

##### JSON Processor

def ValuesQuerySetToDict(vqs):
    return [item for item in vqs]

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime) :
            if obj.utcoffset() is not None:
                obj = obj - obj.utcoffset() + timedelta(0,0,0,0,0,9)
                #logSend('DateTimeEncoder >>> utcoffset() = ' + str(obj.utcoffset()) + ', obj = ' + str(obj))
            encoded_object = obj.strftime('%Y-%m-%d %H:%M:%S')
            #logSend('DateTimeEncoder >>> is YES >>>' + str(encoded_object))
        else:
            encoded_object =json.JSONEncoder.default(self, obj)
            #logSend('DateTimeEncoder >>> is NO >>>' + str(encoded_object))
        return encoded_object

# Cross-Origin Read Allow Rule 
class CRSJsonResponse(JsonResponse):
    def __init__(self, data, **kwargs):
        super().__init__(data, **kwargs)
        self["Access-Control-Allow-Origin"] = "*"
        self["Access-Control-Allow-Methods"] = "GET, OPTIONS, POST"
        self["Access-Control-Max-Age"] = "1000"
        self["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type"
	
class CRSHttpResponse(HttpResponse):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self["Access-Control-Allow-Origin"] = "*"
        self["Access-Control-Allow-Methods"] = "GET, OPTIONS, POST"
        self["Access-Control-Max-Age"] = "1000"
        self["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type"
	
	
# try: 다음에 code = 'argument incorrect'

def exceptionError(funcName, code, e) :
    logError(funcName + ' >>> ' + code + ' ERROR: ' + str(e))
    logSend(funcName + ' >>> ' + code + ' ERROR: ' + str(e))
    result = {'R': 'ERROR', 'MSG': str(e)}
    return HttpResponse(json.dumps(result, cls=DateTimeEncoder))

"""
/operation/reg_staff
운영 직원 등록
POST 
	{
		'pNo': '010-1111-2222',
		'id': 'thinking',
		'pw': 'a~~~8282'
	}
response
	STATUS 200
"""
def reg_staff(request):
    try:
        response = HttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('reg_staff', '503', e)

"""
/operation/login
로그인
POST 
	{
		'id': 'thinking',
		'pw': 'a~~~8282'
	}
response
	STATUS 200
	STATUS 401
		{
		  "err": {
		    "code": 104, 
		    "msg": "The username or password was not correct"
		  }, 
		  "stat": "fail"
		}
"""
def login(request):
    try:
        response = HttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('login', '503', e)

"""
/operation/update_staff
직원 정보를 수정한다.
	주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
		response 는 추후 추가될 예정이다.
POST 
	{
		'id': '암호화된 id',
		'before_pw': '기존 비밀번호',
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
				'msg': '기존 비밀번호가 틀립니다.'
			}
		}
"""
def update_staff(request):
    try:
        response = HttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('update_staff', '503', e)

"""
/operation/reg_customer
고객사를 등록한다.
간단한 내용만 넣어서 등록하고 나머지는 고객사 담당자가 추가하도록 한다.
입력한 전화번호로 SMS 에 id 와 pw 를 보낸다.
	주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
		response 는 추후 추가될 예정이다.
http://0.0.0.0:8000/operation/reg_customer?customer_name=대덕테크&staff_name=박종기&staff_pNo=010-2557-3555&staff_email=thinking@ddtechi.com
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
import requests

@csrf_exempt
def reg_customer(request):
    if request.method == 'OPTIONS':
        return CRSHttpResponse()
    try:
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
            customer_name = rqst["customer_name"]
            staff_name = rqst["staff_name"]
            staff_pNo = rqst["staff_pNo"]
            staff_email = rqst["staff_email"]
        else :
            customer_name = request.GET["customer_name"]
            staff_name = request.GET["staff_name"]
            staff_pNo = request.GET["staff_pNo"]
            staff_email = request.GET["staff_email"]

        rJson = {'customer_name': customer_name,
                 'staff_name': staff_name,
                 'staff_pNo': staff_pNo,
                 'staff_email': staff_email
                 }
        response_customer = requests.post('http://0.0.0.0:8000/customer/reg_customer', json=rJson)
        r = response_customer
        """
        rData = {
            'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
            'user_id': 'yuadocjon22',
            'sender':'01024505942',
            'receiver': '01020736959', #'01025573555',
            'msg_type': 'SMS',
            'msg': '반갑습니다.\n'
                   '\'이지스 팩토리\'예요~~\n'
                   '아이디 temp_id\n'
                   '비밀번호 happy_day!!!\n'
        }

        r = requests.post('https://apis.aligo.in/send/', data=rData)
        """
        print(r.status_code)
        print(r.headers['content-type'])
        print(r.text)
        print(r.json())

        response = CRSJsonResponse(r.json())
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('reg_customer', '503', e)

"""
/operation/update_work_place
사업장 내용을 수정한다.
	주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
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
def update_work_place(request):
    try:
        response = HttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('update_work_place', '503', e)

"""
/operation/update_beacon
비콘 내용을 수정한다.
	주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
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
def update_beacon(request):
    try:
        response = HttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('update_beacon', '503', e)
"""
/operation/list_work_place
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
def list_work_place(request):
    try:
        response = HttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('list_work_place', '503', e)

"""
/operation/list_beacon
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
def list_beacon(request):
    try:
        response = HttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('list_beacon', '503', e)

"""
/operation/detail_beacon
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
def detail_beacon(request):
    try:
        response = HttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('detail_beacon', '503', e)
