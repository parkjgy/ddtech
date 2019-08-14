"""
Employee view

Copyright 2019. DaeDuckTech Corp. All rights reserved.
"""

import random
import inspect

from config.log import logSend, logError
from config.common import ReqLibJsonResponse
from config.common import status422, no_only_phone_no, phone_format, dt_null, dt_str, is_parameter_ok, str_to_datetime
from config.common import str_no, str_to_dt, get_client_ip, get_api
from config.common import Works

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
from .models import Employee_Backup

import requests
from datetime import datetime, timedelta
import datetime

from django.conf import settings
from django.db.models import Q


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
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    print(parameter_check['parameters'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

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
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def check_version(request):
    """
    앱 버전을 확인한다. (마지막 190111 은 필히 6자리)
    - status code:416 이 들오오면 앱의 기존 사용자 데이터를 삭제하고 전화번호 인증부터 다시 받으세요.
    http://0.0.0.0:8000/employee/check_version?v=A.1.0.0.190111&i=BbaBa43219999QJ4CSvmpM14fuSxyhyufYQ
    GET
        v=A.1.0.0.190111
            # A.     : phone type - A or i
            # 1.0.0. : 앱의 버전 구분 업그레이드 필요성과 상관 없다.
            # 190111 : 서버와 호환되는 날짜 - 이 날짜에 의해 서버는 업그레이드 필요를 응답한다.
        i=근로자정보 (전화인증이 끝난 경우만 보낸다.)
            # 등록할 때 서버에서 받은 암호화된 id: eeeeeeeeeeeeeeeeeeeeee
            # 전화번호: 010-1111-2222 > aBa11112222
            # 전화번호 자릿수: 11 > Bb
            # 근로자 정보: BbaBa11112222eeeeeeeeeeeeeeeeeeeeee << Ba aBa 1111 2222 eeeeeeeeeeeeeeeeeeeeee

    response
        STATUS 200
        STATUS 551
        {
            'msg': '업그레이드가 필요합니다.'
            'url': 'http://...' # itune, google play update
        }
        STATUS 416 # 개발자 수정사항 - 앱의 기존 사용자 데이터를 삭제하고 전화번호 인증부터 다시 받으세요.
            {'message': '앱이 리셋됩니다.\n다시 실행해주세요.'}
        STATUS 422 # 개발자 수정사항
            {'message': 'ClientError: 잘못된 id 예요'}  # i 에 들어가는 [암호화된 id] 가 잘못되었다.
            {'message': "ClientError: parameter 'v' 가 없어요'}
            {'message': 'v: A.1.0.0.190111 에서 A 가 잘못된 값이 들어왔어요'}
            {'message': '검사하려는 버전 값이 양식에 맞지 않습니다.'}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['i'])
    if parameter_check['is_ok']:
        info = parameter_check['parameters']['i']
        phone_count = str_no(info[:2])
        phone_no = info[2:int(phone_count) + 2]
        phone_head = str_no(phone_no[:3])
        phone_no = phone_head + phone_no[3:]
        cypher_passer_id = info[int(phone_count) + 2:]
        passer_id = AES_DECRYPT_BASE64(cypher_passer_id)
        if passer_id == '__error':
            return status422(get_api(request), {'message': 'ClientError: 잘못된 id 예요'})
        try:
            passer = Passer.objects.get(pNo=phone_no)
        except Exception as e:
            logError(get_api(request), ' 등록되지 않은 근로자 전화번호({}) - {}'.format(phone_no, str(e)))
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '앱이 리셋됩니다.\n다시 실행해주세요.'})
        if passer.id != int(passer_id):
            logError(get_api(request),
                     ' 등록된 전화번호: {}, 서버 id: {}, 앱 id: {}'.format(phone_no, passer.id, passer_id))
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '앱이 리셋됩니다.\n다시 실행해주세요.'})

    parameter_check = is_parameter_ok(rqst, ['v'])
    if not parameter_check['is_ok']:
        return status422(get_api(request),
                         {'message': '{}'.format(''.join([message for message in parameter_check['results']]))})
        # return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    version = parameter_check['parameters']['v']

    items = version.split('.')
    phone_type = items[0]
    if phone_type != 'A' and phone_type != 'i':
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': 'v: A.1.0.0.190111 에서 A 가 잘못된 값이 들어왔어요'})
    str_dt_ver = items[len(items) - 1]
    logSend('  version dt: {}'.format(str_dt_ver))
    try:
        dt_version = str_to_datetime('20' + str_dt_ver[:2] + '-' + str_dt_ver[2:4] + '-' + str_dt_ver[4:6])
    except Exception as e:
        return REG_520_UNDEFINED.to_json_response({'message': '검사하려는 버전 값이 양식에 맞지 않습니다.'})
    response_operation = requests.post(settings.OPERATION_URL + 'currentEnv', json={})
    logSend('  current environment', response_operation.status_code, response_operation.json())
    cur_env = response_operation.json()['env_list'][0]
    dt_check = str_to_datetime(cur_env['dt_android_upgrade'] if phone_type == 'A' else cur_env['dt_iOS_upgrade'])
    logSend('  DB dt_check: {} vs dt_version: {}'.format(dt_check, dt_version))
    if dt_version < dt_check:
        url_android = "https://play.google.com/store/apps/details?id=com.ddtechi.aegis.employee"
        url_iOS = "https://..."
        url_install = ""
        if phone_type == 'A':
            url_install = url_android
        elif phone_type == 'i':
            url_install = url_iOS
        return REG_551_AN_UPGRADE_IS_REQUIRED.to_json_response({'url': url_install  # itune, google play update
                                                                })
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def reg_employee_for_customer(request):
    """
    <<<고객 서버용>>> 고객사에서 보낸 업무 배정 SMS로 알림 (보냈으면 X)
    -101 : sms 를 보낼 수 없는 전화번호
    -11 : 해당 전화번호를 가진 근로자의 업무와 요청 업무의 기간이 겹친다.
    -21 : 피쳐폰에 이미 업무 요청이 있어서 더 요청할 수 없다.
    http://0.0.0.0:8000/employee/reg_employee_for_customer?customer_work_id=qgf6YHf1z2Fx80DR8o_Lvg&work_place_name=효성1공장&work_name_type=경비 주간&dt_begin=2019/03/04&dt_end=2019/03/31&dt_answer_deadline=2019-03-03 19:00:00&staff_name=이수용&staff_phone=01099993333&phones=01025573555&phones=01046755165&phones=01011112222&phones=01022223333&phones=0103333&phones=01044445555
    POST : json
        {
          "customer_work_id":qgf6YHf1z2Fx80DR8o_Lvg,
          "work_place_name": "효성1공장",
          "work_name_type": "경비(주간)",
          "dt_begin": "2019/03/04",
          "dt_end": "2019/03/31",
          "staff_name": "이수용",
          "staff_phone": "01099993333",
          "dt_answer_deadline": 2019-03-03 19:00:00,
          "dt_begin_employee": "2019/03/04",
          "dt_end_employee": "2019/03/31",
          "is_update": True,
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
                "01011112222": -11, # 다른 업무와 기간이 겹쳤다.
                "01055557777": -31  # 근로자가 받을 수 있는 요청의 갯수가 넘었다.
                "01022223333": -21, # 피쳐폰은 한개 이상의 업무를 받을 수 없다.
                "0103333": -101,    # 잘못된 전화번호임
              }
            }
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'customer_work_id\' 가 없어요'}
            {'message':'ClientError: parameter \'work_place_name\' 가 없어요'}
            {'message':'ClientError: parameter \'work_name_type\' 가 없어요'}
            {'message':'ClientError: parameter \'dt_begin\' 가 없어요'}
            {'message':'ClientError: parameter \'dt_end\' 가 없어요'}
            {'message':'ClientError: parameter \'dt_answer_deadline\' 가 없어요'}
            {'message':'ClientError: parameter \'staff_name\' 가 없어요'}
            {'message':'ClientError: parameter \'staff_phone\' 가 없어요'}
            {'message':'ClientError: parameter \'phones\' 가 없어요'}
            {'message':'ServerError: Work 에 id={} 가 없다'.format(work_id)}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    if request.method == 'GET':
        phone_numbers = rqst.getlist('phones')
    parameter_check = is_parameter_ok(rqst, ['customer_work_id', 'work_place_name', 'work_name_type', 'dt_begin',
                                             'dt_end', 'staff_name', 'staff_phone', 'phones',
                                             'dt_answer_deadline', 'dt_begin_employee', 'dt_end_employee', 'is_update'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    customer_work_id = parameter_check['parameters']['customer_work_id']
    work_place_name = parameter_check['parameters']['work_place_name']
    work_name_type = parameter_check['parameters']['work_name_type']
    dt_begin = parameter_check['parameters']['dt_begin']
    dt_end = parameter_check['parameters']['dt_end']
    staff_name = parameter_check['parameters']['staff_name']
    staff_phone = parameter_check['parameters']['staff_phone']
    phone_numbers = parameter_check['parameters']['phones']
    dt_answer_deadline = parameter_check['parameters']['dt_answer_deadline']
    dt_begin_employee = parameter_check['parameters']['dt_begin_employee']
    dt_end_employee = parameter_check['parameters']['dt_end_employee']
    is_update = parameter_check['parameters']['is_update']

    logSend('  - phone numbers: {}'.format(phone_numbers))

    find_works = Work.objects.filter(customer_work_id=customer_work_id)
    if len(find_works) == 0:
        work = Work(
            customer_work_id=customer_work_id,
            work_place_name=work_place_name,
            work_name_type=work_name_type,
            begin=dt_begin,
            end=dt_end,
            staff_name=staff_name,
            staff_pNo=staff_phone,
        )
        work.save()
    else:
        work = find_works[0]

    # 업무 요청 전화번호로 등록된 근로자 중에서 업무 요청을 할 수 없는 근로자를 가려낸다.
    # [phone_numbers] - [업무 중이고 예약된 근로자]
    passer_list = Passer.objects.filter(pNo__in=phone_numbers)
    passer_id_dict = {}  # passser_id_dict = {'01033335555': 99, '전환번호': passer_id}
    for passer in passer_list:
        passer_id_dict[passer.pNo] = passer.id
    logSend('  - passer_id_dict: {}'.format(passer_id_dict))
    employee_id_list = [passer.employee_id for passer in passer_list if passer.employee_id > 0]
    employee_list = Employee.objects.filter(id__in=employee_id_list)
    employee_status = {}  # {1:-11}
    logSend(' employee_status: {}'.format(employee_status))
    for employee in employee_list:
        works = Works(employee.get_works())
        logSend('  - ', works.data)
        if works.is_overlap({'id': work.id, 'begin': dt_begin, 'end': dt_end}):
            # 중복되는 업무가 있다.
            employee_status[employee.id] = -11
        work_counter = works.work_counter(work.id)
        if work_counter[0] >= 1:
            if work_counter[1] >= 1:
                employee_status[employee.id] = -31
        elif work_counter[1] >= 2:
            employee_status[employee.id] = -31
        logSend(' employee_status: {}'.format(employee_status))
    logSend('  - bad condition phone: {} (기간이 중복되는 업무가 있는 근로자)'.format(employee_status))
    phones_state = {}
    for passer in passer_list:
        if passer.employee_id > 0:
            # 출입자에 근로자 정보가 있으면
            if passer.employee_id in employee_status.keys():
                # 출입자의 근로자가 기간 중복되는 근로자에 포함되면
                phones_state[passer.pNo] = -11  # employee_status[passer.employee_id] == -11
    last_phone_numbers = [phone_no for phone_no in phone_numbers if phone_no not in phones_state.keys()]
    logSend('  - last_phone_numbers: {}'.format(last_phone_numbers))
    # 등록된 근로자 중에서 전화번호로 업무 요청
    msg = '이지체크\n' \
          '새로운 업무를 앱에서 확인해주세요.\n' \
          '앱 설치\n' \
          'https://api.ezchek.co.kr/rq/app'
    # msg_feature = "이지체크\n"\
    #               "효성 3공장-포장(3교대)\n"\
    #               "2019/06/07~2019/06/30\n"\
    #               "박종기 010-2557-3555".format()
    msg_feature = '이지체크\n{}-{}\n{} ~ {}\n{} {}'.format(work.work_place_name,
                                                       work.work_name_type,
                                                       dt_begin_employee,
                                                       dt_end_employee,
                                                       work.staff_name,
                                                       phone_format(work.staff_pNo))
    rData = {
        'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
        'user_id': 'yuadocjon22',
        'sender': settings.SMS_SENDER_PN,
        # 'receiver': phone_numbers[i],
        'msg_type': 'SMS',
        # 'msg': msg,
    }

    # 업무 요청이 등록된 전화번호
    notification_list = Notification_Work.objects.filter(customer_work_id=customer_work_id,
                                                         employee_pNo__in=last_phone_numbers)
    notification_phones = [notification.employee_pNo for notification in notification_list]
    # 업무 요청 삭제 - 업무 요청을 새로 만들기 때문에
    notification_list.delete()
    for phone_no in last_phone_numbers:
        logSend('  - phone_no: {}'.format(phone_no))
        is_feature_phone = False
        if phone_no in passer_id_dict.keys():
            # 등록된 근로자이면
            phones_state[phone_no] = passer_id_dict[phone_no]
            # 등록된 근로자 중에서 피쳐폰 근로자 검색
            for passer in passer_list:
                if passer.pNo == phone_no:
                    passer_feature = passer
                    break
            if passer_feature.pType == 30:
                # 피쳐폰이면 현재 요청 업무외 추가 요청을 막는다.
                is_feature_phone = True
                find_notification_list = Notification_Work.objects.filter(employee_pNo=phone_no)
                logSend('  - notification list (pNo:{}) : {}'.format(phone_no,
                                                                     [notification.employee_pNo for notification in
                                                                      find_notification_list]))
                if len(find_notification_list) > 0:  # 위에서 업무 요청을 모두 지웠기 때문에 이 요청은 갯수에 안들어 간다.
                    phones_state[phone_no] = -21  # 피쳐폰은 업무를 한개 이상 배정받지 못하게 한다.
                    continue
            # 등록된 근로자가 보관하고 있는 업무의 기간을 변경한다.
            for employee in employee_list:
                employee_works = Works(employee.get_works())
                logSend('  - employee id: {}, works: {}'.format(employee.id, employee_works.data))
                if employee_works.find(work.id):
                    del employee_works.data[employee_works.index]
                    logSend('  - employee id: {}, works: {}'.format(employee.id, employee_works.data))
                    # work = works.data[works.index]
                    # work['begin'] = dt_begin_employee
                    # work['end'] = dt_end_employee
                    employee.set_works(employee_works.data)
                    employee.save()
        else:
            phones_state[phone_no] = -1
        if not settings.IS_TEST:
            logSend('  - sms 보냄 phone: {}'.format(phone_no))
            # SMS 를 보낸다.
            rData['receiver'] = phone_no
            if is_feature_phone:
                # 피쳐폰일 때는 문자형식을 바꾼다.
                rData['msg'] = msg_feature
            else:
                rData['msg'] = msg
            response_SMS = requests.post('https://apis.aligo.in/send/', data=rData)
            logSend('  - SMS result: {}'.format(response_SMS.json()))
            is_sms_ok = int(response_SMS.json()['result_code']) < 0
        else:
            is_sms_ok = len(phone_no) < 11
        if is_sms_ok:
            # 전화번호 에러로 문자를 보낼 수 없음.
            phones_state[phone_no] = -101
            logSend('  - sms send fail phone: {}'.format(phone_no))
        else:
            new_notification = Notification_Work(
                work_id=work.id,
                customer_work_id=customer_work_id,
                employee_id=phones_state[phone_no],
                employee_pNo=phone_no,
                dt_answer_deadline=dt_answer_deadline,
                dt_begin=str_to_dt(dt_begin_employee),
                dt_end=str_to_dt(dt_end_employee),
            )
            new_notification.save()
    return REG_200_SUCCESS.to_json_response({'result': phones_state})


@cross_origin_read_allow
def update_work_for_customer(request):
    """
    <<<고객 서버용>>> 고객사에서 보낸 업무 배정 SMS로 알림 (보냈으면 X)
    http://0.0.0.0:8000/employee/update_work_for_customer?customer_work_id=qgf6YHf1z2Fx80DR8o_Lvg&work_place_name=효성1공장&work_name_type=경비 주간&dt_begin=2019/03/04&dt_end=2019/03/31&dt_answer_deadline=2019-03-03 19:00:00&staff_name=이수용&staff_phone=01099993333&phones=01025573555&phones=01046755165&phones=01011112222&phones=01022223333&phones=0103333&phones=01044445555
    POST : json
        {
          "customer_work_id":qgf6YHf1z2Fx80DR8o_Lvg,
          "work_place_name": "효성1공장",
          "work_name_type": "경비(주간)",
          "dt_begin": "2019/03/04",  # 업무 시작날짜
          "dt_end": "2019/03/31",    # 업무 종료날짜
          "staff_name": "이수용",
          "staff_pNo": "01099993333",
          "dt_answer_deadline": 2019-03-03 19:00:00,
          "dt_begin_employee": "2019/03/04",  # 해당 근로자의 업무 시작날짜
          "dt_end_employee": "2019/03/31",    # 해당 근로자의 업무 종료날짜
          "update_employee_pNo_list": ["010-1111-2222", ...],  # 업무시간이 변경된 근로자 전화번호
        }
    response
        STATUS 200
            {"message": "정상적으로 처리되었습니다."}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    find_works = Work.objects.filter(customer_work_id=rqst['customer_work_id'])
    if len(find_works) == 0:
        work = Work(
            customer_work_id=rqst["customer_work_id"],
            work_place_name=rqst["work_place_name"],
            work_name_type=rqst["work_name_type"],
            begin=rqst["begin"],
            end=rqst["end"],
            staff_name=rqst["staff_name"],
            staff_pNo=rqst["staff_pNo"],
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
    #
    # 근로자 중에서 업무 날짜가 변경된 근로자의 업무시간을 변경한다.
    #
    passer_list = Passer.objects.filter(pNo__in=rqst['update_employee_pNo_list'])
    employee_id_list = [passer.id for passer in passer_list]
    employee_list = Employee.objects.filter(id__in=employee_id_list)
    for employee in employee_list:
        employee_works = Works(employee.get_works())
        for employee_work in employee_works.data:
            logSend('  - work: {}'.format(employee_work))
            if employee_work['id'] == work.id:
                if str_to_dt(employee_work['begin']) < str_to_dt(work.begin):
                    employee_work['begin'] = work.begin
                if str_to_dt(work.end) < str_to_dt(employee_work['end']):
                    employee_work['end'] = work.end
        employee.set_works(employee_works.data)
        employee.save()
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
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    passers = Passer.objects.filter(id=AES_DECRYPT_BASE64(rqst['passer_id']))
    if len(passers) == 0:
        return REG_403_FORBIDDEN.to_json_response({'message': '알 수 없는 사용자입니다.'})
    passer = passers[0]
    dt_today = datetime.datetime.now()
    logSend(passer.pNo)
    # notification_list = Notification_Work.objects.filter(employee_pNo=passer.pNo, dt_answer_deadline__gt=dt_today)
    notification_list = Notification_Work.objects.filter(employee_pNo=passer.pNo)
    logSend('  notification: {}'.format([x.dt_begin for x in notification_list]))
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
            'staff_name': work.staff_name,
            'staff_pNo': phone_format(work.staff_pNo),
            'dt_answer_deadline': dt_str(notification.dt_answer_deadline, "%Y-%m-%d %H:%M"),
            'begin': dt_str(notification.dt_begin, "%Y/%m/%d"),
            'end': dt_str(notification.dt_end, "%Y/%m/%d"),
        }
        arr_notification.append(view_notification)
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
            'is_accept': 0       # 1 : 업무 수락, 0 : 업무 거절
        }
    response
        STATUS 200
        STATUS 416
            {'message': '업무 3개가 꽉 찾습니다.'}
        STATUS 542
            {'message':'파견사 측에 근로자 정보가 없습니다.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'passer_id\' 가 없어요'}
            {'message':'ClientError: parameter \'notification_id\' 가 없어요'}
            {'message':'ClientError: parameter \'is_accept\' 가 없어요'}
            {'message':'ClientError: parameter \'passer_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ClientError: parameter \'notification_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ServerError: Passer 출입자({}) 가 없어요'.format(passer_id)}
            {'message':'ServerError: Notification_Work 알림({}) 가 없어요'.format(notification_id)}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter = is_parameter_ok(rqst, ['passer_id_!', 'notification_id_!', 'is_accept'])
    if not parameter['is_ok']:
        return status422(get_api(request), {'message': parameter['message']})
    passer_id = parameter['parameters']['passer_id']
    notification_id = parameter['parameters']['notification_id']
    is_accept = bool(int(parameter['parameters']['is_accept']))
    logSend('  is_accept = {}'.format(is_accept))

    passers = Passer.objects.filter(id=passer_id)
    if len(passers) == 0:
        return status422(get_api(request), {'message': '출입자({}) 가 없어요'.format(passer_id)})
    passer = passers[0]

    notifications = Notification_Work.objects.filter(id=notification_id)
    if len(notifications) == 0:
        return status422(get_api(request), {'message': 'Notification_Work 알림({}) 가 없어요'.format(notification_id)})
    notification = notifications[0]

    employees = Employee.objects.filter(id=passer.employee_id)
    if len(employees) == 0:
        return status422(get_api(request), {'message': 'passer({}) 의 근로자 정보가 없어요.'.format(passer.employee_id)})
    elif len(employees) > 1:
        logError(get_api(request),
                 ' passer {} 의 employee {} 가 {} 개 이다.(정상은 1개)'.format(passer.id, passer.employee_id,
                                                                      len(employees)))
    employee = employees[0]
    employee_works = Works(employee.get_works())
    logSend('  - employee works: {}'.format([work for work in employee_works.data]))
    #
    # 근로자 정보에 업무를 등록 - 수락했을 경우만
    #
    if is_accept == 1:
        # 수락했을 경우
        logSend('  - 수락: works: {}'.format([work for work in employee_works.data]))
        work = Work.objects.get(id=notification.work_id)
        new_work = {'id': notification.work_id,
                    'begin': dt_str(notification.dt_begin, "%Y/%m/%d"),
                    'end': dt_str(notification.dt_end, "%Y/%m/%d"),
                    }
        if employee_works.is_overlap(new_work):
            is_accept = False
        else:
            employee_works.add(new_work)
            employee.set_works(employee_works.data)
            employee.save()
        count_work = 0
        for work in employee_works.data:
            if datetime.datetime.now() < str_to_dt(work['begin']):
                count_work += 1
        logSend('  - 예약된 업무(시작 날짜가 오늘 이후인 업무): {}'.format(count_work))
        logSend('  - works: {}'.format([work for work in employee_works.data]))
        logSend('  - name: ', employee.name)
    else:
        logSend('  - 거절: works 에 있으면 삭제')
        # 거절했을 경우 - 근로자가 업무를 가지고 있으면 삭제한다.
        if employee_works.find(notification.work_id):
            del employee_works.data[employee_works.index]
        employee.set_works(employee_works.data)
        employee.save()
    notification.delete()
    #
    # to customer server
    # 근로자가 수락/거부했음
    #
    request_data = {
        'worker_id': AES_ENCRYPT_BASE64('thinking'),
        'work_id': notification.customer_work_id,
        'employee_id': AES_ENCRYPT_BASE64(str(passer.id)),  # employee.id,
        'employee_name': employee.name,
        'employee_pNo': notification.employee_pNo,
        'is_accept': is_accept
    }
    logSend(request_data)
    response_customer = requests.post(settings.CUSTOMER_URL + 'employee_work_accept_for_employee', json=request_data)
    logSend(response_customer.json())
    if response_customer.status_code != 200:
        return ReqLibJsonResponse(response_customer)

    logSend('  - is_accept: {}'.format(is_accept))
    return REG_200_SUCCESS.to_json_response({'is_accept': is_accept})


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
            passer_info['works'] = employee.get_works()
        else:
            passer_info['name'] = '---'
            passer_info['works'] = []
        passer_info['id'] = AES_ENCRYPT_BASE64(str(passer.id))
        passer_info['pNo'] = passer.pNo
        employee_list.append(passer_info)
    return REG_200_SUCCESS.to_json_response({'passers': employee_list})


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
        logError(get_api(request), ' 비콘 등록 기능 << Beacon 설치할 때 등록되어야 하는데 왜?')
        logError(get_api(request), ' passer_id={} out 인데 어제, 오늘 기록이 없다. dt_beacon={}'.format(passer_id, dt_beacon))
        logError(get_api(request), ' passer_id={} in 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
        logError(get_api(request), ' passer_id={} in 으로 부터 12 시간이 지나서 out 을 무시한다. dt_in={}, dt_beacon={}'.format(passer_id, dt_in, dt_beacon))
        logError(get_api(request), ' passer 의 employee_id={} 에 해당하는 근로자가 없음.'.format(passer.employee_id))
        logError(get_api(request), ' passer 의 employee_id={} 에 해당하는 근로자가 한명 이상임.'.format(passer.employee_id))
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['passer_id_!', 'dt', 'is_in', 'major', 'beacons'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    passer_id = parameter_check['parameters']['passer_id']
    dt = parameter_check['parameters']['dt']
    is_in = int(parameter_check['parameters']['is_in'])
    major = parameter_check['parameters']['major']
    if request.method == 'POST':
        beacons = rqst['beacons']
    else:
        today = dt_str(datetime.datetime.now(), "%Y-%m-%d")
        beacons = [
            {'minor': 11001, 'dt_begin': '{} 08:25:30'.format(today), 'rssi': -70},
            {'minor': 11002, 'dt_begin': '{} 08:25:31'.format(today), 'rssi': -60},
            {'minor': 11003, 'dt_begin': '{} 08:25:32'.format(today), 'rssi': -50}
        ]
    logSend(beacons)
    passers = Passer.objects.filter(id=passer_id)
    if len(passers) != 1:
        return status422(get_api(request),
                         {'message': 'ServerError: Passer 에 passer_id=%s 이(가) 없거나 중복됨' % passer_id})
    passer = passers[0]

    for i in range(len(beacons)):
        # 비콘 이상 유무 확인을 위해 비콘 날짜, 인식한 근로자 앱 저장
        beacon_list = Beacon.objects.filter(major=major, minor=beacons[i]['minor'])
        logSend('  {} {}: {}'.format(major, beacons[i]['minor'], {x.id: x.dt_last for x in beacon_list}))
        if len(beacon_list) > 0:
            beacon_list.delete()
            beacon = Beacon(
                # uuid='12345678-0000-0000-0000-123456789012',
                uuid='3c06aa91-984b-be81-d8ea-82af46f4cda4',
                # 1234567890123456789012345678901234567890
                major=major,
                minor=beacons[i]['minor'],
                dt_last=dt,
                last_passer_id=passer_id,
            )
            beacon.save()
            # beacon = beacon_list[0]
            # beacon.dt_last = dt
            # beacon.last_passer_id = passer_id
            # beacon.save()
        else:
            logError(get_api(request), ' 비콘 등록 기능 << Beacon 설치할 때 등록되어야 하는데 왜?')
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
            passer_id=passer_id,
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
        is_beacon=True,
        dt=dt
    )
    new_pass.save()
    #
    # Pass_History update
    #
    passer_list = Passer.objects.filter(id=passer_id)
    if len(passer_list) == 0:
        # 출입자를 db에서 찾지 못하면
        return REG_200_SUCCESS.to_json_response({'message': '출입자로 등록되지 않았다.'})
    passer = passer_list[0]
    employee_list = Employee.objects.filter(id=passer.employee_id)  # employee_id < 0 인 경우도 잘 처리될까?
    if len(employee_list) == 0:
        # db 에 근로자 정보가 없으면 - 출입자 중에 근로자 정보가 없는 경우, 등록하지 않은 경우, 피쳐폰인 경우
        return REG_200_SUCCESS.to_json_response({'message': '근로자 정보가 없다.'})
    employee = employee_list[0]
    employee_works = Works(employee.get_works())
    if len(employee_works.data) == 0:
        # 근로자 정보에 업무가 없다.
        return REG_200_SUCCESS.to_json_response({'message': '근로자에게 배정된 업무가 없다.'})
    if not employee_works.is_active():
        # 현재 하고 있는 없무가 없다.
        return REG_200_SUCCESS.to_json_response({'message': '근로자가 현재 출퇴근하는 업무가 없다.'})
    employee_work = employee_works.data[employee_works.index]
    work_id = employee_work['id']
    dt_beacon = str_to_datetime(dt)  # datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
    year_month_day = dt_beacon.strftime("%Y-%m-%d")
    pass_histories = Pass_History.objects.filter(passer_id=passer_id, work_id=work_id, year_month_day=year_month_day)
    if not is_in:
        # out 일 경우
        if len(pass_histories) == 0:
            # out 인데 오늘 날짜 pass_history 가 없다? >> 그럼 어제 저녁에 근무 들어갔겠네!
            yesterday = dt_beacon - datetime.timedelta(days=1)
            yesterday_year_month_day = yesterday.strftime("%Y-%m-%d")
            pass_histories = Pass_History.objects.filter(passer_id=passer_id, work_id=work_id,
                                                         year_month_day=yesterday_year_month_day)
            if len(pass_histories) == 0:
                # out 인데 어제, 오늘 출입 기록이 없다? >> 에러 로그 남기고 만다.
                logError(get_api(request),
                         ' passer_id={} out 인데 어제, 오늘 기록이 없다. dt_beacon={}'.format(passer_id, dt_beacon))
                return REG_200_SUCCESS.to_json_response({'message': 'out 인데 어제 오늘 in 기록이 없다.'})
            else:
                pass_history = pass_histories[0]
        else:
            pass_history = pass_histories[0]

        dt_in = pass_history.dt_in if pass_history.dt_in_verify is None else pass_history.dt_in_verify
        if dt_in is None:
            # in beacon, in touch 가 없다? >> 에러처리는 하지 않고 기록만 한다.
            logError(get_api(request), ' passer_id={} in 기록이 없다. dt_in={}'.format(passer_id, dt_in))
        elif (dt_in + datetime.timedelta(hours=12)) < dt_beacon:
            # 출근시간 이후 12 시간이 지났으면 무시한다.
            logError(get_api(request),
                     ' passer_id={} in 으로 부터 12 시간이 지나서 out 을 무시한다. dt_in={}, dt_beacon={}'.format(passer_id, dt_in,
                                                                                                   dt_beacon))
            return REG_200_SUCCESS.to_json_response({'message': 'in 으로 부터 12 시간이 지나서 beacon out 을 무시한다.'})

        pass_history.dt_out = dt_beacon
    else:
        # in 일 경우
        if len(pass_histories) == 0:
            # 오늘 날짜 pass_history 가 없어서 새로 만든다.
            pass_history = Pass_History(
                passer_id=passer_id,
                work_id=work_id,
                year_month_day=year_month_day,
                action=0,
            )
        else:
            pass_history = pass_histories[0]

        if pass_history.dt_in is None:
            pass_history.dt_in = dt_beacon
    pass_history.save()
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
        STATUS 416
            {'message': '출근처리할 업무가 없습니다.'}  # 출근 버튼을 깜박이고 출퇴근 버튼을 모두 disable 하는 방안을 모색 중...
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'passer_id\' 가 없어요'}
            {'message':'ClientError: parameter \'dt\' 가 없어요'}
            {'message':'ClientError: parameter \'is_in\' 가 없어요'}
            {'message':'ClientError: parameter \'passer_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ServerError: Passer 에 passer_id={} 이(가) 없다'.format(passer_id)}
            {'ServerError: Employee 에 employee_id={} 이(가) 없다'.format(passer.employee_id)}
            {'message':'ClientError: parameter \'dt\' 양식을 확인해주세요.'}
    log Error
        logError(get_api(request), ' passer id: {} 중복되었다.'.format(passer_id))
        logError(get_api(request), ' employee id: {} 중복되었다.'.format(passer.employee_id))
        logError(get_api(request), ' passer_id={} out touch 인데 어제, 오늘 기록이 없다. dt_touch={}'.format(passer_id, dt_touch)
        logError(get_api(request), ' passer_id={} in 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
        logError(get_api(request), ' passer_id={} in 기록후 12시간 이상 지나서 out touch가 들어왔다. dt_in={}, dt_touch={}'.format(passer_id, dt_in, dt_touch))
        logError(get_api(request), ' passer 의 employee_id={} 에 해당하는 근로자가 없음.'.format(passer.employee_id))
        logError(get_api(request), ' passer 의 employee_id={} 에 해당하는 근로자가 한명 이상임.'.format(passer.employee_id))
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['passer_id_!', 'dt', 'is_in'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    passer_id = parameter_check['parameters']['passer_id']
    dt = parameter_check['parameters']['dt']
    is_in = int(parameter_check['parameters']['is_in'])

    passers = Passer.objects.filter(id=passer_id)
    if len(passers) == 0:
        return status422(get_api(request),
                         {'message': 'ServerError: Passer 에 passer_id={} 이(가) 없다'.format(passer_id)})
    elif len(passers) > 1:
        logError(get_api(request), ' passer id: {} 중복되었다.'.format(passer_id))
    passer = passers[0]
    employees = Employee.objects.filter(id=passer.employee_id)
    if len(employees) == 0:
        return status422(get_api(request),
                         {'message': 'ServerError: Employee 에 employee_id={} 이(가) 없다'.format(passer.employee_id)})
    elif len(employees) > 1:
        logError(get_api(request), ' employee id: {} 중복되었다.'.format(passer.employee_id))
    employee = employees[0]
    employee_works = Works(employee.get_works())
    if not employee_works.is_active():
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '출근처리할 업무가 없습니다.'})
    work_id = employee_works.data[employee_works.index]['id']
    # 통과 기록 저장
    new_pass = Pass(
        passer_id=passer_id,
        is_in=is_in,
        is_beacon=False,
        dt=dt,
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
            yesterday_pass_histories = Pass_History.objects.filter(passer_id=passer_id,
                                                                   year_month_day=yesterday_year_month_day)
            if len(yesterday_pass_histories) == 0:
                logError(get_api(request),
                         ' passer_id={} out touch 인데 어제, 오늘 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
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
                        work_id=work_id,
                    )
                else:
                    logSend('  어제 오늘 출퇴근 기록이 없고 9시 이후라 오늘 날짜로 처리한다.')
                    # 오늘 pass_history 가 없어서 새로 만든다.
                    pass_history = Pass_History(
                        passer_id=passer_id,
                        year_month_day=year_month_day,
                        action=0,
                        work_id=work_id,
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
                    work_id=work_id,
                )
        else:
            logSend('  오늘 출퇴근 기록이 있어서 오늘에 넣는다.')
            # 오늘 출퇴근이 있으면 오늘 처리한다.
            pass_history = pass_histories[0]

        pass_history.dt_out_verify = dt_touch
        pass_history.dt_out_em = dt_touch
        dt_in = pass_history.dt_in if pass_history.dt_in_verify is None else pass_history.dt_in_verify
        if dt_in is None:
            # in beacon, in touch 가 없다? >> 에러처리는 하지 않고 기록만 한다.
            logError(get_api(request), ' passer_id={} in 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
        elif (dt_in + datetime.timedelta(hours=12)
              + datetime.timedelta(hours=pass_history.overtime // 2 + pass_history.overtime % 2 * .5)) < dt_touch:
            # 출근시간 이후 12 시간이 지나서 out touch가 들어왔다. >> 에러처리는 하지 않고 기록만 한다.
            logError(get_api(request),
                     ' passer_id={} in 기록후 12시간 이상 지나서 out touch가 들어왔다. dt_in={}, dt_touch={}'.format(passer_id, dt_in,
                                                                                                      dt_touch))
    else:
        # in touch 일 경우
        if len(pass_histories) == 0:
            # 오늘 날짜 pass_history 가 없어서 새로 만든다.
            pass_history = Pass_History(
                passer_id=passer_id,
                year_month_day=year_month_day,
                action=0,
                work_id=work_id,
            )
        else:
            pass_history = pass_histories[0]

        if pass_history.dt_in_verify is None:
            pass_history.dt_in_verify = dt_touch
            pass_history.dt_in_em = dt_touch

    #
    # 정상, 지각, 조퇴 처리
    #
    update_pass_history(pass_history)

    pass_history.save()
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def pass_sms(request):
    """
    문자로 출근/퇴근, 업무 수락/거절: 스마트폰이 아닌 사용자가 문자로 출근(퇴근), 업무 수락/거절을 서버로 전송
      - 수락/거절은 복수의 수락/거절에 모두 답하는 문제를 안고 있다.
      - 수락/거절하게 되먼 수락/거절한 업무가 여러개라도 모두 sms 로 보낸다. (업무, 담당자, 담당자 전화번호, 기간)
      - 수락은 이름이 안들어 오면 에러처리한다. (2019/05/22 거절에 이름 확인 기능 삭제)
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
        STATUS 422
            {'message': '수락, 거절, 출근, 퇴근 외에 들어오는거 머지? pNo = {}, sms = \"{}\"'.format(phone_no, sms)}
            {'message': 'Employee 에 passer ({}) 는 있고 employee ({})는 없다.'.format(passer.employee_id)}
            {'message': '근무할 업무가 없다.'.format()}
    error log
        logError(get_api(request), ' 전화번호({})가 근로자로 등록되지 않았다.'.format(phone_format(phone_no)))
        logError(get_api(request), ' Employee 에 passer ({}) 는 있고 employee ({})는 여러개 머지?'.format(passer.id, passer.employee_id))
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    phone_no = no_only_phone_no(rqst['phone_no'])  # 전화번호가 없을 가능성이 없다.
    dt = rqst['dt']
    sms = rqst['sms']
    logSend('---parameter: phone_no: {}, dt: {}, sms: {}'.format(phone_no, dt, sms))

    sms = sms.replace('승락', '수락').replace('거부', '거절')
    if ('수락 ' in sms) or ('거절' in sms):
        # notification_work 에서 전화번호로 passer_id(notification_work 의 employee_id) 를 얻는다.
        notification_work_list = Notification_Work.objects.filter(employee_pNo=phone_no)
        # 하~~~ 피처폰인데 업무 요청 여러개가 들어오면 처리할 방법이 없네... > 에이 모르겠다 몽땅 보내!!!
        # 수락한 내용을 SMS 로 보내줘야할까? (문자를 무한사용? 답답하네...)
        is_accept = True if '수락 ' in sms else False
        if is_accept:
            extract_sms = [element for element in sms.split(' ') if not ((len(element) == 2) and (element == '수락'))]
            if len(extract_sms) > 1:
                logError(get_api(request), ' sms 수락 문자에 이름({})이 여러개?'.format(extract_sms))
            name = ''.join(extract_sms)
            logSend('  name = {}'.format(name))
            if len(name) < 2:
                # 이름이 2자가 안되면 SMS 로 이름이 안들어왔다고 보내야 하나? (휴~~~)
                logError(get_api(request), ' 이름이 너무 짧다. pNo = {}, sms = \"{}\"'.format(phone_no, sms))
                sms_data = {
                    'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
                    'user_id': 'yuadocjon22',
                    'sender': settings.SMS_SENDER_PN,
                    'receiver': phone_no,
                    'msg_type': 'SMS',
                    'msg': '이지체크\n'
                           '수락 문자를 보내실 때는 꼭 이름을 같이 넣어주세요.\n'
                           '예시 \"수락 홍길동\"',
                }
                rSMS = requests.post('https://apis.aligo.in/send/', data=sms_data)
                logSend('SMS result', rSMS.json())
                return status422(get_api(request),
                                 {'message': '이름이 너무 짧다. pNo = {}, sms = \"{}\"'.format(phone_no, sms)})
        else:
            extract_sms = [element for element in sms.split(' ') if not ((len(element) == 2) and (element == '거절'))]
            if len(extract_sms) > 1:
                logError(get_api(request), ' sms 수락 문자에 이름({})이 여러개?'.format(extract_sms))
            name = ''.join(extract_sms)
            logSend('  name = {}'.format(name))
            if len(name) == 0:
                name = '-----'
        sms_data = {
            'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
            'user_id': 'yuadocjon22',
            'sender': settings.SMS_SENDER_PN,
            'receiver': phone_no,
            'msg_type': 'SMS',
        }
        logSend('  name: \'{}\''.format(name))
        for notification_work in notification_work_list:
            # dt_answer_deadline 이 지났으면 처리하지 않고 notification_list 도 삭제
            if notification_work.dt_answer_deadline < datetime.datetime.now():
                notification_work.delete()
                continue

            # 근로자를 강제로 새로 등록한다. (으~~~ 괜히 SMS 기능 넣었나?)
            passer_list = Passer.objects.filter(pNo=phone_no)
            if len(passer_list) == 0:
                # 이 전화번호를 사용하는 근로자가 없다. > 근로자, 출입자 모두 만든다.
                employee = Employee(
                    name=name,
                )
                employee.save()
                logSend('---1 name: {}, phone: {} employee id {}'.format(name, phone_no, employee.id))
                passer = Passer(
                    pNo=phone_no,
                    pType=30,  # 30: 피쳐폰, 10: 아이폰, 20: 안드로이드폰
                    employee_id=employee.id,
                )
                passer.save()
                logSend('---2 name: {}, phone: {}'.format(name, phone_no))
            else:
                # 출입자(passer) 는 있다.
                if len(passer_list) > 1:
                    logError(get_api(request), ' 전화번호({})가 중복되었다.'.format(phone_no))
                passer = passer_list[0]
                employee_list = Employee.objects.filter(id=passer.employee_id)
                if len(employee_list) == 0:
                    # 그런데 출입자와 연결된 근로자가 없다. > 근로자만 새로 만들어 연결한다.
                    logSend('---3 name: {}, phone: {}'.format(name, phone_no))
                    logError(get_api(request),
                             ' passer: {} 의 employee: {} 없어서 새로 만든다.'.format(passer.id, passer.employee_id))
                    employee = Employee(
                        name=name,
                    )
                    employee.save()
                    passer.employee_id = employee.id
                    passer.save()
                else:
                    # 출입자, 근로자 다 있고 연결도 되어있다.
                    logSend('---4 name: {}, phone: {}'.format(name, phone_no))
                    if len(employee_list) > 1:
                        logError(get_api(request), ' employee({})가 중복되었다.'.format(passer.employee_id))
                    employee = employee_list[0]
                    # employee.name = name
                    # employee.save()

            accept_infor = {
                'passer_id': AES_ENCRYPT_BASE64(str(passer.id)),
                'notification_id': AES_ENCRYPT_BASE64(str(notification_work.id)),
                'is_accept': '1' if is_accept else '0',
            }
            r = requests.post(settings.EMPLOYEE_URL + 'notification_accept', json=accept_infor)
            logSend({'url': r.url, 'POST': accept_infor, 'STATUS': r.status_code, 'R': r.json()})
            is_accept = r.json()['is_accept']

            if r.status_code == 416:
                return ReqLibJsonResponse(r)

            if r.status_code == 200 and is_accept:
                work = Work.objects.get(id=notification_work.work_id)
                sms_data['msg'] = '수락됐어요\n{}-{}\n{} ~ {}\n{} {}'.format(work.work_place_name,
                                                                        work.work_name_type,
                                                                        work.begin,
                                                                        work.end,
                                                                        work.staff_name,
                                                                        phone_format(work.staff_pNo))
                rSMS = requests.post('https://apis.aligo.in/send/', data=sms_data)
                logSend('SMS result', rSMS.json())
        return REG_200_SUCCESS.to_json_response()

    elif '출근' in sms:
        is_in = True
    elif '퇴근' in sms:
        is_in = False
    else:
        logError(get_api(request), ' 수락, 거절, 출근, 퇴근 외에 들어오는거 머지? pNo = {}, sms = \"{}\"'.format(phone_no, sms))
        return status422(get_api(request),
                         {'message': '수락, 거절, 출근, 퇴근 외에 들어오는거 머지? pNo = {}, sms = \"{}\"'.format(phone_no, sms)})

    passers = Passer.objects.filter(pNo=phone_no)
    if len(passers) == 0:
        logError(get_api(request), ' 전화번호({})가 근로자로 등록되지 않았다.'.format(phone_format(phone_no)))
        return REG_541_NOT_REGISTERED.to_json_response()
    passer = passers[0]
    passer_id = passer.id
    dt_sms = str_to_datetime(dt)
    logSend(' {}  {}  {}  {}'.format(phone_no, passer.id, dt, is_in))
    employees = Employee.objects.filter(id=passer.employee_id)
    if len(employees) == 0:
        logError(get_api(request),
                 ' Employee 에 passer ({}) 는 있고 employee ({})는 없다.'.format(passer.id, passer.employee_id))
        return status422(get_api(request),
                         {'message': 'Employee 에 passer ({}) 는 있고 employee ({})는 없다.'.format(passer.employee_id)})
    elif len(employees) > 1:
        logError(get_api(request),
                 ' Employee 에 passer ({}) 는 있고 employee ({})는 여러개 머지?'.format(passer.id, passer.employee_id))
    employee = employees[0]
    employee_works = Works(employee.get_works())
    if not employee_works.is_active():
        logError(get_api(request), '근무할 업무가 없다.'.format())
        return status422(get_api(request), {'message': '근무할 업무가 없다.'.format()})
    employee_work = employee_works.data[employee_works.index]
    work_id = employee_work['id']
    new_pass = Pass(
        passer_id=passer.id,
        is_in=is_in,
        is_beacon=False,
        dt=dt_sms,
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
                logError(get_api(request),
                         ' passer_id={} out touch 인데 어제, 오늘 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
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
                        work_id=work_id,
                    )
                else:
                    # 오늘 pass_history 가 없어서 새로 만든다.
                    pass_history = Pass_History(
                        passer_id=passer_id,
                        year_month_day=year_month_day,
                        action=0,
                        work_id=work_id,
                    )
            else:
                pass_history = pass_histories[0]
        else:
            pass_history = pass_histories[0]

        pass_history.dt_out_verify = dt_touch
        pass_history.dt_out_em = dt_touch
        dt_in = pass_history.dt_in if pass_history.dt_in_verify is None else pass_history.dt_in_verify
        if dt_in is None:
            # in beacon, in touch 가 없다? >> 에러처리는 하지 않고 기록만 한다.
            logError(get_api(request), ' passer_id={} in 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
        if (dt_in + datetime.timedelta(hours=12)) < dt_touch:
            # 출근시간 이후 12 시간이 지났서 out touch가 들어왔다. >> 에러처리는 하지 않고 기록만 한다.
            logError(get_api(request),
                     ' passer_id={} in 기록후 12시간 이상 지나서 out touch가 들어왔다. dt_in={}, dt_touch={}'.format(passer_id, dt_in,
                                                                                                      dt_touch))
    else:
        # in touch 일 경우
        if len(pass_histories) == 0:
            # 오늘 날짜 pass_history 가 없어서 새로 만든다.
            pass_history = Pass_History(
                passer_id=passer_id,
                year_month_day=year_month_day,
                action=0,
                work_id=work_id,
            )
        else:
            pass_history = pass_histories[0]

        if pass_history.dt_in_verify is None:
            pass_history.dt_in_verify = dt_touch
            pass_history.dt_in_em = dt_touch

    #
    # 정상, 지각, 조퇴 처리
    #
    update_pass_history(pass_history)

    pass_history.save()
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
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['passer_id_!', 'dt', 'is_in', 'major', 'beacons'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

    passer_id = parameter_check['parameters']['passer_id']
    dt = parameter_check['parameters']['dt']
    is_in = parameter_check['parameters']['is_in']
    major = parameter_check['parameters']['major']
    beacons = parameter_check['parameters']['beacons']

    passers = Passer.objects.filter(id=passer_id)
    if len(passers) != 1:
        logError(get_api(request), ' ServerError: Passer 에 passer_id=%s 이(가) 없거나 중복됨' % passer_id)
        return status422(get_api(request), {'message': 'ServerError: 근로자가 등록되어 있지 않거나 중복되었다.'})

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
        STATUS 416 # 앱에서 아예 리셋을 할 수도 있겠다.
            {'message': '계속 이 에러가 나면 앱을 다시 설치해야합니다.'}
        STATUS 542
            {'message':'전화번호가 이미 등록되어 있어 사용할 수 없습니다.\n고객센터로 문의하십시요.'}
        STATUS 552
            {'message': '인증번호는 3분에 한번씩만 발급합니다.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'phone_no\' 가 없어요'}
            {'message':'ClientError: parameter \'passer_id\' 가 정상적인 값이 아니예요.'}

    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['phone_no'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    phone_no = no_only_phone_no(parameter_check['parameters']['phone_no'])

    parameter_check = is_parameter_ok(rqst, ['passer_id_!'])
    if parameter_check['is_ok']:
        # 기존에 등록된 근로자 일 경우 - 전화번호를 변경하려 한다.
        passer_id = parameter_check['parameters']['passer_id']
        passer = Passer.objects.get(id=passer_id)
        if passer.pNo == phone_no:
            return REG_200_SUCCESS.to_json_response({'message': '변경하려는 전화번호가 기존 전화번호와 같습니다.'})
        # 등록 사용자가 앱에서 전화번호를 바꾸려고 인증할 때
        # 출입자 아이디(passer_id) 의 전화번호 외에 전화번호가 있으면 전화번호(542)처리
        passers = Passer.objects.filter(pNo=phone_no)
        logSend(('  - phone: {}'.format([(passer.pNo, passer.id) for passer in passers])))
        if len(passers) > 0:
            logError(get_api(request), ' phone: ({}, {}), duplication phone: {}'
                     .format(passer.pNo, passer.id, [(passer.pNo, passer.id) for passer in passers]))
            return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response(
                {'message': '전화번호가 이미 등록되어 있어 사용할 수 없습니다.\n고객센터로 문의하십시요.'})
        passer.pNo = phone_no
    else:
        if parameter_check['is_decryption_error']:
            # passer_id 가 있지만 암호 해독과정에서 에러가 났을 때
            logError(get_api(request), parameter_check['results'])
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '계속 이 에러가 나면 앱을 다시 설치해야합니다.'})
        # 새로 근로자 등록을 하는 경우 - 전화번호 중복을 확인해야한다.
        # 신규 등록일 때 전화번호를 사용하고 있으면 에러처리
        passers = Passer.objects.filter(pNo=phone_no)
        if len(passers) == 0:
            passer = Passer(
                pNo=phone_no
            )
        else:
            passer = passers[0]

    if (passer.dt_cn is not None) and (datetime.datetime.now() < passer.dt_cn):
        # 3분 이내에 인증번호 재요청하면
        logSend('  - dt_cn: {}, today: {}'.format(passer.dt_cn, datetime.datetime.now()))
        return REG_552_NOT_ENOUGH_TIME.to_json_response({'message': '인증번호는 3분에 한번씩만 발급합니다.'})

    certificateNo = random.randint(100000, 999999)
    if settings.IS_TEST:
        certificateNo = 201903
    passer.cn = certificateNo
    passer.dt_cn = datetime.datetime.now() + datetime.timedelta(minutes=3)
    passer.save()
    logSend('  - phone: {} certificateNo: {}'.format(phone_no, certificateNo))

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
        return REG_200_SUCCESS.to_json_response(rData)

    rSMS = requests.post('https://apis.aligo.in/send/', data=rData)
    # print(rSMS.status_code)
    # print(rSMS.headers['content-type'])
    # print(rSMS.text)
    # print(rSMS.json())
    logSend('  - ', json.dumps(rSMS.json(), cls=DateTimeEncoder))
    # rJson = rSMS.json()
    # rJson['vefiry_no'] = str(certificateNo)

    # response = HttpResponse(json.dumps(rSMS.json(), cls=DateTimeEncoder))
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
            'phone_type' : 'A', # 안드로이드 폰, 'i': 아이폰
            'push_token' : 'push token',
        }
    response
        STATUS 416
            {'message': '잘못된 전화번호입니다.'}
            {'message': '인증번호 요청을 해주세요.'}
        STATUS 550
            {'message': '인증시간이 지났습니다.\n다시 인증요청을 해주세요.'} # 인증시간 3분
            {'message': '인증번호가 틀립니다.'}
        STATUS 200 # 기존 근로자
        {
            'id': '암호화된 id 그대로 보관되어서 사용되어야 함',
            'name': '홍길동',                      # 필수: 없으면 입력 받는 화면 표시 (기존 근로자 일 때: 없을 수 있음 - 등록 중 중단한 경우)
            'work_start': '09:00',               # 필수: 없으면 입력 받는 화면 표시 (기존 근로자 일 때: 없을 수 있음 - 등록 중 중단한 경우)
            'working_time': '12',                # 필수: 없으면 입력 받는 화면 표시 (기존 근로자 일 때: 없을 수 있음 - 등록 중 중단한 경우)
            'rest_time': -1,                     # 필수: 없으면 입력 받는 화면 표시 (기존 근로자 일 때: 없을 수 있음 - 등록 중 중단한 경우)
            'work_start_alarm': 'X',             # 필수: 없으면 입력 받는 화면 표시 (기존 근로자 일 때: 없을 수 있음 - 등록 중 중단한 경우)
            'work_end_alarm': 'X',               # 필수: 없으면 입력 받는 화면 표시 (기존 근로자 일 때: 없을 수 있음 - 등록 중 중단한 경우)
            'bank': '기업은행',                     # 기존 근로자 일 때 (없을 수 있음 - 등록 중 중단한 경우)
            'bank_account': '12300000012000',     # 기존 근로자 일 때 (없을 수 있음 - 등록 중 중단한 경우)
            'default_time':
                [
                    {'work_start': '09:00', 'working_time': '08', 'rest_time': '01:00'},
                    {'work_start': '07:00', 'working_time': '08', 'rest_time': '00:00'},
                    {'work_start': '15:00', 'working_time': '08', 'rest_time': '00:00'},
                    {'work_start': '23:00', 'working_time': '08', 'rest_time': '00:00'},
                ],
            'bank_list': ['국민은행', ... 'NH투자증권']
        }
        STATUS 201 # 새로운 근로자 : 이름, 급여 이체 은행, 계좌번호를 입력받아야 함
        {
            'id': '암호화된 id 그대로 보관되어서 사용되어야 함',
            'default_time':
                [
                    {'work_start': '09:00', 'working_time': '08', 'rest_time': '01:00'},
                    {'work_start': '18:00', 'working_time': '08', 'rest_time': '00:00'},
                    {'work_start': '02:00', 'working_time': '08', 'rest_time': '00:00'}
                ],
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
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['phone_no', 'cn', 'phone_type'])  # , 'push_token'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    phone_no = parameter_check['parameters']['phone_no']
    cn = parameter_check['parameters']['cn']
    phone_type = parameter_check['parameters']['phone_type']
    push_token = rqst['push_token']
    phone_no = no_only_phone_no(phone_no)

    passers = Passer.objects.filter(pNo=phone_no)
    if len(passers) > 1:
        logError(get_api(request), ' 출입자 등록된 전화번호 중복: {}'.format([passer.id for passer in passers]))
    elif len(passers) == 0:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '잘못된 전화번호입니다.'})
    passer = passers[0]
    if passer.dt_cn == 0:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '인증번호 요청을 해주세요.'})

    if passer.dt_cn < datetime.datetime.now():
        logSend('  인증 시간: {} < 현재 시간: {}'.format(passer.dt_cn, datetime.datetime.now()))
        return REG_550_CERTIFICATION_NO_IS_INCORRECT.to_json_response({'message': '인증시간이 지났습니다.\n다시 인증요청을 해주세요.'})
    else:
        cn = cn.replace(' ', '')
        logSend('  인증번호: {} vs 근로자 입력 인증번호: {}, settings.IS_TEST'.format(passer.cn, cn, settings.IS_TEST))
        if not settings.IS_TEST and passer.cn != int(cn):
            # if passer.cn != int(cn):
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
            logError(get_api(request), ' 발생하면 안됨: passer.employee_id 의 근로자가 employee 에 없다. (새로 만듦)')
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
                result['work_start'] = employee.work_start
                result['working_time'] = employee.working_time
                result['rest_time'] = employee.rest_time
                result['work_start_alarm'] = employee.work_start_alarm
                result['work_end_alarm'] = employee.work_end_alarm
                result['bank'] = employee.bank
                result['bank_account'] = employee.bank_account

    if status_code == 200 or status_code == 201:
        notification_list = Notification_Work.objects.filter(employee_pNo=phone_no)
        for notification in notification_list:
            notification.employee_id = employee.id
            notification.save()
        result['default_time'] = [
                    {'work_start': '09:00', 'working_time': '08', 'rest_time': '01:00'},
                    {'work_start': '07:00', 'working_time': '08', 'rest_time': '00:00'},
                    {'work_start': '15:00', 'working_time': '08', 'rest_time': '00:00'},
                    {'work_start': '23:00', 'working_time': '08', 'rest_time': '00:00'},
                ]

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
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def update_my_info(request):
    """
    근로자 정보 변경 : 근로자의 정보를 변경한다.
    - 근무시작시간, 근무시간, 휴계시간, 출근알람, 퇴근 알람 각각 변경 가능 (2019-08-05)
    - 은행과 계좌번호는 항상 같이 들어와야한다. (2019-08-05)
        주)     로그인이 있으면 앱 시작할 때 화면 표출
            항목이 비어있으면 처리하지 않지만 비워서 보내야 한다.
    http://0.0.0.0:8000/employee/update_my_info?passer_id=qgf6YHf1z2Fx80DR8o/Lvg&name=박종기&bank=기업은행&bank_account=00012345600123&pNo=010-2557-3555
    POST
        {
            'passer_id': '서버로 받아 저장해둔 출입자 id',
            'name': '이름',
            'bank': '기업은행',
            'bank_account': '12300000012000',
            'pNo': '010-2222-3333',     # 추후 SMS 확인 절차 추가

            'work_start':'08:00',       # 출근시간: 24시간제 표시
            'working_time':'8',        # 근무시간: 시간 4 ~ 12
            'rest_time': '01:00'        # 휴계시간: 시간 00:00 ~ 06:00, 간격 30분

            'work_start_alarm':'1:00',  # '-60'(한시간 전), '-30'(30분 전), 'X'(없음) 셋중 하나로 보낸다.
            'work_end_alarm':'30',      # '-30'(30분 전), '0'(정각), 'X'(없음) 셋중 하나로 보낸다.
        }
    response
        STATUS 200
            {'message':'정상적으로 처리되었습니다.'}
        STATUS 416
            {'message':'이름은 2자 이상이어야 합니다.'}
            {'message':'전화번호를 확인해 주세요.'}
            {'message':'계좌번호가 너무 짧습니다.\n다시 획인해주세요.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'passer_id\' 가 없어요'}
            {'message':'ClientError: parameter \'passer_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ServerError: 근로자 id 확인이 필요해요.'}
            {'message': '은행과 계좌는 둘다 들어와야 한다.'}
            {'message': '출근시간, 근무시간, (휴계시간)은 같이 들어와야한다.'}
            {'message': '출근 시간({}) 양식(hh:mm)이 잘못됨'.format(work_start)}
            {'message': '근무 시간({}) 양식이 잘못됨'.format(working_time)}
            {'message': '근무 시간(4 ~ 12) 범위 초과'}
            {'message': '휴계 시간({}) 양식(hh:mm)이 잘못됨'.format(rest_time)})
            {'message': '휴계 시간(00:30 ~ 06:00) 범위 초과 (주:양식도 확인)'})
            {'message': '출근 알람({})이 틀린 값이예요.'.format(work_start_alarm)}
            {'message': '퇴근 알람({})이 틀린 값이예요.'.format(work_end_alarm)}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['passer_id_!'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

    passer_id = parameter_check['parameters']['passer_id']
    logSend('   request passer_id: {}'.format(passer_id))

    try:
        passer = Passer.objects.get(id=passer_id)
    except Exception as e:
        # 출입자에 없는 사람을 수정하려는 경우
        logError(get_api(request), ' passer_id = {} Passer 에 없다.\n{}'.format(passer_id, e))
        return status422(get_api(request), {'message': 'ServerError: 근로자 id 확인이 필요해요.'})
    logSend('  passer: {}'.format({x: passer.__dict__[x] for x in passer.__dict__.keys() if not x.startswith('_')}))

    try:
        employee = Employee.objects.get(id=passer.employee_id)
        # employee = Employee.objects.filter(id=passer.employee_id)
    except Exception as e:
        # 출입자에 근로자 정보가 없는 경우
        logError(get_api(request), ' passer.employee_id = {} Employee 에 없다.\n{}'.format(passer.employee_id, e))
        return status422(get_api(request), {'message': 'ServerError: 근로자 id 확인이 필요해요.'})
    logSend('  employee: {}'.format({x: employee.__dict__[x] for x in employee.__dict__.keys() if not x.startswith('_')}))

    change_log = "UPDATE EMPLOYEE"
    is_update_customer = False
    # 고객 서버 업데이트: name, phone number
    update_employee_data = {}
    if 'name' in rqst:
        if len(rqst['name']) < 2:
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '이름은 2자 이상이어야 합니다.'})
        change_log = '{}  name: {} > {}'.format(change_log, employee.name, rqst['name'])
        employee.name = rqst['name']
        logSend('  update name: {}'.format(employee.name))
        # 고객 서버 update data
        is_update_customer = True
        update_employee_data['name'] = employee.name

    if 'pNo' in rqst:
        pNo = no_only_phone_no(rqst['pNo'])
        if len(pNo) < 9:
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '전화번호를 확인해 주세요.'})
        change_log = '{}  pNo: {} > {}'.format(change_log, passer.pNo, pNo)
        passer.pNo = pNo
        logSend('  update phone number: {}'.format(passer.pNo))
        # 고객 서버 update data
        is_update_customer = True
        update_employee_data['pNo'] = pNo

    if 'bank' in rqst or 'bank_account' in rqst:
        if 'bank' not in rqst or 'bank_account' not in rqst:
            return status422(get_api(request), {'message': '은행과 계좌는 둘다 들어와야 한다.'})
        if len(rqst['bank_account']) < 5:
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '계좌번호가 너무 짧습니다.\n다시 획인해주세요.'})
        change_log = '{}  bank: {} > {}, bank_account: {} > {}'.format(change_log, employee.bank, rqst['bank'],
                                                                      employee.bank_account, rqst['bank_account'])
        employee.bank = rqst['bank']
        employee.bank_account = rqst['bank_account']
        logSend('  update bank: {}, account: {}'.format(employee.bank, employee.bank_account))

    if 'work_start' in rqst or 'working_time' in rqst or 'rest_time' in rqst:
        if 'work_start' not in rqst or 'working_time' not in rqst: # or 'rest_time' not in rqst:
            return status422(get_api(request), {'message': '출근시간, 근무시간, (휴계시간)은 같이 들어와야한다.'})

    if 'work_start' in rqst:
        work_start = rqst['work_start']
        try:
            dt_work_start = datetime.datetime.strptime('2019-01-01 ' + work_start + ':00', "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            return status422(get_api(request), {'message': '출근 시간({}) 양식(hh:mm)이 잘못됨'.format(work_start)})
        employee.work_start = work_start

    if 'working_time' in rqst:
        working_time = rqst['working_time']
        try:
            int_working_time = int(working_time)
        except Exception as e:
            return status422(get_api(request), {'message': '근무 시간({}) 양식이 잘못됨'.format(working_time)})
        if not (4 <= int_working_time <= 12):
            return status422(get_api(request), {'message': '근무 시간(4 ~ 12) 범위 초과'})
        employee.working_time = working_time
        #
        # App 에서 휴계시간(rest_time)을 처리하기 전 한시적 기능
        #   rest_time 이 없을 때는 4시간당 30분으로 계산해서 휴계시간을 넣는다.
        if 'rest_time' not in rqst:
            int_rest_time = int_working_time // 4
            rest_time = '{0:02d}:{1:02d}'.format(int_rest_time // 2, (int_rest_time % 2) * 30)
            employee.rest_time = rest_time
            # 데이터 분석 결과 근로자는 휴게시간을 제외한 순 근로시간을 넣고 있기 때문에 근무시간에 휴게시간을 뺄 필요가 없다.
            # employee.working_time = '{}'.format(int_working_time - int_rest_time / 2)

    if 'rest_time' in rqst:
        rest_time = rqst['rest_time']
        try:
            dt_rest_time = datetime.datetime.strptime('2019-01-01 ' + rest_time + ':00', "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            return status422(get_api(request), {'message': '휴계 시간({}) 양식(hh:mm)이 잘못됨'.format(rest_time)})
        if not (str_to_datetime('2019-01-01 00:30:00') <= dt_rest_time <= str_to_datetime('2019-01-01 06:00:00')):
            return status422(get_api(request), {'message': '휴계 시간(00:30 ~ 06:00) 범위 초과 (주:양식도 확인)'})
        employee.rest_time = rest_time

    if 'work_start_alarm' in rqst:
        work_start_alarm = rqst['work_start_alarm']
        if work_start_alarm not in ['-60', '-30', 'X']:
            return status422(get_api(request), {'message': '출근 알람({})이 틀린 값이예요.'.format(work_start_alarm)})
        employee.work_start_alarm = rqst['work_start_alarm']

    if 'work_end_alarm' in rqst:
        work_end_alarm = rqst['work_end_alarm']
        if work_end_alarm not in ['-30', '0', 'X']:
            return status422(get_api(request), {'message': '퇴근 알람({})이 틀린 값이예요.'.format(work_end_alarm)})
        employee.work_end_alarm = rqst['work_end_alarm']
    #
    # to customer server
    # 고객 서버에 근로자 이름, 전화번호 변경 적용
    #
    if is_update_customer:
        update_employee_data['worker_id'] = AES_ENCRYPT_BASE64('thinking')
        update_employee_data['passer_id'] = AES_ENCRYPT_BASE64(str(passer.id))
        response_customer = requests.post(settings.CUSTOMER_URL + 'update_employee_for_employee', json=update_employee_data)
        if response_customer.status_code != 200:
            logError(get_api(request), ' 고객서버 데이터 변경 중 에러: {}'.format(response_customer.json()))
            return ReqLibJsonResponse(response_customer)
    employee.save()
    passer.save()
    if len(change_log) > 15:
        logError(change_log)

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def my_work_list(request):
    """
    근로자의 진행중이거나 예정된 업무 요청
    http://0.0.0.0:8000/employee/my_work_list?passer_id=qgf6YHf1z2Fx80DR8o/Lvg
    POST
        {
            'passer_id': '서버로 받아 저장해둔 출입자 id',
        }
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "works": [
                {
                  "begin": "2019/05/20",
                  "end": "2019/07/18",
                  "work_place_name": "대덕기공 출입시스템",
                  "work_name_type": "비콘 시험 (주간 오후)",
                  "staff_name": "이요셉",
                  "staff_pNo": "01024505942"
                },
                ......
              ]
            }
        STATUS 422 # 개발자 수정사항
            {'message': 'ClientError: parameter \'passer_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'passer_id\' 가 정상적인 값이 아니예요.'}
            {'message': '서버에 등록되지 않은 출입자 입니다.\n앱이 리셋됩니다.'}
            {'message': '서버에 출입자 정보가 없어요.\n앱이 리셋됩니다.'}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['passer_id_!'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

    passer_id = parameter_check['parameters']['passer_id']
    logSend('  - passer_id: ' + passer_id)
    passers = Passer.objects.filter(id=passer_id)
    if len(passers) != 1:
        # 출입자에 없는 사람을 수정하려는 경우
        logError(get_api(request), ' passer_id = {} Passer 에 없다.(리셋 메세지)'.format(passer_id))
        return status422(get_api(request), {'message': '서버에 등록되지 않은 출입자 입니다.\n앱이 리셋됩니다.'})
    passer = passers[0]
    if passer.employee_id == -1:
        return REG_200_SUCCESS.to_json_response({'works': []})
    employees = Employee.objects.filter(id=passer.employee_id)
    if len(employees) != 1:
        # 출입자의 근로자 정보가 없다.
        logError(get_api(request), ' employee_id = {} Employee 에 없다.(리셋 메세지)'.format(passer.employee_id))
        return status422(get_api(request), {'message': '서버에 출입자 정보가 없어요.\n앱이 리셋됩니다.'})
    employee = employees[0]
    employee_works = Works(employee.get_works())
    work_list = []

    if len(employee_works.data) > 0:
        work_id_list = [work['id'] for work in employee_works.data]
        work_list_db = Work.objects.filter(id__in=work_id_list)
        for work in employee_works.data:
            for work_db in work_list_db:
                if work['id'] == work_db.id:
                    new_work = {'work_id': work['id'],
                                'work_place_name': work_db.work_place_name,
                                'work_name_type': work_db.work_name_type,
                                'staff_name': work_db.staff_name,
                                'staff_pNo': phone_format(work_db.staff_pNo)
                                }
                    if len(work['begin']) == 0:
                        new_work['begin'] = work_db.begin
                    else:
                        new_work['begin'] = work['begin']
                    if len(work['end']) == 0:
                        new_work['end'] = work_db.end
                    else:
                        new_work['end'] = work['end']

                    # del new_work['work_id']  # 시험할 때만
                    work_list.append(new_work)
                    continue
    return REG_200_SUCCESS.to_json_response({'works': work_list})


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
        logError(get_api(request), ' passer_ids={}, year_month_day = {} 에 해당하는 출퇴근 기록이 없다.'.format(employee_ids, year_month_day))

        logError(get_api(request), ' passer_id={} out touch 인데 어제, 오늘 기록이 없다. dt_touch={}'.format(passer_id, dt_touch)
        logError(get_api(request), ' passer_id={} in 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
        logError(get_api(request), ' passer_id={} in 기록후 12시간 이상 지나서 out touch가 들어왔다. dt_in={}, dt_touch={}'.format(passer_id, dt_in, dt_touch))
        logError(get_api(request), ' passer 의 employee_id={} 에 해당하는 근로자가 없음.'.format(passer.employee_id))
        logError(get_api(request), ' passer 의 employee_id={} 에 해당하는 근로자가 한명 이상임.'.format(passer.employee_id))
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    #
    # 서버 대 서버 통신으로 상대방 서버가 등록된 서버인지 확인 기능 추가가 필요하다.
    #
    # if 'employees' not in rqst:
    #     return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': 'ClientError: parameter \'employees\' 가 없어요'})
    # employees = rqst['employees']
    # parameter_check = is_parameter_ok(rqst, ['year_month_day', 'work_id'])
    parameter_check = is_parameter_ok(rqst, ['employees', 'year_month_day', 'work_id'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    employees = parameter_check['parameters']['employees']
    year_month_day = parameter_check['parameters']['year_month_day']
    customer_work_id = parameter_check['parameters']['work_id']
    try:
        # 근로자 서버에는 고객 서버의 업무 id 가 암호화되어 저장되어 있다.
        work = Work.objects.get(customer_work_id=customer_work_id)
        work_id = work.id
    except Exception as e:
        logError(get_api(request), ' 업무 id ({}) 에 해당되는 업무가 없다. ({})'.format(customer_work_id, str(e)))
        work_id = -1
    employee_ids = []
    for employee in employees:
        # key 에 '_id' 가 포함되어 있으면 >> 암호화 된 값이면
        plain = AES_DECRYPT_BASE64(employee)
        if plain == '__error':
            logError(get_api(request), ' 근로자 id ({}) Error 복호화 실패: 처리대상에서 제외'.format(employee))
            # 2019-05-22 여러명을 처리할 때 한명 때문에 에러처리하면 안되기 때문에...
            # return status422(get_api(request), {'message': 'employees 에 있는 employee_id={} 가 해독되지 않는다.'.format(employee)})
        else:
            if int(plain) > 0:
                # 거절 수락하지 않은 근로자 제외 (employee_id == -1)
                employee_ids.append(plain)
    logSend('  고객에서 요청한 employee_ids: {}'.format([employee_id for employee_id in employee_ids]))
    passer_list = Passer.objects.filter(id__in=employee_ids)
    # logSend('  근로자 passer_ids: {}'.format([passer.id for passer in passer_list]))
    employee_info_id_list = [passer.employee_id for passer in passer_list if passer.employee_id > 0]
    # logSend('  근로자 employee_ids: {}'.format([employee_info_id for employee_info_id in employee_info_id_list]))
    if len(passer_list) != len(employee_info_id_list):
        logError(get_api(request), ' 출입자 인원(# passer)과 근로자 인원(# employee)이 틀리다 work_id: {}'.format(work_id))
    employee_info_list = Employee.objects.filter(id__in=employee_info_id_list).order_by('work_start')
    # logSend('  근로자 table read employee_ids: {}'.format([employee_info.id for employee_info in employee_info_list]))
    employee_ids = []
    for employee_info in employee_info_list:
        for passer in passer_list:
            if passer.employee_id == employee_info.id:
                employee_ids.append(passer.id)
    logSend('  new employee_ids: {}'.format([employee_id for employee_id in employee_ids]))
    logSend('  pass_histories : employee_ids : {} work_id {}'.format(employee_ids, work_id))
    if work_id == -1:
        pass_histories = Pass_History.objects.filter(year_month_day=year_month_day, passer_id__in=employee_ids)
    else:
        pass_histories = Pass_History.objects.filter(year_month_day=year_month_day, passer_id__in=employee_ids,
                                                     work_id=work_id)
    if len(pass_histories) == 0:
        logError(get_api(request),
                 ' passer_ids={}, year_month_day = {} 에 해당하는 출퇴근 기록이 없다.'.format(employee_ids, year_month_day))
        # return REG_200_SUCCESS.to_json_response({'message': '조건에 맞는 근로자가 없다.'})
    exist_ids = [pass_history.passer_id for pass_history in pass_histories]
    logSend('  pass_histories passer_ids {}'.format(exist_ids))
    for employee_id in employee_ids:
        if int(employee_id) not in exist_ids:
            if int(employee_id) < 0:
                # 필요없음 위 id 해독부분에서 -1 을 걸러냄
                logError(get_api(request), ' *** 나오면 안된다. employee_id: {}'.format(employee_id))
            else:
                # 출퇴근 기록이 없으면 새로 만든다.
                logSend('   --- new pass_history passer_id {}'.format(employee_id))
                new_pass_history = Pass_History(
                    passer_id=int(employee_id),
                    year_month_day=year_month_day,
                    action=0,
                    work_id=work_id,
                )
                logError(get_api(request), ' 강제로 만든 pass_history: {}'.format(
                    [{key: new_pass_history.__dict__[key]} for key in new_pass_history.__dict__.keys() if
                     not key.startswith('_')]))
                new_pass_history.save()
    if work_id == -1:
        pass_histories = Pass_History.objects.filter(year_month_day=year_month_day, passer_id__in=employee_ids)
    else:
        pass_histories = Pass_History.objects.filter(year_month_day=year_month_day, passer_id__in=employee_ids,
                                                     work_id=work_id)

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
            if overtime < -2 or 18 < overtime:
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
                logSend('--- pass_history: {}'.format(
                    [{key: pass_history.__dict__[key]} for key in pass_history.__dict__.keys() if
                     not key.startswith('_')]))
                update_pass_history(pass_history)

        # 퇴근시간 수정 처리
        if ('dt_out_verify' in rqst.keys()) and ('out_staff_id' in rqst.keys()):
            plain = AES_DECRYPT_BASE64(rqst['out_staff_id'])
            is_ok = True
            if plain == '__error':
                is_ok = False
                fail_list.append(' out_staff_id: 비정상')
            try:
                dt_out_verify = datetime.datetime.strptime('{} {}:00'.format(year_month_day, rqst['dt_out_verify']),
                                                           '%Y-%m-%d %H:%M:%S')
            except Exception as e:
                is_ok = False
                fail_list.append(' dt_out_verify: 날짜 변경 Error ({})'.format(e))
            if is_ok:
                pass_history.action = 0
                pass_history.dt_out_verify = dt_out_verify
                pass_history.out_staff_id = int(plain)
                logSend('--- pass_history: {}'.format(
                    [{key: pass_history.__dict__[key]} for key in pass_history.__dict__.keys() if
                     not key.startswith('_')]))
                update_pass_history(pass_history)

        if len(fail_list) > 0:
            return status422(get_api(request), {'message': 'fail', 'fails': fail_list})

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
    return REG_200_SUCCESS.to_json_response(result)


def update_pass_history(pass_history: dict):
    """
    출퇴근 시간에 맞추어 지각, 조퇴 처리
    to use:
        pass_record_of_employees_in_day_for_customer
        pass_verify
        pass_sms
    """
    logSend('--- pass_history: {}'.format(
        {key: pass_history.__dict__[key] for key in pass_history.__dict__.keys() if not key.startswith('_')}))
    try:
        passer = Passer.objects.get(id=pass_history.passer_id)
    except Exception as e:
        logError('ERROR: Passer 에 passer_id: {} 가 없다. ({})'.format(pass_history.passer_id, str(e)))
        return
    if passer.employee_id <= 0:
        return
    employees = Employee.objects.filter(id=passer.employee_id)
    if len(employees) == 0:
        logError('ERROR: passer 의 employee_id={} 에 해당하는 근로자가 없음.'.format(passer.employee_id))
        return
    if len(employees) > 1:
        logError('ERROR: passer 의 employee_id={} 에 해당하는 근로자가 한명 이상임.'.format(passer.employee_id))
    employee = employees[0]

    # 출근 처리
    if pass_history.dt_in_verify is None:
        action_in = 0
    else:
        # 출근 터치가 있으면 지각여부 처리한다.
        action_in = 100
        # 하~~~ 근로자 앱을 설치할 때 출근시간, 일하는 시간 미등록도 걸러야 하나...
        logSend('  - employee.work_start: {}, pass_history.dt_in_verify: {}'.format(employee.work_start,
                                                                                    pass_history.dt_in_verify))
        # if employee.work_start is None or employee.working_time is None:
        if len(employee.work_start) == 0 or len(employee.working_time) == 0:
            logError('ERROR: 근로자 앱에서 근로자 등록할 때 출근시간, 근로시간이 안들어 왔다.(이 문제는 SMS 출퇴근 때문에 정상 출근으로 처리한다.')
        else:
            dt_in = pass_history.dt_in_verify
            work_in_hour = int(employee.work_start[:2])
            work_in_minute = int(employee.work_start[3:])
            if work_in_hour < dt_in.hour:
                action_in = 200
            elif work_in_hour == dt_in.hour:
                if work_in_minute < dt_in.minute:
                    action_in = 200
    # 퇴근 처리
    if pass_history.overtime == -1:
        # 연장근무가 퇴근 시간 상관없이 빨리 끝내면 퇴근 가능일 경우 << 8시간 근무에 3시간 일해도 적용 가능한가?
        action_out = 10
    else:
        if pass_history.dt_out_verify is None:
            action_out = 0
        else:
            # 퇴근 터치가 있으면 조퇴여부 처리한다.
            action_out = 10
            dt_out = pass_history.dt_out_verify
            logSend('  - employee.work_start: {}, pass_history.dt_in_verify: {}'.format(employee.work_start, dt_out))
            # if employee.work_start is None or employee.working_time is None:
            if len(employee.work_start) == 0 or len(employee.working_time) == 0:
                logError('ERROR: 근로자 앱에서 근로자 등록할 때 출근시간, 근로시간이 안들어 왔다.(이 문제는 SMS 출퇴근 때문에 정상 출근으로 처리한다.')
            else:
                work_out_hour = int(employee.work_start[:2]) + int(employee.working_time[:2])
                work_out_minute = int(employee.work_start[3:])
                if dt_out.hour < work_out_hour:
                    action_out = 20
                elif dt_out.hour == work_out_hour:
                    if dt_out.minute < work_out_minute:
                        action_out = 20
    pass_history.action = action_in + action_out
    pass_history.save()
    logSend('employee/update_pass_history: pass_history.action = {}, passer_id = {}, employee.name = {}'.format(pass_history.action, passer.id,
                                                                                        employee.name))
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
            dt_begin: 2019/04/01   # 근로 시작 날짜
            dt_end: 2019/04/13     # 근로 종료 날짜
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
        logError(get_api(request), ' passer_ids={}, year_month_day = {} 에 해당하는 출퇴근 기록이 없다.'.format(employee_ids, year_month_day))

        logError(get_api(request), ' passer_id={} out touch 인데 어제, 오늘 기록이 없다. dt_touch={}'.format(passer_id, dt_touch)
        logError(get_api(request), ' passer_id={} in 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
        logError(get_api(request), ' passer_id={} in 기록후 12시간 이상 지나서 out touch가 들어왔다. dt_in={}, dt_touch={}'.format(passer_id, dt_in, dt_touch))
        logError(get_api(request), ' passer 의 employee_id={} 에 해당하는 근로자가 없음.'.format(passer.employee_id))
        logError(get_api(request), ' passer 의 employee_id={} 에 해당하는 근로자가 한명 이상임.'.format(passer.employee_id))
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    #
    # 서버 대 서버 통신으로 상대방 서버가 등록된 서버인지 확인 기능 추가가 필요하다.
    #
    parameter_check = is_parameter_ok(rqst, ['employee_id_!', 'work_id'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    passer_id = parameter_check['parameters']['employee_id']
    work_id = parameter_check['parameters']['work_id']
    try:
        passer = Passer.objects.get(id=passer_id)
    except Exception as e:
        return status422(get_api(request), {'message': '해당 근로자({})가 없다. ({})'.format(passer_id, str(e))})
    if passer.employee_id == -1:
        return status422(get_api(request), {'message': '해당 근로자({})의 업무가 등록되지 않았다.'.format(passer_id)})
    try:
        employee = Employee.objects.get(id=passer.employee_id)
    except Exception as e:
        return status422(get_api(request),
                         {'message': '해당 근로자({})의 업무를 찾을 수 없다. ({})'.format(passer_id, str(e))})
    # logSend('   {}'.format(employee.name))
    employee_works = Works(employee.get_works())
    # logSend('  find: 5 > {}'.format(employee_works.find('5')))
    try:
        work = Work.objects.get(customer_work_id=work_id)
    except Exception as e:
        return status422(get_api(request), {'message': '해당 업무({})를 찾을 수 없다. ({})'.format(work_id, str(e))})
    # logSend('  work: {}'.format({x: work.__dict__[x] for x in work.__dict__.keys() if not x.startswith('_')}))
    if not employee_works.find(work.id):
        return status422(get_api(request),
                         {'message': '해당 업무({})를 근로자({})에게서 찾을 수 없다.'.format(work_id, passer_id)})
    employee_work = employee_works.data[employee_works.index]
    if 'dt_begin' in rqst:
        employee_work['begin'] = rqst['dt_begin']
    if 'dt_end' in rqst:
        employee_work['end'] = rqst['dt_end']
    employee_works.add(employee_work)
    employee.set_works(employee_works.data)
    employee.save()
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def my_work_histories_for_customer(request):
    """
    <<<고객 서버용>>> 근로 내용 : 근로자의 근로 내역을 월 기준으로 1년까지 요청함, 캘린더나 목록이 스크롤 될 때 6개월정도 남으면 추가 요청해서 표시할 것
    action 설명
        총 3자리로 구성 첫자리는 출근, 2번째는 퇴근, 3번째는 외출 횟수
        첫번째 자리 1 - 정상 출근, 2 - 지각 출근
        두번째 자리 1 - 정상 퇴근, 2 - 조퇴, 3 - 30분 연장 근무, 4 - 1시간 연장 근무, 5 - 1:30 연장 근무
    overtime 설명
        연장 근무 -2: 휴무, -1: 업무 끝나면 퇴근, 0: 정상 근무, 1~18: 연장 근무 시간( 1:30분, 2:1시간, 3:1:30, 4:2:00, 5:2:30, 6:3:00 7: 3:30, 8: 4:00, 9: 4:30, 10: 5:00, 11: 5:30, 12: 6:00, 13: 6:30, 14: 7:00, 15: 7:30, 16: 8:00, 17: 8:30, 18: 9:00)
    http://0.0.0.0:8000/employee/my_work_histories_for_customer?employee_id=qgf6YHf1z2Fx80DR8o/Lvg&dt=2018-12
    GET
        employee_id = 서버로 받아 저장해둔 출입자 id'
        work_id = 고객 서버의 work id   # 암호화되어 있음
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
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['employee_id_!', 'work_id_@', 'dt'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

    employee_id = parameter_check['parameters']['employee_id']
    customer_work_id = parameter_check['parameters']['work_id']  # 이 work_id 는 고객서버의 work_id 라서 암호화된 채로 사용한다.
    year_month = parameter_check['parameters']['dt']

    passers = Passer.objects.filter(id=employee_id)
    if len(passers) == 0:
        return status422(get_api(request),
                         {'message': 'ServerError: Passer 에 id={} 이(가) 없다'.format(employee_id)})
    elif len(passers) > 1:
        logError(get_api(request), ' Passer(id:{})가 중복되었다.'.format(employee_id))
    passer = passers[0]

    employees = Employee.objects.filter(id=passer.employee_id)
    if len(employees) == 0:
        return status422(get_api(request),
                         {'message': 'ServerError: Employee 에 id={} 이(가) 없다'.format(passer.employee_id)})
    elif len(employees) > 1:
        logError(get_api(request), ' Employee(id:{})가 중복되었다.'.format(passer.employee_id))
    employee = employees[0]
    #
    # 이 근로자의 과거 근로 기록을 보여준다.
    # ? 이 근로자의 현재 업무 과거 기록만 보여줘야하지 않나? - work_id 이용 필요
    #
    logSend('  customer_work_id: {}'.format(customer_work_id))
    if customer_work_id is None or customer_work_id == 'i52bN-IdKYwB4fcddHRn-g':
        pass_record_list = Pass_History.objects.filter(passer_id=passer.id,
                                                       year_month_day__contains=year_month).order_by('year_month_day')
    else:
        works = Work.objects.filter(customer_work_id=customer_work_id)
        if len(works) == 0:
            logError(get_api(request), ' 근로자 서버에 고객서버가 요청한 work_id({}) 가 없다. [발생하면 안됨]'.format(customer_work_id))
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '소속된 업무가 없습니다.'})

        pass_record_list = Pass_History.objects.filter(passer_id=passer.id,
                                                       work_id=works[0].id,
                                                       year_month_day__contains=year_month).order_by('year_month_day')
    workings = []
    for pass_record in pass_record_list:
        working_time = int(float(employee.working_time))
        working_hour = (working_time // 4) * 4
        break_hour = working_time - working_hour
        working = {'year_month_day': pass_record.year_month_day,
                   'action': pass_record.action,
                   'dt_begin': dt_null(pass_record.dt_in_verify),
                   'dt_end': dt_null(pass_record.dt_out_verify),
                   'overtime': pass_record.overtime,  # 2019-07-21 overtime_values[pass_record.overtime + 2],
                   'working_hour': working_hour,
                   'break_hour': break_hour,
                   # 'work_id': pass_record.work_id,
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
    return REG_200_SUCCESS.to_json_response(result)


def virtual_working_data(dt_begin: datetime, dt_end: datetime) -> dict:
    # print(dt_begin.strftime('%Y-%m-%d %H:%M:%S'), ' ', dt_end.strftime('%Y-%m-%d %H:%M:%S'))
    year_month = dt_begin.strftime('%Y-%m')
    last_day = dt_end - datetime.timedelta(hours=1)
    # print(last_day)
    workings = []
    for day in range(1, int(last_day.strftime('%d')) + 1):
        if random.randint(1, 7) > 5:  # 7일에 5일 꼴로 쉬는 날
            continue
        working = {}
        action = 0
        if random.randint(1, 30) > 27:  # 한달에 3번꼴로 지각
            action = 200
            working['dt_begin'] = year_month + '-%02d' % day + ' 08:45:00'
        else:
            action = 100
            working['dt_begin'] = year_month + '-%02d' % day + ' 08:25:00'
        if random.randint(1, 30) > 29:  # 한달에 1번꼴로 조퇴
            action += 20
            working['dt_end'] = year_month + '-%02d' % day + ' 15:33:00'
        elif random.randint(0, 30) > 20:  # 일에 한번꼴로 연장 근무
            action += 40
            working['dt_end'] = year_month + '-%02d' % day + ' 18:35:00'
        else:
            action += 10
            working['dt_end'] = year_month + '-%02d' % day + ' 17:35:00'
        outing = (random.randint(0, 30) - 28) % 3  # 한달에 2번꼴로 외출
        outings = []
        if outing > 0:
            for i in range(outing):
                # print(i)
                outings.append({'dt_begin': year_month + '-%02d' % day + ' ' + str(i + 13) + ':00:00',
                                'dt_end': year_month + '-%02d' % day + ' ' + str(i + 13) + ':30:00'})
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
    overtime 설명
        연장 근무 -2: 휴무, -1: 업무 끝나면 퇴근, 0: 정상 근무, 1~18: 연장 근무 시간( 1:30분, 2:1시간, 3:1:30, 4:2:00, 5:2:30, 6:3:00 7: 3:30, 8: 4:00, 9: 4:30, 10: 5:00, 11: 5:30, 12: 6:00, 13: 6:30, 14: 7:00, 15: 7:30, 16: 8:00, 17: 8:30, 18: 9:00)
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
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    #
    # 근로자 서버로 근로자의 월 근로 내역을 요청
    #
    employee_info = {
        'employee_id': rqst["passer_id"],
        'dt': rqst['dt'],
    }
    response_employee = requests.post(settings.EMPLOYEE_URL + 'my_work_histories_for_customer', json=employee_info)
    logSend(response_employee)

    result = response_employee.json()
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def my_work_records(request):
    """
    근로 내용 : 근로자의 근로 내역을 월 기준으로 1년까지 요청함, 캘린더나 목록이 스크롤 될 때 6개월정도 남으면 추가 요청해서 표시할 것
    action 설명
        총 3자리로 구성 첫자리는 출근, 2번째는 퇴근, 3번째는 외출 횟수
        첫번째 자리 1 - 정상 출근, 2 - 지각 출근
        두번째 자리 1 - 정상 퇴근, 2 - 조퇴, 3 - 30분 연장 근무, 4 - 1시간 연장 근무, 5 - 1:30 연장 근무
    overtime 설명
        연장 근무 -2: 휴무, -1: 업무 끝나면 퇴근, 0: 정상 근무, 1~18: 연장 근무 시간( 1:30분, 2:1시간, 3:1:30, 4:2:00, 5:2:30, 6:3:00 7: 3:30, 8: 4:00, 9: 4:30, 10: 5:00, 11: 5:30, 12: 6:00, 13: 6:30, 14: 7:00, 15: 7:30, 16: 8:00, 17: 8:30, 18: 9:00)
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
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    #
    # 근로자 서버로 근로자의 월 근로 내역을 요청
    #
    employee_info = {
        'employee_id': rqst["passer_id"],
        'work_id': AES_ENCRYPT_BASE64('-1'),
        'dt': rqst['dt'],
    }
    response_employee = requests.post(settings.EMPLOYEE_URL + 'my_work_histories_for_customer', json=employee_info)

    result = response_employee.json()
    return REG_200_SUCCESS.to_json_response(result)


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
    logSend(dic_passer, '\n', dic_passer[1]['name'])
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
    result = []
    employee_list = Employee.objects.all()
    for employee in employee_list:
        logSend('  {}'.format(employee.name))
        if employee.id < 155:
            employee.dt_reg = str_to_datetime('2019-6-30 23:59:59')
        elif employee.id < 188:
            employee.dt_reg = str_to_datetime('2019-07-31 23:59:59')
        else:
            employee.dt_reg = str_to_datetime('2019-08-01 00:00:00')
        logSend('  {}: {}'.format(employee.name, employee.dt_reg))
        result.append({employee.name: employee.dt_reg})
        employee.save()
    return REG_200_SUCCESS.to_json_response({'result': result})

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
            before_pass = Pass.objects \
                .filter(passer_id=passer_id,
                        dt_reg__lt=dt,
                        dt_reg__gt=dt - datetime.timedelta(minutes=30)) \
                .values('id',
                        'passer_id',
                        'is_in',
                        'dt_reg',
                        'dt_verify') \
                .order_by('-dt_reg')\
                .first()
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
                    before_pass = {'id': -1,
                                   'passer_id': passer_id,
                                   'is_in': pass_.is_in,
                                   'dt_reg': None,
                                   'dt_verify': None}
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
            if pass_.is_in:  # in 이면
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
    return REG_200_SUCCESS.to_json_response(
        {'pass_histories': arr_pass_history, 'long_interval_list': long_interval_list, 'error_passes': error_passes})


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
        view_ph = {'passer': dic_passer[ph.passer_id]['name'],
                   'action': ph.action,
                   'dt_in': '...' if ph.dt_in is None else ph.dt_in.strftime("%Y-%m-%d %H:%M:%S"),
                   'dt_in_verify': '...' if ph.dt_in_verify is None else ph.dt_in_verify.strftime("%Y-%m-%d %H:%M:%S"),
                   'dt_out': '...' if ph.dt_out is None else ph.dt_out.strftime("%Y-%m-%d %H:%M:%S"),
                   'dt_out_verify': '...' if ph.dt_out_verify is None else ph.dt_out_verify.strftime(
                       "%Y-%m-%d %H:%M:%S"),
                   'minor': 0
                   }
        arr_pass_histories.append(view_ph)
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
    return REG_200_SUCCESS.to_json_response({'beacons': arr_beacon})


@cross_origin_read_allow
def tk_employee(request):
    """
    [[ 운영 ]] 근로자 조회
    https://api.ezchek.co.kr/employee/tk_employee
    GET
        pNo: 010 3333 5555
        name: 이름
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
    """
    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    passer_dict_list = []
    passer_list = []
    if 'pNo' in rqst:
        pNo = no_only_phone_no(rqst['pNo'])
        passer_list = Passer.objects.filter(pNo=pNo)
        if len(passer_list) == 0:
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '{} not found'.format(phone_format(pNo))})
    if 'name' in rqst:
        name = rqst['name']
        employee_list = Employee.objects.filter(name=name)
        if len(employee_list) == 0:
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response(
                {'message': '{} not found'.format(phone_format(name))})
        passer_list = Passer.objects.filter(employee_id__in=[employee.id for employee in employee_list])
    for passer in passer_list:
        passer_dict = {
            'id': passer.id,
            'pNo': phone_format(passer.pNo),
            'employee_id': passer.employee_id,
        }
        if passer.employee_id > 0:
            employee = Employee.objects.get(id=passer.employee_id)
            passer_dict['name'] = employee.name
            passer_dict['work_start'] = employee.work_start
            passer_dict['working_time'] = employee.working_time
            passer_dict['rest_time'] = employee.rest_time
            employee_works = Works(employee.get_works())
            works = []
            for employee_work in employee_works.data:
                work_dict = {
                    'id': employee_work['id'],
                    'begin': employee_work['begin'],
                    'end': employee_work['end'],
                }
                work = Work.objects.get(id=employee_work['id'])
                work_dict['customer_work_id'] = AES_DECRYPT_BASE64(work.customer_work_id)
                work_dict['work_place_name'] = work.work_place_name
                work_dict['work_name_type'] = work.work_name_type
                work_dict['work_begin'] = work.begin
                work_dict['work_end'] = work.end
                works.append(work_dict)
            passer_dict['works'] = works
        passer_dict_list.append(passer_dict)
    return REG_200_SUCCESS.to_json_response({'passers': passer_dict_list})


@cross_origin_read_allow
def tk_pass(request):
    """
    [[ 운영 ]] 출입정보 조회
    GET
        passer_id: 41
        dt_begin: 2019-06-01
        dt_end: 2019-06-31
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
    """
    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    passes = []
    pass_records = []
    if 'passer_id' in rqst:
        passer_id = rqst['passer_id']
    else:
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if 'dt_begin' in rqst:
        dt_begin = str_to_datetime(rqst['dt_begin'])
        if 'dt_end' in rqst:
            dt_end = str_to_datetime(rqst['dt_end'])
            pass_list = Pass.objects.filter(passer_id=passer_id, dt__gt=dt_begin, dt__lt=dt_end).order_by('dt')
            pass_record_list = Pass_History.objects.filter(passer_id=passer_id, year_month_day__gt=dt_begin,
                                                           year_month_day__lt=dt_end).order_by('year_month_day')
        else:
            pass_list = Pass.objects.filter(passer_id=passer_id, dt__gt=dt_begin).order_by('dt')
            pass_record_list = Pass_History.objects.filter(passer_id=passer_id, year_month_day__gt=dt_begin).order_by(
                'year_month_day')
    else:
        if 'dt_end' in rqst:
            dt_end = str_to_datetime(rqst['dt_end'])
            pass_list = Pass.objects.filter(passer_id=passer_id, dt__lt=dt_end).order_by('dt')
            pass_record_list = Pass_History.objects.filter(passer_id=passer_id, year_month_day__lt=dt_end).order_by(
                'year_month_day')
        else:
            pass_list = Pass.objects.filter(passer_id=passer_id).order_by('dt')
            pass_record_list = Pass_History.objects.filter(passer_id=passer_id).order_by('year_month_day')

    for pass_ in pass_list:
        pass_dict = {
            'dt': dt_null(pass_.dt),
            'is_in': 'YES' if pass_.is_in else 'NO',
            'is_beacon': 'YES' if pass_.is_beacon else 'NO',
            'x': pass_.x,
            'y': pass_.y,
        }
        passes.append(pass_dict)

    for pass_record in pass_record_list:
        pass_record_dict = {
            'year_month_day': pass_record.year_month_day,
            'dt_in': dt_null(pass_record.dt_in),
            'dt_in_verify': dt_null(pass_record.dt_in_verify),
            'dt_out': dt_null(pass_record.dt_out),
            'dt_out_verify': dt_null(pass_record.dt_out_verify),
            'work_id': pass_record.work_id,
        }
        pass_records.append(pass_record_dict)
    return REG_200_SUCCESS.to_json_response({'passes': passes, 'pass_record': pass_records})


@cross_origin_read_allow
def tk_passer_list(request):
    """
    [[ 운영 ]] 출입자 목록: 고객 서버에서 근로자가 정상적인지 파악하기 위해 사용한다.
    GET
        key=vChLo3rsRAl0B4NNuaZOsg (thinking)
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
    """
    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        logError(get_api(request), ' 허가되지 않은 ip: {}'.format(get_client_ip(request)))
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

    # if get_client_ip(request) not in settings.ALLOWED_HOSTS:
    #     return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})
    passer_list = Passer.objects.all()
    passers = {passer.pNo: passer.id for passer in passer_list}
    return REG_200_SUCCESS.to_json_response({'passers': passers})


@cross_origin_read_allow
def tk_list_reg_stop(request):
    """
    [[ 운영 ]] 등록 중지 중인 출입자 list
    - 일정 날짜(until_day) 이전에 중지된 경우
    http://0.0.0.0:8000/employee/tk_list_reg_stop?until_day=2019-08-15

    GET
        until_day: 2019-08-15 # 2019-08-15 까지 등록 시도한 출입자 (default: 오늘)
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
    """
    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        logError(get_api(request), ' 허가되지 않은 ip: {}'.format(get_client_ip(request)))
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    if 'until_day' in rqst:
        try:
            dt_until = str_to_datetime(rqst['until_day'])
        except Exception as e:
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '검사할 날짜({})의 양식(2019-08-15)이 잘못되었어요.'})
    else:
        dt_until = datetime.datetime.now()

    result = []
    # 삭제 대상 출입자 검색
    passer_list = Passer.objects.filter(~Q(cn=0))
    # logSend('--- 삭제 대상: 인증 중 중단, 인증문자를 보낼 수 없는 전화번호(이건 나타나면 안되지)')
    reg_stop_employee_id_list = [x.employee_id for x in passer_list if x.employee_id != -1]
    employee_list = Employee.objects.filter(id__in=reg_stop_employee_id_list)
    employee_dict = {x.id: {'name': x.name, 'td_reg': dt_str(x.dt_reg, "%Y-%m-%d %H:%M:%S")} for x in employee_list}
    reg_stop_list = []
    pType_name = ['모름', '아이폰', '안드로이드폰', '피쳐폰']
    for passer in passer_list:
        reg_stop = {
            'pNo': passer.pNo,
            'dt_cn': dt_null(passer.dt_cn),
            'pType': pType_name[passer.pType // 10],
            'passer_id': passer.id,
            'employee_id': passer.employee_id,
        }
        if passer.employee_id != -1:
            reg_stop['employee'] = employee_dict[passer.employee_id]
        reg_stop_list.append(reg_stop)
        # logSend('  {}'.format(no_employee_id))
    result.append({'reg_stop_list': reg_stop_list})
    return REG_200_SUCCESS.to_json_response({'result': result})


@cross_origin_read_allow
def tk_update_rest_time(request):
    """
    [[ 운영 ]] 근로시간에 휴계시간 기능이 추가되면서 근무시간(working_time)과 휴계 시간(rest_time) 분리 작업을 한다.

    http://0.0.0.0:8000/employee/tk_update_rest_time&is_reg_update=1

    GET
        key=vChLo3rsRAl0B4NNuaZOsg (thinking)
        is_reg_update=1
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
    """
    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        logError(get_api(request), ' 허가되지 않은 ip: {}'.format(get_client_ip(request)))
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    result = []
    #
    # 근로자 등록일자 업데이트 - pass_history 를 뒤져서 기록의 제일 먼저 시간을 넣는다.
    # pass_history 에 없으면 id: < 155(2019-06-30 23:59:59) < 175(2019-07-31 23:59:59) < 226 (2019-08-01 00:00:00)
    #
    employee_list = Employee.objects.all()
    if 'is_reg_update' in rqst and rqst['is_reg_update']:
        employee_id_list = [x.id for x in employee_list]
        passer_list = Passer.objects.filter(employee_id__in=employee_id_list)
        logSend('  len - employee: {}, passer: {}'.format(len(employee_list), len(passer_list)))
        if len(employee_list) != len(passer_list):
            REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '등록된 근로자({})가 출입자({})에 없습니다.'.format(len(employee_list), len(passer_list))})
        passer_dict = {x.employee_id: x.id for x in passer_list}
        # pass_history_list = Pass_History.objects.all()
        for employee in employee_list:
            passer_id = passer_dict[employee.id]
            # logSend('  passer_id: {} < {}'.format(passer_id, employee.id))
            pass_history_list = Pass_History.objects.filter(passer_id=passer_id).order_by('id')
            if len(pass_history_list) > 0:
                ph = pass_history_list[0]
                # logSend('  {}: {} {} {} {} {}'.format(employee.name, ph.year_month_day, ph.dt_in, ph.dt_in_verify, ph.dt_out, ph.dt_out_verify))
                dt_reg = str_to_datetime(ph.year_month_day)
                if ph.dt_out_verify is not None:
                    dt_reg = ph.dt_out_verify
                if ph.dt_out is not None:
                    dt_reg = ph.dt_out
                if ph.dt_in_verify is not None:
                    dt_reg = ph.dt_in_verify
                if ph.dt_in is not None:
                    dt_reg = ph.dt_in
                logSend('  {}: {}'.format(employee.name, dt_reg))
                employee.dt_reg = dt_reg
                employee.save()
            else:
                if employee.id < 155:
                    employee.dt_reg = str_to_datetime("2019-06-30 23:59:59")
                if employee.id < 175:
                    employee.dt_reg = str_to_datetime("2019-07-31 23:59:59")
                if employee.id < 226:
                    employee.dt_reg = str_to_datetime("2019-08-01 00:00:00")
                employee.save()
                logSend('  {}: X {}'.format(employee.name, employee.dt_reg))

    # 출근시간이 없는 근로자 분석
    #
    no_work_time_employee_list = Employee.objects.filter(work_start='')
    no_work_time_employee_dict = {x.id: {
        'name': x.name,
        'work_start': x.work_start,
        'working_time': x.working_time,
        'rest_time': x.rest_time
    } for x in no_work_time_employee_list}
    # logSend(no_work_time_employee_dict)
    employee_id_list = [x.id for x in no_work_time_employee_list]
    passer_list = Passer.objects.filter(employee_id__in=employee_id_list)
    no_work_time_list = []
    for passer in passer_list:
        e = no_work_time_employee_dict[passer.employee_id]
        passer_employee_complex_info = {
            'name': e['name'],
            'pNo': passer.pNo,
            'pType': passer.pType,
            'passer_id': passer.id,
            'employee_id': passer.employee_id,
            'work_start': e['work_start'],
            'working_time': e['working_time'],
            'rest_time': e['rest_time'],
        }
        no_work_time_list.append(passer_employee_complex_info)
        logSend('  {}'.format(passer_employee_complex_info))
    result.append({'no_work_time_employee': no_work_time_list})

    # 휴계시간 update
    # working_time: 9 >> working_time: 8 + rest_time: 1
    #
    change_work_time_list = []
    update_employee_list = Employee.objects.filter(rest_time=-1).exclude(work_start='')
    for update_employee in update_employee_list:
        change_work_time = {
            'id': update_employee.id,
            'name': update_employee.name,
            'work_start': update_employee.work_start,
            'before_working_time': update_employee.working_time,
            'before_rest_time': update_employee.rest_time,
        }
        # logSend('   {} - working_time: {}, rest_time: {}'.format(update_employee.name, update_employee.working_time, update_employee.rest_time))
        try:
            working_time = int(update_employee.working_time)
        except Exception as e:
            working_time = int(float(update_employee.working_time))
            # logSend('   {} - working_time: {} > {}'.format(update_employee.name, update_employee.working_time, working_time))
        rest_time = int(working_time) // 4
        update_employee.working_time = '{}'.format(working_time - rest_time / 2)
        update_employee.rest_time = '{0:02d}:{1:02d}'.format(rest_time // 2, (rest_time % 2) * 30)
        change_work_time['working_time'] = update_employee.working_time
        change_work_time['rest_time'] = update_employee.rest_time
        logSend('  {}'.format(change_work_time))
        # logSend('  {} - working_time: {}, rest_time: {}'.format(update_employee.name, update_employee.working_time, update_employee.rest_time))
        update_employee.save()
        change_work_time_list.append(change_work_time)
    result.append({'change_work_time': change_work_time_list})

    return REG_200_SUCCESS.to_json_response({'result': result}) 


@cross_origin_read_allow
def tk_passer_work_backup(request):
    """
    [[ 운영 ]] 고객 서버에서 받은 업무 완료된 근로자의 업무에서 업무를 뺀다.
    POST
        dt_complete: 2019-07-31
        is_all: 1:YES, 0:NO
        passer_id_list: [ 121, 111, ...]
    http://0.0.0.0:8000/employee/tk_passer_work_backup?dt_complete=2019-05-31&is_all=0&passer_id_list=121&passer_id_list=111&passer_id_list=3
    http://0.0.0.0:8000/employee/tk_passer_work_backup?dt_complete=2019-07-31&is_all=1
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
        STATUS 416
            {'message': '백업할 날짜({})는 오늘({})전이어야 한다..format(dt_complete, dt_today)}
    """
    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        logError(get_api(request), ' 허가되지 않은 ip: {}'.format(get_client_ip(request)))
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    # parameter_check = is_parameter_ok(rqst, ['key_!'])
    # if not parameter_check['is_ok']:
    #     return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})

    # parameter_check = is_parameter_ok(rqst, ['work_id_!'])
    # parameter_check = is_parameter_ok(rqst, ['work_id'])
    # if not parameter_check['is_ok']:
    #     return status422(get_api(request),
    #                      {'message': '{}'.format(''.join([message for message in parameter_check['results']]))})
    # work_id = parameter_check['parameters']['work_id']
    dt_complete = str_to_datetime(rqst['dt_complete'])
    dt_complete = dt_complete + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
    dt_today = datetime.datetime.strptime(datetime.datetime.now().strftime("%Y-%m-%d ") + "00:00:00", "%Y-%m-%d %H:%M:%S")

    logSend('  origin: {}, dt_complete: {}, dt_today: {}'.format(rqst['dt_complete'], dt_complete, dt_today))
    if dt_today < dt_complete:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '백업할 날짜({})는 오늘({})전이어야 한다.'.format(dt_complete, dt_today)})

    result = []
    if 'is_all' in rqst and rqst['is_all'] == '1':
        passer_list = Passer.objects.all()
    else:
        if request.method == 'GET':
            passer_id_list = rqst.getlist('passer_id_list')
        else:
            passer_id_list = rqst['passer_id_list']
        logSend('  pass_id_list: {}'.format(passer_id_list))
        passer_list = Passer.objects.filter(id__in=passer_id_list)
    passer_dict = {}
    for passer in passer_list:
        passer_dict[passer.employee_id] = {'pNo': passer.pNo, 'passer_id': passer.id}
    logSend('  {}'.format(passer_dict))
    employee_id_list = [passer.employee_id for passer in passer_list]
    employee_list = Employee.objects.filter(id__in=employee_id_list)
    employee_work_backup = []
    for employee in employee_list:
        employee_work_list = employee.get_works()
        logSend('  employee: {}'.format({x: employee.__dict__[x] for x in employee.__dict__.keys() if not x.startswith('_')}))
        for employee_work in employee_work_list:
            if str_to_dt(employee_work['end']) < dt_complete:
                remove_work = {'employee_id': employee.id,
                               'name': employee.name,
                               'work_id': employee_work['id'],
                               'dt_begin': employee_work['begin'],
                               'dt_end': employee_work['end'],
                               'pNo': passer_dict[employee.id]['pNo'],
                               'passer_id': passer_dict[employee.id]['passer_id'],
                               }
                employee_work_backup.append(remove_work)
                employee_work_list.remove(employee_work)
                employee_work = Employee_Backup(name=remove_work['name'],
                                                pNo=remove_work['pNo'],
                                                passer_id=remove_work['passer_id'],
                                                employee_id=remove_work['employee_id'],
                                                work_id=remove_work['work_id'],
                                                dt_begin=str_to_dt(remove_work['dt_begin']),
                                                dt_end=str_to_dt(remove_work['dt_end']),
                                                )
                employee_work.save()
        employee.set_works(employee_work_list)
        employee.save()
        logSend('  >> employee: {}'.format({x: employee.__dict__[x] for x in employee.__dict__.keys() if not x.startswith('_')}))
    result.append(employee_work_backup)

    return REG_200_SUCCESS.to_json_response({'result': result})


@cross_origin_read_allow
def tk_match_test_for_customer(request):
    """
    [[ 운영 ]] 고객 서버: 근로자 정보 > 근로자 서버: 근로자 정보 miss match 확인

    http://0.0.0.0:8000/employee/tk_verify_employee_from_customer

    POST
        employee_compare_dict: [{'id': "3", 'name': "unknown", 'pNo': "01024505942", 'employee_id': 70}, ...]
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
    """
    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        logError(get_api(request), ' 허가되지 않은 ip: {}'.format(get_client_ip(request)))
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    employee_compare_list = rqst['employee_compare_list']
    logSend(employee_compare_list)
    employee_pNo_dict = {}
    for employee in employee_compare_list:
        if employee['pNo'] not in employee_pNo_dict.keys():
            employee_pNo_dict[employee['pNo']] = '|'
    logSend('  employee_pNo_dict({}): {}'.format(len(employee_pNo_dict.keys()), employee_pNo_dict))
    employee_pNo_list = [x for x in employee_pNo_dict.keys()]
    logSend(' employee_pNo_list({}): {}'.format(len(employee_pNo_list), employee_pNo_list))
    passer_list = Passer.objects.filter(pNo__in=employee_pNo_list)
    passer_pNo_dict = {x.pNo: {'id': x.id, 'employee_id': x.employee_id} for x in passer_list}
    logSend('  {}'.format(passer_pNo_dict))
    passer_employee_id_dict = {x.id: x.employee_id for x in passer_list if x.employee_id != -1}
    # logSend(passer_pNo_dict)
    employee_id_list = []
    miss_match_list = []
    for employee in employee_compare_list:
        if employee['pNo'] in passer_pNo_dict.keys():
            # logSend('  {} customer:{} vs employee:{}'.format(employee['pNo'],
            #                                                  employee['employee_id'],
            #                                                  passer_pNo_dict[employee['pNo']]))
            if passer_pNo_dict[employee['pNo']]['id'] != employee['employee_id']:
                logSend('  miss match: {} {} < {}'.format(employee['pNo'], employee['employee_id'], passer_pNo_dict[employee['pNo']]['id']))
                miss_match_list.append({'id': employee['id'], 'employee_id': passer_pNo_dict[employee['pNo']]['id']})
                if passer_pNo_dict[employee['pNo']]['employee_id'] != -1:
                    employee_id_list.append(passer_pNo_dict[employee['pNo']]['employee_id'])
        else:
            logSend('  {} customer:{} vs employee:X'.format(employee['pNo'], employee['employee_id']))
            if employee['employee_id'] != -1:
                miss_match_list.append({'id': employee['id'], 'employee_id': -1})
    employee_list = Employee.objects.filter(id__in=employee_id_list)
    employee_dict = {x.id: x.name for x in employee_list}
    for miss_match in miss_match_list:
        if miss_match['employee_id'] in passer_employee_id_dict:
            miss_match['name'] = employee_dict[passer_employee_id_dict[miss_match['employee_id']]]
    return REG_200_SUCCESS.to_json_response({'miss_match_list': miss_match_list})


def work_dict_from_db(id_list):
    works = Work.objects.filter(id__in=id_list)
    work_dict = {}
    for work in works:
        work_dict[work.id] = work
    return work_dict


def passer_dict_from_db(id_list):
    passer_list = Passer.objects.filter(id__in=id_list)
    passer_dict = {passer.id: {key: passer.__dict__[key] for key in passer.__dict__.keys() if not key.startswith('_')} for passer in passer_list}
    # logSend('  passer_dict: {}'.format(passer_dict))

    employee_id_list = [passer.employee_id for passer in passer_list if passer.id is not -1]
    employee_list = Employee.objects.filter(id__in=employee_id_list)
    employee_dict = {employee.id: {key: employee.get_works() if key is "works" else employee.__dict__[key] for key in employee.__dict__.keys() if not key.startswith('_')} for employee in employee_list}
    # logSend('  employee_dict: {}'.format(employee_dict))

    for passer_key in passer_dict.keys():
        passer = passer_dict[passer_key]
        if passer['employee_id'] is not -1:
            employee = employee_dict[passer['employee_id']]
            for key in employee.keys():
                passer['employee_' + key] = employee[key]
            passer_dict[passer_key] = passer
    # logSend('  passer + employee: {}'.format(passer_dict))
    return passer_dict

@cross_origin_read_allow
def tk_in_out_null_list(request):
    """
    [[ 운영 ]] 출입 기록이 없는 근로자 list
    - employee_pass_histoty 에 날짜는 있는데 출입내역이 없는 근로자 표시
    - 필요에 따라 업무별로 찾을 수 있다.
    - 기본 값은 한달이지만 기간을 지정할 수 있다.(월 혹은 날짜까지 만 넣는다. 2019-08, 2019-08-03)
    http://0.0.0.0:8000/employee/tk_in_out_null_list?work_id=&dt_begin=2019-06-01

    POST
        work_id: 암호화된 id (optional)
        dt_begin: '2019-08-01' (optional) default: 이번 달의 1일
    response
        STATUS 200
          "message": "정상적으로 처리되었습니다.",
          "result": [
            {
              "id": 1087,
              "year_month_day": "2019-08-15",
              "work_id": "18",
              "work_place_name": "울산1공장",
              "work_name_type": "생산 (주간)",
              "begin": "2019/06/14",
              "end": "2019/06/29",
              "passer_id": 76,
              "passer_pNo": "01088533337",
              "passer_pType": 20,
              "employee_id": 70,
              "employee_name": "joseph",
              "employee_works": [
                {
                  "id": 20,
                  "begin": "2019/08/03",
                  "end": "2019/08/30"
                },
                {
                  "id": 19,
                  "begin": "2019/07/02",
                  "end": "2019/07/15"
                }
              ]
            },....
           ]
        STATUS 403
            {'message':'저리가!!!'}
    """
    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        logError(get_api(request), ' 허가되지 않은 ip: {}'.format(get_client_ip(request)))
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['work_id_!_@', 'dt_begin_@'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    work_id = parameter_check['parameters']['work_id']
    dt_begin = parameter_check['parameters']['dt_begin']
    if dt_begin is None:
        dt_begin = str_to_datetime(datetime.datetime.now().strftime("%Y-%m") + '-01')
    else:
        dt_begin = str_to_datetime(dt_begin)
    logSend('  work_id: {}, dt_begin: {}'.format(work_id, dt_begin))

    # stop_watch = datetime.datetime.now()
    if work_id is None:
        io_null_list = Pass_History.objects.filter(year_month_day__gt=dt_begin, dt_in=None, dt_in_verify=None, dt_out=None, dt_out_verify=None).exclude(overtime=-2)
    else:
        io_null_list = Pass_History.objects.filter(year_month_day__gt=dt_begin, work_id=work_id, dt_in=None, dt_in_verify=None, dt_out=None, dt_out_verify=None).exclude(overtime=-2)

    work_dict = work_dict_from_db([x.work_id for x in io_null_list])
    passer_dict = passer_dict_from_db([x.passer_id for x in io_null_list])

    result = []
    delete_history = []
    for io_null in io_null_list:
        if io_null.passer_id not in passer_dict.keys():
            logSend('  Not exist passer_id: {}'.format(io_null.passer_id))
            delete_history.append({'id': io_null.id,
                                   'year_month_day': io_null.year_month_day,
                                   'work_id': io_null.work_id,
                                   'work_place_name': work_dict[int(io_null.work_id)].work_place_name,
                                   'work_name_type': work_dict[int(io_null.work_id)].work_name_type,
                                   'begin': work_dict[int(io_null.work_id)].begin,
                                   'end': work_dict[int(io_null.work_id)].end,
                                   })
            io_null.delete()
            continue
        io_null_employee = {
            'id': io_null.id,
            'year_month_day': io_null.year_month_day,
            'work_id': io_null.work_id,
            'work_place_name': work_dict[int(io_null.work_id)].work_place_name,
            'work_name_type': work_dict[int(io_null.work_id)].work_name_type,
            'begin': work_dict[int(io_null.work_id)].begin,
            'end': work_dict[int(io_null.work_id)].end,
            'passer_id': io_null.passer_id,
            'passer_pNo': passer_dict[io_null.passer_id]['pNo'],
            'passer_pType': passer_dict[io_null.passer_id]['pType'],
            'employee_id': passer_dict[io_null.passer_id]['employee_id'],
            'employee_name': passer_dict[io_null.passer_id]['employee_name'],
            'employee_works': passer_dict[io_null.passer_id]['employee_works'],
        }
        result.append(io_null_employee)
    # logSend('  time interval: {}'.format(datetime.datetime.now() - stop_watch))

    return REG_200_SUCCESS.to_json_response({'delete_history': delete_history, 'result': result})
