# log import
import json
import random

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt  # POST 에서 사용

from config.common import logSend, logError
from config.common import DateTimeEncoder, ValuesQuerySetToDict, exceptionError
# secret import
from config.secret import AES_ENCRYPT_BASE64, AES_DECRYPT_BASE64

from .models import Beacon
from .models import Beacon_History
from .models import Employee
from .models import Pass
from .models import Passer

import requests
from datetime import datetime, timedelta
import datetime

from django.conf import settings


def check_version(request):
    """
    앱 버전을 확인한다.
    http://0.0.0.0:8000/employee/check_version?v=A.1.0.0.190111
    GET
        v=A.1.0.0.190111

    response
        STATUS 200
        STATUS 503
        {
            'msg': '업그레이드가 필요합니다.'
            'url': 'http://...' # itune, google play update
        }
    """
    try:
        logSend('--- /employee/check_version')
        print("employee : check version")
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
            version = rqst['v']
        else:
            version = request.GET['v']

        items = version.split('.')
        if (items[4]) == 0:
            result = {'message': '검사하려는 버전 값이 양식에 맞지 않습니다.'}
            response = HttpResponse(json.dumps(result, cls=DateTimeEncoder))
            print(response)
            response.status_code = 503
            print(response.content)
            return response
        ver_dt = items[4]
        dt_version = datetime.datetime.strptime('20' + ver_dt[:2] + '-' + ver_dt[2:4] + '-' + ver_dt[4:6] + ' 00:00:00',
                                                '%Y-%m-%d %H:%M:%S')
        dt_check = datetime.datetime.strptime('2019-01-12 00:00:00', '%Y-%m-%d %H:%M:%S')
        print(dt_version)
        if dt_version < dt_check:
            print('dt_version < dt_check')
            result = {'message': '업그레이드가 필요합니다.',
                      'url': 'http://...'  # itune, google play update
                      }
            response = HttpResponse(json.dumps(result, cls=DateTimeEncoder))
            print(response)
            response.status_code = 503
        else:
            result = {}
            response = HttpResponse()
        print(response.content)
        return response
    except Exception as e:
        return exceptionError('check_version', '503', e)


@csrf_exempt
def passer_reg(request):
    """
    출입자 등록 : 출입 대상자를 등록하는 기능 (파견업체나 출입관리를 희망하는 업체(발주사 포함)에서 사용)
    http://dev.ddtechi.com:8055/employee/passer_reg?pass_type=-1&phones[]=010-1111-2222&phones[]=010-2222-3333&phones[]=010-3333-4444&phones[]=010-4444-5555
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
            'msg': '양식이 잘못되었습니다.'
        }
    """
    try:
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        pass_type = rqst['pass_type']
        phone_numbers = rqst['phones']

        print(phone_numbers)
        for i in range(6):
            passer = Passer(
                pNo=phone_numbers[i],
                employee_id=pass_type
            )
            passer.save()
        response = HttpResponse(json.dumps(phone_numbers, cls=DateTimeEncoder))
        response.status_code = 200
        logSend('<<< /employee/passer_reg')
        return response
    except Exception as e:
        return exceptionError('passer_reg', '509', e)


@csrf_exempt
def pass_reg(request):
    """
    출입등록 : 앱에서 비콘을 3개 인식했을 때 서버에 출근(퇴근)으로 인식하고 보내는 기능
    http://dev.ddtechi.com:8055/employee/pass_reg?passer_id=qgf6YHf1z2Fx80DR8o/Lvg&dt=2019-01-24%2013:33:00&is_in=1&major=11001&beacons[]=
    POST : json
        {
            'passer_id' : '앱 등록시에 부여받은 암호화된 출입자 id',
            'dt' : '2018-01-21 08:25:30',
            'is_in' : 1, # 0: out, 1 : in
            'major' : 11001, # 11 (지역) 001(사업장)
            'beacons' : [
                 {'minor': 11001, 'dt_begin': '2019-01-21 08:25:30', 'rssi': -70},
                 {'minor': 11002, 'dt_begin': '2019-01-21 08:25:31', 'rssi': -70},
                 {'minor': 11003, 'dt_begin': '2019-01-21 08:25:32', 'rssi': -70}
            ]
        }
    response
        STATUS 200
    """
    try:
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        cipher_passer_id = rqst['passer_id']
        dt = rqst['dt']
        is_in = rqst['is_in']
        major = rqst['major']
        beacons = rqst['beacons']

        if request.method == 'GET':
            beacons = [
                {'minor': 11001, 'dt_begin': '2019-01-21 08:25:30', 'rssi': -70},
                {'minor': 11002, 'dt_begin': '2019-01-21 08:25:31', 'rssi': -70},
                {'minor': 11003, 'dt_begin': '2019-01-21 08:25:32', 'rssi': -70}
                # {'minor': 11003, 'dt_begin': '2019-01-21 08:25:32', 'rssi': -70},
                # {'minor': 11002, 'dt_begin': '2019-01-21 08:25:31', 'rssi': -70},
                # {'minor': 11001, 'dt_begin': '2019-01-21 08:25:30', 'rssi': -70},
            ]

        passer_id = AES_DECRYPT_BASE64(cipher_passer_id)
        logSend('\t\t\t\t\t' + passer_id)
        print(passer_id, dt, is_in, major)
        print(beacons)
        for i in range(len(beacons)):
            beacon_list = Beacon.objects.filter(major=major, minor=beacons[i]['minor'])
            if len(beacon_list) > 0:
                beacon = beacon_list[0]
                beacon.dt_last = dt
                beacon.save()
            else:
                # ?? 운영에서 관리하도록 바뀌어야하나?
                beacon = Beacon(
                    uuid='12345678-0000-0000-0000-123456789012',
                    # 1234567890123456789012345678901234567890
                    major=major,
                    minor=beacons[i]['minor'],
                    dt_last=dt
                )
                beacon.save()

            beacon_history = Beacon_History(
                major=major,
                minor=beacons[i]['minor'],
                passer_id=passer_id,
                dt_begin=beacons[i]['dt_begin'],
                RSSI_begin=beacons[i]['rssi']
            )
            beacon_history.save()

        # logSend(is_in + str(is_in_verify(beacons)))
        print(is_in, str(is_in_verify(beacons)))
        new_pass = Pass(
            passer_id=passer_id,
            is_in=is_in,
            dt_reg=dt
        )
        new_pass.save()
        response = HttpResponse()
        response.status_code = 200
        logSend('<<< /employee/pass_reg')
        return response
    except Exception as e:
        return exceptionError('pass_reg', '509', e)


def is_in_verify(beacons):
    in_count = 0
    out_count = 0

    for i in range(1, len(beacons)):
        if beacons[i - 1]['minor'] < beacons[i]['minor']:
            in_count += 1
        else:
            out_count += 1

    return in_count > out_count


@csrf_exempt
def pass_verify(request):
    """
    출입확인 : 앱 사용자가 출근(퇴근) 버튼이 활성화 되었을 때 터치하면 서버로 전송
    http://192.168.219.62:8000/employee/pass_verify?passer_id=qgf6YHf1z2Fx80DR8o/Lvg&dt=2019-01-21 08:25:35&is_in=1
    POST : json
        {
            'passer_id' : '암호화된 출입자 id',
            'dt' : '2018-12-28 12:53:36',
            'is_in' : 1, # 0: out, 1 : in
        }
    response
        STATUS 200
    """
    try:
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        cipher_passer_id = rqst['passer_id']
        dt = rqst['dt']
        is_in = rqst['is_in']

        passer_id = AES_DECRYPT_BASE64(cipher_passer_id)
        logSend('\t\t\t\t\t' + passer_id)
        print(passer_id, dt, is_in)
        dt = datetime.datetime.now()
        # str_dt = dt.strftime('%Y-%m-%d %H:%M:%S')
        # print(dt, str_dt)
        new_pass = Pass(
            passer_id=passer_id,
            is_in=is_in,
            dt_verify=dt
        )
        new_pass.save()
        response = HttpResponse()
        response.status_code = 200
        logSend('<<< /employee/pass_verify')
        return response
    except Exception as e:
        return exceptionError('beacon_verify', '509', e)
    # 가장 최근에 저장된 값부터 가져옮
    # before_passes = Pass.objects.filter(passer_id = passer_id).order_by('-dt_reg')
    # for x in before_passes :
    #     print(x.dt_reg, x.is_in, x.dt_verify)
    #     if is_in == x.is_in and x.dt_verify == '':
    #         print('--- save')
    #         x.dt_verify = dt
    #         # s.save()
    #         break
    #     elif x.dt_verify != '' :
    #         print('--- msg')
    #         result = {'msg': '출근 전에 퇴근이 요청되었습니다.' if is_in else '퇴근 전에 출근이 요청되었습니다.'}
    #         response = HttpResponse(json.dumps(result, cls=DateTimeEncoder))
    #         response.status_code = 503
    #         print(response)
    #         return response
    #         break
    #
    # response = HttpResponse()
    # response.status_code = 200
    # return response


@csrf_exempt
def beacon_verify(request):
    """
    비콘 확인 : 출입 등록 후 10분 후에 서버로 앱에서 수집된 비콘 정보 전송 - 앱의 비콘 정보 삭제
    http://192.168.219.62:8000/employee/beacon_verify?passer_id=qgf6YHf1z2Fx80DR8o/Lvg&dt=2019-01-21 08:25:35&is_in=1&major=11001&beacons[]=
    POST : json
        {
            'passer_id' : '앱 등록시에 부여받은 암호화된 출입자 id',
            'dt' : '2018-01-16 08:29:00',
            'is_in' : 1, # 0: out, 1 : in
            'major' : 11001 # 11 (지역) 001(사업장)
            'beacons' : [
                {'minor': 11001, 'dt_begin': '2018-12-28 12:53:36', 'rssi': -70},
                ......
            ]
        }
    response
        STATUS 200
    """
    try:
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        cipher_passer_id = rqst['passer_id']
        dt = rqst['dt']
        is_in = rqst['is_in']
        major = rqst['major']
        beacons = rqst['beacons']

        if request.method == 'GET':
            beacons = [
                {'minor': 11001, 'dt_begin': '2019-01-21 08:25:30', 'rssi': -70},
                {'minor': 11002, 'dt_begin': '2019-01-21 08:25:31', 'rssi': -70},
                {'minor': 11003, 'dt_begin': '2019-01-21 08:25:32', 'rssi': -70}
                # {'minor': 11003, 'dt_begin': '2019-01-21 08:25:32', 'rssi': -70},
                # {'minor': 11002, 'dt_begin': '2019-01-21 08:25:31', 'rssi': -70},
                # {'minor': 11001, 'dt_begin': '2019-01-21 08:25:30', 'rssi': -70},
            ]
        passer_id = AES_DECRYPT_BASE64(cipher_passer_id)
        # print(passer_id, dt, is_in, major)
        print(beacons)
        for i in range(len(beacons)):
            beacon_list = Beacon.objects.filter(major=major, minor=beacons[i]['minor'])
            if len(beacon_list) > 0:
                beacon = beacon_list[0]
                beacon.dt_last = dt
                beacon.save()
            else:
                # ?? 운영에서 관리하도록 바뀌어야하나?
                beacon = Beacon(
                    uuid='12345678-0000-0000-0000-123456789012',
                    # 1234567890123456789012345678901234567890
                    major=major,
                    minor=beacons[i]['minor'],
                    dt_last=dt
                )
                beacon.save()

            beacon_history = Beacon_History(
                major=major,
                minor=beacons[i]['minor'],
                passer_id=passer_id,
                dt_begin=beacons[i]['dt_begin'],
                RSSI_begin=beacons[i]['rssi']
            )
            beacon_history.save()
        response = HttpResponse()
        response.status_code = 200
        logSend('<<< /employee/beacon_verify')
        return response
    except Exception as e:
        return exceptionError('beacon_verify', '509', e)


@csrf_exempt
def reg_employee(request):
    """
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
    try:
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        phone_no = rqst['phone_no']

        phone_no = phone_no.replace('+82', '0')
        phone_no = phone_no.replace('-', '')
        phone_no = phone_no.replace(' ', '')
        # print(phone_no)
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
            'sender': settings.SMS_SENDER_PN,
            'receiver': passer.pNo,
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
        response = HttpResponse()
        response.status_code = 200
        logSend('<<< /employee/reg_employee', phone_no)
        return response
    except Exception as e:
        return exceptionError('reg_employee', '509', e)


@csrf_exempt
def verify_employee(request):
    """
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
        STATUS 503
        {
            'message': '인증번호가 틀립니다.'
        }
        STATUS 200 # 기존 근로자
        {
            'id': '암호화된 id 그대로 보관되어서 사용되어야 함', 'name': '홍길동', 'bank': '기업은행', 'bank_account': '12300000012000',
            'bank_list': ['국민은행', ... 'NH투자증권']
        }
        STATUS 201 # 새로운 근로자 : 이름, 급여 이체 은행, 계좌번호를 입력받아야 함
        {
            'id': '암호화된 id 그대로 보관되어서 사용되어야 함',
            'bank_list': ['국민은행', ... 'NH투자증권']
        }
        STATUS 202 # 출입 정보만 처리하는 출입자
        {
            'id': '암호화된 id'
        }
    """
    try:
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

        passer = Passer.objects.get(pNo=phone_no)
        cn = AES_DECRYPT_BASE64(cipher_cn)
        if passer.cn != int(cn):
            rMsg = {'message': '인증번호가 틀립니다.'}
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
            if employee.name == 'unknown':
                status_code = 201
            else:
                result['name'] = employee.name
                result['bank'] = employee.bank
                result['bank_account'] = employee.bank_account

        if status_code == 200 or status_code == 201:
            result['bank_list'] = ['국민은행', '기업은행', '농협은행', '신한은행', '산업은행', '우리은행', '한국씨티은행', 'KEB하나은행', 'SC은행', '경남은행',
                                   '광주은행', '대구은행', '도이치은행', '뱅크오브아메리카', '부산은행', '산림조합중앙회', '저축은행', '새마을금고중앙회', '수협은행',
                                   '신협중앙회', '우체국', '전북은행', '제주은행', '카카오뱅크', '중국공상은행', 'BNP파리바은행', 'HSBC은행', 'JP모간체이스은행',
                                   '케이뱅크', '교보증권', '대신증권', 'DB금융투자', '메리츠종합금융증권', '미래에셋대우', '부국증권', '삼성증권', '신영증권',
                                   '신한금융투자', '에스케이증권', '현대차증권주식회사', '유안타증권주식회사', '유진투자증권', '이베스트증권', '케이프투자증권', '키움증권',
                                   '펀드온라인코리아', '하나금융투자', '하이투자증권', '한국투자증권', '한화투자증권', 'KB증권', 'KTB투자증권', 'NH투자증권']
        # print(result)

        passer.pType = 20 if phone_type == 'A' else 10
        passer.push_token = push_token
        passer.cn = 0
        passer.save()

        response = HttpResponse(json.dumps(result, cls=DateTimeEncoder))
        response.status_code = status_code
        # print(response)
        logSend('<<< /employee/verify_employee')
        return response
    except Exception as e:
        return exceptionError('work_list', '503', e)


@csrf_exempt
def work_list(request):
    """
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
    try:
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        cipher_passer_id = rqst["passer_id"]
        str_dt = rqst["dt"]
        passer_id = AES_DECRYPT_BASE64(cipher_passer_id)
        logSend('\t\t\t\t\t' + passer_id)
        print('work_list : passer_id', passer_id)
        passer = Passer.objects.get(id=passer_id)
        employee = Employee.objects.get(id=passer.employee_id)
        print('work_list :', employee.name, ' 현재 가상 데이터 표출')
        dt_begin = datetime.datetime.strptime(str_dt + '-01 00:00:00', '%Y-%m-%d %H:%M:%S')
        dt_end = datetime.datetime.strptime(str_dt + '-01 00:00:00', '%Y-%m-%d %H:%M:%S')
        if dt_end.month + 1 == 13:
            month = 1
            dt_end = dt_end.replace(month=1, year=dt_end.year + 1)
        else:
            dt_end = dt_end.replace(month=dt_end.month + 1)
        # dt_end = dt_end + timedelta(days=31)
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
        # print('work_list :', response)
        logSend('<<< /employee/work_list')

        return response
    except Exception as e:
        return exceptionError('work_list', '503', e)


def generation_pass_history(request):
    """
    출입 기록에서 일자별 출퇴근 기록을 만든다.
    퇴근버튼이 눌렸을 때나 최종 out 기록 후 1시간 후에 처리한다.
    1. 주어진 날짜의 in, dt_verify 를 찾는다. (출근버튼을 누른 시간)
    2. 주어진 날짜의
    """
    try:
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        cipher_passer_id = rqst['passer_id']
        name = rqst['name']
        bank = rqst['bank']
        bank_account = rqst['bank_account']
        pNo = rqst['pNo']

        if len(pNo):
            pNo = pNo.replace('-', '')
            pNo = pNo.replace(' ', '')
            print(pNo)

        print(cipher_passer_id, name, bank, bank_account)
        passer_id = AES_DECRYPT_BASE64(cipher_passer_id)
        logSend('\t\t\t\t\t' + passer_id)
        passer = Passer.objects.get(id=passer_id)
        employee = Employee.objects.get(id=passer.employee_id)
        if len(name) > 0:
            employee.name = name
        if len(bank) > 0 and len(bank_account) > 0:
            employee.bank = bank
            employee.bank_account = bank_account
        employee.save()
        response = HttpResponse()
        response.status_code = 200
        logSend('<<< /employee/generation_pass_history')
        return response
    except Exception as e:
        return exceptionError('exchange_info', '503', e)


@csrf_exempt
def exchange_info(request):
    """
    근로자 정보 변경 : 근로자의 정보를 변경한다.
        주)     로그인이 있으면 앱 시작할 때 화면 표출
            항목이 비어있으면 처리하지 않지만 비워서 보내야 한다.
    http://0.0.0.0:8000/employee/exchange_info?passer_id=qgf6YHf1z2Fx80DR8o/Lvg&name=박종기&bank=기업은행&bank_account=00012345600123&pNo=010-2557-3555
    POST
        {
            'passer_id': '서버로 받아 저장해둔 출입자 id',
            'name': '이름',
            'bank': '기업은행',
            'bank_account': '12300000012000',
            'pNo': '010-2222-3333', # 추후 SMS 확인 절차 추가
        }
    response
        STATUS 200
    """
    try:
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        cipher_passer_id = rqst['passer_id']
        name = rqst['name']
        bank = rqst['bank']
        bank_account = rqst['bank_account']
        pNo = rqst['pNo']

        if len(pNo):
            pNo = pNo.replace('-', '')
            pNo = pNo.replace(' ', '')
            print(pNo)

        print(cipher_passer_id, name, bank, bank_account)
        passer_id = AES_DECRYPT_BASE64(cipher_passer_id)
        logSend('\t\t\t\t\t' + passer_id)
        passer = Passer.objects.get(id=passer_id)
        employee = Employee.objects.get(id=passer.employee_id)
        if len(name) > 0:
            employee.name = name
        if len(bank) > 0 and len(bank_account) > 0:
            employee.bank = bank
            employee.bank_account = bank_account
        employee.save()
        response = HttpResponse()
        response.status_code = 200
        logSend('<<< /employee/exchange_info')
        return response
    except Exception as e:
        return exceptionError('exchange_info', '503', e)
