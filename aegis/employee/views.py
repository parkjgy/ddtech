from django.shortcuts import render

# log import
from config.common import logSend
from config.common import logHeader
from config.common import logError

# secret import
from config.secret import AES_ENCRYPT_BASE64
from config.secret import AES_DECRYPT_BASE64

from employee.models import Employee

from django.forms.models import model_to_dict

import json

from .models import Employee
from .models import Passer
from .models import Pass
from .models import Beacon_History
from .models import Beacon

import random

from django.http import HttpResponse
from django.http import HttpRequest
from django.http import JsonResponse

from django.views.decorators.csrf import csrf_exempt, csrf_protect  # POST 에서 사용


# --- JSON Processor

def ValuesQuerySetToDict(vqs):
    return [item for item in vqs]


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            if obj.utcoffset() is not None:
                obj = obj - obj.utcoffset() + timedelta(0, 0, 0, 0, 0, 9)
                # logSend('DateTimeEncoder >>> utcoffset() = ' + str(obj.utcoffset()) + ', obj = ' + str(obj))
            encoded_object = obj.strftime('%Y-%m-%d %H:%M:%S')
            # logSend('DateTimeEncoder >>> is YES >>>' + str(encoded_object))
        else:
            encoded_object = json.JSONEncoder.default(self, obj)
            # logSend('DateTimeEncoder >>> is NO >>>' + str(encoded_object))
        return encoded_object


# try: 다음에 code = 'argument incorrect'

def exceptionError(funcName, code, e):
    logError(funcName + ' >>> ' + code + ' ERROR: ' + str(e))
    logSend(funcName + ' >>> ' + code + ' ERROR: ' + str(e))
    result = {'R': 'ERROR', 'MSG': str(e)}
    return HttpResponse(json.dumps(result, cls=DateTimeEncoder))


"""
/employee/check_version
앱 버전을 확인한다.
GET
	v=A.1.0.0.190111

response
	STATUS 200
	STATUS 503
	{
		'message': '업그레이드가 필요합니다.'
		'url': 'http://...' # itune, google play update
	}
"""


def checkVersion(request):
    print("employee : check version")
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
        for key in rqst.keys():
            print(key, rqst[key])
    print(rqst)
    result = {'R': 'OK'}
    response = HttpResponse(json.dumps(result, cls=DateTimeEncoder))
    print(response)
    response.status_code = 503
    print(response.content)
    return response


"""
test_RSA
앱에서 만들어 보낸 RSA1024 public key가 정상인지 확인
request:
RSAPublicKey: RSA1024 public key

response:
R: 10
M: ""
D:
	RSAPublicKey: 보낸키 확인용
	testValue: 보낸키로 ABCDEFGHIJKLMNOPQRSTUVWXYZ`0123456789~!@#$%^&*()_+-=[]\;',./{}|:"<>? 을 암호화한 값
"""


def test_RSA(request):
    try:
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
            rsapKey = rqst["RSAPublicKey"]
        # elif settings.IS_COVER_GET :
        #     logSend('>>> :-(')
        #     return HttpResponse(":-(");
        else:
            rsapKey = request.GET["RSAPublicKey"]
        result = {'R': 10,
                  'M': "문제없음",
                  'D': {'RSAPublicKey': rsapKey,
                        'testValue': "ABCDEFGHIJKLMNOPQRSTUVWXYZ`0123456789~!@#$%^&*()_+-=[]\;',./{}|:\"<>?"
                        }
                  }
        response = HttpResponse(json.dumps(result, cls=DateTimeEncoder))
        response.status_code = 503
        return response
        # staffCode = AES_DECRYPT(base64decode(_staffCode.encode('utf-8')))
        # if staffCode == '......' :
        #     return exceptionError('mng_currentEnv', staffCode, 'cannot decrypt')
        # logSend('mng_currentEnv >>> staffCode = ' + staffCode)
        #
        # staffs = Staff.objects.filter(isDeleted = False, id = staffCode[2:])
        # if len(staffs) == 0 :
        #     return jsonNotFoundManagement('mng_currentEnv', staffCode)
        #
        # envirenments = Environment.objects.filter().values('manager_id', 'dt', 'timeOutPushMinute', 'timeOutWorkingMinute', 'timeCheckServer', 'feeDriver', 'responseDelaySec', 'driverRegServiceAmount').order_by('-dt')
        # arrEnv = [env for env in envirenments]
        #
        # result = { 'R': 'OK', 'MSG': 'Current', 'ARRAY': arrEnv }
        # return testMngResponse(json.dumps(result, cls=DateTimeEncoder))
    except Exception as e:
        # return exceptionError('mng_currentEnv', staffCode, e)
        eResponse = HttpResponse(json.dumps({'R': 20, 'M': "에러 났어요"}))
        eResponse.status_code = 503
        return eResponse


"""
request_AES256
대칭키(AES 256) 요청
request:
	rk : 대칭키를 암호화할 RSA 1024 public key,
response:
	R : 10
	M : ""
    D :
    	AESKey : "01234567890123456789012345678900"

test_AES
받은 대칭키(AES 256) 가 정상인지 확인
request:
	cipherText : "검사하고 싶은 문자열"
response:
	R : 00
	M : ""
	D :
		text : "복호화된 문자열"
"""


def request_AES256(request):
    try:
        print(request)
        print(request.GET)
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
            rsapKey = rqst["rk"]
        # elif settings.IS_COVER_GET :
        #     logSend('>>> :-(')
        #     return HttpResponse(":-(");
        else:
            print('# keys = ' + len(request.GET["rk"].keys))
            rsapKey = request.GET["rk"]
        print('# keys = ' + len(rsapKey.keys))
        if rsapKey != '':
            print('parameter empty')

        result = {'R': 10,
                  'M': "문제없음",
                  'D': {'AESKey': "01234567890123456789012345678900"
                        },
                  }
        response = HttpResponse(json.dumps(result, cls=DateTimeEncoder))
        response.status_code = 503
        return response
    except Exception as e:
        print('error ' + str(e))
        return exceptionError('request_AES256', '0', e)
        eResponse = HttpResponse(json.dumps({'R': 20, 'M': "에러 났어요"}))
        eResponse.status_code = 503
        return eResponse


def exceptionError(funcName, code, e):
    logError(funcName + ' >>> ' + code + ' ERROR: ' + str(e))
    logSend(funcName + ' >>> ' + code + ' ERROR: ' + str(e))
    print(str(e))
    result = {'R': 'ERROR', 'MSG': str(e)}
    return HttpResponse(json.dumps(result, cls=DateTimeEncoder))


"""
/employee/passer_reg
출입자 등록 : 출입 대상자를 등록하는 기능 (파견업체나 출입관리를 희망하는 업체(발주사 포함)에서 사용)
http://0.0.0.0:8000/employee/passer_reg?p1=01025573555&p2=01074648939&p3=01020736959&p4=01054214410&p5=01047302499&p6=01024505942
POST : json
	{
	    'pass_type' : -2, # -1 : 일반 출입자, -2 : 출입만 관리되는 출입자 
		'phones': [
			'010-1111-2222', '010-2222-3333', ...
		]
	}
response
	STATUS 200
	STATUS 503
	{
		'message': '양식이 잘못되었습니다.'
	}
"""


@csrf_exempt
def passer_reg(request):
    try:
        phone_numbers = []
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
            pass_type = rqst['pass_type']
            # rqst = {'phones': ["01025573555", "01074648939", "01020736959", "01054214410", "01047302499", "01024505942"]}
            phones = rqst['phones']
            for x in phones:
                phone_numbers.append(x)
        else:
            pass_type = -2
            phone_numbers.append(request.GET["p1"])
            phone_numbers.append(request.GET["p2"])
            phone_numbers.append(request.GET["p3"])
            phone_numbers.append(request.GET["p4"])
            phone_numbers.append(request.GET["p5"])
            phone_numbers.append(request.GET["p6"])

        print(phone_numbers)
        for i in range(6):
            passer = Passer(
                pNo=phone_numbers[i],
                employee_id = pass_type
            )
            passer.save()
        response = HttpResponse(json.dumps(phone_numbers, cls=DateTimeEncoder))
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('passer_reg', '503', e)


"""
/employee/pass_reg
출입등록 : 앱에서 비콘을 3개 인식했을 때 서버에 출근(퇴근)으로 인식하고 보내는 기능
POST : json
	{
		'passer_id' : '앱 등록시에 부여받은 암호화된 출입자 id',
		'dt' : '2018-01-16 08:29:00',
		'action' : 10,
		'major' : 11001 # 11 (지역) 001(사업장)
		'beacons' : [
			{'minor': 11001, 'dt_begin': '2018-12-28 12:53:36', 'rssi': -70},
			{'minor': 11001, 'dt_begin': '2018-12-28 12:53:36', 'rssi': -70},
			{'minor': 11001, 'dt_begin': '2018-12-28 12:53:36', 'rssi': -70}		
		]
	}
response
	STATUS 200
"""


@csrf_exempt
def pass_reg(request):
    try:
        response = HttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('pass_reg', '503', e)


"""
/employee/pass_verify
출입확인 : 앱 사용자가 출근(퇴근) 버튼이 활성화 되었을 때 터치하면 서버로 전송
POST : json
	{
		'passer_id' : '출입자 id',
		'dt' : '2018-12-28 12:53:36',
		'action' : 10,
	} 
response
	STATUS 200
"""


def pass_verify(request):
    try:
        response = HttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('pass_verify', '503', e)


"""
/employee/beacon_verify
비콘 확인 : 출입 등록 후 10분 후에 서버로 앱에서 수집된 비콘 정보 전송 - 앱의 비콘 정보 삭제
POST : json
	{
		'passer_id' : '앱 등록시에 부여받은 암호화된 출입자 id',
		'dt' : '2018-01-16 08:29:00',
		'action' : 10,
		'major' : 11001 # 11 (지역) 001(사업장)
		'beacons' : [
			{'minor': 11001, 'dt_begin': '2018-12-28 12:53:36', 'rssi': -70},
			......
		]
	}
response
	STATUS 200
"""


@csrf_exempt
def beacon_verify(request):
    try:
        response = HttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('beacon_verify', '503', e)


"""
/employee/reg_employee
근로자를 등록한다.
근로자 앱을 처음 실행시킬 때 사용한다.
SMS 로 인증 문자(6자리)를 보낸다.
http://0.0.0.0:8000/employee/reg_employee?phone_no=01025573555
POST : json
{
	'phone_no' : '010-1111-2222'
}
response
	STATUS 200 
"""
import requests


@csrf_exempt
def reg_employee(request):
    try:
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
            phone_no = rqst['phone_no']
        else:
            phone_no = request.GET["phone_no"]

        phone_no = phone_no.replace('-', '')
        phone_no = phone_no.replace(' ', '')
        print(phone_no)
        passers = Passer.objects.filter(pNo=phone_no)
        if len(passers) == 0:
            passer = Passer(
                pNo=phone_no
            )
        else:
            passer = passers[0]

        certificateNo = random.randint(100000, 999999)
        passer.cn = certificateNo
        passer.save()

        rData = {
            'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
            'user_id': 'yuadocjon22',
            'sender': '01024505942',
            'receiver': passer.pNo,
            'msg_type': 'SMS',
            'msg': '이지스 팩토리 앱 사용\n'
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
        response = HttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('reg_employee', '503', e)


"""
/employee/verify_employee
근로자 등록 확인 : 문자로 온 SMS 문자로 근로자를 확인하는 기능 (여기서 사업장에 등록된 근로자인지 확인, 기존 등록 근로자인지 확인)
http://0.0.0.0:8000/employee/verify_employee?phone_no=010-2557-3555&cn=580757&phone_type=A&push_token=token
POST
    { 
	    'phone_no' : '010-1111-2222'
	    'cn' ; 123456
    	'phone_type' : 'A' # 안드로이드 폰
	    'push_token' : 'push token'
	}	
response
    STATUS 503
    {
        'msg': '인증번호가 틀립니다.'
    }
	STATUS 200 # 기존 근로자
	{
		'id': '암호화된 id 그대로 보관되어서 사용되어야 함', 'name': '홍길동', 'bank': '기업은행', 'bank_account': '12300000012000'
	}
	STATUS 201 # 새로운 근로자 : 이름, 급여 이체 은행, 계좌번호를 입력받아야 함
	{
		'id': '암호화된 id 그대로 보관되어서 사용되어야 함'
	}
	STATUS 202 # 출입 정보만 처리하는 출입자
	{
		'id': '암호화된 id'
	}
"""


@csrf_exempt
def verify_employee(request):
    try:
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
            phone_no = rqst['phone_no']
            cn = rqst['cn']
            phone_type = rqst['phone_type']
            push_token = rqst['push_token']
        else:
            phone_no = request.GET["phone_no"]
            cn = request.GET["cn"]
            phone_type = request.GET["phone_type"]
            push_token = request.GET["push_token"]
        phone_no = phone_no.replace('-', '')
        phone_no = phone_no.replace(' ', '')

        print(phone_no)
        passer = Passer.objects.get(pNo=phone_no)
        if passer.cn != int(cn):
            rMsg = {'msg': '인증번호가 틀립니다.'}
            response = HttpResponse(json.dumps(rMsg, cls=DateTimeEncoder))
            response.status_code = 503
            print(response)
            return response
        print('s 1')
        status_code = 200
        result = {'id': AES_ENCRYPT_BASE64(str(passer.id))}
        if passer.employee_id == -2:  # 근로자 아님 출입만 처리함
            status_code = 202
        elif passer.pType == 0:  # 신규 근로자
            status_code = 201
            employee = Employee(
            )
            employee.save()
            passer.employee_id = employee.id
        else:
            employee = Employee.objects.get(id=passer.employee_id)
            result['name'] = employee.name
            result['va_bank'] = employee.va_bank
            result['va_account'] = employee.va_account
        print(result)

        passer.pType = 20 if phone_type == 'A' else 10
        passer.push_token = push_token
        passer.cn = 0
        passer.save()

        response = HttpResponse(json.dumps(result, cls=DateTimeEncoder))
        response.status_code = status_code
        print(response)
        return response
    except Exception as e:
        return exceptionError('verify_employee', '503', e)


"""
/employee/work_list
근로 내용 : 근로자의 근로 내역을 월 기준으로 1년까지 요청함, 캘린더나 목록이 스크롤 될 때 6개월정도 남으면 추가 요청해서 표시할 것
http://0.0.0.0:8000/employee/work_list?passer_id=qgf6YHf1z2Fx80DR8o/Lvg&dt=2018-12
GET
	passer_id='서버로 받아 저장해둔 출입자 id'
	dt = '2018-01'
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
"""

from datetime import datetime, timedelta
import datetime
def work_list(request):
    try:
        cipher_passer_id = request.GET["passer_id"]
        str_dt = request.GET["dt"]
        passer_id = AES_DECRYPT_BASE64(cipher_passer_id)
        print('work_list : passer_id', passer_id)
        passer = Passer.objects.get(id = passer_id)
        employee = Employee.objects.get(id=passer.employee_id)
        print('work_list :', employee.name, ' 현재 가상 데이터 표출')
        dt_begin = datetime.datetime.strptime(str_dt + '-01 00:00:00', '%Y-%m-%d %H:%M:%S')
        dt_end = datetime.datetime.strptime(str_dt + '-01 00:00:00', '%Y-%m-%d %H:%M:%S')
        if dt_end.month + 1 == 13 :
            month = 1
            dt_end = dt_end.replace(month=1, year=dt_end.year + 1)
        else:
            dt_end = dt_end.replace(month=dt_end.month + 1)
        #dt_end = dt_end + timedelta(days=31)
        print(dt_begin, dt_end)
        passes = Pass.objects.filter(passer_id=passer.id, dt_reg__gt=dt_begin, dt_reg__lt=dt_end)
        print('work_list :', len(passes))
        result = {
            'working': [
                {'action': 112, 'dt_begin': '2018-12-03 08:25:00', 'dt_end': '2018-12-03 17:33:00', 'outing': [
                    {'dt_begin': '2018-12-03 12:30:00', 'dt_end': '2018-12-03 13:30:00'}]},
                {'action': 110, 'dt_begin': '2018-12-04 08:25:00', 'dt_end': '2018-12-04 17:33:00', 'outing': []},
                {'action': 110, 'dt_begin': '2018-12-05 08:25:00', 'dt_end': '2018-12-05 17:33:00', 'outing': []},
                {'action': 110, 'dt_begin': '2018-12-06 08:25:00', 'dt_end': '2018-12-06 17:33:00', 'outing': []},
                {'action': 110, 'dt_begin': '2018-12-07 08:25:00', 'dt_end': '2018-12-07 17:33:00', 'outing': []},

                {'action': 210, 'dt_begin': '2018-12-10 08:55:00', 'dt_end': '2018-12-10 17:33:00', 'outing': []},
                {'action': 110, 'dt_begin': '2018-12-11 08:25:00', 'dt_end': '2018-12-11 17:33:00', 'outing': []},
                {'action': 120, 'dt_begin': '2018-12-12 08:25:00', 'dt_end': '2018-12-12 15:33:00', 'outing': []},
                {'action': 110, 'dt_begin': '2018-12-13 08:25:00', 'dt_end': '2018-12-13 17:33:00', 'outing': []},
                {'action': 110, 'dt_begin': '2018-12-14 08:25:00', 'dt_end': '2018-12-14 17:33:00', 'outing': []},

                {'action': 110, 'dt_begin': '2018-12-17 08:25:00', 'dt_end': '2018-17-12 17:33:00', 'outing': []},
                {'action': 110, 'dt_begin': '2018-12-18 08:25:00', 'dt_end': '2018-18-14 17:33:00', 'outing': []},
                {'action': 112, 'dt_begin': '2018-12-19 08:25:00', 'dt_end': '2018-19-15 17:33:00', 'outing': [
                    {'dt_begin': '2018-12-01 12:30:00', 'dt_end': '2018-12-01 13:30:00'}]},
                {'action': 110, 'dt_begin': '2018-12-20 08:25:00', 'dt_end': '2018-12-20 17:33:00', 'outing': []},
                {'action': 110, 'dt_begin': '2018-12-21 08:25:00', 'dt_end': '2018-12-21 17:33:00', 'outing': []},
                {'action': 110, 'dt_begin': '2018-12-31 08:25:00', 'dt_end': '2018-12-31 17:33:00', 'outing': []},
            ]
        }
        response = HttpResponse(json.dumps(result, cls=DateTimeEncoder))
        response.status_code = 200
        print('work_list :', response)
        return response
    except Exception as e:
        return exceptionError('work_list', '503', e)


"""
/employee/exchange_info
근로자 정보 변경 : 근로자의 정보를 변경한다.
	주) 	로그인이 있으면 앱 시작할 때 화면 표출
		항목이 비어있으면 처리하지 않지만 비워서 보내야 한다.
POST
	{
		'passer_id': '서버로 받아 저장해둔 출입자 id',
		'pw': '암호화해서 보낸다.',
		'bank': '기업은행',
		'bank_account': '12300000012000',
		'pNo': '010-2222-3333', # 추후 SMS 확인 절차 추가
	} 
response
	STATUS 200
"""


@csrf_exempt
def exchange_info(request):
    try:
        id = 1
        response = HttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('exchange_info', '503', e)
