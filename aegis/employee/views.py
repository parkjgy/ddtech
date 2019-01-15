from django.shortcuts import render

# log import
from config.common import logSend
from config.common import logHeader
from config.common import logError

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
chech_version
/empolyee/check_version
앱 버전을 확인한다.
request
	v: 1.0.0.190111

response
	R: 	10 - 최신 버전이다.
		20 - 업데이트가 필요하다.
		21 - url 에서 업데이트를 받아라.
	M: 업그레이드 하세요.
	D:
		url: itune, google play update
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
