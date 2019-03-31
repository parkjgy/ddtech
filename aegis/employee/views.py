# log import
import json
import random
import inspect

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt  # POST 에서 사용

from config.common import logSend, logError
from config.common import ReqLibJsonResponse
from config.common import DateTimeEncoder, ValuesQuerySetToDict, exceptionError
from config.common import func_begin_log, func_end_log
from config.common import no_only_phone_no, phone_format

# secret import
from config.secret import AES_ENCRYPT_BASE64, AES_DECRYPT_BASE64
from config.status_collection import *
from config.decorator import cross_origin_read_allow

from .models import Beacon
from .models import Beacon_History
from .models import Employee
from .models import Notification_Work
from .models import Work
from .models import Pass
from .models import Passer
from .models import Pass_History

import requests
from datetime import datetime, timedelta
import datetime

from django.conf import settings


@cross_origin_read_allow
def check_version(request):
    """
    앱 버전을 확인한다. (마지막 190111 은 필히 6자리)
    http://0.0.0.0:8000/employee/check_version?v=A.1.0.0.190111
    GET
        v=A.1.0.0.190111

    response
        STATUS 200
        STATUS 551
        {
            'msg': '업그레이드가 필요합니다.'
            'url': 'http://...' # itune, google play update
        }
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    version = rqst['v']

    items = version.split('.')
    ver_dt = items[len(items) - 1]
    print(ver_dt)
    if len(ver_dt) < 6:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_520_UNDEFINED.to_json_response({'message': '검사하려는 버전 값이 양식에 맞지 않습니다.'})

    dt_version = datetime.datetime.strptime('20' + ver_dt[:2] + '-' + ver_dt[2:4] + '-' + ver_dt[4:6] + ' 00:00:00',
                                            '%Y-%m-%d %H:%M:%S')
    response_operation = requests.post(settings.OPERATION_URL + 'dt_android_upgrade', json={})
    print('status', response_operation.status_code, response_operation.json())
    dt_android_upgrade = response_operation.json()['dt_update']
    print(dt_android_upgrade, datetime.datetime.strptime(dt_android_upgrade, '%Y-%m-%d %H:%M:%S'))

    dt_check = datetime.datetime.strptime(dt_android_upgrade, '%Y-%m-%d %H:%M:%S')
    print(dt_version)
    if dt_version < dt_check:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_551_AN_UPGRADE_IS_REQUIRED.to_json_response({'url': 'http://...'  # itune, google play update
                  })
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def reg_employee_for_customer(request):
    """
    <<<고객 서버용>>> 고객사에서 보낸 업무 배정 SMS로 알림 (보냈으면 X)
    http://0.0.0.0:8000/employee/reg_employee_for_customer?customer_work_id=qgf6YHf1z2Fx80DR8o_Lvg&work_place_name=효성1공장&work_name_type=경비 주간&dt_begin=2019/03/04&dt_end=2019/03/31&dt_answer_deadline=2019-03-03 19:00:00&staff_name=이수용&staff_phone=01099993333&phones=01025573555&phones=01046755165&phones=01011112222&phones=01022223333&phones=0103333&phones=01044445555
    POST : json
        {
          "customer_work_id":qgf6YHf1z2Fx80DR8o_Lvg,
          "work_place_name": "효성1공장",
          "work_name_type": "경비(주간)",
          "dt_begin": "2019/03/04",
          "dt_end": "2019/03/31",
          "dt_answer_deadline": 2019-03-03 19:00:00,
          "staff_name": "이수용",
          "staff_phone": "01099993333",
          "phones": [
            "01025573555",
            "01022223333",
            "01033334444",
            "01044445555"
          ]
        }
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "result": {
                "01025573555": 2,   # 고객이 앱을 설치했음
                "01046755165": -1,  # 고객이 앱을 아직 설치하지 않았음
                "01011112222": -1,
                "01022223333": -1,
                "0103333": -101,    # 잘못된 전화번호임
                "01044445555": -1
              }
            }
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    # print(rqst["customer_work_id"])
    # print(rqst["work_place_name"])
    # print(rqst["work_name_type"])
    # print(rqst["dt_begin"])
    # print(rqst["dt_end"])
    print(rqst["dt_answer_deadline"])
    # print(rqst["staff_name"])
    # print(rqst["staff_phone"])

    # pass_type = rqst['pass_type']
    if request.method == 'POST':
        phone_numbers = rqst['phones']
    else:
        phone_numbers = rqst.getlist('phones')
    print(phone_numbers, rqst['phones'])

    find_works = Work.objects.filter(customer_work_id=rqst['customer_work_id'])
    if len(find_works) == 0:
        work = Work(
            customer_work_id=rqst["customer_work_id"],
            work_place_name=rqst["work_place_name"],
            work_name_type=rqst["work_name_type"],
            begin=rqst["dt_begin"],
            end=rqst["dt_end"],
            staff_name=rqst["staff_name"],
            staff_pNo=rqst["staff_phone"],
        )
        work.save()
    else:
        work = find_works[0]

    msg = '이지체크\n'\
          '새로운 업무를 앱에서 확인해주세요.\n'\
          '앱은 홈페이지에서...\n'\
          'http://0.0.0.0:8000/app'

    # print(len(msg))

    rData = {
        'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
        'user_id': 'yuadocjon22',
        'sender': settings.SMS_SENDER_PN,
        # 'receiver': phone_numbers[i],
        'msg_type': 'SMS',
        'msg': msg,
    }
    if settings.DEBUG:
        rData['testmode_yn'] = 'Y'

    phones_state = {}
    for i in range(len(phone_numbers)):
        print('DDD ', phone_numbers[i])
        notification_list = Notification_Work.objects.filter(customer_work_id=rqst["customer_work_id"], employee_pNo=phone_numbers[i])
        if len(notification_list) > 0:
            print('--- sms 알려서 안보냄 ', phone_numbers[i])
            # 이전에 SMS 를 보낸적있는 전화번호는 전화번호 출입자가 저장하고 있는 근로자 id 만 확인해서 보낸다.
            find_passers = Passer.objects.filter(pNo=phone_numbers[i])
            phones_state[phone_numbers[i]] = -1 if len(find_passers) == 0 else find_passers[0].employee_id  # 등록된 전화번호 없음 (즉, 앱 설치되지 않음)
        else:
            print('--- sms 보냄', phone_numbers[i])
            # SMS 를 보낸다.
            rData['receiver'] = phone_numbers[i]
            rSMS = requests.post('https://apis.aligo.in/send/', data=rData)
            logSend('SMS result', rSMS.json())
            print('--- ', rSMS.json())
            # if int(rSMS.json()['result_code']) < 0:
            if len(phone_numbers[i]) < 11:
                # 전화번호 에러로 문자를 보낼 수 없음.
                phones_state[phone_numbers[i]] = -101
            else:
                # SMS 를 보냈으면 전화번호의 출입자가 앱을 설치하고 알림을 볼 수 있게 저장한다.
                find_passers = Passer.objects.filter(pNo=phone_numbers[i])
                phones_state[phone_numbers[i]] = -1 if len(find_passers) == 0 else find_passers[0].employee_id  # 등록된 전화번호 없음 (즉, 앱 설치되지 않음)
                new_notification = Notification_Work(
                    work_id = work.id,
                    customer_work_id=rqst["customer_work_id"],
                    employee_id= phones_state[phone_numbers[i]],
                    employee_pNo=phone_numbers[i],
                    dt_answer_deadline=rqst["dt_answer_deadline"],
                )
                new_notification.save()
    print('--- ',phones_state)
    logSend({'result':phones_state})
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response({'result':phones_state})


@cross_origin_read_allow
def notification_list(request):
    """
    foreground request 새로운 업무 알림: 앱이 foreground 상태가 될 때 가져와서 선택할 수 있도록 표시한다.
    http://dev.ddtechi.com:8055/employee/notification_list?passer_id=qgf6YHf1z2Fx80DR8o_Lvg
    GET
        passer_id='서버로 받아 저장해둔 출입자 id'  # 암호화된 값임
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "notifications": [
                {
                  "id": "qgf6YHf1z2Fx80DR8o_Lvg==",
                  "work_place_name": "효성1공장",
                  "work_name_type": "경비(주)간",
                  "begin": "2019/03/04",
                  "end": "2019/03/31",
                  "dt_answer_deadline": "2019-03-03 19:00:00",
                  "staff_name": "이수용",
                  "staff_pNo": "01099993333"
                }
              ]
            }

            효성 용연 1공장
            생산(주간)
            2019/03/04 ~ 2019/03/31
            응답 시한: 2019-03-03 19:00:00
            - 담당: 이수용 [전화] [문자]

            work_place_name  효성 용연 1공장
            work_name (type)  생산(주간)
            begin ~ end
            응답 시한: dt_answer_deadline
            - 담당: staff_name [staff_phone_no] [staff_phone_no]
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    passers = Passer.objects.filter(id=AES_DECRYPT_BASE64(rqst['passer_id']))
    if len(passers) != 1:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_403_FORBIDDEN.to_json_response({'message':'알 수 없는 사용자입니다.'})
    passer = passers[0]
    dt_today = datetime.datetime.now()
    print(passer.pNo)
    notification_list = Notification_Work.objects.filter(employee_pNo=passer.pNo, dt_answer_deadline__gt=dt_today)
    print(notification_list)
    arr_notification = []
    for notification in notification_list:
        work = Work.objects.get(id=notification.work_id)
        view_notification = {
            'id': AES_ENCRYPT_BASE64(str(notification.id)),
            'work_playce_name': work.work_place_name,
            'work_name_type': work.work_name_type,
            'begin': work.begin,
            'end': work.end,
            'staff_name': work.staff_name,
            'staff_pNo': work.staff_pNo,
            'dt_answer_deadline': notification.dt_answer_deadline.strftime("%Y-%m-%d %H:%M:%S")
        }
        arr_notification.append(view_notification)
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response({'notifications':arr_notification})


@cross_origin_read_allow
def notification_accept(request):
    """
    새로운 업무에 대한 응답
    http://dev.ddtechi.com:8055/employee/notification_accept?passer_id=qgf6YHf1z2Fx80DR8o_Lvg&notification_id=qgf6YHf1z2Fx80DR8o_Lvg&is_accept=0
    POST : json
        {
            'passer_id' : '서버로 받아 저장해둔 출입자 id',  # 암호화된 값임
            'notification_id': 'cipher id',
            'is_accept': 0       # 1 : 업무 수락, 0 : 업무 거부
        }
    response
        STATUS 200
        STATUS 403
            {'message':'알 수 없는 사용자입니다.'}
            {'message':'알 수 없는 알림입니다.'}
        STATUS 542
            {'message':'파견사 측에 근로자 정보가 없습니다.'}
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    passers = Passer.objects.filter(id=AES_DECRYPT_BASE64(rqst['passer_id']))
    if len(passers) != 1:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_403_FORBIDDEN.to_json_response({'message':'알 수 없는 사용자입니다.'})
    passer = passers[0]

    notifications = Notification_Work.objects.filter(id=AES_DECRYPT_BASE64(rqst['notification_id']))
    if len(notifications) != 1:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_403_FORBIDDEN.to_json_response({'message':'알 수 없는 알림입니다.'})
    notification = notifications[0]

    is_accept = 1 if rqst['is_accept'] == 1 else 0
    #
    # 근로자 정보에 업무를 등록
    #
    if passer.employee_id > 0:
        employee = Employee.objects.get(id=passer.employee_id)
        if employee.work_id != -1:
            # 2개가 모두 있을 때 처리는 version 2.0 에서
            employee.work_id_2 = notification.work_id
    else:
        employee = Employee(
            work_id=notification.work_id
        )
        employee.save()
        logSend('ERROR: 출입자가 근로자가 아닌 경우 - 발생하면 안됨 employee_id:', employee_id)
    print(employee.name)
    #
    # to customer server
    # 근로자가 수락/거부했음
    #
    request_data = {
        'worker_id': AES_ENCRYPT_BASE64('thinking'),
        'work_id':notification.customer_work_id,
        'employee_id':employee.id,
        'employee_name':employee.name,
        'employee_pNo':notification.employee_pNo,
        'is_accept':is_accept
    }
    print(request_data)
    response_customer = requests.post(settings.CUSTOMER_URL + 'employee_work_accept_for_employee', json=request_data)
    print(response_customer)
    if response_customer.status_code != 200:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return ReqLibJsonResponse(response_customer)

    notification.delete()

    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def passer_list(request):
    """
    출입자 리스트 : 출입자 검색
    http://dev.ddtechi.com:8055/employee/passer_list?phone_no=1111
    POST : json
        {
            'phone_no' : 1111  # 폰 번호의 일부 혹은 전부
        }
    response
        STATUS 200
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    phone_no = no_only_phone_no(rqst['phone_no'])

    employee_list = []
    passers = Passer.objects.filter(pNo__contains=phone_no)
    for passer in passers:
        passer_info = {}
        if passer.employee_id > 0:
            employee = Employee.objects.get(id=passer.employee_id)
            passer_info['name'] = employee.name
            passer_info['work_id'] = employee.work_id
            passer_info['work_id_2'] = employee.work_id_2
        else:
            passer_info['name'] = '---'
            passer_info['work_id'] = 0
            passer_info['work_id_2'] = 0
        passer_info['id'] = AES_ENCRYPT_BASE64(str(passer.id))
        passer_info['pNo'] = passer.pNo
        employee_list.append(passer_info)
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response({'passers':employee_list})


@cross_origin_read_allow
def passer_reg(request):
    """
    출입자 등록 : 출입 대상자를 등록하는 기능 (파견업체나 출입관리를 희망하는 업체(발주사 포함)에서 사용)
    http://dev.ddtechi.com:8055/employee/passer_reg?pass_type=-1&phones=010-1111-2222&phones=010-2222-3333&phones=010-3333-4444&phones=010-4444-5555
    POST : json
        {
            'pass_type' : -2, # -1 : 일반 출입자, -2 : 출입만 관리되는 출입자
            'phones': [
                '010-1111-2222', '010-2222-3333', ...
            ]
        }
    response
        STATUS 200
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    pass_type = rqst['pass_type']
    if request.method == 'POST':
        phone_numbers = rqst['phones']
    else:
        phone_numbers = rqst.getlist('phones')

    print(phone_numbers)
    for phone_no in phone_numbers:
        passer = Passer(
            pNo=no_only_phone_no(phone_no),
            employee_id=pass_type
        )
        print([(x, passer.__dict__[x]) for x in Passer().__dict__.keys() if not x.startswith('_')])
        passer.save()
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def pass_reg(request):
    """
    출입등록 : 앱에서 비콘을 3개 인식했을 때 서버에 출근(퇴근)으로 인식하고 보내는 기능
    http://dev.ddtechi.com:8055/employee/pass_reg?passer_id=qgf6YHf1z2Fx80DR8o/Lvg&dt=2019-01-24%2013:33:00&is_in=1&major=11001&beacons=
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    cipher_passer_id = rqst['passer_id']
    dt = rqst['dt']
    is_in = rqst['is_in']
    major = rqst['major']
    beacons = rqst['beacons']
    if request.method == 'POST':
        beacons = rqst['beacons']
    else:
        beacons = rqst.getlist('beacons')

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
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


def is_in_verify(beacons):
    in_count = 0
    out_count = 0

    for i in range(1, len(beacons)):
        if beacons[i - 1]['minor'] < beacons[i]['minor']:
            in_count += 1
        else:
            out_count += 1

    return in_count > out_count


@cross_origin_read_allow
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
    # dt = datetime.datetime.now()
    dt = datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
    # str_dt = dt.strftime('%Y-%m-%d %H:%M:%S')
    # print(dt, str_dt)
    new_pass = Pass(
        passer_id=passer_id,
        is_in=is_in,
        dt_verify=dt
    )
    new_pass.save()
    before_pass = Pass.objects.filter(passer_id=passer_id, dt_reg__lt=dt).values('id', 'passer_id','is_in','dt_reg','dt_verify').order_by('dt_reg').first()
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()
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


@cross_origin_read_allow
def pass_sms(request):
    """
    출입확인 : 전화 사용자가 문자로 출근(퇴근)을 서버로 전송
    http://0.0.0.0:8000/employee/pass_sms?phone_no=010-3333-9999&dt=2019-01-21 08:25:35&sms=출근
    POST : json
        {
            'phone_no' : '문자 보낸 사람 전화번호',
            'dt' : '2018-12-28 12:53:36',
            'sms' : '출근했어요' # '퇴근했어요', '지금 외출 나갑니다', '먼저 퇴근합니다', '외출했다가 왔습니다', '오늘 조금 지각했습니다'
        }
    response
        STATUS 200
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    phone_no = no_only_phone_no(rqst['phone_no'])
    dt = rqst['dt']
    sms = rqst['sms']
    logSend(phone_no, dt, sms)

    if '출근' in sms:
        is_in = True
    elif '퇴근' in sms:
        is_in = False

    passers = Passer.objects.filter(pNo=phone_no)
    if len(passers) == 0:
        logError({'ERROR': '출입자의 전화번호가 없습니다.' + phone_no})
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_541_NOT_REGISTERED.to_json_response()
    passer = passers[0]
    print(phone_no, passer.id, dt, is_in)
    # dt = datetime.datetime.now()
    dt = datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
    # str_dt = dt.strftime('%Y-%m-%d %H:%M:%S')
    # print(dt, str_dt)
    new_pass = Pass(
        passer_id=passer.id,
        is_in=is_in,
        dt_verify=dt
    )
    new_pass.save()
    # before_pass = Pass.objects.filter(passer_id=passer_id, dt_reg__lt=dt).values('id', 'passer_id','is_in','dt_reg','dt_verify').order_by('dt_reg').first()
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()
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


@cross_origin_read_allow
def beacons_is(request):
    """
    비콘 확인 : 출입 등록 후 10분 후에 서버로 앱에서 수집된 비콘 정보 전송 - 앱의 비콘 정보 삭제
    http://192.168.219.62:8000/employee/beacons_is?passer_id=qgf6YHf1z2Fx80DR8o/Lvg&dt=2019-01-21 08:25:35&is_in=1&major=11001&beacons=
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def certification_no_to_sms(request):
    """
    핸드폰 인증 숫자 6자리를 SMS로 요청 - 근로자 앱을 처음 실행할 때 SMS 문자 인증 요청
    - SMS 로 인증 문자(6자리)를 보낸다.
    http://0.0.0.0:8000/employee/certification_no_to_sms?phone_no=010-2557-3555
    POST : json
    {
        'phone_no' : '010-1111-2222'
        'passer_id' : '......' # 암호화된 id 기존 전화번호를 바꾸려는 경우만 사용
    }
    response
        STATUS 200
        STATUS 542
            {'message':'전화번호가 이미 등록되어 있어 사용할 수 없습니다.\n고객센터로 문의하십시요.'}
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    phone_no = rqst['phone_no']

    phone_no = phone_no.replace('+82', '0')
    phone_no = phone_no.replace('-', '')
    phone_no = phone_no.replace(' ', '')
    # print(phone_no)
    if 'passer_id' in rqst and len(rqst['passer_id']) > 6:
        passer_id = AES_DECRYPT_BASE64(rqst['passer_id'])
        passers = Passer.objects.filter(pNo=phone_no).exclude(id=passer_id)
        if len(passers) > 0:
            func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
            return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response({'message':'전화번호가 이미 등록되어 있어 사용할 수 없습니다.\n고객센터로 문의하십시요.'})
        passer = Passer.objects.get(id=passer_id)
        passer.pNo = phone_no
    else:
        passers = Passer.objects.filter(pNo=phone_no)
        if len(passers) == 0:
            passer = Passer(
                pNo=phone_no
            )
        else:
            passer = passers[0]

    if passer.cn == 0:
        certificateNo = random.randint(100000, 999999)
        if settings.IS_TEST:
            certificateNo = 201903
        passer.cn = certificateNo
        passer.save()
        print(certificateNo)
    else:
        certificateNo = passer.cn

    rData = {
        'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
        'user_id': 'yuadocjon22',
        'sender': settings.SMS_SENDER_PN,
        'receiver': passer.pNo,
        'msg_type': 'SMS',
        'msg': '이지체크 앱 사용\n'
               '인증번호[' + str(certificateNo) + ']입니다.'
    }
    if settings.IS_TEST:
        rData['testmode_yn'] = 'Y'
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_200_SUCCESS.to_json_response(rData)

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
def reg_from_certification_no(request):
    """
    근로자 등록 확인 : 문자로 온 SMS 문자로 근로자를 확인하는 기능 (여기서 사업장에 등록된 근로자인지 확인, 기존 등록 근로자인지 확인)
    http://0.0.0.0:8000/employee/reg_from_certification_no?phone_no=010-2557-3555&cn=580757&phone_type=A&push_token=token
    POST
        {
            'phone_no' : '010-1111-2222',
            'cn' : '6자리 SMS 인증숫자',
            'phone_type' : 'A', # 안드로이드 폰
            'push_token' : 'push token',
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    print('--- ', rqst['phone_no'])
    phone_no = no_only_phone_no(rqst['phone_no'])
    cn = rqst['cn']
    phone_type = rqst['phone_type']
    push_token = rqst['push_token']

    passers = Passer.objects.filter(pNo=phone_no)
    if len(passers) > 1:
        duplicate_id = [passer.id for passer in passers]
        print('ERROR: ', phone_no, duplicate_id)
        logSend('ERROR: ', phone_no, duplicate_id)
    passer = passers[0]
    print(passer)
    if passer.cn == 0:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_550_CERTIFICATION_NO_IS_INCORRECT.to_json_response({'message':'인증시간이 지났습니다.\n다시 인증요청을 해주세요.'})
    else:
        cn = cn.replace(' ', '')
        if passer.cn != int(cn):
            func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
            return REG_550_CERTIFICATION_NO_IS_INCORRECT.to_json_response()
    status_code = 200
    result = {'id': AES_ENCRYPT_BASE64(str(passer.id))}
    if passer.employee_id == -2:  # 근로자 아님 출입만 처리함
        status_code = 202
    elif passer.employee_id < 0:  # 신규 근로자
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
        notification_list = Notification_Work.objects.filter(employee_pNo=phone_no)
        for notification in notification_list:
            notification.employee_id = employee.id
            notification.save()
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

    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def update_my_info(request):
    """
    근로자 정보 변경 : 근로자의 정보를 변경한다.
        주)     로그인이 있으면 앱 시작할 때 화면 표출
            항목이 비어있으면 처리하지 않지만 비워서 보내야 한다.
    http://0.0.0.0:8000/employee/update_my_info?passer_id=qgf6YHf1z2Fx80DR8o/Lvg&name=박종기&bank=기업은행&bank_account=00012345600123&pNo=010-2557-3555
    POST
        {
            'passer_id': '서버로 받아 저장해둔 출입자 id',
            'name': '이름',
            'bank': '기업은행',
            'bank_account': '12300000012000',
            'pNo': '010-2222-3333', # 추후 SMS 확인 절차 추가
            'work_start':'08:00', # 오전 오후로 표시하지 않는다.
            'working_time':'08',        # 시간 4 - 12
            'work_start_alarm':'1:00',  # '-60'(한시간 전), '-30'(30분 전), 'X'(없음) 셋중 하나로 보낸다.
            'work_end_alarm':'30',      # '-30'(30분 전), '0'(정각), 'X'(없음) 셋중 하나로 보낸다.
        }
    response
        STATUS 200
            {'message':'정상적으로 처리되었습니다.'}
        STATUS 422
            {'message':'이름은 2자 이상이어야 합니다.'}
            {'message':'전화번호를 확인해 주세요.'}
            {'message':'계좌번호가 너무 짧습니다.\n다시 획인해주세요.'}
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    cipher_passer_id = rqst['passer_id']
    passer_id = AES_DECRYPT_BASE64(cipher_passer_id)
    logSend('   ' + passer_id)
    passer = Passer.objects.get(id=passer_id)
    employee = Employee.objects.get(id=passer.employee_id)

    if 'name' in rqst:
        if len(rqst['name']) < 2:
            func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':'이름은 2자 이상이어야 합니다.'})
        employee.name = rqst['name'];
        logSend('   ' + rqst['name']);
    if 'pNo' in rqst:
        pNo = no_only_phone_no(rqst['pNo'])
        if len(pNo) < 9:
            func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':'전화번호를 확인해 주세요.'})
        passer.pNo = pNo;
        passer.save()
        logSend('   ' + pNo);
    if 'bank' in rqst and 'bank_account' in rqst:
        if len(rqst['bank_account']) < 5:
            func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':'계좌번호가 너무 짧습니다.\n다시 획인해주세요.'})
        employee.bank = rqst['bank'];
        employee.bank_account = rqst['bank_account'];
        logSend('   ' + rqst['bank'], rqst['bank_account'])
    if 'work_start' in rqst and 'working_time' in rqst and 'work_start_alarm' in rqst and 'work_end_alarm' in rqst:
        employee.work_start = rqst['work_start'];
        employee.working_time = rqst['working_time'];
        employee.work_start_alarm = rqst['work_start_alarm'];
        employee.work_end_alarm = rqst['work_end_alarm'];
        logSend('   ' + rqst['work_start'], rqst['working_time'], rqst['work_start_alarm'], rqst['work_end_alarm'])

    employee.save()
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def my_work_histories(request):
    """
    근로 내용 : 근로자의 근로 내역을 월 기준으로 1년까지 요청함, 캘린더나 목록이 스크롤 될 때 6개월정도 남으면 추가 요청해서 표시할 것
    action 설명
        총 3자리로 구성 첫자리는 출근, 2번째는 퇴근, 3번째는 외출 횟수
        첫번째 자리 1 - 정상 출근, 2 - 지각 출근
        두번째 자리 1 - 정상 퇴근, 2 - 조퇴, 3 - 30분 연장 근무, 4 - 1시간 연장 근무, 5 - 1:30 연장 근무
    http://0.0.0.0:8000/employee/my_work_histories?passer_id=qgf6YHf1z2Fx80DR8o/Lvg&dt=2018-12
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    cipher_passer_id = rqst["passer_id"]
    print(cipher_passer_id)
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
    #
    # 가상 데이터 생성
    #
    workings = []
    for day in range(30):
        if random.randint(0,7) > 5: # 7일에 5일 꼴로 쉬는 날
            continue
        working = {}
        action = 0
        if random.randint(0,30) > 27: # 한달에 3번꼴로 지각
            action = 200
            working['dt_begin'] = str_dt + '-%02d'%day + ' 08:45:00'
        else :
            action = 100
            working['dt_begin'] = str_dt + '-%02d'%day + ' 08:25:00'
        if random.randint(0,30) > 29: # 한달에 1번꼴로 조퇴
            action += 20
            working['dt_end'] = str_dt + '-%02d'%day + ' 15:33:00'
        elif random.randint(0,30) > 20 : # 일에 한번꼴로 연장 근무
            action += 40
            working['dt_end'] = str_dt + '-%02d'%day + ' 18:35:00'
        else:
            action += 10
            working['dt_end'] = str_dt + '-%02d' % day + ' 17:35:00'
        outing = (random.randint(0,30) - 28) % 3 # 한달에 2번꼴로 외출
        outings = []
        if outing > 0:
            for i in range(outing):
                print(i)
                outings.append({'dt_begin':str_dt + str(day) + ' ' + str(i+13) + ':00:00',
                               'dt_end':str_dt + str(day) + ' ' + str(i+13) + ':30:00'})
        working['outing'] = outings
        working['action'] = action + outing
        print(working)
        workings.append(working)
    # print(workings)
    result = {'working': workings}
    # result = {
    #     'working': [
    #         {'action': 112, 'dt_begin': '2018-12-03 08:25:00', 'dt_end': '2018-12-03 17:33:00', 'outing': [
    #             {'dt_begin': '2018-12-03 12:30:00', 'dt_end': '2018-12-03 13:30:00'}]},
    #         {'action': 110, 'dt_begin': '2018-12-04 08:25:00', 'dt_end': '2018-12-04 17:33:00', 'outing': []},
    #         {'action': 110, 'dt_begin': '2018-12-05 08:25:00', 'dt_end': '2018-12-05 17:33:00', 'outing': []},
    #         {'action': 110, 'dt_begin': '2018-12-06 08:25:00', 'dt_end': '2018-12-06 17:33:00', 'outing': []},
    #         {'action': 110, 'dt_begin': '2018-12-07 08:25:00', 'dt_end': '2018-12-07 17:33:00', 'outing': []},
    #
    #         {'action': 210, 'dt_begin': '2018-12-10 08:55:00', 'dt_end': '2018-12-10 17:33:00', 'outing': []},
    #         {'action': 110, 'dt_begin': '2018-12-11 08:25:00', 'dt_end': '2018-12-11 17:33:00', 'outing': []},
    #         {'action': 120, 'dt_begin': '2018-12-12 08:25:00', 'dt_end': '2018-12-12 15:33:00', 'outing': []},
    #         {'action': 110, 'dt_begin': '2018-12-13 08:25:00', 'dt_end': '2018-12-13 17:33:00', 'outing': []},
    #         {'action': 110, 'dt_begin': '2018-12-14 08:25:00', 'dt_end': '2018-12-14 17:33:00', 'outing': []},
    #
    #         {'action': 110, 'dt_begin': '2018-12-17 08:25:00', 'dt_end': '2018-17-12 17:33:00', 'outing': []},
    #         {'action': 110, 'dt_begin': '2018-12-18 08:25:00', 'dt_end': '2018-18-14 17:33:00', 'outing': []},
    #         {'action': 112, 'dt_begin': '2018-12-19 08:25:00', 'dt_end': '2018-19-15 17:33:00', 'outing': [
    #             {'dt_begin': '2018-12-01 12:30:00', 'dt_end': '2018-12-01 13:30:00'}]},
    #         {'action': 110, 'dt_begin': '2018-12-20 08:25:00', 'dt_end': '2018-12-20 17:33:00', 'outing': []},
    #         {'action': 110, 'dt_begin': '2018-12-21 08:25:00', 'dt_end': '2018-12-21 17:33:00', 'outing': []},
    #         {'action': 110, 'dt_begin': '2018-12-31 08:25:00', 'dt_end': '2018-12-31 17:33:00', 'outing': []},
    #     ]
    # }
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def generation_pass_history(request):
    """
    출입 기록에서 일자별 출퇴근 기록을 만든다.
    퇴근버튼이 눌렸을 때나 최종 out 기록 후 1시간 후에 처리한다.
    1. 주어진 날짜의 in, dt_verify 를 찾는다. (출근버튼을 누른 시간)
    2. 주어진 날짜의
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


def get_dic_passer():
    employees = Employee.objects.filter().values('id', 'name')
    dic_employee = {}
    for employee in employees:
        dic_employee[employee['id']] = employee['name']
    del employees
    """
    dic_employee = {1:"박종기", 2:"곽명석"}
    """
    passers = Passer.objects.filter().values('id', 'pNo', 'employee_id')
    dic_passer = {}
    for passer in passers:
        employee_id = passer['employee_id']
        passer['name'] = '...' if employee_id < 0 else dic_employee[employee_id]
        dic_passer[passer['id']] = {'name': passer['name'], 'pNo': passer['pNo']}
    print(dic_passer, '\n', dic_passer[1]['name'])
    del passers
    del dic_employee
    """
    dic_passer = {1:{"name":"박종기", "pNo":"01025573555"}, 2:{"name:"곽명석", "pNo": "01054214410"}}
    """
    return dic_passer


@cross_origin_read_allow
def analysys(request):
    """
    출입, 출퇴근 결과 분석
    http://0.0.0.0:8000/employee/analysys
    POST
        {
            'id': 'thinking',
            'pw': 'a~~~8282'
        }
    response
        STATUS 200
            {
              "1": {
                "name": "박종기",
                "pNo": "01025573555",
                "pass": [
                  {
                    "is_in": "IN",
                    "dt_reg": "2019-02-06T08:25:00Z",
                    "dt_verify": null
                  },
                  {
                    "is_in": "IN",
                    "dt_reg": null,
                    "dt_verify": "2019-02-06T08:27:00Z"
                  },
                  {
                    "is_in": "OUT",
                    "dt_reg": "2019-02-07T17:33:00Z",
                    "dt_verify": null
                  },
                  {
                    "is_in": "OUT",
                    "dt_reg": null,
                    "dt_verify": "2019-02-07T17:35:00Z"
                  }
                ]
              },
              "2": {
                "name": "곽명석",
                "pNo": "01054214410",
                "pass": []
              },
              "message": "정상적으로 처리되었습니다."
            }
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    employees = Employee.objects.filter().values('id', 'name')
    dic_employee = {}
    for employee in employees:
        dic_employee[employee['id']] = employee['name']
    del employees
    """
    dic_employee = {1:"박종기", 2:"곽명석"}
    """
    passers = Passer.objects.filter().values('id', 'pNo', 'employee_id')
    dic_passer = {}
    for passer in passers:
        employee_id = passer['employee_id']
        passer['name'] = '...' if employee_id < 0 else dic_employee[employee_id]
        dic_passer[passer['id']] = {'name': passer['name'], 'pNo': passer['pNo']}
    print(dic_passer, '\n', dic_passer[1]['name'])
    del passers
    del dic_employee
    """
    dic_passer = {1:{"name":"박종기", "pNo":"01025573555"}, 2:{"name:"곽명석", "pNo": "01054214410"}}
    """
    passes = Pass.objects.filter().values('id', 'passer_id', 'is_in', 'dt_reg', 'dt_verify')
    for key in dic_passer:
        dic_passer[key]['pass'] = []
        for pass_ in passes:
            if key == pass_['passer_id']:
                new_pass = {'is_in': 'IN' if pass_['is_in'] == 1 else 'OUT',
                            'dt_reg': pass_['dt_reg'],
                            'dt_verify': pass_['dt_verify']}
                dic_passer[key]['pass'].append(new_pass)
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response(dic_passer)


@cross_origin_read_allow
def rebuild_pass_history(request):
    """
    출퇴근 기록 다시 만들기
    http://0.0.0.0:8000/employee/rebuild_pass_history
    POST
        {
            'id': 'thinking',
            'pw': 'a~~~8282'
        }
    response
        STATUS 200
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    passes = Pass.objects.filter()

    error_passes = []
    arr_pass_history = []
    long_interval_list = []
    for pass_ in passes:
        if pass_.dt_reg is None:
            print(pass_.id, pass_.passer_id, pass_.is_in, pass_.dt_verify.strftime("%Y-%m-%d %H:%M:%S"))
            passer_id = pass_.passer_id
            dt = pass_.dt_verify
            # 출퇴근버튼 눌린 시간 이전 출입시간 검색
            before_pass = Pass.objects\
                .filter(passer_id=passer_id,
                        dt_reg__lt = dt,
                        dt_reg__gt = dt - datetime.timedelta(minutes=30)) \
                    .values('id',
                        'passer_id',
                        'is_in',
                        'dt_reg',
                        'dt_verify')\
                .order_by('-dt_reg').first()
            if before_pass is None:
                # 출퇴근버튼 눌린 시간 이후 출입시간 검색
                before_pass = Pass.objects \
                    .filter(passer_id=passer_id,
                            dt_reg__gte=dt,
                            dt_reg__lt=dt + datetime.timedelta(minutes=30)) \
                    .values('id',
                            'passer_id',
                            'is_in',
                            'dt_reg',
                            'dt_verify') \
                    .order_by('dt_reg').first()
                if before_pass is None:
                    # error_passes.append({'id':pass_.id, 'passer_id':pass_.passer_id, 'dt_verify':pass_.dt_verify})
                    # continue
                    before_pass = {'id':-1,
                                   'passer_id':passer_id,
                                   'is_in':pass_.is_in,
                                   'dt_reg':None,
                                   'dt_verify':None}
            # print('  ', before_pass['id'], before_pass['is_in'], before_pass['dt_reg'].strftime("%Y-%m-%d %H:%M:%S"))

            # before_pass['dt_verify'] = pass_.dt_verify
            # before_pass['v_id'] = pass_.id
            # arr_pass_history.append(before_pass)
            # before_pass_dt_reg = datetime.datetime.strptime(before_pass['dt_reg'], "%Y-%m-%d %H:%M:%S")
            before_pass_dt_reg = before_pass['dt_reg']
            # if before_pass_dt_reg < pass_.dt_verify :
            #     time_interval = pass_.dt_verify - before_pass_dt_reg
            # else:
            #     time_interval = before_pass_dt_reg - pass_.dt_verify
            # if time_interval.seconds > (60 * 60 * 12):
            #     long_interval_list.append(before_pass)

    #
    #         print('   ', before_pass['id'], before_pass['passer_id'], before_pass['is_in'], before_pass['dt_reg'],
    #               before_pass['dt_verify'])
    #         # for pass__ in before_pass:
    #         #     print('   ', pass__['id'], pass__['passer_id'], pass__['is_in'], pass__['dt_reg'], pass__['dt_verify'])
            if pass_.is_in: # in 이면
                pass_history = Pass_History(
                    passer_id=passer_id,
                    action=100,
                    dt_in=before_pass['dt_reg'],
                    dt_in_verify=pass_.dt_verify,
                    minor=0
                )
                pass_history.save()
            else:
                last_pass = Pass_History.objects.filter(passer_id=passer_id).last()
                if last_pass is None:
                    pass_history = Pass_History(
                        passer_id=passer_id,
                        action=100,
                        dt_in=None,
                        dt_in_verify=None
                    )
                pass_history.action += 10
                pass_history.dt_out = before_pass['dt_reg']
                pass_history.dt_out_verify = pass_.dt_verify
                pass_history.minor = 0
                pass_history.save()
    print(len(arr_pass_history), len(error_passes))
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response({'pass_histories':arr_pass_history, 'long_interval_list':long_interval_list, 'error_passes': error_passes})


@cross_origin_read_allow
def beacon_status(request):
    """
    beacon 상태
    http://0.0.0.0:8000/employee/beacon_status
    POST
        {
            'id': 'thinking',
            'pw': 'a~~~8282'
        }
    response
        STATUS 200
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    dic_passer = get_dic_passer()
    pass_histories = Pass_History.objects.filter()
    arr_pass_histories = []
    for pass_history in pass_histories:
        ph = pass_history
        if ph.dt_in is not None:
            ph.dt_in += datetime.timedelta(hours=9)
        if ph.dt_in_verify is not None:
        	ph.dt_in_verify += datetime.timedelta(hours=9)
        if ph.dt_out is not None:
        	ph.dt_out += datetime.timedelta(hours=9)
        if ph.dt_out_verify is not None:
        	ph.dt_out_verify += datetime.timedelta(hours=9)
        view_ph = {'passer':dic_passer[ph.passer_id]['name'],
                   'action':ph.action,
                   'dt_in': '...' if ph.dt_in is None else ph.dt_in.strftime("%Y-%m-%d %H:%M:%S"),
                   'dt_in_verify': '...' if ph.dt_in_verify is None else ph.dt_in_verify.strftime("%Y-%m-%d %H:%M:%S"),
                   'dt_out': '...' if ph.dt_out is None else ph.dt_out.strftime("%Y-%m-%d %H:%M:%S"),
                   'dt_out_verify': '...' if ph.dt_out_verify is None else ph.dt_out_verify.strftime("%Y-%m-%d %H:%M:%S"),
                   'minor':0
                   }
        arr_pass_histories.append(view_ph)
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response({'pass_histories': arr_pass_histories})


    employees = Employee.objects.filter().values('id', 'name')
    dic_employee = {}
    for employee in employees:
        dic_employee[employee['id']] = employee['name']
    del employees
    """
    dic_employee = {1:"박종기", 2:"곽명석"}
    """
    passers = Passer.objects.filter()
    dic_passer = {}
    for passer in passers:
        if passer.employee_id == -1:
            print('\t\t', passer.employee_id)
        elif passer.employee_id in dic_employee:
            print(passer.employee_id, dic_employee[passer.employee_id])
        else:
            print(passer.employee_id)
            passer.employee_id = -1
            passer.save()
        dic_passer[passer.id] = passer.pNo
    print(dic_passer)
    passes = Pass.objects.filter()
    for pass_ in passes:
        if not (pass_.passer_id in dic_passer):
            print('   none passer', pass_.id, pass_.is_in)
            # pass_.delete()

    beacons = Beacon.objects.filter().values('id', 'uuid', 'major', 'minor', 'dt_last').order_by('major')
    arr_beacon = [beacon for beacon in beacons]

    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response({'beacons': arr_beacon})


