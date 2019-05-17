"""
Employee view

Copyright 2019. DaeDuckTech Corp. All rights reserved.
"""

import random
import inspect

from config.log import logSend, logError
from config.common import ReqLibJsonResponse
from config.common import func_begin_log, func_end_log
from config.common import status422, no_only_phone_no, phone_format, dt_null, is_parameter_ok

# secret import
from config.secret import AES_ENCRYPT_BASE64, AES_DECRYPT_BASE64
from config.status_collection import *
from config.decorator import cross_origin_read_allow

from .models import Beacon
from .models import Beacon_Record
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
def table_reset_and_clear_for_operation(request):
    """
    <<<운영 서버용>>> 근로자 서버 데이터 리셋 & 클리어
    GET
        { "key" : "사용 승인 key" }
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'key\' 가 없어요'}
            {'message':'ClientError: parameter \'key\' 가 정상적인 값이 아니예요.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    print(parameter_check['parameters'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    Beacon.objects.all().delete()
    Employee.objects.all().delete()
    Notification_Work.objects.all().delete()
    Work.objects.all().delete()
    Pass.objects.all().delete()
    Passer.objects.all().delete()
    Pass_History.objects.all().delete()

    from django.db import connection
    cursor = connection.cursor()
    cursor.execute("ALTER TABLE employee_beacon AUTO_INCREMENT = 1")
    cursor.execute("ALTER TABLE employee_employee AUTO_INCREMENT = 1")
    cursor.execute("ALTER TABLE employee_notification_work AUTO_INCREMENT = 1")
    cursor.execute("ALTER TABLE employee_work AUTO_INCREMENT = 1")
    cursor.execute("ALTER TABLE employee_pass AUTO_INCREMENT = 1")
    cursor.execute("ALTER TABLE employee_passer AUTO_INCREMENT = 1")
    cursor.execute("ALTER TABLE employee_pass_history AUTO_INCREMENT = 1")

    result = {'message': 'employee tables deleted == $ python manage.py sqlsequencereset employee'}
    logSend(result['message'])
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def check_version(request):
    """
    앱 버전을 확인한다. (마지막 190111 은 필히 6자리)
    http://0.0.0.0:8000/employee/check_version?v=A.1.0.0.190111
    GET
        v=A.1.0.0.190111
            # A.     : phone type - A or i
            # 1.0.0. : 앱의 버전 구분 업그레이드 필요성과 상관 없다.
            # 190111 : 서버와 호환되는 날짜 - 이 날짜에 의해 서버는 업그레이드 필요를 응답한다.

    response
        STATUS 200
        STATUS 551
        {
            'msg': '업그레이드가 필요합니다.'
            'url': 'http://...' # itune, google play update
        }
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'v\' 에 phone type 이 없어요'}

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
    phone_type = items[0]
    ver_dt = items[len(items) - 1]
    print(ver_dt)
    if len(ver_dt) < 6:
        func_end_log(func_name)
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
        url_android = "https://play.google.com/store/apps/details?id=com.ddtechi.aegis.employee"
        url_iOS = "https://..."
        url_install = ""
        if phone_type == 'A':
            url_install = url_android
        elif phone_type == 'i':
            url_install = url_iOS
        else:
            return status422(func_name, {'message': 'ClientError: parameter \'v\' 에 phone type 이 없어요'})

        func_end_log(func_name)
        return REG_551_AN_UPGRADE_IS_REQUIRED.to_json_response({'url': url_install  # itune, google play update
                  })
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    # print(rqst["customer_work_id"])
    # print(rqst["work_place_name"])
    # print(rqst["work_name_type"])
    # print(rqst["dt_begin"])
    # print(rqst["dt_end"])
    logSend('  답변 시한 {}'.format(rqst["dt_answer_deadline"]))
    # print(rqst["staff_name"])
    # print(rqst["staff_phone"])

    # pass_type = rqst['pass_type']
    if request.method == 'POST':
        phone_numbers = rqst['phones']
    else:
        phone_numbers = rqst.getlist('phones')
    logSend(phone_numbers, rqst['phones'])

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
          '앱 설치\n'\
          'https://api.ezchek.co.kr/app'

    rData = {
        'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
        'user_id': 'yuadocjon22',
        'sender': settings.SMS_SENDER_PN,
        # 'receiver': phone_numbers[i],
        'msg_type': 'SMS',
        'msg': msg,
    }

    phones_state = {}
    for i in range(len(phone_numbers)):
        logSend('DDD ', phone_numbers[i])
        notification_list = Notification_Work.objects.filter(customer_work_id=rqst["customer_work_id"], employee_pNo=phone_numbers[i])
        logSend('  {}'.format(notification_list))
        if len(notification_list) > 0:
            logSend('--- sms 알려서 안보냄 ', phone_numbers[i])
            # 이전에 SMS 를 보낸적있는 전화번호는 전화번호 출입자가 저장하고 있는 근로자 id 만 확인해서 보낸다.
            find_passers = Passer.objects.filter(pNo=phone_numbers[i])
            phones_state[phone_numbers[i]] = -1 if len(find_passers) == 0 else find_passers[0].employee_id  # 등록된 전화번호 없음 (즉, 앱 설치되지 않음)
        else:
            if not settings.IS_TEST:
                logSend('--- sms 보냄', phone_numbers[i])
                # SMS 를 보낸다.
                rData['receiver'] = phone_numbers[i]
                rSMS = requests.post('https://apis.aligo.in/send/', data=rData)
                logSend('SMS result', rSMS.json())
                logSend('--- ', rSMS.json())
            # if int(rSMS.json()['result_code']) < 0:
            if len(phone_numbers[i]) < 11:
                # 전화번호 에러로 문자를 보낼 수 없음.
                phones_state[phone_numbers[i]] = -101
            else:
                # SMS 를 보냈으면 전화번호의 출입자가 앱을 설치하고 알림을 볼 수 있게 저장한다.
                find_passers = Passer.objects.filter(pNo=phone_numbers[i])
                phones_state[phone_numbers[i]] = -1 if len(find_passers) == 0 else find_passers[0].employee_id  # 등록된 전화번호 없음 (즉, 앱 설치되지 않음)
                new_notification = Notification_Work(
                    work_id=work.id,
                    customer_work_id=rqst["customer_work_id"],
                    employee_id=phones_state[phone_numbers[i]],
                    employee_pNo=phone_numbers[i],
                    dt_answer_deadline=rqst["dt_answer_deadline"],
                )
                new_notification.save()
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result': phones_state})


@cross_origin_read_allow
def update_work_for_customer(request):
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
        }
    response
        STATUS 200
            {"message": "정상적으로 처리되었습니다."}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
        # work.customer_work_id = rqst['customer_work_id']
        work.work_place_name = rqst['work_place_name']
        work.work_name_type = rqst['work_name_type']
        work.begin = rqst['begin']
        work.end = rqst['end']
        work.staff_name = rqst['staff_name']
        work.staff_pNo = rqst['staff_pNo']
        work.save()

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()


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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    passers = Passer.objects.filter(id=AES_DECRYPT_BASE64(rqst['passer_id']))
    if len(passers) == 0:
        func_end_log(func_name)
        return REG_403_FORBIDDEN.to_json_response({'message':'알 수 없는 사용자입니다.'})
    passer = passers[0]
    dt_today = datetime.datetime.now()
    logSend(passer.pNo)
    # notification_list = Notification_Work.objects.filter(employee_pNo=passer.pNo, dt_answer_deadline__gt=dt_today)
    notification_list = Notification_Work.objects.filter(employee_pNo=passer.pNo)
    logSend(notification_list)
    arr_notification = []
    for notification in notification_list:
        # dt_answer_deadline 이 지났으면 처리하지 않고 notification_list 도 삭제
        # 2019/05/17 임시 기능 정지 - 업무 시작 후 업무 참여요청 보낼 필요 발생
        # if notification.dt_answer_deadline < datetime.datetime.now():
        #     notification.delete()
        #     continue
        work = Work.objects.get(id=notification.work_id)
        view_notification = {
            'id': AES_ENCRYPT_BASE64(str(notification.id)),
            'work_place_name': work.work_place_name,
            'work_name_type': work.work_name_type,
            'begin': work.begin,
            'end': work.end,
            'staff_name': work.staff_name,
            'staff_pNo': work.staff_pNo,
            'dt_answer_deadline': notification.dt_answer_deadline.strftime("%Y-%m-%d %H:%M:%S")
        }
        arr_notification.append(view_notification)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'notifications': arr_notification})


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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter = is_parameter_ok(rqst, ['passer_id_!', 'notification_id_!', 'is_accept'])
    if not parameter['is_ok']:
        return status422(func_name, parameter['message'])

    logSend(parameter['parameters'])
    rqst = parameter['parameters']

    # func_end_log(func_name)
    # return REG_403_FORBIDDEN.to_json_response({'message':'알 수 없는 사용자입니다.'})

    # passers = Passer.objects.filter(id=AES_DECRYPT_BASE64(rqst['passer_id']))
    passers = Passer.objects.filter(id=rqst['passer_id'])
    if len(passers) != 1:
        func_end_log(func_name)
        return REG_403_FORBIDDEN.to_json_response({'message':'알 수 없는 사용자입니다.'})
    passer = passers[0]

    notifications = Notification_Work.objects.filter(id=rqst['notification_id'])
    if len(notifications) != 1:
        func_end_log(func_name)
        return REG_403_FORBIDDEN.to_json_response({'message':'알 수 없는 알림입니다.'})
    notification = notifications[0]

    is_accept = 1 if int(rqst['is_accept']) == 1 else 0
    logSend('is_accept = ', rqst['is_accept'], ' ', is_accept)

    employees = Employee.objects.filter(id=passer.employee_id)
    if len(employees) != 1:
        logError(func_name, ' passer {} 의 employee {} 가 {} 개 이다.(정상은 1개)'.format(passer.id, passer.employee_id, len(employees)))
    employee = employees[0]
    #
    # 근로자 정보에 업무를 등록 - 수락했을 경우만
    #
    if is_accept == 1:
        work = Work.objects.get(id=notification.work_id)
        if passer.employee_id > 0:
            if employee.work_id != -1:
                # 2개가 모두 있을 때 처리는 version 2.0 에서
                employee.work_id_2 = notification.work_id
                employee.begin_2 = work.begin
                employee.end_2 = work.end
            else:
                employee.work_id = notification.work_id
                employee.begin_1 = work.begin
                employee.end_1 = work.end
        else:
            logError(func_name, ' ERROR: 출입자가 근로자가 아닌 경우 - 발생하면 안됨 passer_id:', passer.id)
            employee = Employee(
                work_id=notification.work_id,
                begin_1=work.begin,
                end_1=work.end,
            )
        employee.save()
        logSend(employee.name)
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
    logSend(request_data)
    response_customer = requests.post(settings.CUSTOMER_URL + 'employee_work_accept_for_employee', json=request_data)
    logSend(response_customer.json())
    if response_customer.status_code != 200:
        func_end_log(func_name)
        return ReqLibJsonResponse(response_customer)

    notification.delete()

    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def pass_reg(request):
    """
    출입등록 : 앱에서 비콘을 3개 인식했을 때 서버에 출근(퇴근)으로 인식하고 보내는 기능
    http://0.0.0.0:8000/employee/pass_reg?passer_id=qgf6YHf1z2Fx80DR8o/Lvg&dt=2019-05-7 17:45:00&is_in=0&major=11001&beacons=
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
        STATUS 200 - 아래 내용은 처리가 무시되기 때문에 에러처리는 하지 않는다.
            {'message': 'out 인데 어제 오늘 in 기록이 없다.'}
            {'message': 'in 으로 부터 12 시간이 지나서 out 을 무시한다.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'passer_id\' 가 없어요'}
            {'message':'ClientError: parameter \'dt\' 가 없어요'}
            {'message':'ClientError: parameter \'is_in\' 가 없어요'}
            {'message':'ClientError: parameter \'major\' 가 없어요'}
            {'message':'ClientError: parameter \'beacons\' 가 없어요'}
            {'message':'ClientError: parameter \'passer_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Passer 에 passer_id=%s 이(가) 없거나 중복됨' % passer_id }
            {'message':'ServerError: Employee 에 employee_id=%s 이(가) 없거나 중복됨' % employee_id }
            {'message': 'ClientError: parameter \'dt\' 양식을 확인해주세요.'}
    log Error
        logError(func_name, ' 비콘 등록 기능 << Beacon 설치할 때 등록되어야 하는데 왜?')
        logError(func_name, ' passer_id={} out 인데 어제, 오늘 기록이 없다. dt_beacon={}'.format(passer_id, dt_beacon))
        logError(func_name, ' passer_id={} in 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
        logError(func_name, ' passer_id={} in 으로 부터 12 시간이 지나서 out 을 무시한다. dt_in={}, dt_beacon={}'.format(passer_id, dt_in, dt_beacon))
        logError(func_name, ' passer 의 employee_id={} 에 해당하는 근로자가 없음.'.format(passer.employee_id))
        logError(func_name, ' passer 의 employee_id={} 에 해당하는 근로자가 한명 이상임.'.format(passer.employee_id))
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['passer_id_!', 'dt', 'is_in', 'major', 'beacons'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    passer_id = parameter_check['parameters']['passer_id']
    dt = parameter_check['parameters']['dt']
    is_in = int(parameter_check['parameters']['is_in'])
    major = parameter_check['parameters']['major']
    if request.method == 'POST':
        beacons = rqst['beacons']
    else:
        # today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        beacons = [
            {'minor': 11001, 'dt_begin': '%s 08:25:30'%today, 'rssi': -70},
            {'minor': 11002, 'dt_begin': '%s 08:25:31'%today, 'rssi': -60},
            {'minor': 11003, 'dt_begin': '%s 08:25:32'%today, 'rssi': -50}
        ]
    logSend(beacons)
    passers = Passer.objects.filter(id=passer_id)
    if len(passers) != 1:
        return status422(func_name, {'message':'ServerError: Passer 에 passer_id=%s 이(가) 없거나 중복됨' % passer_id })
    passer = passers[0]

    for i in range(len(beacons)):
        # 비콘 이상 유무 확인을 위해 비콘 날짜, 인식한 근로자 앱 저장
        beacon_list = Beacon.objects.filter(major=major, minor=beacons[i]['minor'])
        if len(beacon_list) > 0:
            beacon = beacon_list[0]
            beacon.dt_last = dt
            beacon.last_passer_id = passer_id
            beacon.save()
        else:
            logError(func_name, ' 비콘 등록 기능 << Beacon 설치할 때 등록되어야 하는데 왜?')
            beacon = Beacon(
                uuid='12345678-0000-0000-0000-123456789012',
                # 1234567890123456789012345678901234567890
                major=major,
                minor=beacons[i]['minor'],
                dt_last=dt,
                last_passer_id=passer_id,
            )
            beacon.save()
        # 근로자 앱에서 인식된 비콘 값을 모두 저장 - 아직 용도 없음.
        new_beacon_record = Beacon_Record(
            major=major,
            minor=beacons[i]['minor'],
            dt_begin=beacons[i]['dt_begin'],
            rssi=beacons[i]['rssi']
        )
        new_beacon_record.save()

    # 통과 기록 저장
    new_pass = Pass(
        passer_id=passer_id,
        is_in=is_in,
        dt_reg=dt
    )
    new_pass.save()
    #
    # Pass_History update
    #
    dt_beacon = datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
    year_month_day = dt_beacon.strftime("%Y-%m-%d")
    pass_histories = Pass_History.objects.filter(passer_id=passer_id, year_month_day=year_month_day)
    if not is_in:
        # out 일 경우
        if len(pass_histories) == 0:
            # out 인데 오늘 날짜 pass_history 가 없다? >> 그럼 어제 저녁에 근무 들어갔겠네!
            yesterday = dt_beacon - datetime.timedelta(days=1)
            yesterday_year_month_day = yesterday.strftime("%Y-%m-%d")
            pass_histories = Pass_History.objects.filter(passer_id=passer_id, year_month_day=yesterday_year_month_day)
            if len(pass_histories) == 0:
                # out 인데 어제, 오늘 출입 기록이 없다? >> 에러 로그 남기고 만다.
                logError(func_name, ' passer_id={} out 인데 어제, 오늘 기록이 없다. dt_beacon={}'.format(passer_id, dt_beacon))
                func_end_log(func_name)
                return REG_200_SUCCESS.to_json_response({'message': 'out 인데 어제 오늘 in 기록이 없다.'})
            else:
                pass_history = pass_histories[0]
        else:
            pass_history = pass_histories[0]

        dt_in = pass_history.dt_in if pass_history.dt_in_verify is None else pass_history.dt_in_verify
        if dt_in is None:
            # in beacon, in touch 가 없다? >> 에러처리는 하지 않고 기록만 한다.
            logError(func_name, ' passer_id={} in 기록이 없다. dt_in={}'.format(passer_id, dt_in))
        if (dt_in + datetime.timedelta(hours=12)) < dt_beacon:
            # 출근시간 이후 12 시간이 지났으면 무시한다.
            logError(func_name, ' passer_id={} in 으로 부터 12 시간이 지나서 out 을 무시한다. dt_in={}, dt_beacon={}'.format(passer_id, dt_in, dt_beacon))
            func_end_log(func_name)
            return REG_200_SUCCESS.to_json_response({'message': 'in 으로 부터 12 시간이 지나서 beacon out 을 무시한다.'})

        pass_history.dt_out = dt_beacon
    else:
        # in 일 경우
        if len(pass_histories) == 0:
            # 오늘 날짜 pass_history 가 없어서 새로 만든다.
            pass_history = Pass_History(
                passer_id=passer_id,
                year_month_day=year_month_day,
                action=0,
            )
        else:
            pass_history = pass_histories[0]

        if pass_history.dt_in is None:
            pass_history.dt_in = dt_beacon

    # work_id 처리
    if (pass_history.work_id == -1) and (passer.employee_id > 0):
        employees = Employee.objects.filter(id=passer.employee_id)
        if len(employees) == 0:
            logError(func_name, ' passer 의 employee_id={} 에 해당하는 근로자가 없음.'.format(passer.employee_id))
        else:
            if len(employees) > 1:
                logError(func_name, ' passer 의 employee_id={} 에 해당하는 근로자가 한명 이상임.'.format(passer.employee_id))
            employee = employees[0]
            pass_history.work_id = employee.work_id

    pass_history.save()

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()


def is_in_verify(beacons):
    # 서버에서 beacon 값으로 in out 을 판정 - 2019.5.7. 현재 사용되지 않음.
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
    http://0.0.0.0:8000/employee/pass_verify?passer_id=qgf6YHf1z2Fx80DR8o/Lvg&dt=2019-05-06 17:30:00&is_in=0
    POST : json
        {
            'passer_id' : '암호화된 출입자 id',
            'dt' : '2018-12-28 12:53:36',
            'is_in' : 1, # 0: out, 1 : in
        }
    response
        STATUS 200 - 아래 내용은 처리가 무시되기 때문에 에러처리는 하지 않는다.
            {'message': 'out 인데 어제 오늘 in 기록이 없다.'}
            {'message': 'in 으로 부터 12 시간이 지나서 out 을 무시한다.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'passer_id\' 가 없어요'}
            {'message':'ClientError: parameter \'dt\' 가 없어요'}
            {'message':'ClientError: parameter \'is_in\' 가 없어요'}
            {'message':'ClientError: parameter \'passer_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Passer 에 passer_id=%s 이(가) 없거나 중복됨' % passer_id }
            {'message':'ServerError: Employee 에 employee_id=%s 이(가) 없거나 중복됨' % employee_id }
            {'message':'ClientError: parameter \'dt\' 양식을 확인해주세요.'}
    log Error
        logError(func_name, ' passer_id={} out touch 인데 어제, 오늘 기록이 없다. dt_touch={}'.format(passer_id, dt_touch)
        logError(func_name, ' passer_id={} in 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
        logError(func_name, ' passer_id={} in 기록후 12시간 이상 지나서 out touch가 들어왔다. dt_in={}, dt_touch={}'.format(passer_id, dt_in, dt_touch))
        logError(func_name, ' passer 의 employee_id={} 에 해당하는 근로자가 없음.'.format(passer.employee_id))
        logError(func_name, ' passer 의 employee_id={} 에 해당하는 근로자가 한명 이상임.'.format(passer.employee_id))
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['passer_id_!', 'dt', 'is_in'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    passer_id = parameter_check['parameters']['passer_id']
    dt = parameter_check['parameters']['dt']
    is_in = int(parameter_check['parameters']['is_in'])

    passers = Passer.objects.filter(id=passer_id)
    if len(passers) != 1:
        return status422(func_name, {'message': 'ServerError: Passer 에 passer_id={} 이(가) 없거나 중복됨'.format(passer_id) })
    passer = passers[0]

    # 통과 기록 저장
    new_pass = Pass(
        passer_id=passer_id,
        is_in=is_in,
        dt_verify=dt,
    )
    new_pass.save()

    #
    # Pass_History update
    #
    dt_touch = datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
    year_month_day = dt_touch.strftime("%Y-%m-%d")
    pass_histories = Pass_History.objects.filter(passer_id=passer_id, year_month_day=year_month_day)
    if not is_in:
        # out touch 일 경우
        if len(pass_histories) == 0:
            # out 인데 오늘 날짜 pass_history 가 없다? >> 그럼 어제 저녁에 근무 들어갔겠네!
            yesterday = dt_touch - datetime.timedelta(days=1)
            yesterday_year_month_day = yesterday.strftime("%Y-%m-%d")
            yesterday_pass_histories = Pass_History.objects.filter(passer_id=passer_id, year_month_day=yesterday_year_month_day)
            if len(yesterday_pass_histories) == 0:
                logError(func_name, ' passer_id={} out touch 인데 어제, 오늘 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
                # out 인데 어제, 오늘 in 기록이 없다?
                #   그럼 터치 시간이 9시 이전이면 어제 in 이 누락된거라고 판단하고 어제 날짜에 퇴근처리가 맞겠다.
                #   (9시에 퇴근시간이 찍히면 반나절 4시간 근무(휴식 포함 4:30)라고 하면 4:30 출근인데 그럼 오늘 출근이잖아!)
                #   (로그 찍히니까 계속 감시하는 수 밖에...)
                if dt_touch.hour < 9:
                    logSend('  어제 오늘 출퇴근 기록이 없고 9시 이전이라 어제 날짜로 처리한다.')
                    # 퇴근 누른 시간이 오전 9시 이전이면 어제 pass_history 가 없어서 새로 만든다.
                    pass_history = Pass_History(
                        passer_id=passer_id,
                        year_month_day=yesterday_year_month_day,
                        action=0,
                    )
                else:
                    logSend('  어제 오늘 출퇴근 기록이 없고 9시 이후라 오늘 날짜로 처리한다.')
                    # 오늘 pass_history 가 없어서 새로 만든다.
                    pass_history = Pass_History(
                        passer_id=passer_id,
                        year_month_day=year_month_day,
                        action=0,
                    )
            elif dt_touch.hour < 9:
                # 오늘 출퇴근 내역은 없어도 어제건 있다.
                #   어제 출근처리가 안된것으로 판단하고 어제 출근해서 퇴근한걸로 처리하기 위해 어제 출퇴근에 넣는다.
                logSend('  퇴근시간이 9시 이전이고 어제 출퇴근 기록이 있으면 어제 기록에 넣는다.')
                pass_history = yesterday_pass_histories[0]
            else:
                logSend('  퇴근시간이 9시 이후이면 오늘 출근 처리가 안되고 퇴근하는 것으로 본다.')
                # 오늘 pass_history 가 없어서 새로 만든다.
                pass_history = Pass_History(
                    passer_id=passer_id,
                    year_month_day=year_month_day,
                    action=0,
                )
        else:
            logSend('  오늘 출퇴근 기록이 있어서 오늘에 넣는다.')
            # 오늘 출퇴근이 있으면 오늘 처리한다.
            pass_history = pass_histories[0]

        pass_history.dt_out_verify = dt_touch
        dt_in = pass_history.dt_in if pass_history.dt_in_verify is None else pass_history.dt_in_verify
        if dt_in is None:
            # in beacon, in touch 가 없다? >> 에러처리는 하지 않고 기록만 한다.
            logError(func_name, ' passer_id={} in 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
        elif (dt_in + datetime.timedelta(hours=12)) < dt_touch:
            # 출근시간 이후 12 시간이 지나서 out touch가 들어왔다. >> 에러처리는 하지 않고 기록만 한다.
            logError(func_name, ' passer_id={} in 기록후 12시간 이상 지나서 out touch가 들어왔다. dt_in={}, dt_touch={}'.format(passer_id, dt_in, dt_touch))
    else:
        # in touch 일 경우
        if len(pass_histories) == 0:
            # 오늘 날짜 pass_history 가 없어서 새로 만든다.
            pass_history = Pass_History(
                passer_id=passer_id,
                year_month_day=year_month_day,
                action=0,
            )
        else:
            pass_history = pass_histories[0]

        if pass_history.dt_in_verify is None:
            pass_history.dt_in_verify = dt_touch

    #
    # 정상, 지각, 조퇴 처리 -  pass_record_of_employees_in_day_for_customer
    #
    update_pass_history(pass_history)

    pass_history.save()

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def pass_sms(request):
    """
    문자로 출근/퇴근, 업무 수락/거절: 스마트폰이 아닌 사용자가 문자로 출근(퇴근), 업무 수락/거절을 서버로 전송
      - 수락/거절은 복수의 수락/거절에 모두 답하는 문제를 안고 있다.
      - 수락/거절하게 되먼 수락/거절한 업무가 여러개라도 모두 sms 로 보낸다. (업무, 담당자, 담당자 전화번호, 기간)
      - 수락/거절은 이름이 안들어 오면 에러처리한다.
    http://0.0.0.0:8000/employee/pass_sms?phone_no=010-3333-9999&dt=2019-01-21 08:25:35&sms=출근
    POST : json
        {
            'phone_no': '문자 보낸 사람 전화번호',
            'dt': '2018-12-28 12:53:36',
            'sms': '출근했어요' # '퇴근했어요', '지금 외출 나갑니다', '먼저 퇴근합니다', '외출했다가 왔습니다', '오늘 조금 지각했습니다'
                new message: '수락 이름', '거절 이름'
        }
    response
        STATUS 200
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    phone_no = no_only_phone_no(rqst['phone_no'])  # 전화번호가 없을 가능성이 없다.
    dt = rqst['dt']
    sms = rqst['sms']
    logSend(phone_no, dt, sms)

    if '수락' or '거절' in sms:
        # notification_work 에서 전화번호로 passer_id(notification_work 의 employee_id) 를 얻는다.
        notification_work_list = Notification_Work.objects.filter(employee_pNo=phone_no)
        # 하~~~ 피처폰인데 업무 요청 여러개가 들어오면 처리할 방법이 없네... > 에이 모르겠다 몽땅 보내!!!
        # 수락한 내용을 SMS 로 보내줘야할까? (문자를 무한사용? 답답하네...)
        is_accept = True if '수락' in sms else False
        if is_accept:
            name = sms.replace('수락', '').replace(' ', '')
        else:
            name = sms.replace('거절', '').replace(' ', '')
        logSend('  name = {}'.format(name))
        if len(name) < 2:
            # 이름이 2자가 안되면 SMS 로 이름이 안들어왔다고 보내야 하나? (휴~~~)
            logError(func_name, ' 이름이 너무 짧다. pNo = {}, sms = \"{}\"'.format(phone_no, sms))
            sms_data = {
                'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
                'user_id': 'yuadocjon22',
                'sender': settings.SMS_SENDER_PN,
                'receiver': phone_no,
                'msg_type': 'SMS',
                'msg': '이지체크\n'
                       '수락/거절 문자를 보내실 때는 꼭 이름을 같이 넣어주세요.\n'
                       '예 \"수락 홍길동\"',
            }
            rSMS = requests.post('https://apis.aligo.in/send/', data=sms_data)
            logSend('SMS result', rSMS.json())
            return status422(func_name, {'message': '이름이 너무 짧다. pNo = {}, sms = \"{}\"'.format(phone_no, sms)})
        sms_data = {
            'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
            'user_id': 'yuadocjon22',
            'sender': settings.SMS_SENDER_PN,
            'receiver': phone_no,
            'msg_type': 'SMS',
        }

        for notification_work in notification_work_list:
            # dt_answer_deadline 이 지났으면 처리하지 않고 notification_list 도 삭제
            if notification_work.dt_answer_deadline < datetime.datetime.now():
                notification_work.delete()
                continue

            # 근로자를 강제로 새로 등록한다. (으~~~ 괜히 SMS 기능 넣었나?)
            passer_list = Passer.objects.filter(pNo=phone_no)
            if len(passer_list) == 0:
                # 이 전화번호를 사용하는 근로자가 없기 때문에 새로 만든다.
                employee = Employee(
                    name=name
                )
                employee.save()
                passer = Passer(
                    pNo=phone_no,
                    pType=0,  # 피쳐폰 10:아이폰, 20:안드로이드폰
                    employee_id=employee.id,
                )
                passer.save()
            else:
                # 이경우 골치 아픈데... > 급하니까 첫번째 만 대상으로 한다.
                passer = passer_list[0]

            accept_infor = {
                'passer_id': AES_ENCRYPT_BASE64(str(passer.id)),
                'notification_id': AES_ENCRYPT_BASE64(str(notification_work.id)),
                'is_accept': '1' if is_accept else '0',
            }
            r = requests.post(settings.EMPLOYEE_URL + 'notification_accept', json=accept_infor)
            logSend({'url': r.url, 'POST': accept_infor, 'STATUS': r.status_code, 'R': r.json()})

            if is_accept:
                work = Work.objects.get(id=notification_work.work_id)
                sms_data['msg'] = '수락됐어요\n{}-{}\n{} ~ {}\n{} {}'.format(work.work_place_name,
                                                                          work.work_name_type,
                                                                          work.begin,
                                                                          work.end,
                                                                          work.staff_name,
                                                                          phone_format(work.staff_pNo))
                rSMS = requests.post('https://apis.aligo.in/send/', data=sms_data)
                logSend('SMS result', rSMS.json())

        func_end_log(func_name)
        return REG_200_SUCCESS.to_json_response()
    elif '출근' in sms:
        is_in = True
    elif '퇴근' in sms:
        is_in = False

    passers = Passer.objects.filter(pNo=phone_no)
    if len(passers) == 0:
        logError({'ERROR': '출입자의 전화번호가 없습니다.' + phone_no})
        func_end_log(func_name)
        return REG_541_NOT_REGISTERED.to_json_response()
    passer = passers[0]
    passer_id = passer.id
    dt_sms = datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
    logSend(' {}  {}  {}  {}'.format(phone_no, passer.id, dt, is_in))
    new_pass = Pass(
        passer_id=passer.id,
        is_in=is_in,
        dt_verify=dt_sms
    )
    new_pass.save()

    #
    # Pass_History update
    #
    dt_touch = datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
    year_month_day = dt_touch.strftime("%Y-%m-%d")
    pass_histories = Pass_History.objects.filter(passer_id=passer_id, year_month_day=year_month_day)
    if not is_in:
        # out touch 일 경우
        if len(pass_histories) == 0:
            # out 인데 오늘 날짜 pass_history 가 없다? >> 그럼 어제 저녁에 근무 들어갔겠네!
            yesterday = dt_touch - datetime.timedelta(days=1)
            yesterday_year_month_day = yesterday.strftime("%Y-%m-%d")
            pass_histories = Pass_History.objects.filter(passer_id=passer_id, year_month_day=yesterday_year_month_day)
            if len(pass_histories) == 0:
                logError(func_name, ' passer_id={} out touch 인데 어제, 오늘 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
                # out 인데 어제, 오늘 in 기록이 없다?
                #   그럼 터치 시간이 9시 이전이면 어제 in 이 누락된거라고 판단하고 어제 날짜에 퇴근처리가 맞겠다.
                #   (9시에 퇴근시간이 찍히면 반나절 4시간 근무(휴식 포함 4:30)라고 하면 4:30 출근인데 그럼 오늘 출근이잖아!)
                #   (로그 찍히니까 계속 감시하는 수 밖에...)
                if dt_touch.hour < 9:
                    # 어제 pass_history 가 없어서 새로 만든다.
                    pass_history = Pass_History(
                        passer_id=passer_id,
                        year_month_day=yesterday_year_month_day,
                        action=0,
                    )
                else:
                    # 오늘 pass_history 가 없어서 새로 만든다.
                    pass_history = Pass_History(
                        passer_id=passer_id,
                        year_month_day=year_month_day,
                        action=0,
                    )
            else:
                pass_history = pass_histories[0]
        else:
            pass_history = pass_histories[0]

        pass_history.dt_out_verify = dt_touch
        dt_in = pass_history.dt_in if pass_history.dt_in_verify is None else pass_history.dt_in_verify
        if dt_in is None:
            # in beacon, in touch 가 없다? >> 에러처리는 하지 않고 기록만 한다.
            logError(func_name, ' passer_id={} in 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
        if (dt_in + datetime.timedelta(hours=12)) < dt_touch:
            # 출근시간 이후 12 시간이 지났서 out touch가 들어왔다. >> 에러처리는 하지 않고 기록만 한다.
            logError(func_name, ' passer_id={} in 기록후 12시간 이상 지나서 out touch가 들어왔다. dt_in={}, dt_touch={}'.format(passer_id, dt_in, dt_touch))
    else:
        # in touch 일 경우
        if len(pass_histories) == 0:
            # 오늘 날짜 pass_history 가 없어서 새로 만든다.
            pass_history = Pass_History(
                passer_id=passer_id,
                year_month_day=year_month_day,
                action=0,
            )
        else:
            pass_history = pass_histories[0]

        if pass_history.dt_in_verify is None:
            pass_history.dt_in_verify = dt_touch

    #
    # 정상, 지각, 조퇴 처리 -  pass_record_of_employees_in_day_for_customer
    #
    update_pass_history(pass_history)

    pass_history.save()

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()


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
        STATUS 422 # 개발자 수정사항
            {'message': 'ClientError: parameter \'passer_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'dt\' 가 없어요'}
            {'message': 'ClientError: parameter \'is_in\' 가 없어요'}
            {'message': 'ClientError: parameter \'major\' 가 없어요'}
            {'message': 'ClientError: parameter \'beacons\' 가 없어요'}
            {'message': 'ClientError: parameter \'passer_id\' 가 정상적인 값이 아니예요.'}

            {'message': 'ServerError: 근로자가 등록되어 있지 않거나 중복되었다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['passer_id_!', 'dt', 'is_in', 'major', 'beacons'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    passer_id = parameter_check['parameters']['passer_id']
    dt = parameter_check['parameters']['dt']
    is_in = parameter_check['parameters']['is_in']
    major = parameter_check['parameters']['major']
    beacons = parameter_check['parameters']['beacons']

    passers = Passer.objects.filter(id=passer_id)
    if len(passers) != 1:
        logError(func_name, ' ServerError: Passer 에 passer_id=%s 이(가) 없거나 중복됨' % passer_id)
        return status422(func_name, {'message': 'ServerError: 근로자가 등록되어 있지 않거나 중복되었다.'})

    if request.method == 'GET':
        beacons = [
            {'minor': 11001, 'dt_begin': '2019-02-21 08:25:30', 'rssi': -70},
            {'minor': 11002, 'dt_begin': '2019-02-21 08:25:31', 'rssi': -70},
            {'minor': 11003, 'dt_begin': '2019-02-21 08:25:32', 'rssi': -70}
            # {'minor': 11003, 'dt_begin': '2019-01-21 08:25:32', 'rssi': -70},
            # {'minor': 11002, 'dt_begin': '2019-01-21 08:25:31', 'rssi': -70},
            # {'minor': 11001, 'dt_begin': '2019-01-21 08:25:30', 'rssi': -70},
        ]
    logSend(beacons)

    # ?? 비콘 등록은 운영에서 관리하도록 바뀌어야하나?
    minors = [beacon['minor'] for beacon in beacons]
    logSend(minors)
    beacon_list = Beacon.objects.filter(major=major, minor__in=minors)
    for beacon in beacon_list:
        if beacon.minor in minors:
            beacon.dt_last = dt
            beacon.save()
            minors.remove(beacon.minor)
    logSend(minors)
    if len(minors) > 0:
        for beacon in beacons:
            if beacon['minor'] in minors:
                new_beacon = Beacon(
                    uuid='12345678-0000-0000-0000-123456789012',
                    # 1234567890123456789012345678901234567890
                    major=major,
                    minor=beacon['minor'],
                    dt_last=dt
                )
                new_beacon.save()
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()


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
        STATUS 552
            {'message': '인증번호는 3분에 한번씩만 발급합니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    phone_no = rqst['phone_no']

    phone_no = phone_no.replace('+82', '0')
    phone_no = phone_no.replace('-', '')
    phone_no = phone_no.replace(' ', '')
    # print(phone_no)
    if 'passer_id' in rqst and len(rqst['passer_id']) > 6:
        # 등록 사용자가 앱에서 전화번호를 바꾸려고 인증할 때
        # 출입자 아이디(passer_id) 의 전화번호 외에 전화번호가 있으면 전화번호(542)처리
        passer_id = AES_DECRYPT_BASE64(rqst['passer_id'])
        passers = Passer.objects.filter(pNo=phone_no).exclude(id=passer_id)
        if len(passers) > 0:
            func_end_log(func_name)
            return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response({'message':'전화번호가 이미 등록되어 있어 사용할 수 없습니다.\n고객센터로 문의하십시요.'})
        passer = Passer.objects.get(id=passer_id)
        passer.pNo = phone_no
    else:
        # 신규 등록일 때 전화번호를 사용하고 있으면 에러처리
        passers = Passer.objects.filter(pNo=phone_no)
        if len(passers) == 0:
            passer = Passer(
                pNo=phone_no
            )
        else:
            passer = passers[0]

    if (passer.dt_cn != None) and (passer.dt_cn > datetime.datetime.now()):
        # 3분 이내에 인증번호 재요청하면
        print(passer.dt_cn, datetime.datetime.now())
        func_end_log(func_name)
        return REG_552_NOT_ENOUGH_TIME.to_json_response({'message': '인증번호는 3분에 한번씩만 발급합니다.'})

    certificateNo = random.randint(100000, 999999)
    if settings.IS_TEST:
        certificateNo = 201903
    passer.cn = certificateNo
    passer.dt_cn = datetime.datetime.now() + datetime.timedelta(minutes=3)
    passer.save()
    logSend('   phone: {} certificateNo: {}'.format(phone_no, certificateNo))

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
        func_end_log(func_name)
        return REG_200_SUCCESS.to_json_response(rData)

    rSMS = requests.post('https://apis.aligo.in/send/', data=rData)
    # print(rSMS.status_code)
    # print(rSMS.headers['content-type'])
    # print(rSMS.text)
    # print(rSMS.json())
    logSend(json.dumps(rSMS.json(), cls=DateTimeEncoder))
    # rJson = rSMS.json()
    # rJson['vefiry_no'] = str(certificateNo)

    # response = HttpResponse(json.dumps(rSMS.json(), cls=DateTimeEncoder))
    func_end_log(func_name)
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
        STATUS 422
            {'message':'인증번호 요청없이 인증번호 요청이 들어왔습니다.'}
        STATUS 550
            {'message': '인증시간이 지났습니다.\n다시 인증요청을 해주세요.'} # 인증시간 3분
            {'message': '인증번호가 틀립니다.'}
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
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'phone_no\' 가 없어요'}
            {'message':'ClientError: parameter \'cn\' 가 없어요'}
            {'message':'ClientError: parameter \'phone_type\' 가 없어요'}
            {'message':'ClientError: parameter \'push_token\' 가 없어요'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['phone_no', 'cn', 'phone_type'])  #, 'push_token'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    phone_no = parameter_check['parameters']['phone_no']
    cn = parameter_check['parameters']['cn']
    phone_type = parameter_check['parameters']['phone_type']
    push_token = rqst['push_token']
    phone_no = no_only_phone_no(phone_no)

    passers = Passer.objects.filter(pNo=phone_no)
    if len(passers) > 1:
        duplicate_id = [passer.id for passer in passers]
        logSend('ERROR: ', phone_no, duplicate_id)
    passer = passers[0]
    if passer.dt_cn == None:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':'인증번호 요청없이 인증요청(해킹?)'})

    if passer.dt_cn < datetime.datetime.now():
        logSend(passer.dt_cn, datetime.datetime.now())
        func_end_log(func_name)
        return REG_550_CERTIFICATION_NO_IS_INCORRECT.to_json_response({'message':'인증시간이 지났습니다.\n다시 인증요청을 해주세요.'})
    else:
        cn = cn.replace(' ', '')
        logSend(passer.cn, ' vs ', cn, ' is test = {}'.format(settings.IS_TEST))
        if not settings.IS_TEST and passer.cn != int(cn):
        # if passer.cn != int(cn):
            func_end_log(func_name)
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
        employees = Employee.objects.filter(id=passer.employee_id)
        if len(employees) == 0:
            status_code = 201
            employee = Employee(
            )
            employee.save()
            passer.employee_id = employee.id
        else:
            employee = employees[0]
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
    passer.pType = 20 if phone_type == 'A' else 10
    passer.push_token = push_token
    passer.cn = 0
    passer.dt_cn = None
    passer.save()

    func_end_log(func_name)
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
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'passer_id\' 가 없어요'}
            {'message':'ClientError: parameter \'passer_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ServerError: 근로자 id 확인이 필요해요.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['passer_id_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    passer_id = parameter_check['parameters']['passer_id']
    logSend('   ' + passer_id)
    try:
        passer = Passer.objects.get(id=passer_id)
    except Exception as e:
        # 출입자에 없는 사람을 수정하려는 경우
        logError(func_name, ' passer_id = {} Passer 에 없다.\n{}'.format(passer_id, e))
        return status422(func_name, {'message': 'ServerError: 근로자 id 확인이 필요해요.'})
    try:
        employee = Employee.objects.get(id=passer.employee_id)
    except Exception as e:
        # 출입자에 근로자 정보가 없는 경우
        logError(func_name, ' passer.employee_id = {} Employee 에 없다.\n{}'.format(passer.employee_id, e))
        return status422(func_name, {'message': 'ServerError: 근로자 id 확인이 필요해요.'})

    update_employee_of_customer = {'is_upate': False}
    if 'name' in rqst:
        if len(rqst['name']) < 2:
            func_end_log(func_name)
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':'이름은 2자 이상이어야 합니다.'})
        #
        # 고객사 업무의 근로자 이름도 변경되어야 함.
        #
        update_employee_of_customer['is_upate'] = True
        update_employee_of_customer['old_name'] = employee.name
        update_employee_of_customer['new_name'] = rqst['name']

        employee.name = rqst['name'];
        logSend('   ' + rqst['name']);
    if 'pNo' in rqst:
        pNo = no_only_phone_no(rqst['pNo'])
        if len(pNo) < 9:
            func_end_log(func_name)
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':'전화번호를 확인해 주세요.'})
        #
        # 고객사 업무의 근로자 전화번호도 변경되어야 함.
        #
        update_employee_of_customer['is_upate'] = True
        update_employee_of_customer['old_pNo'] = passer.pNo
        update_employee_of_customer['new_pNo'] = pNo

        passer.pNo = pNo;
        passer.save()
        logSend('   ' + pNo);
    if 'bank' in rqst and 'bank_account' in rqst:
        if len(rqst['bank_account']) < 5:
            func_end_log(func_name)
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

    #
    # to customer server
    # 고객사 근로자의 이름과 전화번호 변경
    #
    if update_employee_of_customer['is_upate'] and employee.work_id > 0:
        request_data = {
            'worker_id': AES_ENCRYPT_BASE64('thinking'),
            'work_id': AES_ENCRYPT_BASE64(str(employee.work_id)),
            'employee_pNo': update_employee_of_customer['old_pNo'] if 'new_pNo' in update_employee_of_customer else passer.pNo,
            'new_name': update_employee_of_customer['old_name'] if 'new_name' in update_employee_of_customer else employee.name,
            'new_pNo': update_employee_of_customer['new_pNo'] if 'new_pNo' in update_employee_of_customer else passer.pNo,
        }
        logSend(request_data)
        response_customer = requests.post(settings.CUSTOMER_URL + 'update_employee_for_employee', json=request_data)
        logSend(response_customer.json())
        if response_customer.status_code != 200:
            func_end_log(func_name)
            return ReqLibJsonResponse(response_customer)

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def pass_record_of_employees_in_day_for_customer(request):
    """
    << 고객 서버용 >> 복수 근로자의 날짜별 출퇴근 기록 요청
    - work 의 시작 날짜 이전을 요청하면 안된다. - work 의 시작 날짜를 검사하지 않는다.
    - 출퇴근 기록이 없으면 출퇴근 기록을 새로 만든다.
    - 수정한 시간 오류 검사 X : 출근 시간보다 퇴근 시간이 느리다, ...
    http://0.0.0.0:8000/employee/pass_record_of_employees_in_day_for_customer?employees=&dt=2019-05-06
    POST : json
        {
            employees: [ employee_id, employee_id, ...],  # 배열: 대상 근로자 (암호화된 값)
            year_month_day: 2018-12-28,                   # 대상 날짜
            work_id: work_id,                             # 업무 id (암호화된 값): 암호를 풀어서 -1 이면 업무 특정짓지 않는다.

            #
            # 아래항은 옵션임 - 값이 없으면 처리하지 않음
            #
            overtime: 0,                    # 연장 근무 -1 : 업무 끝나면 퇴근, 0: 정상 근무, 1~6: 연장 근무 시간( 1:30분, 2:1시간, 3:1:30, 4:2:00, 5:2:30, 6:3:00 )
            overtime_staff_id: staff_id,    # 처리 직원 id (암호화된 값)

            dt_in_verify: 08:00,            # 수정된 출근시간 (24 시간제)
            in_staff_id: staff_id,          # 출근 시간 수정 직원 id (암호화됨)

            dt_out_verify: 17:00,            # 수정된 퇴근시간 (24 시간제)
            out_staff_id: staff_id,          # 퇴근 시간 수정 직원 id (암호화됨)
        }
    response
        STATUS 200 - 아래 내용은 처리가 무시되기 때문에 에러처리는 하지 않는다.
            'passer_id': AES_ENCRYPT_BASE64(str(pass_history.passer_id)),
            'year_month_day': pass_history.year_month_day,
            'action': pass_history.action,
            'work_id': pass_history.work_id,
            'dt_in': pass_history.dt_in,
            'dt_in_verify': pass_history.dt_in_verify,
            'in_staff_id': pass_history.in_staff_id,
            'dt_out': pass_history.dt_out,
            'dt_out_verify': pass_history.dt_out_verify,
            'out_staff_id': pass_history.out_staff_id,
            'overtime': pass_history.overtime,
            'overtime_staff_id': pass_history.overtime_staff_id,
            'x': pass_history.x,
            'y': pass_history.y,

            {'message': 'out 인데 어제 오늘 in 기록이 없다.'}
            {'message': 'in 으로 부터 12 시간이 지나서 out 을 무시한다.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'employees\' 가 없어요'}
            {'message':'ClientError: parameter \'year_month_day\' 가 없어요'}
            {'message':'ClientError: parameter \'work_id\' 가 없어요'}
            {'message':'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Passer 에 passer_id=%s 이(가) 없거나 중복됨' % passer_id }
            {'message':'ServerError: Employee 에 employee_id=%s 이(가) 없거나 중복됨' % employee_id }
            {'message':'ClientError: parameter \'dt\' 양식을 확인해주세요.'}
    log Error
        logError(func_name, ' passer_ids={}, year_month_day = {} 에 해당하는 출퇴근 기록이 없다.'.format(employee_ids, year_month_day))

        logError(func_name, ' passer_id={} out touch 인데 어제, 오늘 기록이 없다. dt_touch={}'.format(passer_id, dt_touch)
        logError(func_name, ' passer_id={} in 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
        logError(func_name, ' passer_id={} in 기록후 12시간 이상 지나서 out touch가 들어왔다. dt_in={}, dt_touch={}'.format(passer_id, dt_in, dt_touch))
        logError(func_name, ' passer 의 employee_id={} 에 해당하는 근로자가 없음.'.format(passer.employee_id))
        logError(func_name, ' passer 의 employee_id={} 에 해당하는 근로자가 한명 이상임.'.format(passer.employee_id))
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    #
    # 서버 대 서버 통신으로 상대방 서버가 등록된 서버인지 확인 기능 추가가 필요하다.
    #
    parameter_check = is_parameter_ok(rqst, ['employees', 'year_month_day', 'work_id'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    employees = parameter_check['parameters']['employees']
    year_month_day = parameter_check['parameters']['year_month_day']
    customer_work_id = parameter_check['parameters']['work_id']
    try:
        work = Work.objects.get(customer_work_id=customer_work_id)
        work_id = work.id
    except Exception as e:
        work_id = -1
    employee_ids = []
    for employee in employees:
        # key 에 '_id' 가 포함되어 있으면 >> 암호화 된 값이면
        plain = AES_DECRYPT_BASE64(employee)
        if plain == '__error':
            return status422(func_name, {'message': 'employees 에 있는 employee_id={} 가 해독되지 않는다.'.format(employee)})
        else:
            employee_ids.append(plain)

    # logSend('--- pass_histories : employee_ids : {} work_id {}'.format(employee_ids, work_id))
    if work_id == -1:
        pass_histories = Pass_History.objects.filter(year_month_day=year_month_day, passer_id__in=employee_ids)
    else:
        pass_histories = Pass_History.objects.filter(year_month_day=year_month_day, passer_id__in=employee_ids, work_id=work_id)
    if len(pass_histories) == 0:
        logError(func_name, ' passer_ids={}, year_month_day = {} 에 해당하는 출퇴근 기록이 없다.'.format(employee_ids, year_month_day))
        # func_end_log(func_name)
        # return REG_200_SUCCESS.to_json_response({'message': '조건에 맞는 근로자가 없다.'})
    exist_ids = [pass_history.passer_id for pass_history in pass_histories]
    logSend('--- pass_histories passer_ids {}'.format(exist_ids))
    for employee_id in employee_ids:
        if int(employee_id) not in exist_ids:
            # 출퇴근 기록이 없으면 새로 만든다.
            logSend('   --- new pass_history passer_id {}'.format(employee_id))
            Pass_History(
                passer_id=int(employee_id),
                year_month_day=year_month_day,
                action=0
            ).save()
    if work_id == -1:
        pass_histories = Pass_History.objects.filter(year_month_day=year_month_day, passer_id__in=employee_ids)
    else:
        pass_histories = Pass_History.objects.filter(year_month_day=year_month_day, passer_id__in=employee_ids, work_id=work_id)

    exist_ids = [pass_history.passer_id for pass_history in pass_histories]
    logSend('--- pass_histories passer_ids {}'.format(exist_ids))
    fail_list = []
    for pass_history in pass_histories:
        # 연장 근무 처리
        if ('overtime' in rqst.keys()) and ('overtime_staff_id' in rqst.keys()):
            overtime = int(rqst['overtime'])
            plain = AES_DECRYPT_BASE64(rqst['overtime_staff_id'])
            is_ok = True
            if plain == '__error':
                is_ok = False
                fail_list.append(' overtime_staff_id: 비정상')
            if overtime < -1 or 6 < overtime:
                is_ok = False
                fail_list.append(' overtime: 범위 초과')
            if is_ok:
                pass_history.overtime = overtime
                pass_history.overtime_staff_id = int(plain)

        # 출근시간 수정 처리
        if ('dt_in_verify' in rqst.keys()) and ('in_staff_id' in rqst.keys()):
            plain = AES_DECRYPT_BASE64(rqst['in_staff_id'])
            is_ok = True
            if plain == '__error':
                is_ok = False
                fail_list.append(' in_staff_id: 비정상')
            try:
                dt_in_verify = datetime.datetime.strptime('{} {}:00'.format(year_month_day, rqst['dt_in_verify']),
                                                          '%Y-%m-%d %H:%M:%S')
            except Exception as e:
                is_ok = False
                fail_list.append(' dt_in_verify: 날짜 변경 Error ({})'.format(e))
            if is_ok:
                pass_history.dt_in_verify = dt_in_verify
                pass_history.in_staff_id = int(plain)
                update_pass_history(pass_history)

        # 퇴근시간 수정 처리
        if ('dt_out_verify' in rqst.keys()) and ('out_staff_id' in rqst.keys()):
            plain = AES_DECRYPT_BASE64(rqst['out_staff_id'])
            is_ok = True
            if plain == '__error':
                is_ok = False
                fail_list.append(' out_staff_id: 비정상')
            try:
                dt_out_verify = datetime.datetime.strptime('{} {}:00'.format(year_month_day, rqst['dt_out_verify']), '%Y-%m-%d %H:%M:%S')
            except Exception as e:
                is_ok = False
                fail_list.append(' dt_out_verify: 날짜 변경 Error ({})'.format(e))
            if is_ok:
                pass_history.action = 0
                pass_history.dt_out_verify = dt_out_verify
                pass_history.out_staff_id = int(plain)
                update_pass_history(pass_history)

        if len(fail_list) > 0:
            return status422(func_name, {'message':'fail', 'fails': fail_list})

        pass_history.save()

        # *** 출퇴근 시간이 바뀌면 pass_verify 로 변경해야하는데...
        # 문제 없을까?
        # action 처리가 안된다.

    list_pass_history = []
    for pass_history in pass_histories:
        pass_history_dict = {
            'passer_id': AES_ENCRYPT_BASE64(str(pass_history.passer_id)),
            'year_month_day': pass_history.year_month_day,
            'action': pass_history.action,
            'work_id': pass_history.work_id,
            'dt_in': pass_history.dt_in,
            'dt_in_verify': pass_history.dt_in_verify,
            'in_staff_id': pass_history.in_staff_id,
            'dt_out': pass_history.dt_out,
            'dt_out_verify': pass_history.dt_out_verify,
            'out_staff_id': pass_history.out_staff_id,
            'overtime': pass_history.overtime,
            'overtime_staff_id': pass_history.overtime_staff_id,
            'x': pass_history.x,
            'y': pass_history.y,
        }
        # for key in pass_history.__dict__.keys():
        #     logSend(key, ' ', pass_history.__dict__[key])
        #     json_pass_history[key] = pass_history.__dict__[key]
        # list_pass_history.append(json_pass_history)
        list_pass_history.append(pass_history_dict)
    # logSend(list_pass_history)
    result = {'employees': list_pass_history,
              'fail_list': fail_list,
              }
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)


def update_pass_history(pass_history):
    """
    출퇴근 시간에 맞추어 지각, 조퇴 처리
    to use:
        pass_record_of_employees_in_day_for_customer
        pass_verify
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    try:
        passer = Passer.objects.get(id=pass_history.passer_id)
    except Exception as e:
        func_end_log(func_name, e)
        return
    if passer.employee_id <= 0:
        func_end_log(func_name)
        return
    employees = Employee.objects.filter(id=passer.employee_id)
    if len(employees) == 0:
        logError(func_name, ' passer 의 employee_id={} 에 해당하는 근로자가 없음.'.format(passer.employee_id))
        func_end_log(func_name)
        return
    if len(employees) > 1:
        logError(func_name, ' passer 의 employee_id={} 에 해당하는 근로자가 한명 이상임.'.format(passer.employee_id))
    employee = employees[0]
    if pass_history.dt_in_verify is not None:
        action_in = 100
        if (pass_history.dt_in_verify.hour >= int(employee.work_start[:2])) and (pass_history.dt_in_verify.minute > int(employee.work_start[3:])):
            action_in = 200
    else:
        action_in = 0

    if pass_history.overtime == -1:
        # 연장근무가 퇴근 시간 상관없이 빨리 끝내면 퇴근 가능일 경우 << 8시간 근무에 3시간 일해도 적용 가능한가?
        action_out = 10
    else:
        if pass_history.dt_out_verify is not None:
            action_out = 10
            dt_out = pass_history.dt_out_verify
            work_out_hour = int(employee.work_start[:2]) + int(employee.working_time[:2])
            work_out_minute = int(employee.work_start[3:])
            if (dt_out.hour <= work_out_hour) and (dt_out.minute < work_out_minute):
                action_out = 20
        else:
            action_out = 0
    pass_history.action = action_in + action_out
    pass_history.save()
    func_end_log(func_name, ' pass_history.action = {}, passer_id = {}, employee.name = {}'.format(pass_history.action, passer.id, employee.name))
    return


@cross_origin_read_allow
def change_work_period_for_customer(request):
    """
    << 고객 서버용 >> 현장 소장이 근로자의 업무 날짜를 조정한다.
    - work 의 시작 날짜 이전을 요청하면 안된다. - work 의 시작 날짜를 검사하지 않는다.
    - 출퇴근 기록이 없으면 출퇴근 기록을 새로 만든다.
    - 수정한 시간 오류 검사 X : 출근 시간보다 퇴근 시간이 느리다, ...
    http://0.0.0.0:8000/employee/change_work_period_for_customer?employees=&dt=2019-05-06
    POST : json
        {
            employee_id: qgf6YHf1z2Fx80DR8o_Lvg  # 근로자 id (passer_id = customer.employee.employee_id)
            work_id: qgf6YHf1z2Fx80DR8o_Lvg  # 업무 id (암호화 된 값)
            dt_begin: 2019-04-01   # 근로 시작 날짜
            dt_end: 2019-04-13     # 근로 종료 날짜
        }
    response
        STATUS 200 - 아래 내용은 처리가 무시되기 때문에 에러처리는 하지 않는다.
            {'message': 'out 인데 어제 오늘 in 기록이 없다.'}
            {'message': 'in 으로 부터 12 시간이 지나서 out 을 무시한다.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'employees\' 가 없어요'}
            {'message':'ClientError: parameter \'year_month_day\' 가 없어요'}
            {'message':'ClientError: parameter \'work_id\' 가 없어요'}
            {'message':'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Passer 에 passer_id=%s 이(가) 없거나 중복됨' % passer_id }
            {'message':'ServerError: Employee 에 employee_id=%s 이(가) 없거나 중복됨' % employee_id }
            {'message':'ClientError: parameter \'dt\' 양식을 확인해주세요.'}
    log Error
        logError(func_name, ' passer_ids={}, year_month_day = {} 에 해당하는 출퇴근 기록이 없다.'.format(employee_ids, year_month_day))

        logError(func_name, ' passer_id={} out touch 인데 어제, 오늘 기록이 없다. dt_touch={}'.format(passer_id, dt_touch)
        logError(func_name, ' passer_id={} in 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
        logError(func_name, ' passer_id={} in 기록후 12시간 이상 지나서 out touch가 들어왔다. dt_in={}, dt_touch={}'.format(passer_id, dt_in, dt_touch))
        logError(func_name, ' passer 의 employee_id={} 에 해당하는 근로자가 없음.'.format(passer.employee_id))
        logError(func_name, ' passer 의 employee_id={} 에 해당하는 근로자가 한명 이상임.'.format(passer.employee_id))
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    #
    # 서버 대 서버 통신으로 상대방 서버가 등록된 서버인지 확인 기능 추가가 필요하다.
    #
    parameter_check = is_parameter_ok(rqst, ['employee_id_!', 'work_id'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    passer_id = parameter_check['parameters']['employee_id']
    work_id = parameter_check['parameters']['work_id']
    try:
        passer = Passer.objects.get(id=passer_id)
    except:
        return status422(func_name, {'message': '해당 근로자({})가 없다.'.format(passer_id)})
    if passer.employee_id == -1:
        return status422(func_name, {'message': '해당 근로자({})의 업무가 등록되지 않았다.'.format(passer_id)})
    try:
        employee = Employee.objects.get(id=passer.employee_id)
    except:
        return status422(func_name, {'message': '해당 근로자({})의 업무를 찾을 수 없다.'.format(passer_id)})
    logSend('   {}'.format(employee.name))
    try:
        work = Work.objects.get(customer_work_id=work_id)
    except:
        return status422(func_name, {'message': '해당 업무({})를 찾을 수 없다.'.format(work_id)})
    if 'dt_begin' not in rqst:
        dt_begin = work.begin
    else:
        dt_begin = rqst['dt_begin']

    if 'dt_end' not in rqst:
        dt_end = work.end
    else:
        dt_end = rqst['dt_end']
    if employee.work_id == work.id:
        employee.begin_1 = dt_begin
        employee.end_1 = dt_end
        employee.save()
    elif employee.work_id_2 == work.id:
        employee.begin_2 = dt_begin
        employee.end_2 = dt_end
        employee.save()
    elif employee.work_id_3 == work.id:
        employee.begin_3 = dt_begin
        employee.end_3 = dt_end
        employee.save()
    else:
        return status422(func_name, {'message': '해당 업무({})를 근로자({})에게서 찾을 수 없다.'.format(work_id, passer_id)})
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()



@cross_origin_read_allow
def employee_day_working_from_customer(request):
    """
    <<<고객 서버용>>> 근로자 한명의 하루 근로 내용
    http://0.0.0.0:8000/employee/employee_day_working_from_employee?employee_id=qgf6YHf1z2Fx80DR8o_Lvg&dt=2019-04-18
    GET
        employee_id='근로자 id'
        dt = '2019-04-18'
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
            {'message':'ClientError: parameter \'id\' 가 없어요'}
            {'message':'ClientError: parameter \'employee_id\' 가 없어요'}
            {'message':'ClientError: parameter \'year_month\' 가 없어요'}
            {'message':'ClientError: parameter \'id\' 가 정상적인 값이 아니예요.'}
            {'message':'ClientError: parameter \'employee_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Staff 에 id=%s 이(가) 없거나 중복됨' % staff_id }
            {'message':'ServerError: Employee 에 id=%s 이(가) 없거나 중복됨' % employee_id }
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    passer_id = AES_DECRYPT_BASE64(rqst['employee_id'])
    dt = rqst['dt']
    dt_begin = datetime.datetime.strptime(dt+' 00:00:00', '%Y-%m-%d %H:%M:%S')
    dt_end = dt_begin + datetime.timedelta(days=1)
    logSend(dt_begin, '  ', dt_end)

    pass_history_list = Pass_History.objects.filter(passer_id=passer_id, dt_in__gt=dt_begin, dt_in__lt=dt_end)
    if len(pass_history_list) > 0:
        pass_history = pass_history_list[0]
        day_work = {'dt_begin_beacon': dt_null(pass_history.dt_in),
                    'dt_end_beacon': dt_null(pass_history.dt_out),
                    'dt_begin_touch': dt_null(pass_history.dt_in_verify),
                    'dt_end_touch': dt_null(pass_history.dt_out_verify),
                    'action': pass_history.action,
                    }
        func_end_log(func_name)
        return REG_200_SUCCESS.to_json_response({'dt': day_work})

    pass_history = Pass_History(passer_id=passer_id,
                                action=110,
                                minor=0,
                                )

    # passer = Passer.objects.get(id=passer_id)
    passes = Pass.objects.filter(passer_id=passer_id, dt_reg__gt=dt_begin, dt_reg__lt=dt_end, is_in=1)
    if len(passes) > 0:
        begin_beacon = passes[0]
        # logSend(begin_beacon.dt_reg, ' ', begin_beacon.is_in)
        pass_history.dt_in = begin_beacon.dt_reg
    else:
        pass_history.dt_in = dt_begin + datetime.timedelta(hours=8, minutes=20)

    passes = Pass.objects.filter(passer_id=passer_id, dt_reg__gt=pass_history.dt_in + datetime.timedelta(hours=5),
                                 dt_reg__lt=pass_history.dt_in + datetime.timedelta(hours=14), is_in=0)
    if len(passes) > 0:
        end_beacon = passes[len(passes) - 1]
        # logSend(end_beacon.dt_reg, ' ', end_beacon.is_in)
        pass_history.dt_out = end_beacon.dt_reg
    else:
        pass_history.dt_out = pass_history.dt_in + datetime.timedelta(hours=9, minutes=30)

    passes = Pass.objects.filter(passer_id=passer_id, dt_verify__gt=dt_begin, dt_verify__lt=dt_end, is_in=1)
    if len(passes) > 0:
        begin_button = passes[0]
        # logSend(begin_button.dt_verify, ' ', begin_button.is_in)
        pass_history.dt_in_verify = begin_button.dt_verify
    else:
        pass_history.dt_in_verify = dt_begin + datetime.timedelta(hours=8, minutes=25)

    passes = Pass.objects.filter(passer_id=passer_id, dt_verify__gt=pass_history.dt_in_verify, dt_verify__lt=pass_history.dt_in_verify + datetime.timedelta(days=1), is_in=0)
    if len(passes) > 0:
        end_button = passes[0]
        # logSend(end_button.dt_verify, ' ', end_button.is_in)
        pass_history.dt_out_verify = end_button.dt_verify
    else:
        pass_history.dt_out_verify = pass_history.dt_in + datetime.timedelta(hours=10)

    pass_history.save()

    day_work = {'dt_begin_beacon':dt_null(pass_history.dt_in),
                'dt_end_beacon':dt_null(pass_history.dt_out),
                'dt_begin_touch':dt_null(pass_history.dt_in_verify),
                'dt_end_touch':dt_null(pass_history.dt_out_verify),
                'action':pass_history.action,
                }
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'dt':day_work})


@cross_origin_read_allow
def my_work_histories_for_customer(request):
    """
    <<<고객 서버용>>> 근로 내용 : 근로자의 근로 내역을 월 기준으로 1년까지 요청함, 캘린더나 목록이 스크롤 될 때 6개월정도 남으면 추가 요청해서 표시할 것
    action 설명
        총 3자리로 구성 첫자리는 출근, 2번째는 퇴근, 3번째는 외출 횟수
        첫번째 자리 1 - 정상 출근, 2 - 지각 출근
        두번째 자리 1 - 정상 퇴근, 2 - 조퇴, 3 - 30분 연장 근무, 4 - 1시간 연장 근무, 5 - 1:30 연장 근무
    http://0.0.0.0:8000/employee/my_work_histories_for_customer?employee_id=qgf6YHf1z2Fx80DR8o/Lvg&dt=2018-12
    GET
        employee_id='서버로 받아 저장해둔 출입자 id'
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
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'id\' 가 없어요'}
            {'message':'ClientError: parameter \'employee_id\' 가 없어요'}
            {'message':'ClientError: parameter \'year_month\' 가 없어요'}
            {'message':'ClientError: parameter \'id\' 가 정상적인 값이 아니예요.'}
            {'message':'ClientError: parameter \'employee_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Staff 에 id=%s 이(가) 없거나 중복됨' % staff_id }
            {'message':'ServerError: Employee 에 id=%s 이(가) 없거나 중복됨' % employee_id }
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['employee_id_!', 'dt'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    employee_id = parameter_check['parameters']['employee_id']
    year_month = parameter_check['parameters']['dt']

    passers = Passer.objects.filter(id=employee_id)
    if len(passers) != 1:
        return status422(func_name, {'message':'ServerError: Passer 에 employee_id=%s 이(가) 없거나 중복됨' % employee_id })
    passer = passers[0]

    employees = Employee.objects.filter(id=passer.employee_id)
    if len(employees) != 1:
        return status422(func_name, {'message':'ServerError: Employee 에 id=%s 이(가) 없거나 중복됨' % passer.employee_id })
    employee = employees[0]

    dt_begin = datetime.datetime.strptime(year_month + '-01 00:00:00', '%Y-%m-%d %H:%M:%S')
    dt_today = datetime.datetime.now()
    if dt_today.strftime('%Y-%m') == year_month:
        # 근무 내역 요청이 이번달이면 근무 마지막 날을 오늘로 한다.
        dt_end = datetime.datetime.strptime(dt_today.strftime('%Y-%m-%d') + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
        dt_end = dt_end + timedelta(hours=24)
    else:
        # 이번달이 아니면 그 달의 마지막 날을 계산한다.
        dt_end = datetime.datetime.strptime(year_month + '-01 00:00:00', '%Y-%m-%d %H:%M:%S')
        if dt_end.month + 1 == 13:
            # 12월이면 다음 해 1월로
            dt_end = dt_end.replace(month=1, year=dt_end.year + 1)
        else:
            dt_end = dt_end.replace(month=dt_end.month + 1)
        dt_end = dt_end - timedelta(days=1)
        # if dt_today < dt_end:
        #     dt_end = datetime.datetime.strptime()
    logSend(' dt_begin: {}  dt_end: {}'.format(dt_begin, dt_end))

    year_month_day_list = []
    day = dt_begin
    while day < dt_end:
        year_month_day_list.append(day.strftime('%Y-%m-%d'))
        day = day + datetime.timedelta(days=1)
    logSend(year_month_day_list)
    pass_record_list = Pass_History.objects.filter(passer_id=passer.id, year_month_day__in=year_month_day_list)
    workings = []
    overtime_values = [0., 0., .5, 1., 1.5, 2., 2.5, 3.]
    for pass_record in pass_record_list:
        working_time = int(employee.working_time)
        working_hour = (working_time // 4) * 4
        break_hour = working_time - working_hour
        working = {'action': pass_record.action,
                   'dt_begin': dt_null(pass_record.dt_in_verify),
                   'dt_end': dt_null(pass_record.dt_out_verify),
                   'overtime': overtime_values[pass_record.overtime + 1],
                   'working_hour': working_hour,
                   'break_hour': break_hour,
                   }
        workings.append(working)

    # year_month = dt_begin.strftime('%Y-%m')
    # last_day = dt_end - datetime.timedelta(hours=1)
    # s = requests.session()
    # workings = []
    # day_infor = {'employee_id':AES_ENCRYPT_BASE64(str(passer.id))}
    # for day in range(1, int(last_day.strftime('%d')) + 1):
    #     day_infor['dt'] = year_month + '-%02d'%day
    #     r = s.post(settings.EMPLOYEE_URL + 'employee_day_working_from_customer', json=day_infor)
    #     logSend({'url': r.url, 'POST': day_infor, 'STATUS': r.status_code, 'R': r.json()})
    #     if 'dt' in r.json():
    #         work_day = r.json()['dt']
    #         working = {'action':work_day['action'],
    #                    'dt_begin':work_day['dt_begin_touch'],
    #                    'dt_end':work_day['dt_end_touch']
    #                    }
    #         workings.append(working)
    result = {"working": workings}
    #
    # 가상 데이터 생성
    #
    # result = virtual_working_data(dt_begin, dt_end)
    #

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)


def virtual_working_data(dt_begin : datetime, dt_end : datetime)->dict:
    # print(dt_begin.strftime('%Y-%m-%d %H:%M:%S'), ' ', dt_end.strftime('%Y-%m-%d %H:%M:%S'))
    year_month = dt_begin.strftime('%Y-%m')
    last_day = dt_end - datetime.timedelta(hours=1)
    # print(last_day)
    workings = []
    for day in range(1, int(last_day.strftime('%d')) + 1):
        if random.randint(1,7) > 5: # 7일에 5일 꼴로 쉬는 날
            continue
        working = {}
        action = 0
        if random.randint(1,30) > 27: # 한달에 3번꼴로 지각
            action = 200
            working['dt_begin'] = year_month + '-%02d'%day + ' 08:45:00'
        else :
            action = 100
            working['dt_begin'] = year_month + '-%02d'%day + ' 08:25:00'
        if random.randint(1,30) > 29: # 한달에 1번꼴로 조퇴
            action += 20
            working['dt_end'] = year_month + '-%02d'%day + ' 15:33:00'
        elif random.randint(0,30) > 20 : # 일에 한번꼴로 연장 근무
            action += 40
            working['dt_end'] = year_month + '-%02d'%day + ' 18:35:00'
        else:
            action += 10
            working['dt_end'] = year_month + '-%02d' % day + ' 17:35:00'
        outing = (random.randint(0,30) - 28) % 3 # 한달에 2번꼴로 외출
        outings = []
        if outing > 0:
            for i in range(outing):
                # print(i)
                outings.append({'dt_begin':year_month + '-%02d' % day + ' ' + str(i+13) + ':00:00',
                               'dt_end':year_month + '-%02d' % day + ' ' + str(i+13) + ':30:00'})
        working['outing'] = outings
        working['action'] = action + outing
        # print(working)
        workings.append(working)
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
    return {'working': workings}


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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])
    #
    # 근로자 서버로 근로자의 월 근로 내역을 요청
    #
    employee_info = {
            'employee_id' : rqst["passer_id"],
            'dt' : rqst['dt'],
        }
    response_employee = requests.post(settings.EMPLOYEE_URL + 'my_work_histories_for_customer', json=employee_info)
    logSend(response_employee)

    result = response_employee.json()
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def generation_pass_history(request):
    """
    출입 기록에서 일자별 출퇴근 기록을 만든다.
    퇴근버튼이 눌렸을 때나 최종 out 기록 후 1시간 후에 처리한다.
    1. 주어진 날짜의 in, dt_verify 를 찾는다. (출근버튼을 누른 시간)
    2. 주어진 날짜의
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
    func_end_log(func_name)
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
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

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
    func_end_log(func_name)
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

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'beacons': arr_beacon})


