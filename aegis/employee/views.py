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

from django.http import HttpResponse
from django.http import HttpRequest
from django.http import JsonResponse

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

# try: 다음에 code = 'argument incorrect'

def exceptionError(funcName, code, e) :
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
    try :
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
            rsapKey = rqst["RSAPublicKey"]
        # elif settings.IS_COVER_GET :
        #     logSend('>>> :-(')
        #     return HttpResponse(":-(");
        else :
            rsapKey = request.GET["RSAPublicKey"]
        result = {'R': 10,
                  'M': "문제없음",
                  'D': { 'RSAPublicKey': rsapKey,
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
        else :
            print('# keys = ' + len(request.GET["rk"].keys))
            rsapKey = request.GET["rk"]
        print('# keys = ' + len(rsapKey.keys))
        if rsapKey != '':
            print('parameter empty')

        result = {'R': 10,
                  'M': "문제없음",
                  'D': { 'AESKey': "01234567890123456789012345678900"
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

def exceptionError(funcName, code, e) :
    logError(funcName + ' >>> ' + code + ' ERROR: ' + str(e))
    logSend(funcName + ' >>> ' + code + ' ERROR: ' + str(e))
    print(str(e))
    result = {'R': 'ERROR', 'MSG': str(e)}
    return HttpResponse(json.dumps(result, cls=DateTimeEncoder))

"""
/employee/passer_reg
출입자 등록 : 출입 대상자를 등록하는 기능 (파견업체나 출입관리를 희망하는 업체(발주사 포함)에서 사용)
POST : json
	{
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
def passer_reg(request):
    try:
        response = HttpResponse()
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
def beacon_verify(request):
    try:
        response = HttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('beacon_verify', '503', e)

"""
/employee/reg_employee
근로자 앱 활성화 : 앱을 처음 작동 시켰을 때
POST : json
{
	'phone_no' : '010-1111-2222'
	'phone_type' : 'A' # 안드로이드 폰
	'push_token' : 'push token'	
}
response
	STATUS 200 
	전화번호 확인용 SMS 발송(6자리 숫자)
"""
def reg_employee(request):
    try:
        response = HttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('reg_employee', '503', e)

"""
/employee/verify_employee
근로자 등록 확인 : 문자로 온 SMS 문자로 근로자를 확인하는 기능 (여기서 사업장에 등록된 근로자인지 확인, 기존 등록 근로자인지 확인)
GET 
	pNo=010-1111-2222
	vNo=123456
response
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
def verify_employee(request):
    try:
        id = 1
        str_id = str(id)
        infor = {'id': AES_ENCRYPT_BASE64(str_id)}
        response = HttpResponse(json.dumps(infor, cls=DateTimeEncoder))
        print(response)
        response.status_code = 201
        return response
    except Exception as e:
        return exceptionError('verify_employee', '503', e)
