from django.shortcuts import render

# Create your views here.
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
