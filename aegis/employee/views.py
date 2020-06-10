"""
Employee view

Copyright 2019. DaeDuckTech Corp. All rights reserved.
"""

import random
import inspect
import secrets  # uuid token 만들 때 사용
import copy

from config.log import logSend, logError, send_slack
from config.common import ReqLibJsonResponse
from config.common import status422, no_only_phone_no, phone_format, dt_null, dt_str, is_parameter_ok, str_to_datetime
from config.common import str_no, str_to_dt, get_client_ip, get_api, str2min, time_gap, min2str, int_none, zero_blank
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
from dateutil.relativedelta import relativedelta

from django.conf import settings
from django.db.models import Q
from operator import itemgetter

# APNs
from config.apns import notification


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
    # Work.objects.all().delete()
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
    - 인증할 때는 parameter v 만 보낸다.
    - 인증 후에는 p, t, i 를 보내서 등록된 전화번호인지, 새로운 폰에 설치되었는지 확인한다.
    http://0.0.0.0:8000/employee/check_version?v=A.1.0.0.190111&i=BbaBa43219999QJ4CSvmpM14fuSxyhyufYQ
    POST
        v=A.1.0.0.190111
            # A.     : phone type - A or i
            # 1.0.0. : 앱의 버전 구분 업그레이드 필요성과 상관 없다.
            # 190111 : 서버와 호환되는 날짜 - 이 날짜에 의해 서버는 업그레이드 필요를 응답한다.
        i=근로자정보 (전화인증이 끝난 경우만 보낸다.)
            # 등록할 때 서버에서 받은 암호화된 id: eeeeeeeeeeeeeeeeeeeeee
            # 전화번호: 010-1111-2222 > aBa11112222
            # 전화번호 자릿수: 11 > Bb
            # 근로자 정보: BbaBa11112222eeeeeeeeeeeeeeeeeeeeee << Ba aBa 1111 2222 eeeeeeeeeeeeeeeeeeeeee
        t=push token (2대의 폰에서 사용을 막기 위한 용도로도 사용한다.) 인증 상태일 때는 보내지 않는다.값 (삭제 예정)
        uuid=전화번호 인증하면 받는 기기 고유 32 byte hex (인증되지 않은 상태일 때는 보내지 않는다.)

    response
        STATUS 200
            {'today': '2019/09/18 00:00:00'}  # 서버의 현재 시간 - 폰의 시간과 10초 이상 차이나면 "폰의 시간이 잘못되어있습니다." 표시하고 앱 종료
        STATUS 551
        {
            'msg': '업그레이드가 필요합니다.'
            'url': 'http://...' # itune, google play update
        }
        STATUS 416 # 개발자 수정사항 - 앱의 기존 사용자 데이터를 삭제하고 전화번호 인증부터 다시 받으세요.
            {'message': '앱이 리셋됩니다.\n다시 실행해주세요.'}
            {'message': '다른 폰에 앱이 새로 설치되어 사용할 수 없습니다.'}
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
        logSend('  passer.id: {} vs passer_id: {}'.format(passer.id, passer_id))
        if passer.id != int(passer_id):
            logError(get_api(request),
                     ' 등록된 전화번호: {}, 서버 id: {}, 앱 id: {}'.format(phone_no, passer.id, passer_id))
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '앱이 리셋됩니다.\n다시 실행해주세요.'})
        if 't' in rqst:
            logSend('[{}] vs [{}]'.format(rqst['t'], passer.push_token))
            if rqst['t'] == 'Token_did_not_registration':
                passer.push_token = rqst['t']
                passer.save()
            elif rqst['t'] != passer.push_token:
                return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '다른 폰에 앱이 새로 설치되어 사용할 수 없습니다.'})
        if 'uuid' in rqst:
            logSend('[{}] vs [{}]'.format(rqst['uuid'], passer.uuid))
            if rqst['uuid'] == 'None':
                passer.uuid = secrets.token_hex(32)
                passer.save()
            elif rqst['uuid'] != passer.uuid:
                return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '다른 폰에 앱이 새로 설치되어 사용할 수 없습니다.'})
        if 'v' in rqst:
            passer.app_version = rqst['v']
            passer.save()

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
        url_iOS = "https://apps.apple.com/us/app/이지체크/id1477838861?l=ko&ls=1"
        url_install = ""
        if phone_type == 'A':
            url_install = url_android
        elif phone_type == 'i':
            url_install = url_iOS
        return REG_551_AN_UPGRADE_IS_REQUIRED.to_json_response({'url': url_install  # itune, google play update
                                                                })
    if 'uuid' in rqst and rqst['uuid'] == 'None':
        return REG_200_SUCCESS.to_json_response({'uuid': passer.uuid})
    return REG_200_SUCCESS.to_json_response({'today': dt_null(datetime.datetime.now())})
    # return REG_200_SUCCESS.to_json_response({'today': dt_null(datetime.datetime.now()-datetime.timedelta(seconds=9))})  # 시험용 9초


@cross_origin_read_allow
def list_my_work(request):
    """
    내가 현재 하고 있는 업무는?
    - 현재 근무하고 있는 업무의 리스트
    - 15일 전에 그만둔 업무까지 보내 준다.(분쟁이 생겼을 때 업무 담당자와 통화할 수 있도록)
    http://0.0.0.0:8000/employee/list_my_work?passer_id=B-jfwtR0WB01TAdjcSLDuA
    POST : json
        passer_id: chiper_text_id  // 암호화된 출입자 id
    response
        STATUS 200 - 아래 내용은 처리가 무시되기 때문에 에러처리는 하지 않는다.
            {'message': 'out 인데 어제 오늘 in 기록이 없다.'}
            {'message': 'in 으로 부터 12 시간이 지나서 out 을 무시한다.'}
            {
              "message": "정상적으로 처리되었습니다.",
              "works": [
                {
                    'begin': '2019/08/03',
                    'end': '2019/08/30',
                    'work_place_name': '테덕테크 서울지사',
                    'work_name_type': '안드로이드 개발 (주간)',
                    'staff_name': '홍길동',
                    'staff_pNo': '01077778888',
                    'time_info': {
                      'paid_day': 0,
                      'time_type': 0,
                      'week_hours': 40,
                      'month_hours': 209,
                      'working_days': [1, 2, 3, 4, 5],
                      'work_time_list': [
                        {
                          't_begin': '09:00',
                          't_end': '21:00',
                          'break_time_type': 1,
                          'break_time_total': '01:30'
                        },
                      ],
                      'is_holiday_work': 1
                    },
                },
                ...
              ]
            }
        STATUS 416
            {'message': '출근처리할 업무가 없습니다.'}  # 출근 버튼을 깜박이고 출퇴근 버튼을 모두 disable 하는 방안을 모색 중...
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'passer_id\' 가 없어요'}
            {'message':'ClientError: parameter \'passer_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ServerError: Passer 에 passer_id={} 이(가) 없다'.format(passer_id)}
            {'ServerError: Employee 에 employee_id={} 이(가) 없다'.format(passer.employee_id)}
    log Error
        logError(get_api(request), ' passer id: {} 중복되었다.'.format(passer_id))
        logError(get_api(request), ' employee id: {} 중복되었다.'.format(passer.employee_id))
        logError(get_api(request), ' passer 의 employee_id={} 에 해당하는 근로자가 없음.'.format(passer.employee_id))
        logError(get_api(request), ' passer 의 employee_id={} 에 해당하는 근로자가 한명 이상임.'.format(passer.employee_id))
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['passer_id_!'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    passer_id = parameter_check['parameters']['passer_id']

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
    logSend('   --- employee works: {}'.format(employee.get_works()))
    work_list = Works(employee.get_works())
    logSend('   > current work: {}'.format(work_list.find_work_by_date(datetime.datetime.now())))
    current_work = work_list.find_work_by_date(datetime.datetime.now())
    if current_work == None:
        return REG_200_SUCCESS.to_json_response({'works': []})
    work_dict = get_work_dict([current_work['id']])
    if len(work_dict.keys()) == 0:
        return REG_200_SUCCESS.to_json_response({'works': []})
    # logSend('   > work: {}, {}'.format(current_work['id'], work_dict[str(current_work['id'])]))
    work_list = [work_dict[str(current_work['id'])]]
    work_time_list = work_list[0]['time_info']['work_time_list']
    logSend('  > work_time: {}'.format(work_time_list))
    for work_time in work_time_list:
        if work_time['break_time_type'] == 2:
            work_time['break_time_total'] = 0
        elif work_time['break_time_type'] == 0:
            for break_time in work_time['break_time_list']:
                begin = str2min(break_time['bt_begin'])
                end = str2min(break_time['bt_end'])
                time = end - begin
                if end < begin:
                    time = end + (1440 - begin)
                work_time['break_time_total'] = time

    work_list[0]['begin'] = current_work['begin']
    work_list[0]['end'] = current_work['end']
    return REG_200_SUCCESS.to_json_response({'works': work_list, 'work': work_list[0]})

    employee_works = employee.get_works()
    before15day = datetime.datetime.now() - timedelta(days=15)
    # before15day = datetime.datetime.now() - timedelta(days=100)
    # logSend(before15day)
    lately_work_list = [employee_work for employee_work in employee_works if before15day < str_to_dt(employee_work['end'])]
    lately_work_dict = {employee_work['id']: 'id' for employee_work in employee_works if before15day < str_to_dt(employee_work['end'])}
    # logSend('  > lately_work_dict: {}'.format(lately_work_dict))
    work_id_list = list(lately_work_dict.keys())
    work_dict = get_work_dict(work_id_list)
    # logSend('  > work_dict: {}'.format(work_dict.keys()))
    if len(work_dict.keys()) == 0:
        return REG_200_SUCCESS.to_json_response({'works': []})
    work_list = []
    for lately_work in lately_work_list:
        # logSend('  > id: {}, work_dict: {}'.format(lately_work['id'], 11))
        # logSend('  >> work_dict: {}'.format(work_dict['68']))
        work_infor = copy.deepcopy(work_dict[str(lately_work['id'])])
        work_infor['begin'] = lately_work['begin']
        work_infor['end'] = lately_work['end']
        work_list.append(work_infor)
    return REG_200_SUCCESS.to_json_response({'works': work_list, 'work': work_list[0]})


@cross_origin_read_allow
def reg_employee_for_customer(request):
    """
    <<<고객 서버용>>> 고객사에서 보낸 업무 배정 SMS로 알림 (보냈으면 X)
    -101 : sms 를 보낼 수 없는 전화번호
    -11 : 해당 전화번호를 가진 근로자의 업무와 요청 업무의 기간이 겹친다.
    -21 : 피쳐폰에 이미 업무 요청이 있어서 더 요청할 수 없다.
    http://0.0.0.0:8000/employee/reg_employee_for_customer?customer_work_id=37&work_place_name=효성1공장&work_name_type=경비 주간&dt_begin=2020/02/14&dt_end=2020/02/29&dt_answer_deadline=2020-02-13 19:00:00&dt_begin_employee=2020/02/14&dt_end_employee=2020/02/27&is_update=1&staff_name=이수용&staff_phone=01046755165&phones=01025573555&phones=01084333579&phones=01046755165
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
                "01025573555": 2,   # 고객이 앱을 설치했고 토큰이 있어서 push 를 보낸다.
                "01084333579": 1,   # 고객이 앱을 설치했지만 토큰이 없어서 SMS 를 보냈다.
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

    parameter_check = is_parameter_ok(rqst, ['customer_work_id', 'work_place_name', 'work_name_type', 'dt_begin',
                                             'dt_end', 'staff_name', 'staff_phone', 'phones', 'time_info_@',
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
    time_info = parameter_check['parameters']['time_info']


    if request.method == 'GET':
        phone_numbers = rqst.getlist('phones')
    logSend('  - phone numbers: {}'.format(phone_numbers))

    # 업무 요청 전화번호로 등록된 근로자 중에서 업무 요청을 할 수 없는 근로자를 가려낸다.
    # [phone_numbers] - [업무 중이고 예약된 근로자]
    # 출입자 검색 >> result: passer_list
    passer_list = Passer.objects.filter(pNo__in=phone_numbers)
    # 출입자 전화번호 를 키로하는 dict 만들기
    passer_pNo_dict = {passer.pNo: passer for passer in passer_list}
    logSend('  - passer_pNo_dict: {}'.format(passer_pNo_dict))

    # 출입자 list에서 근로자 id list 만들기
    employee_id_list = [passer.employee_id for passer in passer_list if passer.employee_id > 0]
    employee_list = Employee.objects.filter(id__in=employee_id_list)
    # 근로자 list 로 업무 중복 근로자 찾기
    employee_status = {}  # {1:-11} 업무 중복되는 근로자 id 를 key 로하는 근로자 dict
    logSend(' employee_status: {}'.format(employee_status))
    for employee in employee_list:
        works = Works(employee.get_works())
        logSend('  1. 현재 업무: {} vs 새 업무: {}'.format(works.data, {'id': customer_work_id, 'begin': dt_begin, 'end': dt_end}))
        # 업무 중에 같은 업무가 있으면 삭제한다. (단, 업무 시작 날짜가 오늘 이후인 업무만)
        today = datetime.datetime.now()
        for work_dict in works.data:
            if work_dict['id'] == customer_work_id:
                if is_update:
                    works.data.remove(work_dict)
                    continue
                if today < str_to_dt(work_dict['begin']):
                    works.data.remove(work_dict)
        logSend('  2. 현재 업무: {} vs 새 업무: {}'.format(works.data, {'id': customer_work_id, 'begin': dt_begin, 'end': dt_end}))
        if works.is_overlap({'id': customer_work_id, 'begin': dt_begin_employee, 'end': dt_end_employee}):
            # 중복되는 업무가 있다.
            employee_status[employee.id] = -11  # 기간이 중복된 경우
        # 업무 요청 갯수 제한 확인
        work_counter = works.work_counter(customer_work_id)  # (count_started, count_reserve) 시잔된, 예정된 업무 갯수
        if work_counter[0] >= 1:  # count_started 시작된 업무 갯수가 한개 이상이면
            if work_counter[1] >= 1:  # 예정된 업무 갯수가 하나 이상이면
                employee_status[employee.id] = -31  # 받을 수 있는 업무 갯수 제한에 걸림
        elif work_counter[1] >= 2:  # 예정된 업무 갯수가 2개 이상이면
            employee_status[employee.id] = -31  # 받을 수 있는 업무 갯수 제한에 걸림
        logSend(' employee_status: {}'.format(employee_status))
    logSend('  - bad condition phone: {} (기간이 중복되는 업무가 있는 근로자)'.format(employee_status))

    # 기간 중복이나 업무 갯수 제한에 걸린 전화번호 를 걸러낸 전화번호 찾기
    phones_state = {}
    for passer in passer_list:
        if passer.employee_id > 0:
            # 출입자에 근로자 정보가 있으면
            if passer.employee_id in employee_status.keys():
                # 출입자의 근로자가 기간 중복되는 근로자에 포함되면
                phones_state[passer.pNo] = -11  # employee_status[passer.employee_id] == -11
    last_phone_numbers = [phone_no for phone_no in phone_numbers if phone_no not in phones_state.keys()]
    logSend('  - last_phone_numbers: {} (기간 중복/업무 갯수 제한을 걸러낸 전화번호)'.format(last_phone_numbers))

    # 업무 요청이 등록된 전화번호 삭제처리
    notification_list = Notification_Work.objects.filter(is_x=False,
                                                         work_id=customer_work_id,
                                                         employee_pNo__in=phone_numbers)
    # 업무 요청 삭제 - 업무 요청을 새로 만들기 때문에...
    # 업무 요청이 이상 증상을 보여 삭제하지 않고 is_x 로 처리: 2019/09/10
    for notification in notification_list:
        notification.is_x = True
        notification.save()

    # 등록된 근로자 중에서 전화번호로 업무 요청
    msg = '이지체크\n' \
          '새로운 업무를 앱에서 확인해주세요.\n' \
          '앱 설치\n' \
          'https://api.ezchek.co.kr/rq/app'
    # msg_feature = "이지체크\n"\
    #               "효성 3공장-포장(3교대)\n"\
    #               "2019/06/07~2019/06/30\n"\
    #               "박종기 010-2557-3555".format()
    msg_feature = '이지체크\n{}-{}\n{} ~ {}\n{} {}'.format(work_place_name,
                                                       work_name_type,
                                                       dt_begin_employee,
                                                       dt_end_employee,
                                                       staff_name,
                                                       phone_format(staff_phone))
    rData = {
        'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
        'user_id': 'yuadocjon22',
        'sender': settings.SMS_SENDER_PN,
        # 'receiver': phone_numbers[i],
        'msg_type': 'SMS',
        # 'msg': msg,
    }

    push_list = []
    for phone_no in last_phone_numbers:
        logSend('  - phone_no: {}'.format(phone_no))
        is_feature_phone = False
        if phone_no in passer_pNo_dict.keys():  # 출입자로 이미 등록된 근로자 일 때
            # 피쳐폰이면 다른 요청업무가 없을 때만 문자를 보낸다.
            # 아이폰이면 token 을 확인하고 push 를 보낸다.
            # 안드로이드폰이면 token 을 확인하고 push 를 보낸다.
            phones_state[phone_no] = 1  # 등록된 SMS 대상
            passer = passer_pNo_dict[phone_no]
            if passer.pType == 10:  # 아이폰
                if len(passer.push_token) < 64:  # 토큰 없음 SMS 보냄
                    logSend('   SMS: iOS {}'.format(phone_no))
                else:
                    push_list.append({'id': passer.id, 'token': passer.push_token, 'pType': passer.pType})
                    phones_state[phone_no] = 2  # push 대상
            elif passer.pType == 20:  # 안드로이드폰
                if len(passer.push_token) < 64:  # 토큰 없음 SMS 보냄
                    logSend('   SMS: android {}'.format(phone_no))
                else:
                    push_list.append({'id': passer.id, 'token': passer.push_token, 'pType': passer.pType})
                    phones_state[phone_no] = 2  # push 대상
            elif passer.pType == 30:  # 피쳐폰
                is_feature_phone = True
                find_notification_list = Notification_Work.objects.filter(is_x=False, employee_pNo=phone_no)
                logSend('  - notification list (pNo:{}) : {}'.format(phone_no,
                                                                     [notification.employee_pNo for notification in
                                                                      find_notification_list]))
                if len(find_notification_list) > 0:  # 위에서 업무 요청을 모두 지웠기 때문에 이 요청은 갯수에 안들어 간다.
                    phones_state[phone_no] = -21  # 피쳐폰은 업무를 한개 이상 배정받지 못하게 한다.
                    continue
        else:
            phones_state[phone_no] = -1  # 등록안된 SMS 대상

        if phones_state[phone_no] in [-1, 1]:
            settings.IS_TEST = True
            logSend('>>> IS_TEST: {}'.format(settings.IS_TEST))
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
                if int(response_SMS.json()['result_code']) < 0:
                    phones_state[phone_no] = -101
                    logSend('  - sms send fail phone: {}'.format(phone_no))
                    continue
            else:
                if len(phone_no) < 10:
                    phones_state[phone_no] = -101
                    logSend('  - sms send fail phone: {} (전화번호 너무 짧다.)'.format(phone_no))
                    continue

        new_notification = Notification_Work(
            work_id=customer_work_id,
            customer_work_id='',
            employee_id=passer.id,  # phones_state[phone_no],
            employee_pNo=phone_no,
            dt_answer_deadline=dt_answer_deadline,
            dt_begin=str_to_dt(dt_begin_employee),
            dt_end=str_to_dt(dt_end_employee),
            # 이하 시스템 관리용
            work_place_name=work_place_name,
            work_name_type=work_name_type,
            # is_x=False,  # default
            # dt_reg=datetime.datetime.now(),  # default
            notification_type=-30,  # 알림 종류: -30: 새업무 알림,
            # -21: 퇴근시간 수정, -20: 출근시간 수정,
            # 근무일 구분 0: 유급휴일, 1: 주휴일(연장 근무), 2: 소정근로일, 3: 휴일(휴일/연장 근무)
            # -13: 휴일(휴일근무), -12: 소정근로일, -11: 주휴일(연장근무), -10: 유급휴일
            # -3: 반차휴무, -2: 연차휴무, -1: 조기퇴근, 0:정상근무, 1~18: 연장근무 시간
        )
        new_notification.save()
    if len(push_list) > 0:
        push_contents = {
            'target_list': push_list,
            'func': 'user',
            'isSound': True,
            'badge': 1,
            'contents': {'title': '업무 요청',
                         'subtitle': '{}: {}'.format(work_place_name, work_name_type),
                         'body': {'action': 'NewWork', 'current': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                         }
        }
        send_push(push_contents)

    return REG_200_SUCCESS.to_json_response({'result': phones_state})


def send_push(push_contents):
    push_result = notification(push_contents)
    logSend('push result: {}'.format(push_result))
    return


@cross_origin_read_allow
def update_work_for_customer(request):
    """
    <<<고객 서버용>>> 고객사에서 보낸 업무 배정 SMS로 알림 (보냈으면 X)
    - 2020/02/13 업무 내용 수정 기능 삭제
    http://0.0.0.0:8000/employee/update_work_for_customer?customer_work_id=qgf6YHf1z2Fx80DR8o_Lvg&work_place_name=효성1공장&work_name_type=경비 주간&dt_begin=2019/03/04&dt_end=2019/03/31&dt_answer_deadline=2019-03-03 19:00:00&staff_name=이수용&staff_phone=01099993333&phones=01025573555&phones=01046755165&phones=01011112222&phones=01022223333&phones=0103333&phones=01044445555
    POST : json
        {
          "customer_work_id": 37,  # 업무 id
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

    parameter_check = is_parameter_ok(rqst, ['customer_work_id', 'dt_begin_employee', 'dt_end_employee'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    customer_work_id = parameter_check['parameters']['customer_work_id']
    dt_begin_employee = parameter_check['parameters']['dt_begin_employee']
    dt_end_employee = parameter_check['parameters']['dt_end_employee']

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
            if employee_work['id'] == customer_work_id:
                if str_to_dt(employee_work['begin']) < str_to_dt(dt_begin_employee):
                    employee_work['begin'] = dt_begin_employee
                if str_to_dt(dt_end_employee) < str_to_dt(employee_work['end']):
                    employee_work['end'] = dt_end_employee
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
        STATUS 422
            {'message': 'ClientError: parameter \'passer_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'passer_id\' 가 정상적인 값이 아니예요.'}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['passer_id_!'])
    if not parameter_check['is_ok']:
        return status422(get_api(request), {'message': '{}'.format(''.join([message for message in parameter_check['results']]))})
    passer_id = parameter_check['parameters']['passer_id']

    try:
        passer = Passer.objects.get(id=passer_id)
    except Exception as e:
        logError('  employee_passer 에 passer_id:{} 없음.'.format(passer_id))
        return REG_403_FORBIDDEN.to_json_response({'message': '알 수 없는 사용자입니다.'})

    dt_today = datetime.datetime.now()
    logSend(passer.pNo)
    # notification_list = Notification_Work.objects.filter(is_x=False, employee_pNo=passer.pNo, dt_answer_deadline__gt=dt_today)
    notification_list = Notification_Work.objects.filter(is_x=False, employee_pNo=passer.pNo)
    logSend('  notification: {}'.format([x.dt_begin for x in notification_list]))
    arr_notification = []
    work_dict = get_work_dict([notification.work_id for notification in notification_list])
    for notification in notification_list:
        # dt_answer_deadline 이 지났으면 처리하지 않고 notification_list 도 삭제
        # 2019/05/17 임시 기능 정지 - 업무 시작 후 업무 참여요청 보낼 필요 발생
        # if notification.dt_answer_deadline < datetime.datetime.now():
        #     notification.delete()
        #     continue
        work = work_dict[str(notification.work_id)]
        view_notification = {
            'id': AES_ENCRYPT_BASE64(str(notification.id)),
            'work_place_name': work['work_place_name'],
            'work_name_type': work['work_name_type'],
            'staff_name': work['staff_name'],
            'staff_pNo': work['staff_pNo'],
            'dt_answer_deadline': dt_str(notification.dt_answer_deadline, "%Y-%m-%d %H:%M"),
            'begin': dt_str(notification.dt_begin, "%Y/%m/%d"),
            'end': dt_str(notification.dt_end, "%Y/%m/%d"),
        }
        arr_notification.append(view_notification)
    return REG_200_SUCCESS.to_json_response({'notifications': arr_notification})


@cross_origin_read_allow
def notification_list_v2(request):
    """
    foreground request 새로운 업무 알림: 앱이 foreground 상태가 될 때 가져와서 선택할 수 있도록 표시한다.
    http://dev.ddtechi.com:8055/employee/notification_list_v2?passer_id=qgf6YHf1z2Fx80DR8o_Lvg
    GET
        passer_id='서버로 받아 저장해둔 출입자 id'  # 암호화된 값임
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "notifications": [
                {
                    "id": "yTKazFfuKEJ_fGBbPU84Ag",             # 알림 id (사용 X)
                    "work_place_name": "서울지사",                  # 사업장
                    "work_name_type": "기획 (주간)",                # 업무(형태)
                    "staff_name": "박종기",                        # 담당 관리자
                    "staff_pNo": "010-2557-3555",               # 담당 관리자 전화번호
                    "dt_answer_deadline": "2020-03-26 01:32",   # 결정 시한 이 시간이 지나면 보내지 않음 (???)
                    "begin": "2020/03/23",                      # 사용 X
                    "end": "2019/12/05",                        # 사용 X
                    "notification_type": -20,                   # 알림 종류: -30: 새업무 알림, -21: 퇴근시간 수정, -20: 출근시간 수정, -4: 유급휴일 해제, -3: 유급휴일 지정, -2: 연차휴무, -1: 조기퇴근, 0:정상근무, 1~18: 연장근무 시간
                    "notification_type_str": "출근시간 수정",         # 알렴 설명
                    "comment": "출근 시간이 2020-03-23 08:25:00 으로 수정되었습니다.", # 전달 사항
                    "dt_io": "2020-03-23 08:25"                     # 출퇴근시간 변경일 때 변경될 시간
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
        STATUS 422
            {'message': 'ClientError: parameter \'passer_id\' 가 없어요'}
            {'message': 'ClientError: parameter \'passer_id\' 가 정상적인 값이 아니예요.'}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['passer_id_!'])
    if not parameter_check['is_ok']:
        return status422(get_api(request), {'message': '{}'.format(''.join([message for message in parameter_check['results']]))})
    passer_id = parameter_check['parameters']['passer_id']

    try:
        passer = Passer.objects.get(id=passer_id)
    except Exception as e:
        logError('  employee_passer 에 passer_id:{} 없음.'.format(passer_id))
        return REG_403_FORBIDDEN.to_json_response({'message': '알 수 없는 사용자입니다.'})

    dt_today = datetime.datetime.now()
    logSend(passer.pNo)
    # notification_list = Notification_Work.objects.filter(is_x=False, employee_pNo=passer.pNo, dt_answer_deadline__gt=dt_today)
    notification_list = Notification_Work.objects.filter(is_x=0, employee_pNo=passer.pNo)
    # logSend('  notification: {}'.format([x.work_id for x in notification_list]))
    notification_work_id_dict = {notification.work_id: notification.id for notification in notification_list}
    # logSend('  notification work_id list: {}'.format(list(notification_work_id_dict.keys())))
    arr_notification = []
    work_dict = get_work_dict(list(notification_work_id_dict.keys()))
    notification_type_dict = {-30: '새업무',
                              -23: '퇴근 취소', -22: '출근 취소', -21: '퇴근시간 수정', -20: '출근시간 수정',
                              -13: '휴일(휴일근무)', -12: '소정근로일', -11: '주휴일(연장근무)', -10: '유급휴일',
                              -3: '반차휴무', -2: '연차휴무', -1: '조기퇴근', 0: '정상근무'}
    for notification in notification_list:
        # dt_answer_deadline 이 지났으면 처리하지 않고 notification_list 도 삭제
        if notification.dt_answer_deadline < datetime.datetime.now():
            notification.is_x = 3
            notification.save()
            continue
        work = work_dict[str(notification.work_id)]
        view_notification = {
            'id': AES_ENCRYPT_BASE64(str(notification.id)),
            'work_place_name': work['work_place_name'],
            'work_name_type': work['work_name_type'],
            'staff_name': work['staff_name'],
            'staff_pNo': work['staff_pNo'],
            # 'dt_answer_deadline': dt_str(notification.dt_answer_deadline, "%Y-%m-%d %H:%M"),
            'dt_answer_deadline': dt_str(notification.dt_answer_deadline, "%Y/%m/%d %H:%M"),
            'begin': dt_str(notification.dt_begin, "%Y/%m/%d"),
            'end': dt_str(notification.dt_end, "%Y/%m/%d"),
            'notification_type': notification.notification_type,
            'notification_type_str': notification_type_dict[notification.notification_type] if notification.notification_type <= 0 else "연장근무",
            'comment': notification.comment,
            # 'dt_io': dt_str(notification.dt_inout, "%Y-%m-%d %H:%M"),
            'dt_io': dt_str(notification.dt_inout, "%Y/%m/%d %H:%M"),
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
            {'message':'업무 요청이 취소되었습니다.'}
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
    is_accept = int(parameter['parameters']['is_accept'])
    logSend('  is_accept = {}'.format(is_accept))

    passers = Passer.objects.filter(id=passer_id)
    if len(passers) == 0:
        return status422(get_api(request), {'message': '출입자({}) 가 없어요'.format(passer_id)})
    passer = passers[0]

    notifications = Notification_Work.objects.filter(is_x=False, id=notification_id)
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
        new_work = {'id': notification.work_id,
                    'begin': dt_str(notification.dt_begin, "%Y/%m/%d"),
                    'end': dt_str(notification.dt_end, "%Y/%m/%d"),
                    }
        if employee_works.find(notification.work_id):
            logSend('  > 이미 등록되어 있는 업무다. work_id: {}'.format(notification.work_id))
        elif employee_works.is_overlap(new_work):
            logSend('  > 업무 기간이 겹쳤다.(업무 부여할 때 겹침을 확인하는데 가능한가?')
            # 다른 업무와 겹쳤을 때 (이게 가능한가?)
            is_accept = 0
        else:
            # 근로자에 업무를 추가해서 저장한다.
            employee_works.add(new_work)
            employee.set_works(employee_works.data)
            employee.save()
        count_work = 0
        for work in employee_works.data:
            if datetime.datetime.now() < str_to_dt(work['begin']):
                count_work += 1
        logSend('  - 예약된 업무(시작 날짜가 오늘 이후인 업무): {}'.format(count_work))
        logSend('  - name: ', employee.name)
        logSend('  - works: {}'.format([work for work in employee_works.data]))
    else:
        # 거절했을 경우 - 근로자가 업무를 가지고 있으면 삭제한다.
        logSend('  - 거절: works 에 있으면 삭제')
        if employee_works.find(notification.work_id):
            del employee_works.data[employee_works.index]
        employee.set_works(employee_works.data)
        employee.save()
    #
    # to customer server
    # 근로자가 수락/거부했음
    #
    request_data = {
        'worker_id': AES_ENCRYPT_BASE64('thinking'),
        'work_id': notification.work_id,
        'employee_id': AES_ENCRYPT_BASE64(str(passer.id)),  # employee.id,
        'employee_name': employee.name,
        'employee_pNo': notification.employee_pNo,
        'is_accept': is_accept
    }
    response_customer = requests.post(settings.CUSTOMER_URL + 'employee_work_accept_for_employee', json=request_data)
    logSend(response_customer.json())
    if response_customer.status_code != 200:
        return ReqLibJsonResponse(response_customer)

    # 정상적으로 처리되었을 때 알림을 완료한다.
    # notification.delete()
    notification.is_x = True
    notification.save()
    logSend('  - is_accept: {}'.format(is_accept))
    return REG_200_SUCCESS.to_json_response({'is_accept': is_accept})


@cross_origin_read_allow
def notification_accept_v2(request):
    """
    새로운 업무에 대한 응답
    http://dev.ddtechi.com:8055/employee/notification_accept_v2?passer_id=qgf6YHf1z2Fx80DR8o_Lvg&notification_id=qgf6YHf1z2Fx80DR8o_Lvg&is_accept=0
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
            {'message':'업무 요청이 취소되었습니다.'}
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
    is_accept = int(parameter['parameters']['is_accept'])
    logSend('  is_accept = {}'.format(is_accept))

    try:
        passer = Passer.objects.get(id=passer_id)
    except Exception as e:
        return status422(get_api(request), {'message': '출입자({}) 가 없어요'.format(passer_id)})

    try:
        notification = Notification_Work.objects.get(is_x=0, id=notification_id)
    except Exception as e:
        return status422(get_api(request), {'message': 'Notification_Work 알림({}) 가 없어요'.format(notification_id)})

    try:
        employee = Employee.objects.get(id=passer.employee_id)
    except Exception as e:
        return status422(get_api(request), {'message': 'passer({}) 의 근로자 정보가 없어요.'.format(passer.employee_id)})
    employee_works = Works(employee.get_works())
    logSend('  - employee works: {}'.format([work for work in employee_works.data]))
    #
    # 근로자 정보에 업무를 등록 - 수락했을 경우만
    #
    if is_accept == 1:
        # 수락했을 경우
        if notification.notification_type == -30:
            #
            # (업무 요청)에 대한 처리
            #
            logSend('  - 수락: works: {}'.format([work for work in employee_works.data]))
            new_work = {'id': notification.work_id,
                        'begin': dt_str(notification.dt_begin, "%Y/%m/%d"),
                        'end': dt_str(notification.dt_end, "%Y/%m/%d"),
                        }
            if employee_works.is_overlap(new_work):
                logSend('  > 업무 기간이 겹쳤다.(업무 부여할 때 겹침을 확인하는데 가능한가?')
                # 다른 업무와 겹쳤을 때 (이게 가능한가?)
                is_accept = 0
            elif employee_works.find(notification.work_id):
                logSend('  > 이미 등록되어 있는 업무다. work_id: {}'.format(notification.work_id))
            else:
                # 근로자에 업무를 추가해서 저장한다.
                employee_works.add(new_work)
                employee.set_works(employee_works.data)
                employee.save()
            count_work = 0
            for work in employee_works.data:
                if datetime.datetime.now() < str_to_dt(work['begin']):
                    count_work += 1
            logSend('  - 예약된 업무(시작 날짜가 오늘 이후인 업무): {}'.format(count_work))
            logSend('  - name: ', employee.name)
            logSend('  - works: {}'.format([work for work in employee_works.data]))
        else:
            #
            # (근태정보 변경)에 대한 처리
            #
            if notification.dt_answer_deadline < datetime.datetime.now():
                notification.is_x = 3  # 확인 시간을 초과했다.
                notification.save()
                return REG_200_SUCCESS.to_json_response({'is_accept': is_accept})

            year_month_day = dt_str(notification.dt_inout, "%Y-%m-%d")
            pass_record_list = Pass_History.objects.filter(work_id=notification.work_id, passer_id=notification.employee_id, year_month_day=year_month_day)
            if len(pass_record_list) == 0:
                pass_record = Pass_History(
                    passer_id=notification.employee_id,
                    work_id=notification.work_id,
                    year_month_day=year_month_day,
                    action=0,
                    # x=x,
                    # y=y,
                )
                work_dict = get_work_dict([notification.work_id])
                work = work_dict[list(work_dict.keys())[0]]
                work['id'] = list(work_dict.keys())[0]
                update_pass_history(pass_record, work)
                pass_record.save()
            else:
                pass_record = pass_record_list[0]

            pass_record.dt_accept = datetime.datetime.now()
            if notification.notification_type == -21:  # 퇴근시간 수정
                pass_record.dt_out_verify = notification.dt_inout
                pass_record.out_staff_id = notification.staff_id
            elif notification.notification_type == -20:  # 출근시간 수정
                pass_record.dt_in_verify = notification.dt_inout
                pass_record.in_staff_id = notification.staff_id
            elif notification.notification_type == -22:  # 출근시간 삭제
                pass_record.dt_in_verify = None
                pass_record.in_staff_id = notification.staff_id
            elif notification.notification_type == -23:  #퇴근시간 삭제
                pass_record.dt_out_verify = None
                pass_record.in_staff_id = notification.staff_id
            elif notification.notification_type == -5:  # 소정근로일 부여
                pass_record.day_type = 2
                pass_record.day_type_staff_id = notification.staff_id
            elif notification.notification_type == -4:  # 무급휴일 부여
                pass_record.day_type = 1
                pass_record.day_type_staff_id = notification.staff_id
            elif notification.notification_type == -3:  # 유급휴일 부여
                pass_record.day_type = 0
                pass_record.day_type_staff_id = notification.staff_id
            # elif notification.notification_type == -2:  # 연차휴무 부여
            # elif notification.notification_type == -1:  # 조기퇴근 부여
            # elif notification.notification_type == 0:  # 연차휴무, 조기퇴근, 연장근로 취소
            else:  # 연장근로 부여
                pass_record.overtime = notification.notification_type
                pass_record.overtime_staff_id = notification.staff_id
            pass_record.save()
            # if notification.pass_record_id is not -1:
            #     try:
            #         pass_record = Pass_History.objects.get(id=notification.pass_record_id)
            #     except Exception as e:
            #         return status422(get_api(request),
            #                          {'message': 'pass_record({}) 의 근태 정보가 없어요.'.format(notification.pass_record_id)})
            #     pass_record.dt_accept = datetime.datetime.now()
            #     pass_record.save()
            #
            notification.is_x = 1  # 처리완료 (삭제와 같은 효과)
            notification.save()
    else:
        # 거절했을 경우 - 근로자가 업무를 가지고 있으면 삭제한다.
        if notification.notification_type == -30:
            logSend('  - 거절: works 에 있으면 삭제')
            if employee_works.find(notification.work_id):
                del employee_works.data[employee_works.index]
            employee.set_works(employee_works.data)
            employee.save()
        else:
            #
            # pass_history 에
            #
            notification.is_x = 2  # 관리자의 근태 정보 변경을 거절했다.
            notification.save()
    if notification.notification_type == -30:
        #
        # to customer server
        # 근로자가 수락/거부했음
        #
        request_data = {
            'worker_id': AES_ENCRYPT_BASE64('thinking'),
            'work_id': notification.work_id,
            'employee_id': AES_ENCRYPT_BASE64(str(passer.id)),  # employee.id,
            'employee_name': employee.name,
            'employee_pNo': notification.employee_pNo,
            'is_accept': is_accept
        }
        response_customer = requests.post(settings.CUSTOMER_URL + 'employee_work_accept_for_employee', json=request_data)
        logSend(response_customer.json())
        if response_customer.status_code != 200:
            return ReqLibJsonResponse(response_customer)

        # 정상적으로 처리되었을 때 알림을 완료한다.
        # notification.delete()
        notification.is_x = 1  # 처리완료 (삭제와 같은 효과)
        notification.save()
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
    출입등록 : 앱에서 인식된 비콘 값을 서버로 보낸다.
        - 인식은 앱이 포그라운드가 되어있는 시간동안에 인식된 값이다.
        - 앱이 포그라운드가 되면 그전 비콘 값을 지우고 새로 수집한다.
        - 수집 대상은 비콘 처음 인식시간, 처음 인식한 신호 강도, 마지막 인식시간, 처음과 마지막 인식시간 동안 수집된 갯
        http://0.0.0.0:8000/employee/pass_reg?passer_id=qgf6YHf1z2Fx80DR8o/Lvg&dt=2019-05-7 17:45:00&is_in=0&major=11001&beacons=
    POST : json
        {
            'passer_id' : '앱 등록시에 부여받은 암호화된 출입자 id',
            'dt' : '2018-01-21 08:25:30',
            'is_in' : 1, # 0: out, 1 : in
            'major' : 11001, # 11 (지역) 001(사업장)
            'beacons' : [
                 {'minor': 11001, 'dt_begin': '2019-01-21 08:25:30', 'rssi': -70, 'dt_end': '2019-01-21 08:30:00', 'count': 660},  # 5:30 초당 2번
                 {'minor': 11002, 'dt_begin': '2019-01-21 08:25:31', 'rssi': -70, 'dt_end': '2019-01-21 08:30:01', 'count': 660},  # 5:30 초당 2번
                 {'minor': 11003, 'dt_begin': '2019-01-21 08:25:32', 'rssi': -70, 'dt_end': '2019-01-21 08:30:02', 'count': 660},  # 5:30 초당 2번
            ]
            'x': latitude (optional),
            'y': longitude (optional),
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

    parameter_check = is_parameter_ok(rqst, ['passer_id_!', 'dt', 'is_in', 'major', 'beacons', 'x_@', 'y_@'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    passer_id = parameter_check['parameters']['passer_id']
    dt = parameter_check['parameters']['dt']
    dt_touch = str_to_datetime(dt)  #datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
    is_in = int(parameter_check['parameters']['is_in'])
    major = parameter_check['parameters']['major']
    if request.method == 'POST':
        beacons = rqst['beacons']
    else:
        today = dt_str(datetime.datetime.now(), "%Y-%m-%d")
        beacons = [
            {'minor': 11001, 'dt_begin': '{} 08:25:30'.format(today), 'rssi': -70, 'dt_end': '{} 08:30:01'.format(today), 'count': 660},
            {'minor': 11002, 'dt_begin': '{} 08:25:31'.format(today), 'rssi': -60, 'dt_end': '{} 08:30:01'.format(today), 'count': 660},
            {'minor': 11003, 'dt_begin': '{} 08:25:32'.format(today), 'rssi': -50, 'dt_end': '{} 08:30:01'.format(today), 'count': 660},
        ]
    x = parameter_check['parameters']['x']
    y = parameter_check['parameters']['y']
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
                uuid='3c06aa91-984b-be81-d8ea-82af46f4cda4',
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
            rssi=beacons[i]['rssi'],
            x=x,
            y=y,
        )
        if 'dt_end' in beacons[i]:
            new_beacon_record.dt_end = beacons[i]['dt_end']
        if 'count' in beacons[i]:
            new_beacon_record.count = beacons[i]['count']
        new_beacon_record.save()

    # 통과 기록 저장
    new_pass = Pass(
        passer_id=passer_id,
        is_in=is_in,
        is_beacon=True,
        dt=dt,
        x=x,
        y=y,
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
    if not employee_works.is_active(dt_touch):
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
                x=x,
                y=y,
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
def pass_beacon(request):
    """
### 출입할 때 beacon 값을 서버에 전달
    - 수집: 앱이 포그라운드 상태가 되면 그전 수집 값을 지우고 새로 수집을 시작한다.
    - 전달: 앱이 백그라운드 상태가 될 때 서버로 전달한다.
    - 수집 내용: major, minor, dt_begin(첫 인식시간), dt_end(마지막 인식시간), rssi(신호강도 값의 최저치), count(인식 시간동안 인식 횟수)

##### 시험 사례
    http://0.0.0.0:8000/employee/pass_beacon?passer_id=qgf6YHf1z2Fx80DR8o/Lvg&dt=2019-05-7 17:45:00&is_in=0&major=11001&beacons=

##### POST : json
    {
        'passer_id' : '앱 등록시에 부여받은 암호화된 출입자 id',
        'dt' : '2018-01-21 08:25:30',
        'is_in' : 1,        # 0: out, 1 : in
        'major' : 11001,    # 11 (지역) 001(사업장)
        'beacons' : [
             {'minor': 11001, 'dt_begin': '2019-01-21 08:25:30', 'rssi': -70, 'dt_end': '2019-01-21 08:30:00', 'count': 660},  # 5:30 초당 2번
             {'minor': 11002, 'dt_begin': '2019-01-21 08:25:31', 'rssi': -70, 'dt_end': '2019-01-21 08:30:01', 'count': 660},  # 5:30 초당 2번
             {'minor': 11003, 'dt_begin': '2019-01-21 08:25:32', 'rssi': -70, 'dt_end': '2019-01-21 08:30:02', 'count': 660},  # 5:30 초당 2번
        ]
        'x': 37.6135,       # latitude (optional),
        'y': 126.8350,      # longitude (optional),
    }
##### response
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
##### log Error
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

    parameter_check = is_parameter_ok(rqst, ['passer_id_!', 'dt', 'is_in', 'major', 'beacons', 'x_@', 'y_@'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    passer_id = parameter_check['parameters']['passer_id']
    dt = parameter_check['parameters']['dt']
    dt_beacon = str_to_datetime(dt)  #datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
    is_in = int(parameter_check['parameters']['is_in'])
    major = parameter_check['parameters']['major']
    if request.method == 'POST':
        beacons = rqst['beacons']
    else:
        today = dt_str(datetime.datetime.now(), "%Y-%m-%d")
        beacons = [
            {'minor': 11001, 'dt_begin': '{} 08:25:30'.format(today), 'rssi': -70, 'dt_end': '{} 08:30:01'.format(today), 'count': 660},
            {'minor': 11002, 'dt_begin': '{} 08:25:31'.format(today), 'rssi': -60, 'dt_end': '{} 08:30:01'.format(today), 'count': 660},
            {'minor': 11003, 'dt_begin': '{} 08:25:32'.format(today), 'rssi': -50, 'dt_end': '{} 08:30:01'.format(today), 'count': 660},
        ]
    x = parameter_check['parameters']['x']
    y = parameter_check['parameters']['y']
    logSend(beacons)
    try:
        passer = Passer.objects.get(id=passer_id)
    except Exception as e:
        logError(get_api(request), ' ServerError: passer_id={} 이(가) 없거나 중복됨'.format(passer_id))
        return REG_200_SUCCESS.to_json_response({'message': '출입자로 등록되지 않았다.'})

    for i in range(len(beacons)):
        # 비콘 이상 유무 확인을 위해 비콘 날짜, 인식한 근로자 앱 저장
        beacon_list = Beacon.objects.filter(major=major, minor=beacons[i]['minor'])
        logSend('  {} {}: {}'.format(major, beacons[i]['minor'], {x.id: dt_null(x.dt_last) for x in beacon_list}))
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
                uuid='3c06aa91-984b-be81-d8ea-82af46f4cda4',
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
            rssi=beacons[i]['rssi'],
            x=x,
            y=y,
        )
        if 'dt_end' in beacons[i]:
            new_beacon_record.dt_end = beacons[i]['dt_end']
        if 'count' in beacons[i]:
            new_beacon_record.count = beacons[i]['count']
        new_beacon_record.save()

    # 통과 기록 저장
    try:
        year_month_day = dt[0:10]
        passer_pass_list = Pass.objects.filter(passer_id=passer_id, is_in=is_in, dt__contains=year_month_day)
        passer_pass = passer_pass_list[0]
        logSend('  > #: {}'.format(len(passer_pass_list)))
        if is_in == 1:
            # 출근했을 때
            if dt_beacon < passer_pass.dt:
                # 비콘으로 안으로 들어온 시간이 더 일찍이면 시간 변경 - 발생 가능성 없음
                logSend('  >> 비콘 시간에 출근시간인데 더 빨라진 경우: 발생하면 안됨')
                passer_pass.dt = dt_beacon
                passer_pass.save()
        else:
            # 퇴근할 때
            if passer_pass.dt < dt_beacon:
                # 비콘의 시간이 변경되면 밖으로 나간 시간을 변경 - 거의 발생
                logSend('  >> 비콘 시간에 출근시간인데 더 빨라진 경우: 발생하면 안됨')
                passer_pass.dt = dt_beacon
                passer_pass.save()
    except Exception as e:
        logSend('  > new pass: none: {}'.format(e))
        new_pass = Pass(
            passer_id=passer_id,
            is_in=is_in,
            is_beacon=True,
            dt=dt,
            x=x,
            y=y,
        )
        new_pass.save()
    #
    # Pass_History update
    #
    if passer.employee_id == -2:
        # 전화번호로 출입만 관리되는 출입자
        try:
            pass_history = Pass_History.objects.get(passer_id=passer_id, work_id=-1, year_month_day=dt[0:10])
        except Exception as e:
            pass_history = Pass_History(
                passer_id=passer_id,
                work_id=-1,
                year_month_day=dt[0:10],    # 2020-05-18 19:00:00 >> dt[0:10] >> 2020-05-18
                x=x,
                y=y,
            )
        if is_in == 1:
            if pass_history.dt_in is None:
                pass_history.dt_in = dt_beacon
            elif dt_beacon < pass_history.dt_in:
                pass_history.dt_in = dt_beacon
        else:
            if pass_history.dt_out is None:
                pass_history.dt_out = dt_beacon
            elif pass_history.dt_out < dt_beacon:
                pass_history.dt_out = dt_beacon
        pass_history.save()
        return REG_200_SUCCESS.to_json_response()
    try:
        employee = Employee.objects.get(id=passer.employee_id)  # employee_id < 0 인 경우도 잘 처리될까?
    except Exception as e:
        # db 에 근로자 정보가 없으면 - 출입자 중에 근로자 정보가 없는 경우, 등록하지 않은 경우, 피쳐폰인 경우
        return REG_200_SUCCESS.to_json_response({'message': '근로자 정보가 없다.'})
    employee_works = Works(employee.get_works())
    if len(employee_works.data) == 0:
        # 근로자 정보에 업무가 없다.
        return REG_200_SUCCESS.to_json_response({'message': '근로자에게 배정된 업무가 없다.'})
    if not employee_works.is_active(dt_beacon):
        # 현재 하고 있는 없무가 없다.
        return REG_200_SUCCESS.to_json_response({'message': '근로자가 현재 출퇴근하는 업무가 없다.'})
    logSend('  > index: {}, id: {}, begin: {}, end: {}'.format(employee_works.index, employee_works.data[employee_works.index]['id'], employee_works.data[employee_works.index]['begin'], employee_works.data[employee_works.index]['end']))
    employee_work = employee_works.data[employee_works.index]
    work_dict = get_work_dict([employee_work['id']])
    # logSend('  > {} - {}'.format(employee_work['id'], work_dict))
    work = work_dict[list(work_dict.keys())[0]]
    work['id'] = list(work_dict.keys())[0]
    logSend('  > work id: {}, {}({}) - {}'.format(work['id'], work['name'], work['type'], work['work_place_name']))
    year_month_day = dt[0:10]  # 2020-05-19 00:00:00 >> [0:10] >> 2020-05-19
    pass_histories = Pass_History.objects.filter(passer_id=passer_id, work_id=work['id'], year_month_day=year_month_day)
    #
    # Pass_History update
    #
    if not is_in:
        # out touch 일 경우
        time_gap = 1440
        mins_touch = str2min(dt[11:16])
        # logSend('   >>> time_info: {}'.format(work['time_info']))
        work_time_list = work['time_info']['work_time_list']
        for work_time in work_time_list:
            if str2min(work_time['t_begin']) >= str2min(work_time['t_end']):
                # 퇴근시간이 더 빠르면 전날 출근해서 다음날 퇴근하는 케이스다.
                work_time['is_next_day'] = True
            else:
                work_time['is_next_day'] = False
            work_time['gap_out'] = abs(mins_touch - str2min(work_time['t_end']))
            if time_gap > work_time['gap_out']:
                time_gap = work_time['gap_out']
                current_work_time = work_time
        # logSend('  >>> work_time_list: {}'.format(work_time_list))
        logSend('  >>> current_work_time: {}'.format(current_work_time))
        # ? 연장근무나 시간 수정이 되었을 때
        # ? 문제가 발생할 수 있다.
        yesterday = dt_beacon - datetime.timedelta(days=1)
        yesterday_year_month_day = yesterday.strftime("%Y-%m-%d")
        yesterday_pass_histories = Pass_History.objects.filter(passer_id=passer_id,
                                                               year_month_day=yesterday_year_month_day)
        if len(pass_histories) == 0:
            # in (츨근 처리를 하지 않았다.)
            # out 인데 오늘 날짜 pass_history 가 없다? >> 그럼 어제 저녁에 근무 들어갔겠네!
            if len(yesterday_pass_histories) == 0:
                # out 인데 어제, 오늘 in 기록이 없다?
                # 1. 어제 출근해서 오늘 퇴근하는 근무시간이 없으면 현재시간으로 퇴근시간을 처리한다.
                # 2. 연장근무 시간을 차감한 퇴근시간과 유사한 근무시간을 찾는다.
                logError(get_api(request),
                         ' passer_id={} out touch 인데 어제, 오늘 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
                if current_work_time['is_next_day']:
                    logSend('  > 어제 출근 오늘 퇴근 근무시간: 출근이 없어서 만든다.')
                    pass_history = Pass_History(
                        passer_id=passer_id,
                        year_month_day=yesterday_year_month_day,
                        action=0,
                        work_id=work_id,
                        x=x,
                        y=y,
                    )
                else:
                    logSend('  > 오늘 출근 오늘 퇴근 근무시간: 출근이 없어서 만든다.')
                    pass_history = Pass_History(
                        passer_id=passer_id,
                        year_month_day=year_month_day,
                        action=0,
                        work_id=work_id,
                        x=x,
                        y=y,
                    )
            elif current_work_time['is_next_day']:
                # 어제 출근이 있는 경우
                logSend('  > 어제 출근에 오늘 퇴근 근무시간: 어제 근무시간에 퇴근을 넣는다.')
                pass_history = yesterday_pass_histories[0]
            else:
                logSend('  > 오늘 출근에 오늘 퇴근 근무시간: 오늘 근무시간을 만든다.(출근 시간 누락)')
                # 오늘 pass_history 가 없어서 새로 만든다.
                pass_history = Pass_History(
                    passer_id=passer_id,
                    year_month_day=year_month_day,
                    action=0,
                    work_id=work['id'],
                    x=x,
                    y=y,
                )
        elif current_work_time['is_next_day']:
            logSend('  > 어제 출근에 오늘 퇴근 근무시간: 오늘 출근이 있어도 어제에 넣는다.')
            pass_history = yesterday_pass_histories[0]
        else:
            logSend('  > 오늘 출근에 오늘 퇴근 근무시간: 오늘 근무시간에 퇴근을 넣는다.')
            pass_history = pass_histories[0]

        if pass_history.dt_out is None:
            pass_history.dt_out = dt_beacon
        elif pass_history.dt_out < dt_beacon:
            pass_history.dt_out = dt_beacon
    else:
        # in baecon 일 경우
        if len(pass_histories) == 0:
            # 오늘 날짜 pass_history 가 없어서 새로 만든다.
            pass_history = Pass_History(
                passer_id=passer_id,
                year_month_day=year_month_day,
                action=0,
                work_id=work['id'],
                x=x,
                y=y,
            )
        else:
            pass_history = pass_histories[0]

        if pass_history.dt_in is None:
            pass_history.dt_in = dt_beacon
        elif dt_beacon < pass_history.dt_in:
            pass_history.dt_in = dt_beacon
        # elif :  # 앱 실행 후 처음이 [출근]이라 [퇴근]눌러야 할 경우 [출근]을 눌러서 [츨근]을 덮어 써야하는 상황
        # 첫날 데이터가 퇴근 인 상황에서 출근으로 처리하면 퇴근이 안되는 현상

    pass_history.save()
    return REG_200_SUCCESS.to_json_response()


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
            'beacons' : [
                 {'major': 11001, 'minor': 11001, 'dt_begin': '2019-01-21 08:25:30', 'rssi': -70, 'dt_end': '2019-01-21 08:30:00', 'count': 660},  # 5:30 초당 2번
                 {'major': 11001, 'minor': 11002, 'dt_begin': '2019-01-21 08:25:31', 'rssi': -70, 'dt_end': '2019-01-21 08:30:01', 'count': 660},  # 5:30 초당 2번
                 {'major': 11001, 'minor': 11003, 'dt_begin': '2019-01-21 08:25:32', 'rssi': -70, 'dt_end': '2019-01-21 08:30:02', 'count': 660},  # 5:30 초당 2번
            ]
            'x': latitude (optional)
            'y': longitude (optional)
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

    parameter_check = is_parameter_ok(rqst, ['passer_id_!', 'dt', 'is_in', 'x_@', 'y_@', 'beacons_@'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    passer_id = parameter_check['parameters']['passer_id']
    dt = parameter_check['parameters']['dt']
    dt_touch = str_to_datetime(dt)  #datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
    is_in = int(parameter_check['parameters']['is_in'])
    beacons = parameter_check['parameters']['beacons']
    x = parameter_check['parameters']['x']
    y = parameter_check['parameters']['y']
    logSend(' x: {}, y:{}'.format(x, y))
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
    logSend('  > employee_works: {}'.format(employee_works.data))
    if not employee_works.is_active(dt_touch):
        message = '출근처리할 업무가 없습니다.\npasser.id: {}\nemployee.name: {}\nworks: {}'.format(passer.id, employee.name, employee_works)
        send_slack(' <상용> employee/pass_verify \npasser.id: {}\nemployee.name: {}\nworks: {}'.format(passer.id, employee.name, employee_works),
                   message, channel='#server_bug')
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '출근처리할 업무가 없습니다.'})
    work_id = employee_works.data[employee_works.index]['id']
    work = get_work_dict([work_id])
    #
    # 1. 기존에 인식했던 비콘이면 통과 (passer.beacons)
    # 2. 새로운 비콘이면 비콘 위치 > 업무 출근 위치 > 업무 출근 위치와 30m 이내이면 출근인정 > 인정된 비콘 저장 (passer.beacons)
    #

    #
    # Pass_History update
    #
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
                        x=x,
                        y=y,
                    )
                else:
                    logSend('  어제 오늘 출퇴근 기록이 없고 9시 이후라 오늘 날짜로 처리한다.')
                    # 오늘 pass_history 가 없어서 새로 만든다.
                    pass_history = Pass_History(
                        passer_id=passer_id,
                        year_month_day=year_month_day,
                        action=0,
                        work_id=work_id,
                        x=x,
                        y=y,
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
                    x=x,
                    y=y,
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
        # in touch 일 경우 (출근 버튼이 눌렸을 때)
        if len(pass_histories) == 0:
            # 오늘 날짜 pass_history 가 없어서 새로 만든다.
            pass_history = Pass_History(
                passer_id=passer_id,
                year_month_day=year_month_day,
                action=0,
                work_id=work_id,
                x=x,
                y=y,
            )
        else:
            pass_history = pass_histories[0]

        if pass_history.dt_in_verify is None:
            pass_history.dt_in_verify = dt_touch
            pass_history.dt_in_em = dt_touch
        # elif :  # 앱 실행 후 처음이 [출근]이라 [퇴근]눌러야 할 경우 [출근]을 눌러서 [츨근]을 덮어 써야하는 상황
        # 첫날 데이터가 퇴근 인 상황에서 출근으로 처리하면 퇴근이 안되는 현상

    # push to staff
    push_staff(employee.name, dt_touch, work_id, is_in)
    #
    # 정상, 지각, 조퇴 처리
    #
    update_pass_history(pass_history, work)

    pass_history.save()

    logSend(' x: {}, y:{}'.format(x, y))
    # 통과 기록 저장
    new_pass = Pass(
        passer_id=passer_id,
        is_in=is_in,
        is_beacon=False,
        dt=dt,
        x=x,
        y=y,
    )
    new_pass.save()

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def pass_touch(request):
    """
    출입확인 : 앱 사용자가 출근(퇴근) 버튼이 활성화 되었을 때 터치하면 서버로 전송
    http://0.0.0.0:8000/employee/pass_touch?passer_id=qgf6YHf1z2Fx80DR8o/Lvg&dt=2019-05-06 17:30:00&is_in=0
    POST : json
        {
            'passer_id' : '암호화된 출입자 id',
            'dt' : '2018-12-28 12:53:36',
            'is_in' : 1, # 0: out, 1 : in
            'beacons' : [
                 {'major': 11001, 'minor': 11001, 'dt_begin': '2019-01-21 08:25:30', 'rssi': -70, 'dt_end': '2019-01-21 08:30:00', 'count': 660},  # 5:30 초당 2번
                 {'major': 11001, 'minor': 11002, 'dt_begin': '2019-01-21 08:25:31', 'rssi': -70, 'dt_end': '2019-01-21 08:30:01', 'count': 660},  # 5:30 초당 2번
                 {'major': 11001, 'minor': 11003, 'dt_begin': '2019-01-21 08:25:32', 'rssi': -70, 'dt_end': '2019-01-21 08:30:02', 'count': 660},  # 5:30 초당 2번
            ]
            'x': latitude (optional)
            'y': longitude (optional)
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

    parameter_check = is_parameter_ok(rqst, ['passer_id_!', 'dt', 'is_in', 'x_@', 'y_@', 'beacons_@'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    passer_id = parameter_check['parameters']['passer_id']
    dt = parameter_check['parameters']['dt']
    dt_touch = str_to_datetime(dt)  #datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
    is_in = int(parameter_check['parameters']['is_in'])
    beacons = parameter_check['parameters']['beacons']
    x = parameter_check['parameters']['x']
    y = parameter_check['parameters']['y']
    # logSend(' x: {}, y:{}'.format(x, y))
    try:
        passer = Passer.objects.get(id=passer_id)
    except Exception as e:
        return status422(get_api(request),
                         {'message': 'ServerError: Passer 에 passer_id={} 이(가) 없다'.format(passer_id)})
    try:
        employee = Employee.objects.get(id=passer.employee_id)
    except Exception as e:
        return status422(get_api(request),
                         {'message': 'ServerError: Employee 에 employee_id={} 이(가) 없다'.format(passer.employee_id)})
    employee_works = Works(employee.get_works())
    logSend('  > employee_works: {}'.format(employee_works.data))
    if not employee_works.is_active(dt_touch):
        message = '출근처리할 업무가 없습니다.\npasser.id: {}\nemployee.name: {}\nworks: {}'.format(passer.id, employee.name, employee_works)
        send_slack(' <상용> employee/pass_touch \npasser.id: {}\nemployee.name: {}\nworks: {}'.format(passer.id, employee.name, employee_works),
                   message, channel='#server_bug')
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '출근처리할 업무가 없습니다.'})
    work_id = employee_works.data[employee_works.index]['id']
    work_dict = get_work_dict([work_id])
    work = work_dict[str(work_id)]
    # logSend('  >> work: {}'.format(work))
    work['id'] = work_id
    #
    # 1. 기존에 인식했던 비콘이면 통과 (passer.beacons)
    # 2. 새로운 비콘이면 비콘 위치 > 업무 출근 위치 > 업무 출근 위치와 30m 이내이면 출근인정 > 인정된 비콘 저장 (passer.beacons)
    #

    #
    # Pass_History update
    #
    year_month_day = dt_touch.strftime("%Y-%m-%d")
    pass_histories = Pass_History.objects.filter(passer_id=passer_id, year_month_day=year_month_day)
    if not is_in:
        # out touch 일 경우
        time_gap = 1440
        mins_touch = str2min(dt[11:16])
        # logSend('   >>> time_info: {}'.format(work['time_info']))
        work_time_list = work['time_info']['work_time_list']
        for work_time in work_time_list:
            if str2min(work_time['t_begin']) >= str2min(work_time['t_end']):
                # 퇴근시간이 더 빠르면 전날 출근해서 다음날 퇴근하는 케이스다.
                work_time['is_next_day'] = True
            else:
                work_time['is_next_day'] = False
            work_time['gap_out'] = abs(mins_touch - str2min(work_time['t_end']))
            if time_gap > work_time['gap_out']:
                time_gap = work_time['gap_out']
                current_work_time = work_time
        # logSend('  >>> work_time_list: {}'.format(work_time_list))
        logSend('  >>> current_work_time: {}'.format(current_work_time))
        # ? 연장근무나 시간 수정이 되었을 때
        # ? 문제가 발생할 수 있다.
        yesterday = dt_touch - datetime.timedelta(days=1)
        yesterday_year_month_day = yesterday.strftime("%Y-%m-%d")
        yesterday_pass_histories = Pass_History.objects.filter(passer_id=passer_id,
                                                               year_month_day=yesterday_year_month_day)
        if len(pass_histories) == 0:
            # in (츨근 처리를 하지 않았다.)
            # out 인데 오늘 날짜 pass_history 가 없다? >> 그럼 어제 저녁에 근무 들어갔겠네!
            if len(yesterday_pass_histories) == 0:
                # out 인데 어제, 오늘 in 기록이 없다?
                # 1. 어제 출근해서 오늘 퇴근하는 근무시간이 없으면 현재시간으로 퇴근시간을 처리한다.
                # 2. 연장근무 시간을 차감한 퇴근시간과 유사한 근무시간을 찾는다.
                logError(get_api(request),
                         ' passer_id={} out touch 인데 어제, 오늘 기록이 없다. dt_touch={}'.format(passer_id, dt_touch))
                if current_work_time['is_next_day']:
                    logSend('  > 어제 출근 오늘 퇴근 근무시간: 출근이 없어서 만든다.')
                    pass_history = Pass_History(
                        passer_id=passer_id,
                        year_month_day=yesterday_year_month_day,
                        action=0,
                        work_id=work_id,
                        x=x,
                        y=y,
                    )
                else:
                    logSend('  > 오늘 출근 오늘 퇴근 근무시간: 출근이 없어서 만든다.')
                    pass_history = Pass_History(
                        passer_id=passer_id,
                        year_month_day=year_month_day,
                        action=0,
                        work_id=work_id,
                        x=x,
                        y=y,
                    )
            elif current_work_time['is_next_day']:
                # 어제 출근이 있는 경우
                logSend('  > 어제 출근에 오늘 퇴근 근무시간: 어제 근무시간에 퇴근을 넣는다.')
                pass_history = yesterday_pass_histories[0]
            else:
                logSend('  > 오늘 출근에 오늘 퇴근 근무시간: 오늘 근무시간을 만든다.(출근 시간 누락)')
                # 오늘 pass_history 가 없어서 새로 만든다.
                pass_history = Pass_History(
                    passer_id=passer_id,
                    year_month_day=year_month_day,
                    action=0,
                    work_id=work_id,
                    x=x,
                    y=y,
                )
        elif current_work_time['is_next_day']:
            logSend('  > 어제 출근에 오늘 퇴근 근무시간: 오늘 출근이 있어도 어제에 넣는다.')
            pass_history = yesterday_pass_histories[0]
        else:
            logSend('  > 오늘 출근에 오늘 퇴근 근무시간: 오늘 근무시간에 퇴근을 넣는다.')
            pass_history = pass_histories[0]

        if pass_history.dt_out_verify is None:
            pass_history.dt_out_verify = dt_touch
            pass_history.dt_out_em = dt_touch
    else:
        # in touch 일 경우 (출근 버튼이 눌렸을 때)
        if len(pass_histories) == 0:
            # 오늘 날짜 pass_history 가 없어서 새로 만든다.
            pass_history = Pass_History(
                passer_id=passer_id,
                year_month_day=year_month_day,
                action=0,
                work_id=work_id,
                x=x,
                y=y,
            )
        else:
            pass_history = pass_histories[0]

        if pass_history.dt_in_verify is None:
            pass_history.dt_in_verify = dt_touch
            pass_history.dt_in_em = dt_touch

    # push to staff
    push_staff(employee.name, dt_touch, work_id, is_in)
    #
    # 정상, 지각, 조퇴 처리
    #
    update_pass_history(pass_history, work)

    pass_history.save()

    logSend(' x: {}, y:{}'.format(x, y))
    # 통과 기록 저장
    new_pass = Pass(
        passer_id=passer_id,
        is_in=is_in,
        is_beacon=False,
        dt=dt,
        x=x,
        y=y,
    )
    new_pass.save()

    return REG_200_SUCCESS.to_json_response()


def push_staff(name, dt, work_id, is_in):
    # logSend('  {} {} {} {}'.format(name, dt, customer_work_id, is_in))
    push_info = {
        'name': name,
        'dt': dt_null(dt),
        'work_id': work_id,
        'is_in': is_in,
    }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'push_from_employee', json=push_info)
    logSend('  {}'.format({'url': r.url, 'POST': push_info, 'STATUS': r.status_code, 'R': r.json()}))
    # result_json = r.json()
    # return REG_200_SUCCESS.to_json_response(result_json)
    return


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
    dt_touch = str_to_datetime(dt)  #datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
    sms = rqst['sms']
    logSend('---parameter: phone_no: {}, dt: {}, sms: {}'.format(phone_no, dt, sms))

    sms = sms.replace('승락', '수락').replace('거부', '거절')
    if ('수락 ' in sms) or ('거절' in sms):
        # notification_work 에서 전화번호로 passer_id(notification_work 의 employee_id) 를 얻는다.
        notification_work_list = Notification_Work.objects.filter(is_x=False, employee_pNo=phone_no)
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
                notification.is_x = True
                notification.save()
                # notification_work.delete()  # 2019/09/10 삭제하지 않고 유지
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
                work_dict = get_work_dict([notification_work.work_id])
                work = work_dict[str(notification_work.work_id)]
                # work = Work.objects.get(id=notification_work.work_id)
                # sms_data['msg'] = '수락됐어요\n{}-{}\n{} ~ {}\n{} {}'.format(work.work_place_name,
                #                                                         work.work_name_type,
                #                                                         work.begin,
                #                                                         work.end,
                #                                                         work.staff_name,
                #                                                         phone_format(work.staff_pNo))
                sms_data['msg'] = '수락됐어요\n{}-{}\n{} ~ {}\n{} {}'.format(work['work_place_name'],
                                                                        work['work_name_type'],
                                                                        work['dt_begin'],
                                                                        work['dt_end'],
                                                                        work['staff_name'],
                                                                        work['staff_pNo'])
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
    if not employee_works.is_active(dt_touch):
        logError(get_api(request), '근무할 업무가 없다.'.format())
        return status422(get_api(request), {'message': '근무할 업무가 없다.'.format()})
    employee_work = employee_works.data[employee_works.index]
    work_id = employee_work['id']
    work = get_work_dict([work_id])
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
        elif (dt_in + datetime.timedelta(hours=12)) < dt_touch:
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
    update_pass_history(pass_history, work)

    pass_history.save()
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def pass_sms_v2(request):
    """
    문자로 출근/퇴근, 업무 수락/거절: 스마트폰이 아닌 사용자가 문자로 출근(퇴근), 업무 수락/거절을 서버로 전송
      - 수락/거절은 복수의 수락/거절에 모두 답하는 문제를 안고 있다.
      - 수락/거절하게 되먼 수락/거절한 업무가 여러개라도 모두 sms 로 보낸다. (업무, 담당자, 담당자 전화번호, 기간)
      - 수락은 이름이 안들어 오면 에러처리한다. (2019/05/22 거절에 이름 확인 기능 삭제)
    http://0.0.0.0:8000/employee/pass_sms_v2?phone_no=010-3333-9999&dt=2019-01-21 08:25:35&sms=출근
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
    dt_touch = str_to_datetime(dt)  #datetime.datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
    sms = rqst['sms']
    logSend('---parameter: phone_no: {}, dt: {}, sms: {}'.format(phone_no, dt, sms))

    sms = sms.replace('승락', '수락').replace('거부', '거절')
    if ('수락 ' in sms) or ('거절' in sms):
        # notification_work 에서 전화번호로 passer_id(notification_work 의 employee_id) 를 얻는다.
        notification_work_list = Notification_Work.objects.filter(is_x=False, employee_pNo=phone_no)
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
                notification.is_x = True
                notification.save()
                # notification_work.delete()  # 2019/09/10 삭제하지 않고 유지
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
                work_dict = get_work_dict([notification_work.work_id])
                work = work_dict[str(notification_work.work_id)]
                # work = Work.objects.get(id=notification_work.work_id)
                # sms_data['msg'] = '수락됐어요\n{}-{}\n{} ~ {}\n{} {}'.format(work.work_place_name,
                #                                                         work.work_name_type,
                #                                                         work.begin,
                #                                                         work.end,
                #                                                         work.staff_name,
                #                                                         phone_format(work.staff_pNo))
                sms_data['msg'] = '수락됐어요\n{}-{}\n{} ~ {}\n{} {}'.format(work['work_place_name'],
                                                                        work['work_name_type'],
                                                                        work['dt_begin'],
                                                                        work['dt_end'],
                                                                        work['staff_name'],
                                                                        work['staff_pNo'])
                rSMS = requests.post('https://apis.aligo.in/send/', data=sms_data)
                logSend('SMS result', rSMS.json())
        return REG_200_SUCCESS.to_json_response()

    elif '출근' in sms:
        is_in = 1
    elif '퇴근' in sms:
        is_in = 0
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
    if not employee_works.is_active(dt_touch):
        logError(get_api(request), '근무할 업무가 없다.'.format())
        return status422(get_api(request), {'message': '근무할 업무가 없다.'.format()})
    employee_work = employee_works.data[employee_works.index]
    work_id = employee_work['id']
    work = get_work_dict([work_id])
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
        elif (dt_in + datetime.timedelta(hours=12)) < dt_touch:
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
    update_pass_history(pass_history, work)

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
                    uuid='3c06aa91-984b-be81-d8ea-82af46f4cda4',
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
    - 기존 전화번호를 바꿀 때는 새로운 API 를 사용한다. (2019-08-25) 당분간 호환성 때문에 passer_id 는 그냥 둔다.
      * exchange_phone_no_to_sms, exchange_phone_no_verify
    http://0.0.0.0:8000/employee/certification_no_to_sms?phone_no=010-2557-3555
    POST : json
    {
        'phone_no' : '010-1111-2222'
    }
    response
        STATUS 200
            {'dt_next': '2019-09-02 00:00:00'}
        STATUS 416 # 앱에서 아예 리셋을 할 수도 있겠다.
            {'message': '인증번호를 보낼 수 없는 전화번호 입니다.'}
            {'message': '올바른 전화번호가 아닙니다.'}  # 전화번호가 9자리 미만일 때
            {'message': '계속 이 에러가 나면 앱을 다시 설치해야합니다.'}
        STATUS 542
            {'message':'전화번호가 이미 등록되어 있어 사용할 수 없습니다.\n고객센터로 문의하십시요.'}
        STATUS 552
            {'message': '인증번호는 3분에 한번씩만 발급합니다.\n(혹시 1899-3832 수신 거부하지는 않으셨죠?)'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'phone_no\' 가 없어요'}

    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['phone_no'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    phone_no = no_only_phone_no(parameter_check['parameters']['phone_no'])
    if len(phone_no) < 9:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '올바른 전화번호가 아닙니다.'})

    # 새로 근로자 등록을 하는 경우 - 전화번호 중복을 확인해야한다.
    # 신규 등록일 때 전화번호를 사용하고 있으면 에러처리
    passers = Passer.objects.filter(pNo=phone_no)
    for passer in passers:
        if passer.employee_id == -6:
            passer.delete()
    if len(passers) == 0:
        passer = Passer(
            pNo=phone_no,
            employee_id=-6,  # 인증이 안된 근로자: 전화번호가 잘못되었거나 등... (나중에 삭제할 때 기준이 된다. 2019-08-25)
        )
    else:
        # 기존 근로자일 경우
        if len(passers) > 1:
            logError(get_api(request), ' 전화번호가 중복된 근로자가 있다. (phone: {})'.format(phone_format(phone_no)))
        passer = passers[0]

    if (passer.dt_cn is not None) and (datetime.datetime.now() < passer.dt_cn):
        # 3분 이내에 인증번호 재요청하면
        logSend('  - dt_cn: {}, today: {}'.format(passer.dt_cn, datetime.datetime.now()))
        return REG_552_NOT_ENOUGH_TIME.to_json_response({'message': '인증번호는 3분에 한번씩만 발급합니다.\n'
                                                                    '(혹시 1899-3832 수신 거부하지는 않으셨죠?)',
                                                         'dt_next': dt_null(passer.dt_cn)})

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
        'msg': '[' + str(certificateNo) + '] 이지체크 \n'
        '인증번호 입니다.'
    }
    if settings.IS_TEST:
        rData['testmode_yn'] = 'Y'
        return REG_200_SUCCESS.to_json_response({'dt_next': dt_null(passer.dt_cn)})

    rSMS = requests.post('https://apis.aligo.in/send/', data=rData)
    # print(rSMS.status_code)
    # print(rSMS.headers['content-type'])
    # print(rSMS.text)
    # print(rSMS.json())
    logSend('  - ', json.dumps(rSMS.json(), cls=DateTimeEncoder))
    # if int(rSMS.json()['result_code']) < 0:
    #     return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '인증번호를 보낼 수 없는 전화번호 입니다.'})
    # rJson = rSMS.json()
    # rJson['vefiry_no'] = str(certificateNo)

    # response = HttpResponse(json.dumps(rSMS.json(), cls=DateTimeEncoder))
    return REG_200_SUCCESS.to_json_response({'dt_next': dt_null(passer.dt_cn)})


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
            'uuid': 32byte (앱이 하나의 폰에만 설치되서 사용하도록 하기위한 기기 고유 값을 서버에서 만들어 보내는 값)
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
            'uuid': 32byte (앱이 하나의 폰에만 설치되서 사용하도록 하기위한 기기 고유 값을 서버에서 만들어 보내는 값)
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
            'uuid': 32byte (앱이 하나의 폰에만 설치되서 사용하도록 하기위한 기기 고유 값을 서버에서 만들어 보내는 값)
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

    parameter_check = is_parameter_ok(rqst, ['phone_no', 'cn', 'phone_type', 'push_token_@'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    phone_no = parameter_check['parameters']['phone_no']
    cn = parameter_check['parameters']['cn']
    phone_type = parameter_check['parameters']['phone_type']
    push_token = rqst['push_token']
    phone_no = no_only_phone_no(phone_no)
    # logSend('   *** phone_type: ({})'.format(phone_type))

    passers = Passer.objects.filter(pNo=phone_no)
    if len(passers) > 1:
        logError(get_api(request), ' 출입자 등록된 전화번호 중복: {}'.format([passer.id for passer in passers]))
    elif len(passers) == 0:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '잘못된 전화번호입니다.'})
    passer = passers[0]
    passer.user_agent = request.META['HTTP_USER_AGENT']
    passer.save()

    if passer.dt_cn == 0:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '인증번호 요청을 해주세요.'})

    if passer.dt_cn < datetime.datetime.now():
        logSend('  인증 시간: {} < 현재 시간: {}'.format(passer.dt_cn, datetime.datetime.now()))
        return REG_550_CERTIFICATION_NO_IS_INCORRECT.to_json_response({'message': '인증시간이 지났습니다.\n다시 인증요청을 해주세요.'})
    else:
        if (phone_no == '01084333579') and (int(cn) == 111333):
            logSend('*** apple 심사용 전화번호')
        else:
            cn = cn.replace(' ', '')
            logSend('  인증번호: {} vs 근로자 입력 인증번호: {}, settings.IS_TEST: {}'.format(passer.cn, cn, settings.IS_TEST))
            if not settings.IS_TEST and passer.cn != int(cn):
                # if passer.cn != int(cn):
                return REG_550_CERTIFICATION_NO_IS_INCORRECT.to_json_response()
    status_code = 200
    passer.uuid = secrets.token_hex(32)
    result = {'id': AES_ENCRYPT_BASE64(str(passer.id)),
              'uuid': passer.uuid
              }
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
        notification_list = Notification_Work.objects.filter(is_x=False, employee_pNo=phone_no)
        for notification in notification_list:
            if notification.employee_id == -1:
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
    phone_type = phone_type.upper().replace(' ', '')
    passer.pType = 20 if phone_type[:1] == 'A' else 10
    passer.push_token = push_token
    # passer.cn = 0
    # passer.dt_cn = None
    passer.save()
    return StatusCollection(status_code, '정상적으로 처리되었습니다.').to_json_response(result)
    # return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def update_my_info(request):
    """
    근로자 정보 변경 : 근로자의 정보를 변경한다.
    - 근무시작시간, 근무시간, 휴게시간, 출근알람, 퇴근 알람 각각 변경 가능 (2019-08-05)
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
            'pNo': '010-2222-3333',     # 전화번호 인증 따로 있어서 사용 안함
            'push_token': push_token,        # push token

            'work_start':'08:00',       # 출근시간: 24시간제 표시
            'working_time':'8',        # 근무시간: 시간 4 ~ 12
            'rest_time': '01:00'        # 휴게시간: 시간 00:00 ~ 06:00, 간격 30분

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
            {'message': '출근시간, 근무시간, (휴게시간)은 같이 들어와야한다.'}
            {'message': '출근 시간({}) 양식(hh:mm)이 잘못됨'.format(work_start)}
            {'message': '근무 시간({}) 양식이 잘못됨'.format(working_time)}
            {'message': '근무 시간(4 ~ 12) 범위 초과'}
            {'message': '휴게 시간({}) 양식(hh:mm)이 잘못됨'.format(rest_time)})
            {'message': '휴게 시간(00:30 ~ 06:00) 범위 초과 (주:양식도 확인)'})
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

    if 'push_token' in rqst:
        push_token = rqst['push_token']
        if len(push_token) < 64:
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': 'push_token 값이 너무 짧습니다.'})
        change_log = '{}  push_token: {} > {}'.format(change_log, passer.push_token, push_token)
        passer.push_token = push_token
        logSend('  update push token: {}'.format(passer.push_token))

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
            return status422(get_api(request), {'message': '출근시간, 근무시간, (휴게시간)은 같이 들어와야한다.'})

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
        # App 에서 휴게시간(rest_time)을 처리하기 전 한시적 기능
        #   rest_time 이 없을 때는 4시간당 30분으로 계산해서 휴게시간을 넣는다.
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
            return status422(get_api(request), {'message': '휴게 시간({}) 양식(hh:mm)이 잘못됨'.format(rest_time)})
        if not (str_to_datetime('2019-01-01 00:00:00') <= dt_rest_time <= str_to_datetime('2019-01-01 06:00:00')):
            return status422(get_api(request), {'message': '휴게 시간(00:00 ~ 06:00) 범위 초과 (주:양식도 확인)'})
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
def reg_from_certification_no_2(request):
    """
    근로자 등록 확인 : 문자로 온 SMS 문자로 근로자를 확인하는 기능 (여기서 사업장에 등록된 근로자인지 확인, 기존 등록 근로자인지 확인)
    http://0.0.0.0:8000/employee/reg_from_certification_no_2?phone_no=010-2557-3555&cn=580757&phone_type=A&push_token=token
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
            'uuid': 32byte (앱이 하나의 폰에만 설치되서 사용하도록 하기위한 기기 고유 값을 서버에서 만들어 보내는 값)
            'id': '암호화된 id 그대로 보관되어서 사용되어야 함',
            'name': '홍길동',                      # 필수: 없으면 입력 받는 화면 표시 (기존 근로자 일 때: 없을 수 있음 - 등록 중 중단한 경우)
            'work_start': '09:00',               # 필수: 없으면 입력 받는 화면 표시 (기존 근로자 일 때: 없을 수 있음 - 등록 중 중단한 경우)
            'working_time': '12',                # 필수: 없으면 입력 받는 화면 표시 (기존 근로자 일 때: 없을 수 있음 - 등록 중 중단한 경우)
            'rest_time': -1,                     # 필수: 없으면 입력 받는 화면 표시 (기존 근로자 일 때: 없을 수 있음 - 등록 중 중단한 경우)
            'work_start_alarm': 'X',             # 필수: 없으면 입력 받는 화면 표시 (기존 근로자 일 때: 없을 수 있음 - 등록 중 중단한 경우)
            'work_end_alarm': 'X',               # 필수: 없으면 입력 받는 화면 표시 (기존 근로자 일 때: 없을 수 있음 - 등록 중 중단한 경우)
            'bank': '기업은행',                     # 기존 근로자 일 때 (없을 수 있음 - 등록 중 중단한 경우)
            'bank_account': '12300000012000',     # 기존 근로자 일 때 (없을 수 있음 - 등록 중 중단한 경우)
            'time_info': {
              'paid_day': 0,
              'time_type': 0,
              'week_hours': 40,
              'month_hours': 209,
              'working_days': [1, 2, 3, 4, 5],
              'work_time_list': [
                {
                  't_begin': '09:00',
                  't_end': '21:00',
                  'break_time_type': 1,
                  'break_time_total': '01:30'
                },
              ],
              'is_holiday_work': 1
            },
            'bank_list': ['국민은행', ... 'NH투자증권']
        }
        STATUS 201 # 새로운 근로자 : 이름, 급여 이체 은행, 계좌번호를 입력받아야 함
        {
            'uuid': 32byte (앱이 하나의 폰에만 설치되서 사용하도록 하기위한 기기 고유 값을 서버에서 만들어 보내는 값)
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
            'uuid': 32byte (앱이 하나의 폰에만 설치되서 사용하도록 하기위한 기기 고유 값을 서버에서 만들어 보내는 값)
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

    parameter_check = is_parameter_ok(rqst, ['phone_no', 'cn', 'phone_type', 'push_token_@'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    phone_no = parameter_check['parameters']['phone_no']
    cn = parameter_check['parameters']['cn']
    phone_type = parameter_check['parameters']['phone_type']
    push_token = rqst['push_token']
    phone_no = no_only_phone_no(phone_no)
    # logSend('   *** phone_type: ({})'.format(phone_type))

    passers = Passer.objects.filter(pNo=phone_no)
    if len(passers) > 1:
        logError(get_api(request), ' 출입자 등록된 전화번호 중복: {}'.format([passer.id for passer in passers]))
    elif len(passers) == 0:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '잘못된 전화번호입니다.'})
    passer = passers[0]
    passer.user_agent = request.META['HTTP_USER_AGENT']
    passer.save()

    if passer.dt_cn == 0:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '인증번호 요청을 해주세요.'})

    if passer.dt_cn < datetime.datetime.now():
        logSend('  인증 시간: {} < 현재 시간: {}'.format(passer.dt_cn, datetime.datetime.now()))
        return REG_550_CERTIFICATION_NO_IS_INCORRECT.to_json_response({'message': '인증시간이 지났습니다.\n다시 인증요청을 해주세요.'})
    else:
        if (phone_no == '01084333579') and (int(cn) == 111333):
            logSend('*** apple 심사용 전화번호')
        else:
            cn = cn.replace(' ', '')
            logSend('  인증번호: {} vs 근로자 입력 인증번호: {}, settings.IS_TEST: {}'.format(passer.cn, cn, settings.IS_TEST))
            if not settings.IS_TEST and str(passer.cn) != cn:
                # if passer.cn != int(cn):
                return REG_550_CERTIFICATION_NO_IS_INCORRECT.to_json_response()
    status_code = 200
    passer.uuid = secrets.token_hex(32)
    result = {'id': AES_ENCRYPT_BASE64(str(passer.id)),
              'uuid': passer.uuid
              }
    if passer.employee_id == -2:  # 근로자 아님 출입만 처리함
        status_code = 202
    elif passer.employee_id < 0:  # 신규 근로자
        status_code = 201
        employee = Employee(
            work_start_alarm='X',
            work_end_alarm='X',
        )
        employee.save()
        passer.employee_id = employee.id
    else:
        employees = Employee.objects.filter(id=passer.employee_id)
        if len(employees) == 0:
            logError(get_api(request), ' 발생하면 안됨: passer.employee_id 의 근로자가 employee 에 없다. (새로 만듦)')
            status_code = 201
            employee = Employee(
            work_start_alarm='X',
            work_end_alarm='X',
            )
            employee.save()
            passer.employee_id = employee.id
        else:
            employee = employees[0]
            if employee.name == 'unknown':
                status_code = 201
            else:
                result['name'] = employee.name
                # result['work_start'] = employee.work_start
                # result['working_time'] = employee.working_time
                # result['rest_time'] = employee.rest_time
                result['work_start_alarm'] = employee.work_start_alarm
                result['work_end_alarm'] = employee.work_end_alarm
                result['bank'] = employee.bank
                result['bank_account'] = employee.bank_account
                works = employee.get_works()
                logSend('... works: {}'.format(works))
                today = datetime.datetime.now()
                for work in works:
                    logSend('... {} vs {}'.format(work['end'], str_to_dt(work['end']) + datetime.timedelta(days=1)))
                    if today < str_to_dt(work['end']) + datetime.timedelta(days=1):
                        # current_work = Work.objects.get(id=work['id'])
                        # logSend('... {}'.format(current_work.get_time_info()))
                        # result['time_info'] = current_work.get_time_info()
                        work_dict = get_work_dict([work['id']])
                        logSend('  > work_dict: {}'.format(work_dict))
                        logSend('  > work: {}'.format(work))
                        current_work = work_dict[str(work['id'])]
                        logSend('... {}'.format(current_work['time_info']))
                        result['time_info'] = current_work['time_info']

    if status_code == 200 or status_code == 201:
        # notification_list = Notification_Work.objects.filter(is_x=0, employee_pNo=phone_no)
        # logSend('... {}'.format(len(notification_list)))
        # for notification in notification_list:
        #     logSend('... {}, {}'.format(notification.employee_pNo, notification.work_id))
        #     if notification.employee_id == -1:
        #         notification.employee_id = employee.id
        #         notification.save()
        #     work = Work.objects.get(id=notification.work_id)
        #     logSend('... {}'.format(work.get_time_info()))
        #     result['time_info'] = work.get_time_info()
        # result['default_time'] = [
        #             {'work_start': '09:00', 'working_time': '08', 'rest_time': '01:00'},
        #             {'work_start': '07:00', 'working_time': '08', 'rest_time': '00:00'},
        #             {'work_start': '15:00', 'working_time': '08', 'rest_time': '00:00'},
        #             {'work_start': '23:00', 'working_time': '08', 'rest_time': '00:00'},
        #         ]

        result['bank_list'] = ['국민은행', '기업은행', '농협은행', '신한은행', '산업은행', '우리은행', '한국씨티은행', 'KEB하나은행', 'SC은행', '경남은행',
                               '광주은행', '대구은행', '도이치은행', '뱅크오브아메리카', '부산은행', '산림조합중앙회', '저축은행', '새마을금고중앙회', '수협은행',
                               '신협중앙회', '우체국', '전북은행', '제주은행', '카카오뱅크', '중국공상은행', 'BNP파리바은행', 'HSBC은행', 'JP모간체이스은행',
                               '케이뱅크', '교보증권', '대신증권', 'DB금융투자', '메리츠종합금융증권', '미래에셋대우', '부국증권', '삼성증권', '신영증권',
                               '신한금융투자', '에스케이증권', '현대차증권주식회사', '유안타증권주식회사', '유진투자증권', '이베스트증권', '케이프투자증권', '키움증권',
                               '펀드온라인코리아', '하나금융투자', '하이투자증권', '한국투자증권', '한화투자증권', 'KB증권', 'KTB투자증권', 'NH투자증권']
    phone_type = phone_type.upper().replace(' ', '')
    passer.pType = 20 if phone_type[:1] == 'A' else 10
    passer.push_token = push_token
    # passer.cn = 0
    # passer.dt_cn = None
    passer.save()
    return StatusCollection(status_code, '정상적으로 처리되었습니다.').to_json_response(result)
    # return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def update_my_info_2(request):
    """
    근로자 정보 변경 : 근로자의 정보를 변경한다.
    - 근무시작시간, 근무시간, 휴게시간, 출근알람, 퇴근 알람 각각 변경 가능 (2019-08-05)
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
            'pNo': '010-2222-3333',     # 전화번호 인증 따로 있어서 사용 안함
            'push_token': push_token,        # push token

            'work_start':'08:00',       # 출근시간: 24시간제 표시
            'working_time':'8',        # 근무시간: 시간 4 ~ 12
            'rest_time': '01:00'        # 휴게시간: 시간 00:00 ~ 06:00, 간격 30분

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
            {'message': '출근시간, 근무시간, (휴게시간)은 같이 들어와야한다.'}
            {'message': '출근 시간({}) 양식(hh:mm)이 잘못됨'.format(work_start)}
            {'message': '근무 시간({}) 양식이 잘못됨'.format(working_time)}
            {'message': '근무 시간(4 ~ 12) 범위 초과'}
            {'message': '휴게 시간({}) 양식(hh:mm)이 잘못됨'.format(rest_time)})
            {'message': '휴게 시간(00:30 ~ 06:00) 범위 초과 (주:양식도 확인)'})
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

    if 'push_token' in rqst:
        push_token = rqst['push_token']
        if len(push_token) < 64:
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': 'push_token 값이 너무 짧습니다.'})
        change_log = '{}  push_token: {} > {}'.format(change_log, passer.push_token, push_token)
        passer.push_token = push_token
        logSend('  update push token: {}'.format(passer.push_token))

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
            return status422(get_api(request), {'message': '출근시간, 근무시간, (휴게시간)은 같이 들어와야한다.'})

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
        # App 에서 휴게시간(rest_time)을 처리하기 전 한시적 기능
        #   rest_time 이 없을 때는 4시간당 30분으로 계산해서 휴게시간을 넣는다.
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
            return status422(get_api(request), {'message': '휴게 시간({}) 양식(hh:mm)이 잘못됨'.format(rest_time)})
        if not (str_to_datetime('2019-01-01 00:00:00') <= dt_rest_time <= str_to_datetime('2019-01-01 06:00:00')):
            return status422(get_api(request), {'message': '휴게 시간(00:00 ~ 06:00) 범위 초과 (주:양식도 확인)'})
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
def exchange_phone_no_to_sms(request):
    """
    핸드폰 인증 숫자 6자리를 SMS로 요청 - 근로자 앱을 처음 실행할 때 SMS 문자 인증 요청
    - SMS 로 인증 문자(6자리)를 보낸다.
    http://0.0.0.0:8000/employee/exchange_phone_no_to_sms?phone_no=010-2557-3555&passer_id=
    POST : json
    {
        'phone_no' : '010-1111-2222'
        'passer_id' : 암호화된 출입자 id
    }
    response
        STATUS 200
            {'dt_next': '2019-08-15 00:25:00}
        STATUS 416 # 앱에서 아예 리셋을 할 수도 있겠다.
            {'message': '올바른 전화번호가 아닙니다.'}
            {'message': '인증번호를 보낼 수 없는 전화번호 입니다.'}
            {'message': '기존 전화번호와 같습니다.'}
            {'message': '계속 이 에러가 나면 지우고 새로 설치하세요.'}
        STATUS 542
            {'message':'다른 사람이 사용 중인 전화번호 입니다.'}
        STATUS 552
            {'message': '인증번호가 안가나요?', 'dt_next': '2019-08-15 00:25:00} << {'message': '인증번호는 3분에 한번씩만 발급합니다.'}
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
    if len(phone_no) < 9:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '올바른 전화번호가 아닙니다.'})

    parameter_check = is_parameter_ok(rqst, ['passer_id_!'])
    if parameter_check['is_ok']:
        # 기존에 등록된 근로자 일 경우 - 전화번호를 변경하려 한다.
        passer_id = parameter_check['parameters']['passer_id']
        passer = Passer.objects.get(id=passer_id)
        if passer.pNo == phone_no:
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '기존 전화번호와 같습니다.'})
        # 등록 사용자가 앱에서 전화번호를 바꾸려고 인증할 때
        # 출입자 아이디(passer_id) 의 전화번호 외에 전화번호가 있으면 전화번호(542)처리
        passers = Passer.objects.filter(pNo=phone_no).exclude(employee_id=-7)
        logSend(('  - phone: {}'.format([(passer.pNo, passer.id) for passer in passers])))
        if len(passers) > 0:
            logError(get_api(request), ' phone: ({}, {}), duplication phone: {}'
                     .format(passer.pNo, passer.id, [(passer.pNo, passer.id) for passer in passers]))
            return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response(
                {'message': '다른 사람이 사용 중인 전화번호 입니다.'})
    else:
        # passer_id 가 있지만 암호 해독과정에서 에러가 났을 때
        logError(get_api(request), parameter_check['results'])
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '계속 이 에러가 나면 지우고 새로 설치하세요.'})
    temp_passer_list = Passer.objects.filter(notification_id=passer_id)
    for temp_passer in temp_passer_list:
        if temp_passer.employee_id == -7:
            temp_passer.delete()
    if len(temp_passer_list) > 0:
        if len(temp_passer_list) > 1:
            logError(get_api(request), ' 근로자 임시 전화번호가 2개 이상: {}'.format(phone_no))
        temp_passer = temp_passer_list[0]
        if (temp_passer.pNo == phone_no) and (temp_passer.dt_cn is not None) and (datetime.datetime.now() < temp_passer.dt_cn):
            # 3분 이내에 인증번호 재요청하면
            logSend('  - dt_cn: {}, today: {}'.format(temp_passer.dt_cn, datetime.datetime.now()))
            return REG_552_NOT_ENOUGH_TIME.to_json_response({'message': '인증번호가 안가나요?',
                                                             'dt_next': dt_null(temp_passer.dt_cn)})
        temp_passer.pNo = phone_no
    else:
        temp_passer = Passer(
            pNo=phone_no,
            employee_id=-7,  # Temp 의 T 와 7 이 비슷하게 보여서...
            notification_id=passer_id,
        )

    certificateNo = random.randint(100000, 999999)
    if settings.IS_TEST:
        certificateNo = 201903
    temp_passer.cn = certificateNo
    temp_passer.dt_cn = datetime.datetime.now() + datetime.timedelta(minutes=3)
    temp_passer.save()
    logSend('  - phone: {} certificateNo: {}'.format(phone_no, certificateNo))

    rData = {
        'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
        'user_id': 'yuadocjon22',
        'sender': settings.SMS_SENDER_PN,
        'receiver': phone_no,
        'msg_type': 'SMS',
        'msg': '[' + str(certificateNo) + '] 이지체크\n'
        '인증번호 입니다.'
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
    if int(rSMS.json()['result_code']) < 0:
        temp_passer.delete()
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '인증번호를 보낼 수 없는 전화번호 입니다.'})

    # rJson = rSMS.json()
    # rJson['vefiry_no'] = str(certificateNo)

    # response = HttpResponse(json.dumps(rSMS.json(), cls=DateTimeEncoder))
    return REG_200_SUCCESS.to_json_response({'dt_next': dt_null(temp_passer.dt_cn)})


@cross_origin_read_allow
def exchange_phone_no_verify(request):
    """
    근로자 등록 확인 : 문자로 온 SMS 문자로 근로자를 확인하는 기능 (여기서 사업장에 등록된 근로자인지 확인, 기존 등록 근로자인지 확인)
    http://0.0.0.0:8000/employee/exchange_phone_no_verify?passer_id=.......&cn=123456
    POST
        {
            'passer_id' : 암호화된 출입자 id,
            'cn' : '6자리 SMS 인증숫자',
        }
    response
        STATUS 200
        STATUS 416
            {'message': '잘못된 전화번호입니다.'}
            {'message': '인증번호 요청을 해주세요.'}
        STATUS 550
            {'message': '인증시간이 지났습니다.\n다시 인증요청을 해주세요.'} # 인증시간 3분
            {'message': '인증번호가 틀립니다.'}
        STATUS 200 # 기존 근로자
            {'message': '정산적으로 처리되었습니다.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'passer_id\' 가 없어요'}
            {'message':'ClientError: parameter \'cn\' 가 없어요'}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['passer_id_!', 'cn'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    passer_id = parameter_check['parameters']['passer_id']
    cn = parameter_check['parameters']['cn']

    temp_passers = Passer.objects.filter(employee_id=-7, notification_id=passer_id)

    if len(temp_passers) > 1:
        logError(get_api(request), ' 출입자 등록된 전화번호 중복: {}'.format([passer.id for passer in temp_passers]))
    elif len(temp_passers) == 0:
        logError(get_api(request), ' 임시 데에터 없음: notification_id=passer_id({})'.format(passer_id))
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '변경되지 않았습니다.\n고객센터로 문의해 주십시요.'})
    temp_passer = temp_passers[0]
    if temp_passer.dt_cn == 0:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '인증번호 요청을 해주세요.'})

    if temp_passer.dt_cn < datetime.datetime.now():
        logSend('  인증 시간: {} < 현재 시간: {}'.format(temp_passer.dt_cn, datetime.datetime.now()))
        return REG_550_CERTIFICATION_NO_IS_INCORRECT.to_json_response({'message': '인증시간이 지났습니다.\n다시 인증번호 요청을 해주세요.'})
    else:
        cn = cn.replace(' ', '')
        logSend('  인증번호: {} vs 근로자 입력 인증번호: {}, settings.IS_TEST: {}'.format(temp_passer.cn, cn, settings.IS_TEST))
        if not settings.IS_TEST and temp_passer.cn != int(cn):
            # if passer.cn != int(cn):
            return REG_550_CERTIFICATION_NO_IS_INCORRECT.to_json_response()
    passers = Passer.objects.filter(id=passer_id)
    if len(passers) > 1:
        logError(get_api(request), ' 출입자 등록된 전화번호 중복: {}'.format([passer.id for passer in passers]))
    elif len(passers) == 0:
        logError(get_api(request), ' 출입자 id({}) 없음.'.format(passer_id))
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '변경되지 않았습니다.\n고객센터로 문의해 주십시요.'})

    passer = passers[0]
    passer.pNo = temp_passer.pNo
    #
    # to customer server
    # 고객 서버에 근로자 전화번호 변경 적용
    #
    update_employee_data = {
        'pNo': passer.pNo,
        'worker_id': AES_ENCRYPT_BASE64('thinking'),
        'passer_id': AES_ENCRYPT_BASE64(str(passer.id)),
    }
    response_customer = requests.post(settings.CUSTOMER_URL + 'update_employee_for_employee', json=update_employee_data)
    if response_customer.status_code != 200:
        logError(get_api(request), ' 고객서버 데이터 변경 중 에러: {}'.format(response_customer.json()))
        return ReqLibJsonResponse(response_customer)

    passer.save()
    temp_passer.delete()

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
        work_dict = get_work_dict(work_id_list)
        for work_key in work_dict.keys():
            work = work_dict[work_key]
            work['work_id'] = work_key
            work['begin'] = work['dt_begin']
            work['end'] = work['dt_end']
            work_list.append(work)

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
    parameter_check = is_parameter_ok(rqst, ['employees', 'year_month_day', 'work_id_!'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    employees = parameter_check['parameters']['employees']
    year_month_day = parameter_check['parameters']['year_month_day']
    work_id = parameter_check['parameters']['work_id']

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
    logSend('  근로자 passer_ids: {}'.format([passer.id for passer in passer_list]))
    employee_info_id_list = [passer.employee_id for passer in passer_list if passer.employee_id > 0]
    logSend('  근로자 employee_ids: {}'.format([employee_info_id for employee_info_id in employee_info_id_list]))
    if len(passer_list) != len(employee_info_id_list):
        logError(get_api(request), ' 출입자 인원(# passer)과 근로자 인원(# employee)이 틀리다 work_id: {}'.format(work_id))
    employee_info_list = Employee.objects.filter(id__in=employee_info_id_list).order_by('work_start')
    logSend('  근로자 table read employee_ids: {}'.format([employee_info.id for employee_info in employee_info_list]))
    employee_ids = []
    for employee_info in employee_info_list:
        for passer in passer_list:
            if passer.employee_id == employee_info.id:
                employee_ids.append(passer.id)
    logSend('  new employee_ids: {}'.format([employee_id for employee_id in employee_ids]))
    logSend('  pass_histories : employee_ids : {} work_id {}'.format(employee_ids, work_id))
    if int(work_id) == -1:
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
    if int(work_id) == -1:
        pass_histories = Pass_History.objects.filter(year_month_day=year_month_day, passer_id__in=employee_ids)
    else:
        pass_histories = Pass_History.objects.filter(year_month_day=year_month_day, passer_id__in=employee_ids,
                                                     work_id=work_id)

    exist_ids = [pass_history.passer_id for pass_history in pass_histories]
    logSend('--- pass_histories passer_ids {}'.format(exist_ids))
    fail_list = []
    int_work_id = int(work_id)
    for pass_history in pass_histories:
        if int_work_id == -1:
            int_work_id = int(pass_history.work_id)
            work = get_work_dict([int_work_id])
        elif int_work_id != int(pass_history.work_id):
            int_work_id = int(pass_history.work_id)
            work = get_work_dict([int_work_id])

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
                update_pass_history(pass_history, work)

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
                update_pass_history(pass_history, work)

        if len(fail_list) > 0:
            return status422(get_api(request), {'message': 'fail', 'fail_list': fail_list})

        pass_history.save()

        # *** 출퇴근 시간이 바뀌면 pass_verify 로 변경해야하는데...
        # 문제 없을까?
        # action 처리가 안된다.

    #
    # 유급휴일이 수동지정이면 day_type 으로 소정근로일/무급휴일/유급휴일을 표시해야한다.
    # 근태정보 변경 알림을 확인/거절/기한지남 인 경우 표시해야 한다.
    #
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
            'day_type': pass_history.day_type,
            'day_type_staff_id': pass_history.day_type_staff_id,
            'day_type_description': '소정근로일',
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


@cross_origin_read_allow
def work_record_in_day_for_customer(request):
    """
    << 고객 서버용 >> 복수 근로자의 하루 근무 기록
    - 2020/03/27 new API << pass_record_of_employees_in_day_for_customer
    - work 의 시작 날짜 이전을 요청하면 안된다. - work 의 시작 날짜를 검사하지 않는다.
    - 출퇴근 기록이 없으면 출퇴근 기록을 새로 만든다.
    - 수정한 시간 오류 검사 X : 출근 시간보다 퇴근 시간이 느리다,
    - 휴일 여부(소정근로일/무급휴일/유급휴일) 추가 pass_record_of_employees_in_day_for_customer 를 대
    http://0.0.0.0:8000/employee/work_record_in_day_for_customer?employees=&dt=2019-05-06
    POST : json
        {
            employees: [ employee_id, employee_id, ...],  # 배열: 대상 근로자 (암호화된 값)
            year_month_day: 2018-12-28,                   # 대상 날짜
            work_id: work_id,                             # 업무 id (암호화된 값): 암호를 풀어서 -1 이면 업무 특정짓지 않는다.
        }
    response
        STATUS 200 - 아래 내용은 처리가 무시되기 때문에 에러처리는 하지 않는다.
            {
                "message": "정상적으로 처리되었습니다.",
                "employees": [
                    {
                        "passer_id": "LjmQXEHbJu-Rdt5pAMBUlw",
                        "year_month_day": "2020-03-22",
                        "action": 0,
                        "work_id": "PinmZxCWGvvrcnj20cRanw",
                        "dt_in": null,
                        "dt_in_verify": null,
                        "in_staff_id": -1,
                        "dt_out": null,
                        "dt_out_verify": null,
                        "out_staff_id": -1,
                        "overtime": 0,
                        "overtime_staff_id": 12,
                        "x": null,
                        "y": null,
                        "notification": 2,                 # -1: 알림 없음, 0: 근로자가 확인하지 않은 알림 있음 (이름: 파랑), 2: 근로자가 거절한 알림 있음 (이름 빨강), 3: 답변시한 지난 알림 (이름 빨강)
                        "week": "일",                      # 요일
                        "day_type": 0,                    # 이날의 근무 형태 0: 유급휴일, 1: 무급휴일, 2: 소정근무일
                        "day_type_description": "유급휴일"  # 근무 형태 설명
                    },
                    ......
                ],
                "fail_list": {
                    "fail_passer_id_list": [
                        "639"
                    ],
                    "no_working_passer_id_list": [
                        636
                    ]
                }
            }
            {'message': 'out 인데 어제 오늘 in 기록이 없다.'}
            {'message': 'in 으로 부터 12 시간이 지나서 out 을 무시한다.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'employees\' 가 없어요'}
            {'message':'ClientError: parameter \'year_month_day\' 가 없어요'}
            {'message':'ClientError: parameter \'work_id\' 가 없어요'}
            {'message':'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}
            {'message': 'ClientError: 해당 업무가 없어요.'}
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
    parameter_check = is_parameter_ok(rqst, ['employees', 'year_month_day', 'work_id_!'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    employees = parameter_check['parameters']['employees']
    year_month_day = parameter_check['parameters']['year_month_day']
    work_id = parameter_check['parameters']['work_id']
    if int(work_id) == -1:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': 'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'})
    work_dict = get_work_dict([work_id])
    # logSend('  > work: {}'.format(work_dict))
    if len(list(work_dict.keys())) == 0:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': 'ClientError: 해당 업무가 없어요.'})
    work = work_dict[list(work_dict.keys())[0]]
    work['id'] = list(work_dict.keys())[0]
    logSend('  > work: {}'.format(work))
    fail_dict = {}
    fail_employee_id_list = []
    employee_ids = []
    for employee in employees:
        # key 에 '_id' 가 포함되어 있으면 >> 암호화 된 값이면
        plain = AES_DECRYPT_BASE64(employee)
        if plain == '__error':
            fail_employee_id_list.append(employee)
            # logError(get_api(request), ' 근로자 id ({}) Error 복호화 실패: 처리대상에서 제외'.format(employee))
            # 2019-05-22 여러명을 처리할 때 한명 때문에 에러처리하면 안되기 때문에...
            # return status422(get_api(request), {'message': 'employees 에 있는 employee_id={} 가 해독되지 않는다.'.format(employee)})
        else:
            if int(plain) > 0:
                # 거절 수락하지 않은 근로자 제외 (employee_id == -1)
                employee_ids.append(plain)
    if len(fail_employee_id_list) > 0:
        fail_dict['fail_employee_id_list'] = fail_employee_id_list
    logSend('  > employee_ids: {} fail(복호화되지 않는 id): {}'.format(employee_ids, fail_employee_id_list))
    passer_list = Passer.objects.filter(id__in=employee_ids)
    passer_dict = {passer.id: passer for passer in passer_list}
    fail_passer_id_list = copy.deepcopy(employee_ids)  # 근로자를 넣고 Passer 에서 가져온 id 와 비교해서 문제있으면
    logSend('  > 검사 대상 passer_id_list: {}'.format(fail_passer_id_list))
    for passer in passer_list:
        if str(passer.id) in fail_passer_id_list:
            fail_passer_id_list.remove(str(passer.id))
    if len(fail_passer_id_list) > 0:
        fail_dict['fail_passer_id_list'] = fail_passer_id_list
    logSend('  > (정상 출입자) passer_ids: {}, (등록되지 않은 출입자)fail_passer_id_list: {}'.format(list(passer_dict.keys()), fail_passer_id_list))
    # employee_id_list = [passer.employee_id for passer in passer_list]
    # employee_list = Employee.objects.filter(id__in=employee_id_list)
    # employee_dict = {employee.id: employee for employee in employee_list}
    # no_working_passer_id_list = list(passer_dict.keys())
    # working_passer_id_list = []
    # for passer_id in passer_dict.keys():
    #     passer = passer_dict[passer_id]
    #     if passer.employee_id in employee_dict.keys():  # passer 의 employee 가 있으면
    #         employee = employee_dict[passer.employee_id]
    #         works = Works(employee.get_works())
    #         if works.find_work_include_date(work['id'], str_to_datetime(year_month_day)) != None:  # 날짜에 업무를 하고 있는지 확인
    #             no_working_passer_id_list.remove(passer_id)
    #             working_passer_id_list.append(passer_id)
    # logSend('  > (업무가 없거나 시작되지 않은) passer_id_list: {}'.format(no_working_passer_id_list))
    # if len(no_working_passer_id_list) > 0:
    #     fail_dict['no_working_passer_id_list'] = no_working_passer_id_list
    # logSend('  > fail: {}, working_passer_id_list: {}'.format(fail_dict, working_passer_id_list))
    working_passer_id_list = list(passer_dict.keys())
    #
    # 유급휴일이 수동지정이면 day_type 으로 소정근로일/무급휴일/유급휴일을 표시해야한다.
    # 근태정보 변경 알림을 확인/거절/기한지남 인 경우 표시해야 한다.
    #   근로자 변경 알림은 거절(2)이 미확인(0)보다 우선하여 표시한다. - 이름에 미확인(0)은 파랑색, 거절(2)은 빨강색
    # noti_list = Notification_Work.objects.filter(dt_inout__startswith=dt_last_day.date())
    dt_year_month_day = str_to_datetime(year_month_day)
    notification_list = Notification_Work.objects.filter(work_id=work['id'], employee_id__in=working_passer_id_list,
                                                         dt_inout__startswith=dt_year_month_day.date(), is_x__in=[0, 2])
    # is_x__in=[0, 2, 3]  # 0: 알림 답변 전 상태, 1: 알림 확인 적용된 상태, 2: 알림 내용 거절, 3: 알림 확인 시한 지남
    notification_passer_key_dict = {}
    for notification in notification_list:
        if notification.employee_id in notification_passer_key_dict.keys():
            # notification_passer_key_dict[notification.employee_id].append(notification.is_x)
            if notification_passer_key_dict[notification.employee_id] < notification.is_x:
                notification_passer_key_dict[notification.employee_id] = notification.is_x
        else:
            # notification_passer_key_dict[notification.employee_id] = [notification.is_x]
            notification_passer_key_dict[notification.employee_id] = notification.is_x
    logSend('  > notification_passer_key_dict: {}'.format(notification_passer_key_dict))

    pass_record_list = Pass_History.objects.filter(year_month_day=year_month_day, passer_id__in=working_passer_id_list,
                                                   work_id=work_id)
    no_pass_record_passer_id_list = copy.deepcopy(working_passer_id_list)  # 근로기록에 passer 가 없은 경우 만들기 위해 찾는다.
    for pass_record in pass_record_list:
        if pass_record.passer_id in no_pass_record_passer_id_list:
            no_pass_record_passer_id_list.remove(pass_record.passer_id)
    if len(no_pass_record_passer_id_list) > 0:
        fail_dict['no_pass_record_passer_id_list'] = no_pass_record_passer_id_list  # 근로기록 없는 근로자
    logSend('  > fail: {}, working_passer_id_list: {}'.format(fail_dict, working_passer_id_list))
    for passer_id in no_pass_record_passer_id_list:
        new_pass_record = Pass_History(
            passer_id=int(passer_id),
            year_month_day=year_month_day,
            action=0,
            work_id=work_id,
        )
        new_pass_record.save()
    pass_histories = Pass_History.objects.filter(year_month_day=year_month_day, passer_id__in=employee_ids,
                                                 work_id=work_id)
    list_pass_history = []
    week_comments = ["일", "월", "화", "수", "목", "금", "토"]
    week_index = str_to_datetime(year_month_day).weekday()
    week_index = (week_index + 1) % 7
    logSend('  > week_index: {}, {}'.format(week_index, week_comments[week_index]))
    day_type_descriptions = ["유급휴일", "무급휴일", "소정근무일", "수동지정"]
    day_type = 3
    if work['time_info']['paid_day'] == -1:  # 유급휴일 수동지정
        day_type = 3
    elif week_index == work['time_info']['paid_day']:
        day_type = 0
    elif week_index in work['time_info']['working_days']:
        day_type = 2
    else:
        day_type = 1
    for pass_history in pass_histories:
        if work['time_info']['paid_day'] == -1:  # 유급휴일 수동지정
            # pass_history.day_type  # 근무일 구분 0: 유급휴일, 1: 주휴일(연장 근무), 2: 소정근로일, 3: 휴일(휴일/연장 근무)
            day_type = pass_history.day_type
        pass_history_dict = {
            'passer_id': AES_ENCRYPT_BASE64(str(pass_history.passer_id)),
            'year_month_day': pass_history.year_month_day,
            'action': pass_history.action,
            'work_id': AES_ENCRYPT_BASE64(work['id']),
            'dt_in': dt_null(pass_history.dt_in),
            'dt_in_verify': dt_null(pass_history.dt_in_verify),
            'in_staff_id': pass_history.in_staff_id,
            'dt_out': dt_null(pass_history.dt_out),
            'dt_out_verify': dt_null(pass_history.dt_out_verify),
            'out_staff_id': pass_history.out_staff_id,
            'overtime': pass_history.overtime,
            'overtime_staff_id': pass_history.overtime_staff_id,
            'x': pass_history.x,
            'y': pass_history.y,
            'notification': notification_passer_key_dict[pass_history.passer_id] if pass_history.passer_id in notification_passer_key_dict.keys() else -1,
            'week': week_comments[week_index],
            'day_type': day_type,
            'day_type_description': day_type_descriptions[day_type],
        }
        list_pass_history.append(pass_history_dict)
    result = {'employees': list_pass_history,
              'fail_list': fail_dict,
              # 'work': work,
              }
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def pass_record_of_employees_in_day_for_customer_v2(request):
    """
    << 고객 서버용 >> 복수 근로자의 출퇴근 시간 수정, 유급 휴일 지정/해제, 연차 휴무, 조기 퇴근, 연장근로 부여/수정
    - work 의 시작 날짜 이전을 요청하면 안된다. - work 의 시작 날짜를 검사하지 않는다.
    - 출퇴근 기록이 없으면 출퇴근 기록을 새로 만든다.
    - 수정한 시간 오류 검사 X : 출근 시간보다 퇴근 시간이 느리다, ...
    http://0.0.0.0:8000/employee/pass_record_of_employees_in_day_for_customer_v2?employees=&dt=2019-05-06
    POST : json
        {
            employees: [ employee_id, employee_id, ...],  # 배열: 대상 근로자 (암호화된 값)
            year_month_day: 2018-12-28,                   # 대상 날짜
            work_id: work_id,                             # 업무 id (암호화된 값): 암호를 풀어서 -1 이면 업무 특정짓지 않는다.
            #
            # 아래항은 옵션임 - 값이 없으면 처리하지 않음
            #
            overtime: 0                     # -3: 반차휴무, -2: 연차휴무, -1: 조기퇴근, 0: 정상 근무, 1~6: 연장 근무 시간( 1:30분, 2:1시간, 3:1:30, 4:2:00, 5:2:30, 6:3:00 )
            overtime_staff_id: staff_id     # 처리 직원 id (암호화된 값)
            comment: 막내 운동회               # 유급휴일, 연차휴무, 조기퇴근 의 사유

            dt_in_verify: 08:00             # 수정된 출근시간 (24 시간제)
            in_staff_id: staff_id           # 출근 시간 수정 직원 id (암호화됨)

            dt_out_verify: 17:00             # 수정된 퇴근시간 (24 시간제)
            out_staff_id: staff_id           # 퇴근 시간 수정 직원 id (암호화됨)

            day_type: 0                     # 근무일 구분 0: 유급휴일, 1: 주휴일(연장 근무), 2: 소정근로일, 3: 휴일(휴일/연장 근무)
            day_type_staff_id: staff_id     # 근무일 구분을 변경한 직원 id (암호화됨)
            comment: 투표                    # 근무일 구분을 변경한 사유
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
    parameter_check = is_parameter_ok(rqst, ['employees', 'year_month_day', 'work_id_!', 'comment_@'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    employees = parameter_check['parameters']['employees']
    year_month_day = parameter_check['parameters']['year_month_day']
    work_id = parameter_check['parameters']['work_id']
    send_comment = parameter_check['parameters']['comment']
    if send_comment == None:
        send_comment = ""

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
    passer_dict = {passer.id: passer for passer in passer_list}
    #
    # 근로자 id가 빠지지 않았는지 확인하는 기능이 필요하면 여기 넣는다.
    #

    # 지정된 근로자에게 알림(notification_work) 을 만들고 보낸다.
    # 업무 로딩
    work = get_work_dict([int(work_id)])
    logSend('  > work: {}'.format(work))
    work_dict = work[list(work.keys())[0]]
    work_dict['id'] = list(work.keys())[0]  # work_dic 에 'id'가 없어서 넣어준다.
    logSend('  > work_dict: {}'.format(work_dict))
    fail_list = []
    notification_type = 0
    push_title = ''
    staff_id = -1
    comment = ''
    dt_inout = str_to_datetime("2019-12-05")
    # 근무일 변경 처리
    if ('day_type' in rqst.keys()) and ('day_type_staff_id' in rqst.keys()):
        day_type = int(rqst['day_type'])
        day_type_staff_id = AES_DECRYPT_BASE64(rqst['day_type_staff_id'])
        is_ok = True
        if day_type_staff_id == '__error':
            is_ok = False
            fail_list.append(' overtime_staff_id: 비정상')
        else:
            notification_type = (day_type + 10) * -1
            dt_inout = str_to_datetime(year_month_day)
            staff_id = day_type_staff_id
            # 근무일 구분 0: 유급휴일, 1: 주휴일(연장 근무), 2: 소정근로일, 3: 휴일(휴일/연장 근무)
            if day_type == 0:
                push_title = '{} 유급휴일로 부여합니다.'.format(year_month_day)
                comment = send_comment
            elif day_type == 1:
                push_title = '{} 주휴일(연장근로)로 부여합니다.'.format(year_month_day)
                comment = send_comment
            elif day_type == 2:
                push_title = '{} 소정근로일로 부여합니다.'.format(year_month_day)
                comment = send_comment
            else:
                push_title = '{} 휴일(휴일근로)로 부여합니다.'.format(year_month_day)
                comment = send_comment
    # 연장 근무 처리
    if ('overtime' in rqst.keys()) and ('overtime_staff_id' in rqst.keys()):
        overtime = int(rqst['overtime'])
        overtime_staff_id = AES_DECRYPT_BASE64(rqst['overtime_staff_id'])
        is_ok = True
        if overtime_staff_id == '__error':
            is_ok = False
            fail_list.append(' overtime_staff_id: 비정상')
        else:
            notification_type = overtime
            dt_inout = str_to_datetime(year_month_day)
            staff_id = overtime_staff_id
            if overtime == -3:
                push_title = '{} 반차휴가로 부여합니다.'.format(year_month_day)
                comment = send_comment
            elif overtime == -2:
                push_title = '{} 연차휴가를 부여합니다.'.format(year_month_day)
                comment = send_comment
            elif overtime == -1:
                push_title = '{} 조기퇴근을 부여합니다.'.format(year_month_day)
                comment = send_comment
            elif overtime == 0:
                push_title = '{} 휴가, 조퇴, 연장이 철회됩니다.'.format(year_month_day)
                comment = '연차휴가, 조기퇴근, 연장근무'
            else:
                push_title = '{} 연장근로를 부여합니다.'.format(year_month_day)
                comment = '{0:02d} 시간 {1:02d} 분'.format(overtime // 2, (overtime % 2) * 30)

    # 출근시간 수정 처리
    if ('dt_in_verify' in rqst.keys()) and ('in_staff_id' in rqst.keys()):
        in_staff_id = AES_DECRYPT_BASE64(rqst['in_staff_id'])
        is_ok = True
        if in_staff_id == '__error':
            is_ok = False
            fail_list.append(' in_staff_id: 비정상')
        else:
            staff_id = int(in_staff_id)
            if rqst['dt_in_verify'][0:2] == '25':
                notification_type = -22
                push_title = '{} 출근시간을 삭제합니다.'.format(year_month_day)
                comment = '출근이 취소됩니다.'
                dt_inout = str_to_datetime(year_month_day)
            else:
                notification_type = -20
                push_title = '{} 출근시간을 조정합니다.'.format(year_month_day)
                comment = '{}'.format(rqst['dt_in_verify'])
                dt_inout = str_to_datetime('{} {}'.format(year_month_day, rqst['dt_in_verify']))

    # 퇴근시간 수정 처리
    if ('dt_out_verify' in rqst.keys()) and ('out_staff_id' in rqst.keys()):
        out_staff_id = AES_DECRYPT_BASE64(rqst['out_staff_id'])
        is_ok = True
        if out_staff_id == '__error':
            is_ok = False
            fail_list.append(' out_staff_id: 비정상')
        else:
            staff_id = int(out_staff_id)
            if rqst['dt_out_verify'][0:2] == '25':
                notification_type = -23
                push_title = '{} 퇴근시간을 삭제합니다.'.format(year_month_day)
                comment = '퇴근이 취소됩니다.'
                dt_inout = str_to_datetime(year_month_day)
            else:
                notification_type = -21
                push_title = '{} 퇴근시간을 조정합니다.'.format(year_month_day)
                comment = '{}'.format(rqst['dt_out_verify'])
                dt_inout = str_to_datetime('{} {}'.format(year_month_day, rqst['dt_out_verify']))
    #
    # 중복된 알림이 있으면 취소처리한다.
    # 예) 2020-06-05, 퇴근 취소(-21) > 2020-06-05, 23:00 퇴근(-23) 이면 앞을 취소처리
    #
    cancel_noti_list = Notification_Work.objects.filter(dt_inout__startswith=dt_inout.date(), notification_type=notification_type)
    for cancel_noti in cancel_noti_list:
        cancel_noti.is_x = 1
        cancel_noti.save()
    #
    # 유급휴일이 수동지정이면 day_type 으로 소정근로일/무급휴일/유급휴일을 표시해야한다.
    # 근태정보 변경 알림을 확인/거절/기한지남 인 경우 표시해야 한다.
    #
    today = datetime.datetime.now()
    push_list = []
    for passer_id in passer_dict.keys():
        passer = passer_dict[passer_id]
        new_notification = Notification_Work(
            work_id=work_id,
            employee_id=passer_id,
            employee_pNo=passer.pNo,
            dt_answer_deadline=today + datetime.timedelta(days=2),
            # dt_begin=dt_in_verify,    # 사용안함
            # dt_end=dt_out_verify,     # 사용안함
            dt_reg=today,
            work_place_name=work_dict['work_place_name'],
            work_name_type=work_dict['work_name_type'],
            is_x=0,  # 사용확인 용?
            notification_type=notification_type,  # 알림 종류: -30: 새업무 알림,
            # -21: 퇴근시간 수정, -20: 출근시간 수정,
            # 근무일 구분 0: 유급휴일, 1: 주휴일(연장 근무), 2: 소정근로일, 3: 휴일(휴일/연장 근무)
            # -13: 휴일(휴일근무), -12: 소정근로일, -11: 주휴일(연장근무), -10: 유급휴일
            # -3: 반차휴무, -2: 연차휴무, -1: 조기퇴근, 0:정상근무, 1~18: 연장근무 시간
            comment=comment,
            staff_id=staff_id,
            dt_inout=dt_inout,
        )
        new_notification.save()
        logSend('  > notification: {}'.format(new_notification))
        push_list.append({'id': passer.id, 'token': passer.push_token, 'pType': passer.pType})
    logSend(push_list)
    if len(push_list) > 0:
        push_contents = {
            'target_list': push_list,
            'func': 'user',
            'isSound': True,
            'badge': 1,
            'contents': {'title': push_title,
                         'subtitle': comment,
                         'body': {'action': 'ChangeWork',
                                  'current': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                         }
        }
        send_push(push_contents)
    result = {'fail_list': fail_list,
              }
    return REG_200_SUCCESS.to_json_response(result)


def update_pass_history(pass_history: dict, work: dict):
    """
    출퇴근 시간에 맞추어 지각, 조퇴 처리
    to use:
        pass_record_of_employees_in_day_for_customer
        pass_verify
        pass_sms
    """
    # logSend('  > pass_history: {}'.format({key: pass_history.__dict__[key] for key in pass_history.__dict__.keys() if not key.startswith('_')}))
    # logSend('  > work: {}'.format({key: work[key] for key in work.keys() if not key.startswith('_')}))
    if 'time_info' in work.keys():
        # 업무가 있는 경우 2020/02/05 새로 만들다.
        # 출근 처리
        if pass_history.dt_in_verify is None:
            action_in = 0
        else:
            # 출근 터치가 있으면 지각여부 처리한다.
            action_in = 100
            # logSend('  > time_info: {}'.format(work['time_info']))
            time_info = work['time_info']
            # logSend('  > time_info: {} {}'.format(time_info, type(time_info)))
            work_time_list = time_info['work_time_list']
            begin_list = [str2min(work_time['t_begin']) for work_time in work_time_list]
            # logSend(' >> work begin: {}'.format(begin_list))
            dt_in_verify = pass_history.dt_in_verify.hour * 60 + pass_history.dt_in_verify.minute
            # logSend('  > dt_in_verify: {}:{} {}'.format(pass_history.dt_in_verify.hour, pass_history.dt_in_verify.minute, dt_in_verify))
            min = 1440
            for begin in begin_list:
                gap = begin - dt_in_verify
                if abs(gap) < abs(min):
                    min = gap
                # logSend('  > gap: {} = {} - {} min: {}'.format(gap, begin, dt_in_verify, min))
            # logSend(' >> out: {}, gap: {}'.format(dt_in_verify, min2str(min)))
            if min > 0:  # 출근시간을 넘겼다.
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
                logSend('  > time_info: {}'.format(work['time_info']))
                time_info = work['time_info']
                # logSend('  > time_info: {} {}'.format(time_info, type(time_info)))
                work_time_list = time_info['work_time_list']
                end_list = [str2min(work_time['t_end']) for work_time in work_time_list]
                # logSend(' >> work end: {}'.format(end_list))
                dt_out_verify = pass_history.dt_out_verify.hour * 60 + pass_history.dt_out_verify.minute
                # logSend('  > dt_out_verify: {}:{} {}'.format(pass_history.dt_out_verify.hour, pass_history.dt_out_verify.minute, dt_out_verify))
                min = 1440
                for end in end_list:
                    gap = dt_out_verify - end
                    if abs(gap) < abs(min):
                        min = gap
                    # logSend('  > gap: {} = {} - {} min: {}'.format(gap, end, dt_out_verify, min))
                # logSend(' >> out: {}, gap: {}'.format(dt_out_verify, min2str(min)))
                if min < 0:  # 퇴근시간에서 모자란다.
                    action_in = 20
        pass_history.action = action_in + action_out

        return
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
            work_id: 37             # 업무 id
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

    if not employee_works.find(work_id):
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
    work_id = parameter_check['parameters']['work_id']
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
    logSend('  > work_id: {}'.format(work_id))
    if work_id is None or int(work_id) == -1:
        pass_record_list = Pass_History.objects.filter(passer_id=passer.id,
                                                       year_month_day__contains=year_month).order_by('year_month_day')
    else:
        # works = Work.objects.filter(customer_work_id=customer_work_id)
        # work_dict = get_work_dict(work_id)
        # if len(work_dict.keys()) == 0:
        #     logError(get_api(request), ' 근로자 서버에 고객서버가 요청한 work_id({}) 가 없다. [발생하면 안됨]'.format(customer_work_id))
        #     return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '소속된 업무가 없습니다.'})
        pass_record_list = Pass_History.objects.filter(passer_id=passer.id,
                                                       work_id=work_id,
                                                       year_month_day__contains=year_month).order_by('year_month_day')
    workings = []
    for pass_record in pass_record_list:
        try:
            working_time = int(float(employee.working_time))
            working_hour = (working_time // 4) * 4
            break_hour = working_time - working_hour
        except Exception as e:
            logError(get_api(request), ' 근무시간이 등록되지 않은 근로자({}) - {}'.format(employee.name, e))
            working_hour = 8
            break_hour = 1
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


@cross_origin_read_allow
def work_report_for_customer(request):
    """
    <<<고객 서버용>>> 근로 내용 : 근로자의 근로 내역을 월 기준으로 1년까지 요청함, 캘린더나 목록이 스크롤 될 때 6개월정도 남으면 추가 요청해서 표시할 것
    action 설명
        총 3자리로 구성 첫자리는 출근, 2번째는 퇴근, 3번째는 외출 횟수
        첫번째 자리 1 - 정상 출근, 2 - 지각 출근
        두번째 자리 1 - 정상 퇴근, 2 - 조퇴, 3 - 30분 연장 근무, 4 - 1시간 연장 근무, 5 - 1:30 연장 근무
    overtime 설명
        연장 근무 -2: 휴무, -1: 업무 끝나면 퇴근, 0: 정상 근무, 1~18: 연장 근무 시간( 1:30분, 2:1시간, 3:1:30, 4:2:00, 5:2:30, 6:3:00 7: 3:30, 8: 4:00, 9: 4:30, 10: 5:00, 11: 5:30, 12: 6:00, 13: 6:30, 14: 7:00, 15: 7:30, 16: 8:00, 17: 8:30, 18: 9:00)
    http://0.0.0.0:8000/employee/work_report_for_customer?employee_id=qgf6YHf1z2Fx80DR8o/Lvg&dt=2018-12
    GET
        employee_id = 근로자 id        # employee 서버의 passer_id
        work_id = 업무 id             # customer 서버의 work_id  = customer_work_id (암호화되어 있음)
        year_month = '2018-01'
    response
        STATUS 200
            {'message': '근태내역이 없습니다.', "arr_working": [] }
            {
              "message": "정상적으로 처리되었습니다.",
              "arr_working": [
                {
                  "name": "이영길",        # 이름
                  "break_sum": 0,        # 휴게시간 합계
                  "basic_sum": 180,      # 기본근로시간 합계
                  "night_sum": 0,        # 야간근로시간 합계
                  "overtime_sum": 8,     # 연장근로시간 합계
                  "holiday_sum": 0,      # 휴일근로시간 합계
                  "ho_sum": 0,           # 휴일/연장근로시간 합계
                  "2019-10": [
                    {
                      "01": {                       # 근무한 날짜
                        "dt_in_verify": "06:27",        # 출근시간
                        "dt_out_verify": "15:00",       # 퇴근시간
                        "break": "01:00"                # 휴게시간
                        "basic": "",                    # 기본근로
                        "night": "",                    # 야간근로
                        "overtime": 0,                  # 연장근무
                        "holiday": "",                  # 휴일근로
                        "ho": ""                        # 휴일/연장 근로
                      }
                    },
                    ......
                    {
                      "31": {                       # 근무한 날짜
                        "dt_in_verify": "06:27",        # 출근시간
                        "dt_out_verify": "15:00",       # 퇴근시간
                        "break": "01:00"                # 휴게시간
                        "basic": "",                    # 기본근로
                        "night": "",                    # 야간근로
                        "overtime": 0,                  # 연장근무
                        "holiday": "",                  # 휴일근로
                        "ho": ""                        # 휴일/연장 근로
                      }
                    }
                  ]
                }
              ]
            }
        STATUS 416
            {'message': '업무기간을 벗어났습니다.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'work_id\' 가 없어요'}
            {'message':'ClientError: parameter \'year_month\' 가 없어요'}
            {'message':'ClientError: parameter \'work_id\' 가 정상적인 값이 아니예요.'}
            {'message':'ClientError: parameter \'employee_id\' 가 정상적인 값이 아니예요.'}
            {'message': '업무가 없어요.({})'.format(e)}
            {'message': '해당 근로자가 없어요.({})'.format(e)}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['work_id_!', 'employee_id_!_@', 'year_month'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    work_id = parameter_check['parameters']['work_id']
    passer_id = parameter_check['parameters']['employee_id']
    year_month = parameter_check['parameters']['year_month']

    if int(work_id) == -1:
    # if customer_work_id == 'i52bN-IdKYwB4fcddHRn-g':  # AES_ENCRYPT_BASE64('-1')
        # 근로자 한명에 대한 업무 내역이라 모든 업무를 가져올 때
        # my_work_records 에서 사용
        try:
            passer = Passer.objects.get(id=passer_id)
        except Exception as e:
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '해당 근로자가 없어요.({})'.format(e)})
        pass_record_list = Pass_History.objects.filter(passer_id=passer.id,
                                                       year_month_day__contains=year_month).order_by('year_month_day')
        work_id_dict = {}
        for pass_record in pass_record_list:
            if pass_record.work_id not in work_id_dict.keys():
                work_id_dict[pass_record.work_id] = id
        # work_id_dict = {pass_record.work_id:id for pass_record in pass_record_list if pass_record.work_id not in work_id_dict.keys()}
        work_dict = get_work_dict(list(work_id_dict.keys()))
        logSend('  > work_dict: {}'.format(work_dict))
    else:
        work_dict = get_work_dict([work_id])
        logSend('  > work_dict: {}'.format(work_dict))
        if len(work_dict.keys()) == 0:
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '업무가 없어요.({})'.format(e)})
        work = work_dict[work_id]
        # try:
        #     work = Work.objects.get(customer_work_id=customer_work_id)
        # except Exception as e:
        #     return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '업무가 없어요.({})'.format(e)})
        print('   > {}'.format(passer_id))
        is_one_passer = False
        if passer_id is not None:
            is_one_passer = True
            try:
                passer = Passer.objects.get(id=passer_id)
            except Exception as e:
                return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '해당 근로자가 없어요.({})'.format(e)})
        logSend('>> work_id: {}, passer_id: {} year_month: {}'.format(work_id, passer_id, year_month))
        work_begin = str_to_dt(work['dt_begin'])
        work_end = str_to_dt(work['dt_end']) + datetime.timedelta(days=1)
        ym = str_to_datetime(year_month)

        ym_low = ym + relativedelta(months=1) - datetime.timedelta(minutes=1)
        ym_high = ym_low - relativedelta(months=1)
        # print('>>> begin: {}, end: {}'.format(work.begin, work.end))
        # print('  > begin: {}, end: {}'.format(work_begin, work_end))
        # print('  > ym: {}, low: {}, high: {}'.format(ym, ym_low, ym_high))

        if not (work_begin < ym_low and ym_high < work_end):
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '업무기간을 벗어났습니다.'})
        if is_one_passer:
            pass_record_list = Pass_History.objects.filter(passer_id=passer.id, work_id=work_id,
                                                           year_month_day__contains=year_month).order_by('year_month_day')
        else:
            pass_record_list = Pass_History.objects.filter(work_id=work_id,
                                                           year_month_day__contains=year_month).order_by('year_month_day')
    if len(pass_record_list) == 0:
        return REG_200_SUCCESS.to_json_response({'message': '근태내역이 없습니다.', 'arr_working': []})
    #
    # 근로자의 근로내역 생성: 근로자 id 를 키로하는 dictionary
    #
    week_comment = ['월', '화', '수', '목', '금', '토', '일']
    passer_rec_dict = {}
    for pass_record in pass_record_list:
        passer_record_dict = {
            'passer_id': pass_record.passer_id,
            'year_month_day': pass_record.year_month_day,
            'action': pass_record.action,
            'work_id': pass_record.work_id,
            'dt_in': dt_str(pass_record.dt_in, "%H:%M"),
            'dt_in_em': dt_str(pass_record.dt_in_em, "%H:%M"),
            'dt_in_verify': dt_str(pass_record.dt_in_verify, "%H:%M"),
            'in_staff_id': pass_record.in_staff_id,
            'dt_out': dt_str(pass_record.dt_out, "%H:%M"),
            'dt_out_em': dt_str(pass_record.dt_out_em, "%H:%M"),
            'dt_out_verify': dt_str(pass_record.dt_out_verify, "%H:%M"),
            'out_staff_id': pass_record.out_staff_id,
            'overtime': zero_blank(pass_record.overtime),
            'overtime_staff_id': pass_record.overtime_staff_id,
            'week': week_comment[str_to_datetime(pass_record.year_month_day).weekday()],
        }
        if pass_record.passer_id in passer_rec_dict.keys():  # 출입자 id 의 근로자가 있으면 근로내역을 추가한다.
            passer_rec_dict[pass_record.passer_id].append(passer_record_dict)
            # print('   + {} {}'.format(passer_record_dict['year_month_day'], passer_record_dict['passer_id']))
        else:
            passer_rec_dict[pass_record.passer_id] = [passer_record_dict]
            # print('   n {} {}'.format(passer_record_dict['year_month_day'], passer_record_dict['passer_id']))
    # 근로자 정보: 이름 전화번호
    passer_id_list = list(passer_rec_dict.keys())
    logSend('  > passer_id_list: {}'.format(passer_id_list))
    passer_list = Passer.objects.filter(id__in=passer_id_list)
    employee_id_list = [passer.employee_id for passer in passer_list]
    employee_list = Employee.objects.filter(id__in=employee_id_list)
    employee_dict = {employee.id: employee.name for employee in employee_list}
    if len(passer_id_list) != len(employee_list):
        logError(get_api(request), ' 인원(근로자) != 인원(근로자 정보): 근로자 정보가 없는 근로자가 있다.')
        for passer in passer_list:
            if passer.employee_id not in employee_dict.keys():
                employee_dict[passer.employee_id] = '-----'
    passer_dict = {}
    for passer in passer_list:
        passer_dict[passer.id] = {'pNo': passer.pNo, 'name': employee_dict[passer.employee_id]}
    if len(passer_id_list) != len(passer_list):
        logError(get_api(request), ' 인원(근로자) != 인원(근로기록): 근로기록의 근로자가 없다.'.format(work_id))
        for passer_id in passer_rec_dict.keys():
            if passer_id not in passer_dict.keys():
                passer_dict[passer_id] = {'pNo': '01099990000', 'name': '---'}
    # for passer_key in passer_rec_dict.keys():
    #     passer_rec_list = passer_rec_dict[passer_key]
    #     for passer_day in passer_rec_list:
    #         #
    #         # 여기서 연장근무, 휴게근무, 야간근무를 처리하던가
    #         #
    #         print('   {} {} {} {}'.format(passer_day['year_month_day'], passer_day['dt_in_verify'], passer_day['dt_out_verify'], passer_dict[passer_day['passer_id']]['name']))
    arr_working = []
    for passer_id in passer_rec_dict.keys():
        logSend('  > passer_rec_dict: {}'.format(passer_rec_dict[passer_id]))
        working = {'name': passer_dict[passer_id]['name'],
                   'days': {}}
        sum_break = 5
        sum_basic = 209
        sum_night = 0
        sum_overtime = 8
        sum_holiday = 0
        sum_ho = 0
        day_list = passer_rec_dict[passer_id]
        for day in day_list:
            day_key = day['year_month_day'][8:10]
            del day['action']
            # del day['passer_id']
            del day['year_month_day']
            # del day['work_id']
            del day['dt_in']
            del day['dt_in_em']
            del day['in_staff_id']
            del day['dt_out']
            del day['dt_out_em']
            del day['out_staff_id']
            del day['overtime_staff_id']
            day['break'] = '01:00'  # 휴게시간
            day['basic'] = ''       # 기본근로
            day['night'] = ''       # 야간근로
            # day['overtime']       # 연장근로
            day['holiday'] = ''     # 휴일근무
            day['ho'] = ''          # 휴일/연장

            sum_break += str2min(day['break'])
            sum_basic += int_none(day['basic'])
            sum_night += int_none(day['night'])
            sum_overtime += int_none(day['overtime'])
            sum_holiday += int_none(day['holiday'])
            sum_ho += int_none(day['ho'])

            # day_work = {day_key: day}
            working['days'][day_key] = day
            #
            # 시간제이면 이번주를 개근했는지 확인해서 주휴수당 시간을 추가해야한다.
            #   - 유급휴일이 수동지정이면 이전 유급휴일부터 다음 유급휴일 사이에 개근했는지 확인해야한다.
            #   - 소정근로일이 월/수/금 이면 월수금을 개근했는지 확인해야한다.
            #
        working['break_sum'] = min2str(sum_break)
        working['basic_sum'] = sum_basic
        working['night_sum'] = sum_night
        working['overtime_sum'] = sum_overtime
        working['holiday_sum'] = sum_holiday
        working['ho_sum'] = sum_ho
        arr_working.append(working)
    result = {"arr_working": arr_working}
    logSend('> {}'.format(arr_working))
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
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'passer_id\' 가 없어요'}
            {'message':'ClientError: parameter \'dt\' 가 없어요'}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    parameter_check = is_parameter_ok(rqst, ['passer_id', 'dt'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    passer_id = parameter_check['parameters']['passer_id']
    dt = parameter_check['parameters']['dt']
    #
    # 근로자 서버로 근로자의 월 근로 내역을 요청
    #
    employee_info = {
        'employee_id': passer_id,
        'dt': dt,
    }
    response_employee = requests.post(settings.EMPLOYEE_URL + 'my_work_histories_for_customer', json=employee_info)
    logSend(response_employee)
    # employee_info = {
    #     'employee_id': passer_id,
    #     'work_id': AES_ENCRYPT_BASE64('-1'),
    #     'year_month': dt,
    # }
    # response_employee = requests.post(settings.EMPLOYEE_URL + 'work_report_for_customer', json=employee_info)
    # logSend(response_employee)
    """
        <<<고객 서버용>>> 근로 내용 : 근로자의 근로 내역을 월 기준으로 1년까지 요청함, 캘린더나 목록이 스크롤 될 때 6개월정도 남으면 추가 요청해서 표시할 것
    action 설명
        총 3자리로 구성 첫자리는 출근, 2번째는 퇴근, 3번째는 외출 횟수
        첫번째 자리 1 - 정상 출근, 2 - 지각 출근
        두번째 자리 1 - 정상 퇴근, 2 - 조퇴, 3 - 30분 연장 근무, 4 - 1시간 연장 근무, 5 - 1:30 연장 근무
    overtime 설명
        연장 근무 -2: 휴무, -1: 업무 끝나면 퇴근, 0: 정상 근무, 1~18: 연장 근무 시간( 1:30분, 2:1시간, 3:1:30, 4:2:00, 5:2:30, 6:3:00 7: 3:30, 8: 4:00, 9: 4:30, 10: 5:00, 11: 5:30, 12: 6:00, 13: 6:30, 14: 7:00, 15: 7:30, 16: 8:00, 17: 8:30, 18: 9:00)
    http://0.0.0.0:8000/employee/work_report_for_customer?employee_id=qgf6YHf1z2Fx80DR8o/Lvg&dt=2018-12
    GET
        employee_id = 근로자 id        # employee 서버의 passer_id
        work_id = 업무 id             # customer 서버의 work_id  = customer_work_id (암호화되어 있음)
        year_month = '2018-01'

    """
    result = response_employee.json()
    # result['working'] = result.pop('arr_working')
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
            {'message': '근태내역이 없습니다.', "working": [], "work_infor': [] }
            {
              "message": "정상적으로 처리되었습니다.",
              "working": [
                {
                  "year_month_day": "2020-01-01",
                  "action": 110,
                  "dt_begin": "2020-01-01 08:29",
                  "dt_end": "2020-01-01 17:33",
                  "overtime": "",
                  "week": "수",
                  "break": "01:00",
                  "basic": "",
                  "night": "",
                  "holiday": "",
                  "ho": ""
                },
                ......
                {
                  "year_month_day": "2020-01-27",
                  "action": 110,
                  "dt_begin": "2020-01-27 08:29",
                  "dt_end": "2020-01-27 17:33",
                  "overtime": "",
                  "week": "월",
                  "break": "01:00",
                  "basic": "",
                  "night": "",
                  "holiday": "",
                  "ho": ""
                }
              ],
              "work_infor": [
                {
                  "name": "박종기",
                  "break_sum": "19:05",
                  "basic_sum": 209,
                  "night_sum": 0,
                  "overtime_sum": 8,
                  "holiday_sum": 0,
                  "ho_sum": 0
                }
              ]
            }
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'passer_id\' 가 없어요'}
            {'message':'ClientError: parameter \'dt\' 가 없어요'}
            {'message': 'passer_id 근로자가 서버에 없다.'}
            {'message': 'passer_id 의  근로자 정보가 서버에 없다.'}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['passer_id', 'dt'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    passer_id = parameter_check['parameters']['passer_id']
    dt = parameter_check['parameters']['dt']
    #
    # 근로자 서버로 근로자의 월 근로 내역을 요청
    #
    employee_info = {
        'employee_id': passer_id,
        'work_id': AES_ENCRYPT_BASE64('-1'),
        'year_month': dt,
    }
    response_employee = requests.post(settings.EMPLOYEE_URL + 'work_report_for_customer', json=employee_info)

    working_result = []
    work_infor = []
    arr_working = response_employee.json()['arr_working']
    for working in arr_working:
        days = working['days']
        for day_key in days.keys():
            day = days[day_key]
            day_info = {
                "year_month_day": '{}-{}'.format(dt, day_key),
                "work_id": day['work_id'],
                "action": 110,
                "dt_begin": '{}'.format(day['dt_in_verify']),
                "dt_end": '{}'.format(day['dt_out_verify']),
                "overtime": day['overtime'],
                "week": day['week'],
                "break": day['break'],
                "basic": int_none(day['basic']),
                "night": int_none(day['night']),
                "holiday": int_none(day['holiday']),
                "ho": int_none(day['ho']),
            }
            working_result.append(day_info)
        del working['days']
        work_infor.append(working)

    return REG_200_SUCCESS.to_json_response({'working': working_result, 'work_infor': work_infor})


def get_dic_passer():
    """
    use:
        def beacon_status(request):
    return:
        dic_passer = {
                        1: {"name":"박종기", "pNo":"01025573555"},
                        2: {"name:"곽명석", "pNo": "01054214410"}
                    }
    """
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


def set_break_time_of_work_time_info(work_dict: dict):
    # 업무 정보에서 휴게시간을 계산해서 넣어둔다.
    # logSend('----------- work time list')
    for work_dict_key in work_dict.keys():
        work_time_list = work_dict[work_dict_key]['time_info']['work_time_list']
        for work_time in work_time_list:
            # logSend('  > work_time: {}'.format(work_time))
            if work_time['break_time_type'] == 0:
                break_time_sum = 0
                for break_time in work_time['break_time_list']:
                    begin = str2min(break_time['bt_begin'])
                    end = str2min(break_time['bt_end'])
                    time = end - begin
                    if end < begin:
                        time = end + (1440-begin)
                    break_time_sum = time
                # logSend('  >> break_time_list: {} - {} - {}'.format(work_time['break_time_list'], break_time_sum, (break_time_sum/60)))
            elif work_time['break_time_type'] == 1:
                break_time_sum = str2min(work_time['break_time_total'])
                # logSend('  >> break_time_total: {} - {} - {}'.format(work_time['break_time_total'], break_time_sum, (break_time_sum/60)))
            else:
                break_time_sum = 0
                # logSend('  >> break_time: {}'.format(break_time_sum))
            work_time['break_hours'] = break_time_sum / 60
        work_dict[work_dict_key]['time_info']['work_time_list'] = sorted(work_time_list, key=itemgetter('t_begin'))
        logSend('  ----- work_time_list: {}'.format(work_dict[work_dict_key]['time_info']['work_time_list']))
    # logSend('----------- work time list')
    return


def get_work_time(work_time_list: list, dt_in_verify: datetime, dt_out_verify: datetime, overtime: int) ->dict:
    """
    출근이나 퇴근시간으로
    업무에서 설정한 출퇴근 시간 리스트에서
    근무시간의 기준이되는 출퇴근시간을 찾고
    기본근로시간, 휴게시간을 계산해 넣는다.
    :param work_time_list: 출퇴근시간리스트
    :param time_in: 출근시간
    :param time_out: 퇴근시간
    :param overtime: 연장근로시간 1 > 30분, 2 > 60분, ... (0 이하 무시)
    :return: {
            'dt_in': "2020-05-13 05:00:00",
            'dt_out': "2020-05-13 13:00:00",
            'work_minutes': 480,
            'break_hours': 0,
            'work_time': {'t_begin': '15:00', 't_end': '23:00', 'break_time_type': 2, 'break_time_list': None, 'break_time_total': None, 'break_hours': 0.0}
            }
    """
    if dt_in_verify is None or dt_out_verify is None:
        result = {'dt_in': dt_in_verify,
                  'dt_out': dt_out_verify,
                  'work_minutes': 0,
                  'break_hours': 0,
                  'work_time': None
                  }
        return result

    index_work_time = 0    # 근무시간 색인: 실제 출퇴근시간이 가장 근접한 근무시간 배열의 색인

    mins_in = str2min(dt_str(dt_in_verify, "%H:%M"))  # 시간과 분으로 분으로 환산: 1:30 > 90

    mins_overtime = (0 if overtime < 0 else overtime) * 30
    logSend('   > mins_overtime: {}, dt_out_verify: {}'.format(mins_overtime, dt_out_verify))
    basic_dt_out_verify = dt_out_verify - datetime.timedelta(minutes=mins_overtime)  # 연장근로를 뺀 퇴근시간
    mins_out = str2min(dt_str(basic_dt_out_verify, "%H:%M"))  # 시간과 분으로 분으로 환산: 1:30 > 90

    mins_gap = 1440     # 24 * 60

    for i in range(0, len(work_time_list)):
        work_time = work_time_list[i]
        mins_begin = str2min(work_time['t_begin'])  # 분으로 환산한 출근시간
        mins_end = str2min(work_time['t_end'])  # 분으로 환산한 출근시간
        new_gap = time_gap(mins_in, mins_begin) + time_gap(mins_out, mins_end)
        if mins_gap > new_gap:
            index_work_time = i
            mins_gap = new_gap
    find_work_time = work_time_list[index_work_time]
    # logSend('   > find_work_time: {}'.format(find_work_time))
    dt_in = str_to_datetime(dt_str(dt_in_verify, "%Y-%m-%d ") + find_work_time['t_begin'])
    dt_out = str_to_datetime(dt_str(dt_out_verify, "%Y-%m-%d ") + find_work_time['t_end']) + timedelta(minutes=mins_overtime)
    mins_begin = str2min(find_work_time['t_begin'])
    mins_end = str2min(find_work_time['t_end'])
    mins_work = mins_end - mins_begin
    if mins_end < mins_begin:
        mins_work = mins_end + (1440 - mins_begin)
    mins_work -= find_work_time['break_hours'] * 60
    # mins_work += mins_overtime
    result = {'dt_in': dt_in,
              'dt_out': dt_out,
              'work_minutes': mins_work,
              'break_hours': find_work_time['break_hours'],
              'work_time': find_work_time
              }
    return result


def process_pass_record(passer_record_dict: dict, pass_record: dict, work_dict: dict):
    week_comment = ['월', '화', '수', '목', '금', '토', '일']
    current_work_id = pass_record.work_id
    # 근로자에게 알림이 있을 때 처리 - 2020/03/31 확인하기 전까지 알림 내용이 적용되지 않기 때문에 쓸모가 없어졌다.
    # if (pass_record.in_staff_id != -1) or (pass_record.out_staff_id != -1) or (pass_record.overtime_staff_id != -1) or (pass_record.day_type_staff_id != -1):
    #     # 근로자에게 가 알림을 확인 했으면
    #     if pass_record.dt_accept is None:
    #         passer_record_dict['is_accept'] = '0'  # 관리자에 의한 근태변경을 근로자가 인정하지 않았다.
    #     else:
    #         passer_record_dict['is_accept'] = '1'  # 관리자에 의한 근태변경을 근로자가 확인했다.

    # 연장근로 처리
    #   - 출퇴근 시간과 상관없이 처리한다.
    #   - 조기퇴근은 출퇴근 시간과 상관있다.
    # -2: 연차휴무, -1: 조기퇴근, 0: 정상근무, 1~18: 연장근무(1: 30분, 2: 1시간, ..., 17: 8시간 30분, 18: 9시간)
    # logSend('  > overtime: {}'.format(pass_record.overtime))
    passer_record_dict['overtime'] = str(pass_record.overtime)
    if pass_record.overtime == -2:
        # logSend('  >> overtime: {}'.format(pass_record.overtime))
        if (pass_record.dt_in_verify is None) and (pass_record.dt_out_verify is None):
            passer_record_dict['remarks'] = "연차휴가"
        else:
            passer_record_dict['remarks'] = "연차휴가(반차)"
        return  # 근무가 없기 때문에 더 처리할 일이 없다.
    elif pass_record.overtime == -1:
        # logSend('  >> overtime: {}'.format(pass_record.overtime))
        passer_record_dict['remarks'] = "조기퇴근"
    elif pass_record.overtime == 0:
        # logSend('  >> overtime: {}'.format(pass_record.overtime))
        passer_record_dict['remarks'] = "정상근무"
    else:
        passer_record_dict['remarks'] = '연장근무: {0:02d}:{1:02d}'.format((pass_record.overtime // 2), (pass_record.overtime % 2) * 30)
    #
    # 출퇴근 기록이 없음: 무급휴일이나 유급휴일이겠네.
    #
    if (pass_record.dt_in_verify is None) and (pass_record.dt_out_verify is None):
        passer_record_dict['remarks'] = ""
        return

    # 출퇴근 시간중에 하나라도 있으면 - 어찌되었건 출근했다.
    work_time_list = work_dict[current_work_id]['time_info']['work_time_list']
    r = get_work_time(work_time_list, pass_record.dt_in_verify, pass_record.dt_out_verify, pass_record.overtime)
    # result = {'dt_in': dt_str(dt_in_verify, "%Y-%m-%d %H:%M:%S"),
    #           'dt_out': dt_str(dt_out_verify, "%Y-%m-%d %H:%M:%S"),
    #           'work_minutes': min_work,
    #           'break_hours': find_work_time['break_hours']
    #           }
    logSend('  > get_work_time: {}'.format(r))
    if r['work_minutes'] == 0:
        return
    # 휴게시간
    dt_in = r['dt_in']
    dt_out = r['dt_out']
    passer_record_dict['break'] = str(r['break_hours'])
    # 기본근로시간
    basic_minutes = r['work_minutes']
    basic_hours = basic_minutes / 60
    logSend('  > basic minutes: {}, hours: {}'.format(basic_minutes, basic_hours))
    passer_record_dict['basic'] = str(basic_hours)
    # 연장근로시간
    if pass_record.overtime > 0:
        overtime = pass_record.overtime / 2
        passer_record_dict['overtime'] = str(overtime)
    # 야간근로시간 22:00 ~ 06:00
    # if work_dict[current_work_id]['time_info']['time_type'] != 3:
    #     # 감시단속직은 야간근로시간 없다.
    logSend('  > time: {} ~ {}'.format(dt_in, dt_out))
    dt_night_begin = str_to_datetime(dt_str(dt_in, "%Y-%m-%d 22:00:00"))
    dt_night_end = dt_night_begin + datetime.timedelta(hours=8)
    logSend('  > night: {} ~ {}'.format(dt_night_begin, dt_night_end))
    if (dt_in < dt_night_begin < dt_out) or (dt_in < dt_night_end < dt_out):
        if dt_night_begin < dt_in:
            dt_night_begin = dt_in
        if dt_out < dt_night_end:
            dt_night_end = dt_out
        dt_night = dt_night_end - dt_night_begin
        night = int(dt_night.seconds / 360) / 10
        # night_sum += night
        passer_record_dict['night'] = str(night)
    # 유급휴일근로시간
    week_index = str_to_datetime(pass_record.year_month_day).weekday()
    week_index_db = (week_index + 1) % 7
    logSend('  >> {} week: {} - {}, db: {}'.format(pass_record.year_month_day, week_index, week_comment[week_index], week_index_db))
    # logSend('  > {}'.format(work_dict[current_work_id]['time_info']))
    if week_index_db not in work_dict[current_work_id]['time_info']['working_days']:
        # 소정근로일이 아닌경우 >> 무급휴일이거나 유급 휴일
        # 근무일 구분 0: 유급휴일, 1: 주휴일(연장 근무), 2: 소정근로일, 3: 휴일(휴일/연장 근무)
        if passer_record_dict['day_type'] == 2:
            # 근무일 구분이 default = 2 이면
            if work_dict[current_work_id]['time_info']['paid_day'] == week_index_db:
                # 요일이 유급휴일이면 근무일을 유급휴일로 표시
                passer_record_dict['day_type'] = 0
            elif work_dict[current_work_id]['time_info']['is_holiday_work'] == 1:
                # 무급휴일이 휴일근무로 규정되어 있으면 휴일(휴일/연장 근무)
                passer_record_dict['day_type'] = 3
            else:
                passer_record_dict['day_type'] = 1
        if passer_record_dict['day_type'] == 0:  # 유급휴일: 기본근로, 휴일근로, 휴일연장
            passer_record_dict['remarks'] = '유급휴일: {:2.1f}H'.format(basic_hours + pass_record.overtime / 2)
            passer_record_dict['holiday'] = str(basic_hours)
            if pass_record.overtime > 0:
                passer_record_dict['overtime'] = ''
                passer_record_dict['ho'] = str(pass_record.overtime / 2)
        elif passer_record_dict['day_type'] == 1:  # 무급휴무일: 기본근로, 연장근로
            holiday = basic_hours
            if pass_record.overtime > 0:
                holiday += pass_record.overtime / 2
            passer_record_dict['remarks'] = '무급휴무일: {:2.1f}H'.format(holiday)
            passer_record_dict['overtime'] = str(holiday)
        elif passer_record_dict['day_type'] == 3:  # 무급휴일: 기본근로, 휴일근로, 휴일연장
            passer_record_dict['remarks'] = '무급휴일: {:2.1f}H'.format(basic_hours + pass_record.overtime / 2)
            passer_record_dict['holiday'] = str(basic_hours)
            if pass_record.overtime > 0:
                passer_record_dict['overtime'] = ''
                passer_record_dict['ho'] = str(pass_record.overtime / 2)
        logSend('   > 휴일근로: {} {} << 0: 유급휴일, 1: 주휴일(연장 근무)무급휴무일, 2: 소정근로일, 3: 휴일(휴일/연장 근무)무급휴일'.format(passer_record_dict['day_type'], passer_record_dict['remarks']))
    return


@cross_origin_read_allow
def my_work_records_v2(request):
    """
    근로 내용 : 근로자의 월별 근로 내역 응답
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
        work_id = '암호화된 업무 id'  # optional: only use /customer/staff_employee_working_v2
    response
        STATUS 204 # 일한 내용이 없어서 보내줄 데이터가 없다.
        STATUS 200
            {'message': '근태내역이 없습니다.', "work_dict": {}, "work_day_dict': {} }
            {
                "message": "정상적으로 처리되었습니다.",
                "work_dict": {
                    "ErKSUq7CYPAJMLzKN4Q5VA": {
                        "time_info": {
                            "time_type": 1,
                            "week_hours": "20",
                            "month_hours": null,
                            "working_days": [1, 2, 3, 4, 5],
                            "paid_day": 0,
                            "is_holiday_work": 1,
                            "work_time_list": [
                                {
                                    "t_begin": "08:30",
                                    "t_end": "17:30",
                                    "break_time_type": 1,
                                    "break_time_list": null,
                                    "break_time_total": "01:00",
                                    "break_hours": 1.0
                                }
                            ]
                        },
                        "name": "운영",
                        "type": "주간",
                        "work_name_type": "운영 (주간)",
                        "work_place_name": "서울지사",
                        "dt_begin": "2020/02/01",
                        "dt_end": "2020/02/29",
                        "dt_begin_full": "2020-02-01 00:00:00",
                        "dt_end_full": "2020-02-29 23:59:59",
                        "staff_name": "박종기",
                        "staff_pNo": "010-2557-3555",
                        "staff_email": "id@mail.com",
                        "e_begin": "2020/01/21",
                        "e_end": "2020/02/05",

                        "hours_basic": 56.0,      # 기본근로시간		basic_sum
                        "hours_break": 7.0,       # 휴게시간			break_sum
                        "hours_night": 0,         # 야간근로시간		night_sum
                        "hours_holiday": 8.0,     # 휴일근로시간		holiday_sum
                        "hours_overtime": 23.0,   # 연장근로시간		overtime_sum
                        "hours_ho": 2.5,          # 휴일/연장근로시간	ho_sum

                        "hours_week": 32.0,       # 주 소정근로시간 (근로시간의 20%)
                        "hours_month": 0,         # 원 소정근로시간

                        "days_working": 7,        # 근무 일수
                        "days_week": 0,           # 유급휴무 일수
                        "days_holiday": 2,        # 연차휴무 일수
                        "days_early_out": 0       # 조퇴 일수
                    },
                    ......
                },
                "work_day_dict": {
                    "03": {
                        "year_month_day": "2020-02-03",
                        "week": "월",
                        "action": 110,
                        "work_id": "ErKSUq7CYPAJMLzKN4Q5VA",
                        "begin": "08:29",
                        "end": "17:33",
                        "break": "1.0",
                        "basic": "9.0",
                        "night": "",
                        "overtime": "0.0",
                        "holiday": "",
                        "ho": "",
                        "remarks": "",
                        "is_accept": "1"
                    },
                    ......
                    "29": {
                        "year_month_day": "2020-02-29",
                        "week": "토",
                        "action": 0,
                        "work_id": "PinmZxCWGvvrcnj20cRanw",
                        "begin": "",
                        "end": "",
                        "break": "",
                        "basic": "",
                        "night": "",
                        "overtime": "",
                        "holiday": "",
                        "ho": "",
                        "remarks": "",
                        "is_accept": "1"
                    }
                }
            }
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'passer_id\' 가 없어요'}
            {'message':'ClientError: parameter \'dt\' 가 없어요'}
            {'message': 'passer_id: {} 없음. {}'.format(passer_id, str(e))}
            {'message': 'employee_id{} 없음. {}'.format(passer.employee_id, str(e))}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['passer_id_!', 'dt', 'work_id_!_@'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    passer_id = parameter_check['parameters']['passer_id']
    year_month = parameter_check['parameters']['dt']
    work_id = parameter_check['parameters']['work_id']
    # print('   > work_id: {}'.format(work_id))

    # 출입자(근로자) 정보 가져오기
    try:
        passer = Passer.objects.get(id=passer_id)
    except Exception as e:
        return status422(get_api(request), {'message': 'passer_id: {} 없음. {}'.format(passer_id, str(e))})
    # 출입자(근로자)의 근로 정보 가져오기
    try:
        employee = Employee.objects.get(id=passer.employee_id)
    except Exception as e:
        return status422(get_api(request), {'message': 'employee_id{} 없음. {}'.format(passer.employee_id, str(e))})
    if work_id is not None:
        # 업무 id 가 있을 경우: 그 업무의 근무 내역만 구한다.
        # /customer/staff_employee_working_v2 에서 사용할 때는 work_id 가 있다.
        # 월 근로내역에서 업무 찾기 (중복 업무 거르기)
        work_dict = get_work_dict([work_id])
        logSend('  > work_dict: {}'.format(work_dict.keys()))
        employee_works = Works(employee.get_works())
        # 출입자(근로자)의 월 근로 내역 가져오기
        pass_record_list = Pass_History.objects.filter(passer_id=passer.id, work_id=work_id,
                                                       year_month_day__contains=year_month).order_by('year_month_day')
        if len(pass_record_list) == 0:
            return REG_200_SUCCESS.to_json_response({'message': '근태내역이 없습니다.', 'arr_working': []})
    else:
        # 근로자가 한달 내에 여러개의 업무를 가지고 있을 때 처리
        # 출입자(근로자)의 월 근로 내역 가져오기
        pass_record_list = Pass_History.objects.filter(passer_id=passer.id,
                                                       year_month_day__contains=year_month).order_by('year_month_day')
        if len(pass_record_list) == 0:
            return REG_200_SUCCESS.to_json_response({'message': '근태내역이 없습니다.', 'arr_working': []})
        # 월 근로내역에서 업무 찾기 (중복 업무 거르기)
        work_id_dict = {}
        for pass_record in pass_record_list:
            if pass_record.work_id not in work_id_dict.keys():
                work_id_dict[pass_record.work_id] = id
        work_dict = get_work_dict(list(work_id_dict.keys()))
        logSend('  > work_dict: {}'.format(work_dict.keys()))
        employee_works = Works(employee.get_works())
    # 업무내역에서 복잡한 휴게시간 미리 계산하기
    set_break_time_of_work_time_info(work_dict)
    #
    # 근로자의 근로내역 생성: 근로자 id 를 key 로하는 dictionary
    #
    week_comment = ['월', '화', '수', '목', '금', '토', '일']
    passer_rec_dict = {}
    for pass_record in pass_record_list:
        # logSend('  > current: {} vs pass_record: {}'.format(current_work_id, pass_record.work_id))
        passer_record_dict = {
            'year_month_day': pass_record.year_month_day,
            'week': week_comment[str_to_datetime(pass_record.year_month_day).weekday()],
            'action': pass_record.action,
            'work_id': AES_ENCRYPT_BASE64(str(pass_record.work_id)),
            'begin': dt_str(pass_record.dt_in_verify, "%H:%M"),
            'end': dt_str(pass_record.dt_out_verify, "%H:%M"),
            'break': '',    # 휴게시간
            'basic': '',    # 기본근로
            'night': '',    # 야간근로
            'overtime': '',  # 연장근로
            'holiday': '',  # 휴일근무
            'ho': '',       # 휴일/연장
            'remarks': '',  #
            'is_accept': '1',  # 관리자에 의해 근태가 변경되지 않았다. (출/퇴근시간, 유급휴일, 연차휴가, 조기퇴근, 연장근무)
            'dt_accept': "" if pass_record.dt_accept is None else pass_record.dt_accept.strftime("%Y-%m-%d %H:%M:%S"),
            'day_type': pass_record.day_type,  # 근무일 구분 0: 유급휴일, 1: 주휴일(연장 근무), 2: 소정근로일, 3: 휴일(휴일/연장 근무)
            'passer_id': passer.id,
        }
        logSend('------------------ {}'.format(pass_record.year_month_day))
        process_pass_record(passer_record_dict, pass_record, work_dict)
        logSend('  >> {}: {}'.format(passer_record_dict['year_month_day'], passer_record_dict))
        passer_rec_dict[pass_record.year_month_day[8:10]] = passer_record_dict  # {'03': {...}, '04': {...}}
    month_work_dict = process_month_pass_record(passer_rec_dict, work_dict, employee_works)
    for day in passer_rec_dict.keys():
        passer_rec = passer_rec_dict[day]
        # logSend('>>> passer_record: {}'.format(passer_rec))
        passer_rec['passer_id'] = AES_ENCRYPT_BASE64(str(passer_rec['passer_id']))
    return REG_200_SUCCESS.to_json_response({'work_dict': month_work_dict, 'work_day_dict': passer_rec_dict})


def process_month_pass_record(passer_rec_dict, work_dict, employee_works):
    week_comment = ['월', '화', '수', '목', '금', '토', '일']
    month_work_dict = {}
    work_id = ''  		# 현재 업무 id
    hours_basic = 0       	# 기본근로시간 합계
    hours_break = 0       	# 휴게시간 합계
    hours_night = 0       	# 야간근로시간 합계
    hours_overtime = 0    	# 연장근로시간 합계
    hours_holiday = 0     	# 유급휴일근로시간 합계
    hours_ho = 0          	# 휴일/연장근로시간 합계
    hours_week = 0   		# 주 소정근로시간
    hours_month = 0         # 월 소정근로시간

    days_working = 0  	# 근무일수
    days_week = 0		# 유급휴일 횟수
    days_holiday = 0  	# 연차휴무 횟수
    days_early_out = 0  # 조기퇴근 횟수

    week_dict = {}      # 소정근로 시간을 처리하기 위해 유급휴일 전까지 근로 내역을 저장

    logSend('>>> {}'.format(passer_rec_dict.keys()))
    logSend('>>> {}'.format(work_dict.keys()))
    is_first_day = True     # 이번달의 첫날이면 그전 10일의 근로내역을 가져와서 week_dict 를 넣기 위한 flag

    first_day_rec = passer_rec_dict[list(passer_rec_dict.keys())[0]]
    work_id_db = AES_DECRYPT_BASE64(first_day_rec['work_id'])
    logSend('  > paid_day: {}'.format(work_dict[work_id_db]['time_info']['paid_day']))
    if work_dict[work_id_db]['time_info']['paid_day'] == -1:
        # 유급휴일이 수동지정일 경우
        dt_paid_day = ''
        for day in passer_rec_dict.keys():
            day_dict = passer_rec_dict[day]
            if day_dict['day_type'] == 0:  # 0: 유급휴일, 1: 휴무일(연장 근무), 2: 소정근로일, 3: 휴일(휴일/연장 근무)
                dt_paid_day = str_to_datetime(day_dict['year_month_day'])
                break
        # 첫번째 유급휴일 날
        logSend('  > dt_paid_day: {}'.format(dt_paid_day))
    else:
        dt_paid_day = str_to_datetime(first_day_rec['year_month_day'][0:7])
        for i in range(1, 8):
            week_index = dt_paid_day.weekday()
            logSend('   > {} {} {} {}'.format(dt_paid_day, week_index, week_comment[week_index], str((week_index + 1) % 7)))
            if work_dict[work_id_db]['time_info']['paid_day'] == (week_index + 1) % 7:
                break
            dt_paid_day = dt_paid_day + datetime.timedelta(days=1)
    logSend('   > dt_paid_day: {} {}'.format(dt_paid_day, week_comment[dt_paid_day.weekday()]))
    if dt_paid_day != '':
        # 1일이면 그 전 1주일 데이터를 week_dict 에 넣는다.
        # 일주일전 근로내역을 가져온다.
        dt_current = dt_paid_day
        before_days = []
        for i in range(1, 8):
            dt_before = dt_current - datetime.timedelta(days=i)
            before_days.append(dt_str(dt_before, "%Y-%m-%d"))
        logSend('   > before 7 days: {}'.format(before_days))
        before_pass_record_list = Pass_History.objects.filter(passer_id=first_day_rec['passer_id'], work_id=work_id_db,
                                                              year_month_day__in=before_days).order_by('year_month_day')
        for pass_record in before_pass_record_list:
            logSend(
                '  >> pass_record: {} {} {}'.format(pass_record.year_month_day, pass_record.work_id, pass_record.passer_id))
            is_working = False
            if pass_record.overtime == 0:
                # 연장근무가 0 이면 근무가 없을 수도 있다.
                if (pass_record.dt_in_verify is not None) or (pass_record.dt_out_verify is not None):
                    # 출퇴근중 하나가 있으면 근무가 있었다.
                    is_working = True
            else:
                # 연장근무가 0이 아니면 월차, 조기퇴근, 연장근무를 했으니까 근무한 것이다.
                is_working = True
            if is_working:
                week_dict[(str_to_datetime(pass_record.year_month_day).weekday() + 1) % 7] = {
                    'week': week_comment[str_to_datetime(pass_record.year_month_day).weekday()],
                    'day_type': pass_record.day_type,
                    'is_working': is_working,
                }
        logSend('  >> week_dict: {}'.format(week_dict))

    for day in passer_rec_dict.keys():
        day_dict = passer_rec_dict[day]
        if work_id == '':
            # 아직 업무가 정해지지 않았으면
            work_id = day_dict['work_id']
            work_id_db = AES_DECRYPT_BASE64(work_id)
            month_work_dict[work_id] = copy.deepcopy(work_dict[work_id_db])
            # work_time_list = month_work_dict[current_work_id]['work_time_list']
            logSend('   {}, {}'.format(work_id_db, str(work_id_db)))
            current_employee_work = employee_works.find_work_include_date(work_id_db, str_to_datetime(day_dict['year_month_day']))
            logSend(' >> current_employee_work: {}'.format(current_employee_work))
            logSend('  > month_work_dict[{}]: {}'.format(work_id_db, month_work_dict[work_id]))
            if current_employee_work is None:
                # 근로자의 업무 목록(employee.get_works)에서 업무가 없는 경우 (발생하면 안되는 경우)
                # 이 업무의 근로 시작일: 업무의 시작일 > 근태요구 첫날
                # month_work_dict[encryted_work_id]['e_begin'] = month_work_dict[encryted_work_id]['dt_begin']
                month_work_dict[work_id]['e_begin'] = str_to_datetime(day_dict['year_month_day'])
                # 이 업무의 근로 종료일: 업무의 종료일 > 업무의 마지막 날
                # month_work_dict[encryted_work_id]['e_end'] = month_work_dict[encryted_work_id]['dt_end']
                month_work_dict[work_id]['e_end'] = ''  # 업무가 바뀔 때 넣어야 한다.
            else:
                # 이 업무의 근로 시작일
                month_work_dict[work_id]['e_begin'] = current_employee_work['begin']
                # 이 업무의 근로 종료일
                month_work_dict[work_id]['e_end'] = current_employee_work['end']
        elif work_id != day_dict['work_id']:
            # logSend(' >> {} {}'.format(current_work_id, pass_record.work_id))
            # 업무가 바뀌었다.
            # 계산된 값을 저장하고 설정 값은 초기
            month_work_dict[work_id]['hours_break'] = hours_break
            month_work_dict[work_id]['hours_basic'] = hours_basic
            month_work_dict[work_id]['hours_night'] = hours_night
            month_work_dict[work_id]['hours_overtime'] = hours_overtime
            month_work_dict[work_id]['hours_holiday'] = hours_holiday
            month_work_dict[work_id]['hours_ho'] = hours_ho
            month_work_dict[work_id]['hours_week'] = hours_week

            month_work_dict[work_id]['days_working'] = days_working
            month_work_dict[work_id]['days_holiday'] = days_holiday
            month_work_dict[work_id]['days_early_out'] = days_early_out

            if month_work_dict[work_id]['e_end'] == '':  # 업무 종료 날짜를 알수 없는 경우 처리
                month_work_dict[work_id]['e_end'] = day_dict['year_month_day']
            # 업무가 바뀌어 전 업무의 합계값을 저장한다.

            work_id = day_dict['work_id']
            work_id_db = AES_DECRYPT_BASE64(work_id)
            month_work_dict[work_id] = copy.deepcopy(work_dict[work_id_db])
            current_employee_work = employee_works.find_work_include_date(work_id_db, str_to_datetime(day_dict['year_month_day']))
            if current_employee_work is None:
                month_work_dict[work_id]['e_begin'] = day_dict['year_month_day']
                month_work_dict[work_id]['e_end'] = ''
            else:
                month_work_dict[work_id]['e_begin'] = current_employee_work['begin']
                month_work_dict[work_id]['e_end'] = current_employee_work['end']
            hours_break = 0  # 휴게시간 합계
            hours_basic = 0  # 기본근로시간 합계
            hours_night = 0  # 야간근로시간 합계
            hours_overtime = 0  # 연장근로시간 합계
            hours_holiday = 0  # 유급휴일근로시간 합계
            hours_ho = 0  # 휴일/연장근로시간 합계
            hours_week = 0  # 주 소정근로시간

            days_working = 0           # 근무일수
            days_holiday = 0    # 연차휴무 횟수
            days_early_out = 0          # 조기퇴근 횟수

        #
        # 소정근로 시간 추가
        #
        if dt_paid_day != '':
            # 유급휴일이 수동지정일 경우 유급휴일을 아직 지정하지 않은 경우
            # 소정근로시간 추가를 계산하지 않는다.
            if dt_paid_day <= str_to_datetime(day_dict['year_month_day']):
                # 유급 휴일이거나 유급휴일이 지났으면
                # 소정근로에 결근이 없었는지 확인하고
                # 소정근로시간을 추가하고 week_dict 를 초기화한다.
                logSend('  >> week_dict: {}'.format(week_dict))
                is_all_week = True
                for week_index in month_work_dict[work_id]['time_info']['working_days']:
                    # 업무의 소정근로일에
                    if week_index not in week_dict.keys():
                        # 근무를 하지 않았으면
                        is_all_week = False
                        break
                if is_all_week:  # 소정근로시간을 채웠다.
                    hours_week += int(month_work_dict[work_id]['time_info']['week_hours']) * .2  # 주 소정근로시간
                    logSend('  > 주 소정근로시간: {}'.format(hours_week))
                dt_paid_day = dt_paid_day + datetime.timedelta(days=7)
                week_dict = {}
            # logSend(' >> day_dict: {} {}'.format(day_dict['year_month_day'], day_dict['week']))
            is_working = False
            if day_dict['overtime'] == 0:
                # 연장근무가 0 이면 근무가 없을 수도 있다.
                if (day_dict['dt_in_verify'] is not None) or (day_dict['dt_out_verify'] is not None):
                    # 출퇴근중 하나가 있으면 근무가 있었다.
                    is_working = True
            else:
                # 연장근무가 0이 아니면 월차, 조기퇴근, 연장근무를 했으니까 근무한 것이다.
                is_working = True
            if is_working:
                week_dict[(str_to_datetime(day_dict['year_month_day']).weekday() + 1) % 7] = {
                    'week': week_comment[str_to_datetime(day_dict['year_month_day']).weekday()],
                    'day_type': day_dict['day_type'],
                    'is_working': is_working,
                }
            # logSend('  >> week_dict: {}'.format(week_dict))

        if len(day_dict['basic']) > 0:
            hours_basic += float(day_dict['basic'])
            days_working += 1
        if len(day_dict['break']) > 0:
            hours_break += float(day_dict['break'])
        if len(day_dict['overtime']) > 0:
            overtime = float(day_dict['overtime'])
            if overtime > 0:
                hours_overtime += overtime
            elif overtime < -1.9:
                days_holiday += 1   # 연차 휴무 횟수 증가
            elif overtime < -0.9:
                days_early_out += 1         # 조기퇴근 횟수 증가
        if len(day_dict['night']) > 0:
            hours_night += float(day_dict['night'])
        if len(day_dict['holiday']) > 0:
            hours_holiday += float(day_dict['holiday'])
        if len(day_dict['ho']) > 0:
            hours_ho += float(day_dict['ho'])

    month_work_dict[work_id]['hours_break'] = hours_break
    month_work_dict[work_id]['hours_basic'] = hours_basic
    month_work_dict[work_id]['hours_night'] = hours_night
    month_work_dict[work_id]['hours_overtime'] = hours_overtime
    month_work_dict[work_id]['hours_holiday'] = hours_holiday
    month_work_dict[work_id]['hours_ho'] = hours_ho
    month_work_dict[work_id]['hours_week'] = hours_week
    month_work_dict[work_id]['hours_month'] = hours_month

    month_work_dict[work_id]['days_working'] = days_working
    month_work_dict[work_id]['days_week'] = days_week
    month_work_dict[work_id]['days_holiday'] = days_holiday
    month_work_dict[work_id]['days_early_out'] = days_early_out

    if month_work_dict[work_id]['e_end'] == '':  # 업무 종료 날짜를 알수 없는 경우 처리
        month_work_dict[work_id]['e_end'] = day_dict['year_month_day']

    return month_work_dict


@cross_origin_read_allow
def alert_recruiting(request):
    """
    채용 알림 : 근로자에게 채용 내용을 알림
        1. 채용 대상자 선정: 구인 ON 인 사람
        2. 알림 DB 설정
        3. push 알림
    http://0.0.0.0:8000/employee/alert_recruiting?
    POST
        work_id: 고객 서버의 업무 id   # 암호화 된 상태
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
            {'message':'ClientError: parameter \'work_id\' 가 없어요'}
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    parameter_check = is_parameter_ok(rqst, ['work_id'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    work_id = parameter_check['parameters']['work_id']

    work_dict = get_work_dict([work_id])
    if len(work_dict.keys()) == 0:
        return status422(get_api(request), {'message': '해당 업무(customer_work_id: {}) 없음. {}'.format(work_id, str(e))})
    work = work_dict([work_id])
    # try:
    #     work = Work.objects.get(customer_work_id=work_id)
    # except Exception as e:
    #     return status422(get_api(request), {'message': '해당 업무(customer_work_id: {}) 없음. {}'.format(work_id, str(e))})
    recruiting_passer_list = Passer.objects.filter(is_recruiting=True)
    #
    # 구직 등록자 중에서 업무 시작일이 가능한 근로자 검색
    #
    push_list = []
    push_phone_list = []
    for passer in recruiting_passer_list:
        try:
            employee = Employee.objects.get(id=passer.employee_id)
        except Exception as e:
            logError('   passer: {} 의 employee: {} 없음'.format(passer.id, passer.employee_id))
            continue
        works = Works(employee.get_works())
        work_term = { 'begin': work.begin, 'end': work.end }
        if not works.is_overlap(work_term):
            # 근로자의 업무 기간이 겹치지 않는 경우 채용정보 푸시, 알림 등록
            dt_work_begin = str_to_dt(work.begin)
            new_notification = Notification_Work(
                work_id=work_id,
                # customer_work_id=customer_work_id,
                employee_id=employee.id,
                employee_pNo=passer.pNo,
                dt_answer_deadline=dt_work_begin + datetime.timedelta(days= -2),
                dt_begin=dt_work_begin,
                dt_end=str_to_dt(work['dt_end']),
                # 이하 시스템 관리용
                work_place_name=work['work_place_name'],
                work_name_type=work['work_name_type'],
                # is_x=False,  # default
                # dt_reg=datetime.datetime.now(),  # default
            )
            new_notification.save()
            push_list.append({'id': passer.id, 'token': passer.push_token, 'pType': passer.pType})
            push_phone_list.append(passer.pNo)
    logSend('push_list: {}'.format(push_phone_list))
    if len(push_list) > 0:
        push_contents = {
            'target_list': push_list,
            'func': 'user',
            'isSound': True,
            'badge': 1,
            'contents': {'title': '(채용정보) {}: {}'.format(work['work_place_name'], work['work_name_type']),
                         'subtitle': '{} ~ {}'.format(work['dt_begin'], work['dt_end']),
                         'body': {'action': 'NewWork',  # 'NewRecruiting',
                                  'dt_begin': work['dt_begin'],
                                  'dt_end': work['dt_end']
                                  }
                         }
        }
        send_push(push_contents)

    return REG_200_SUCCESS.to_json_response({'phone_list': push_phone_list})


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
        pNo: 010 3333 5555  # optional
        name: 이름            # optional
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
    # logSend('   >> 1')
    if 'pNo' in rqst and len(rqst['pNo']) > 9:
        pNo = no_only_phone_no(rqst['pNo'])
        passer_list = Passer.objects.filter(pNo=pNo)
        if len(passer_list) == 0:
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '{} not found'.format(phone_format(pNo))})
    # logSend('   >> 2')
    if 'name' in rqst and len(rqst['name']) > 1:
        name = rqst['name']
        logSend('   > {}'.format(name))
        employee_list = Employee.objects.filter(name__contains=name)
        if len(employee_list) == 0:
            return REG_416_RANGE_NOT_SATISFIABLE.to_json_response(
                {'message': '{} not found'.format(phone_format(name))})
        passer_list = Passer.objects.filter(employee_id__in=[employee.id for employee in employee_list])
    # logSend('   >> 3')
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
            work_dict = get_work_dict([employee_work['id'] for employee_work in employee_works.data])
            works = []
            for employee_work in employee_works.data:
                work = work_dict[str(employee_work['id'])]
                work['begin'] = employee_work['begin']
                work['end'] = employee_work['end']
                work['id'] = str(employee_work['id'])
                works.append(work)
            passer_dict['works'] = works
            pass_history_list = Pass_History.objects.filter(passer_id=passer.id).values('id', 'year_month_day', 'passer_id', 'work_id', 'dt_in',
                                                                                        'dt_in_verify', 'dt_out', 'dt_out_verify',
                                                                                        'overtime')
            pass_histoies = [{x: pass_history[x] for x in pass_history.keys()} for pass_history in pass_history_list]
            logError(' {}'.format(pass_histoies))
            if len(pass_histoies) > 0:
                sorted(pass_histoies, key=itemgetter('year_month_day'))
                records = [pass_histoies[-1]]
                if len(pass_histoies) > 1:
                    records.append(pass_histoies[-2])
                passer_dict['records'] = records
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
    [[ 운영 ]] 근로시간에 휴게시간 기능이 추가되면서 근무시간(working_time)과 휴게 시간(rest_time) 분리 작업을 한다.

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

    # 휴게시간 update
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

    work_dict = get_work_dict([x.work_id for x in io_null_list])
    passer_dict = passer_dict_from_db([x.passer_id for x in io_null_list])

    result = []
    delete_history = []
    for io_null in io_null_list:
        if io_null.passer_id not in passer_dict.keys():
            logSend('  Not exist passer_id: {}'.format(io_null.passer_id))
            delete_history.append({'id': io_null.id,
                                   'year_month_day': io_null.year_month_day,
                                   'work_id': io_null.work_id,
                                   'work_place_name': work_dict[str(io_null.work_id)]['work_place_name'],
                                   'work_name_type': work_dict[str(io_null.work_id)]['work_name_type'],
                                   'begin': work_dict[str(io_null.work_id)]['dt_begin'],
                                   'end': work_dict[str(io_null.work_id)]['dt_end'],
                                   })
            io_null.delete()
            continue
        io_null_employee = {
            'id': io_null.id,
            'year_month_day': io_null.year_month_day,
            'work_id': io_null.work_id,
            'work_place_name': work_dict[str(io_null.work_id)]['work_place_name'],
            'work_name_type': work_dict[str(io_null.work_id)]['work_name_type'],
            'begin': work_dict[str(io_null.work_id)]['dt_begin'],
            'end': work_dict[str(io_null.work_id)]['dt_end'],
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


@cross_origin_read_allow
def tk_patch(request):
    """
    [[ 운영 ]] patch 해야할 때 사용
    http://0.0.0.0:8000/employee/tk_patch

    POST
    response
        STATUS 200
          "message": "정상적으로 처리되었습니다.",
        STATUS 403
            {'message':'저리가!!!'}
    """
    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        logError(get_api(request), ' 허가되지 않은 ip: {}'.format(get_client_ip(request)))
        return REG_403_FORBIDDEN.to_json_response({'message': '저리가!!!'})

    # if request.method == 'POST':
    #     rqst = json.loads(request.body.decode("utf-8"))
    # else:
    #     rqst = request.GET

    # passer = Passer.objects.get(id=130)
    # target_passer = Passer.objects.get(id=262)
    # copy_table(passer, target_passer, ['pType', 'push_token', 'notification_id', 'cn', 'user_agent'])
    # target_passer.save()
    #
    # logSend('  {} {}'.format(passer.employee_id, target_passer.employee_id))
    # s_employee = Employee.objects.get(id=passer.employee_id)
    # t_employee = Employee.objects.get(id=target_passer.employee_id)
    # copy_table(s_employee, t_employee, ['bank_account', 'bank', 'work_end_alarm', 'work_start', 'work_start_alarm', 'working_time', 'rest_time', 'works', 'dt_reg'])
    # works = t_employee.get_works()
    # works[0]['id'] = 17
    # logSend(works)
    # t_employee.set_works(works)
    # t_employee.save()
    #
    # record_list = Pass_History.objects.filter(passer_id=130)
    # for record in record_list:
    #     print(record.year_month_day)
    #     new_record = Pass_History(
    #         year_month_day=record.year_month_day,
    #         passer_id=262,
    #         work_id=17,
    #         dt_in=record.dt_in,
    #         dt_in_em=record.dt_in_em,
    #         dt_in_verify=record.dt_in_verify,
    #         in_staff_id=record.in_staff_id,
    #         dt_out=record.dt_out,
    #         dt_out_em=record.dt_out_em,
    #         dt_out_verify=record.dt_out_verify,
    #         out_staff_id=record.out_staff_id,
    #         overtime=record.overtime,
    #         overtime_staff_id=record.overtime_staff_id,
    #         x=record.x,
    #         y=record.y,
    #     ).save()
    # apns_test(request)
    return REG_200_SUCCESS.to_json_response()


def copy_table(source, target, key_list):
    for key in source.__dict__.keys():
        if key in key_list:
            target.__dict__[key] = source.__dict__[key]
            logSend('   {}: {}'.format(key, target.__dict__[key]))
    return


def apns_test(request):
    # if request.method == 'POST':
    #     rqst = json.loads(request.body.decode("utf-8"))
    #     #_userCode = rqst['uc']
    #     token = rqst['t']
    # elif settings.IS_COVER_GET :
    #     logSend('>>> :-(')
    #     return HttpResponse(":-(")
    # else :
    #     #rqst = json.loads(request.GET)
    #     #logSend(`rqst['uc']` + ' ' + `rqst['array']`)
    #     #_userCode = rqst['uc']
    #     token = request.GET['t']

    # apns = APNs(use_sandbox=True, cert_file='cert.pem', key_file='key.pem')
    # apns = APNs(use_sandbox=True, cert_file=settings.APNS_PEM_EMPLOYEE_FILE)
    # # Send a notification
    # token_hex = '5503313048040d911e7dc8979ddc640499fd3e8c2b61054641caf4893ed9a12a'
    # payload = Payload(alert="Hello World!", sound="default", badge=1)
    # apns.gateway_server.send_notification(token_hex, payload)
    #
    # # Send multiple notifications in a single transmission
    # frame = Frame()
    # identifier = 1
    # expiry = time.time() + 3600
    # priority = 10
    # frame.add_item('5503313048040d911e7dc8979ddc640499fd3e8c2b61054641caf4893ed9a12a', payload, identifier, expiry, priority)
    # apns.gateway_server.send_notification_multiple(frame)

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['pNo'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    pNo = parameter_check['parameters']['pNo']

    try:
        passer = Passer.objects.get(pNo=pNo)
    except Exception as e:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '전환번호({}) 로 찾을 수 없다. <{}>'.format(pNo, e)})

    if passer.push_token == 'Token_did_not_registration':
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': 'did not registration token({})'.format(passer.push_token)})
    push_contents = {
        'target_list': [{'id': passer.id, 'token': passer.push_token, 'pType': passer.pType},
                        # {'id': 262, 'token': '84653d4521cd224c73b21b9f5e8b9646150c94dc34b033c15b8178e2b53c0213', 'pType': 10}
                        ],
        'func': 'user',
        'isSound': True,
        'badge': 1,
        # 'contents': None,
        'contents': {'title': '업무 요청',
                     'subtitle': 'SK 케미칼: 동력_EGB(3교대)',
                     'body': {
                         'action': 'NewWork',
                         'current': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                     }
    }
    response = notification(push_contents)

    return REG_200_SUCCESS.to_json_response({'response': json.dumps(response)})


@cross_origin_read_allow
def test_beacon_list(request):
    """
    비콘 값 업로드: 스마트폰에서 테스트용으로 수집된 비콘 값들을 서버로 보낸다.
        http://0.0.0.0:8000/employee/test_beacon_list
    POST : json
        { 'beacon_list': [
            {
            'passer_id' : '앱 등록시에 부여받은 암호화된 출입자 id',
            'dt' : '2018-01-21 08:25:30.333',   # 주) 초 밑 단위 있음.
            'major': 11001,                     # 11 (지역) 001(사업장)
            'minor': 11001,                     # 11 (출입) 001(일련번호)
            'rssi': -65,
            'x': latitude (optional),
            'y': longitude (optional),
            },
            ......
            ]
        }
    response
        STATUS 200
            {'message': 'out 인데 어제 오늘 in 기록이 없다.'}
            {'message': 'in 으로 부터 12 시간이 지나서 out 을 무시한다.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'beacon_list\' 가 없어요'}
    log Error
            logError(get_api(request), ' 잘못된 비콘 양식: {} - {}'.format(e, beacon))
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['beacon_list'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    beacon_list = parameter_check['parameters']['beacon_list']
    for beacon in beacon_list:
        try:
            passer_id = AES_DECRYPT_BASE64(beacon['passer_id'])
            # logSend('  ?? passer_id: ({})'.format(passer_id))
            if passer_id == '__error':
                logError(get_api(request), ' ERROR: passer_id: {} - {}'.format(passer_id, beacon))
                continue
            new_beacon_record = Beacon_Record(
                passer_id=passer_id,
                dt_begin=datetime.datetime.strptime(beacon['dt'], "%Y-%m-%d %H:%M:%S.%f"),
                major=beacon['major'],
                minor=beacon['minor'],
                rssi=beacon['rssi'],
                x=beacon['x'],
                y=beacon['y'],
                is_test=True,
            )
            new_beacon_record.save()
            # logSend('  < {} {} {}'.format(new_beacon_record.passer_id, new_beacon_record.dt_begin, new_beacon_record.rssi))
        except Exception as err:
            logError(get_api(request), ' 잘못된 비콘 양식: {} - {}'.format(err, beacon))
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def get_test_beacon_list(request):
    """
    시험 결과 요청: 스마트폰에서 테스트용으로 수집된 비콘 값들을 가져온다.
        http://0.0.0.0:8000/employee/get_test_beacon_list?user=thinking
    POST : json
        'user': 'thinking'
    response
        STATUS 200
            { 'beacon_list':
                [
                    {
                        'passer_id': passer_id,
                        'phone_no': 010-3333-5555,
                        'beacon_list':
                            [
                                {
                                    'major': 11001,
                                    'minor': 11002,
                                    'dt': 2019-10-14 05:36:33.555,
                                    'rssi': -65,
                                    'x': 35.3333,
                                    'y': 126.3333,
                                },
                                ...
                            ]
                    },
                    ...
                ]
            }
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'user\' 가 없어요'}
            {'message': '사용 권한이 없습니다.'}
    log Error
            logError(get_api(request), ' 잘못된 비콘 양식: {} - {}'.format(e, beacon))
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['user'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    user = parameter_check['parameters']['user']
    if user != 'thinking':
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '사용 권한이 없습니다.'})

    employee_list = Employee.objects.all()
    employee_name = {employee.id: employee.name for employee in employee_list}

    passer_list = Passer.objects.all()
    passer_dict = {passer.id: passer for passer in passer_list}

    beacon_list = Beacon_Record.objects.filter(is_test=True).order_by('passer_id', 'dt_begin')
    passer_id_dict = {}
    for beacon in beacon_list:
        if beacon.passer_id not in passer_id_dict.keys():
            passer_id_dict[beacon.passer_id] = 'pNo'
    # logSend('  >> passer: {}'.format(passer_id_dict))

    beacon_dict = {}
    for beacon in beacon_list:
        # logSend('  ^ {} {}'.format(beacon.passer_id, beacon_dict))
        if beacon.passer_id not in beacon_dict:
            beacon_dict[beacon.passer_id] = {'beacon_list': []}
        get_beacon = {
            'major': beacon.major,
            'minor': beacon.minor,
            'dt': dt_str(beacon.dt_begin, "%Y-%m-%d %H:%M:%S.%f")[:-3],
            'rssi': beacon.rssi,
            'x': beacon.x,
            'y': beacon.y,
        }
        beacon_dict[beacon.passer_id]['beacon_list'].append(get_beacon)
    get_beacon_list = [{'passer_id': passer_id,
                        'name': employee_name[passer_dict[passer_id].employee_id],
                        'phone_no': phone_format(passer_dict[passer_id].pNo),
                        'beacon_list': beacon_dict[passer_id]['beacon_list'],
                        } for passer_id in beacon_dict.keys()
    ]
    # logSend('  >> beacon: {}'.format(beacon_dict))
    return REG_200_SUCCESS.to_json_response({'beacon_list': get_beacon_list})


@cross_origin_read_allow
def del_test_beacon_list(request):
    """
    테스트 비콘 값 삭제: 새로 테스트하기 위해 시험 데이터를 삭제한다.
        http://0.0.0.0:8000/employee/get_test_beacon_list?user=thinking
    POST : json
        'user': 'thinking'
    response
        STATUS 200
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'user\' 가 없어요'}
            {'message': '사용 권한이 없습니다.'}
    log Error
            logError(get_api(request), ' 잘못된 비콘 양식: {} - {}'.format(e, beacon))
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['user'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    user = parameter_check['parameters']['user']
    if user != 'thinking':
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '사용 권한이 없습니다.'})

    Beacon_Record.objects.all().delete()
    Pass.objects.all().delete()
    # beacon_list = Beacon_Record.objects.filter(is_test=True)
    # for beacon in beacon_list:
    #     beacon.delete()

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def list_employee(request):
    """
    카메라를 제어하기 위한 근로자 리스트(모니터링 앱)
        http://0.0.0.0:8000/employee/list_employee
    POST : json
    response
        STATUS 200
            {
                list_employee: [
                    {
                        'passer_id': passer.id,
                        'name': dict_employee[passer.employee_id],
                        'pNo': passer.pNo,
                        'is_camera_stop': passer.is_camera_stop
                    },
                    ...
                ]
            }
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'dt\' 가 없어요'}
    log Error
            logError(get_api(request), ' 잘못된 비콘 양식: {} - {}'.format(e, beacon))
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    list_passer = Passer.objects.all()
    list_employee = Employee.objects.all()
    dict_employee = {employee.id: employee.name for employee in list_employee}
    logSend('  {}'.format(dict_employee))
    list_passer_json = []
    for passer in list_passer:
        try:
            passer_dict = {
                'passer_id': passer.id,
                'name': dict_employee[passer.employee_id],
                'pNo': passer.pNo,
                'is_camera_stop': passer.is_camera_stop
            }
            list_passer_json.append(passer_dict)
        except Exception as e:
            logSend('  {} - {}'.format(passer.employee_id, passer.pNo))

    # list_passer_json = [
    #     {
    #         'passer_id': passer.id,
    #         'name': dict_employee[passer.employee_id],
    #         'pNo': passer.pNo,
    #         'is_camera_stop': passer.is_camera_stop
    #     } for passer in list_passer
    # ]

    return REG_200_SUCCESS.to_json_response({'list_employee': list_passer_json})


@cross_origin_read_allow
def update_camera(request):
    """
    카메라 상태 변경: 지정된 근로자의 앱을 통해 카메라 사용을 금지 시킨다.
        http://0.0.0.0:8000/employee/update_camera?passer_id=307&is_stop=1
    POST : json
        passer_id: 2    # 근로자 id - 암호화 X
        is_stop: 1      # 0: 카메라 작동, 1: 카메라 스톱
    response
        STATUS 200
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'passer_id\' 가 없어요'}
            {'message':'ClientError: parameter \'is_accept\' 가 없어요'}
    log Error
            logError(get_api(request), ' 잘못된 비콘 양식: {} - {}'.format(e, beacon))
    PUSH
        notification: {
            'title': '카메라 {}'.format(stop_tag), # 잠긍 / 해제
            'body': stop_message, # '보안상 이유로 카메라가 사용할 수 없게됩니다.' / '보안지역을 벗어났기 때문에 카메라 잠금을 해제하였습니다.'
            }
        data: {
            'action': 'camera_status',
            'is_stop': is_stop,
            'message': stop_message,
            }
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['passer_id', 'is_stop'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    passer_id = parameter_check['parameters']['passer_id']
    is_stop = parameter_check['parameters']['is_stop']

    try:
        passer = Passer.objects.get(id=passer_id)
    except Exception as e:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': ' 해당 근로자({})가 없습니다.'.format(passer_id)})
    passer.is_camera_stop = is_stop
    passer.save()
    if int(passer.is_camera_stop) == 1:
        stop_tag = '잠금'
        stop_message = '보안상 이유로 카메라가 사용할 수 없게됩니다.'
    else:
        stop_tag = '해제'
        stop_message = '보안지역을 벗어났기 때문에 카메라 잠금을 해제하였습니다.'
    # push - 알림 화면이 없이 실행가능한 형태
    push_contents = {
        'target_list': [{'id': passer.id, 'token': passer.push_token, 'pType': passer.pType}],
        'func': 'user',
        'isSound': True,
        'badge': 0,
        'contents': {'body': {'action': 'camera_status',
                              'is_stop': is_stop,
                              'message': stop_message,
                              }
                     }
    }
    # push - 알림 화면이 있지만 실행되지 않는 형태
    if passer.pType == 10:  # 아이폰 일 때는 넣어준다.
        push_contents['contents']['title'] = '카메라 {}'.format(stop_tag)
        push_contents['contents']['subtitle'] = stop_message
    # push_contents = {
    #     'target_list': [{'id': passer.id, 'token': passer.push_token, 'pType': passer.pType}],
    #     'func': 'user',
    #     'isSound': True,
    #     'badge': 0,
    #     'contents': {'title': '카메라 {}'.format(stop_tag),
    #                  'subtitle': stop_message,
    #                  'body': {'action': 'camera_status',
    #                           'is_stop': is_stop,
    #                           'message': stop_message,
    #                           }
    #                  }
    # }
    response = notification(push_contents)

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def push_work(request):
    """
    새 업무 알림 발송: 구직 신청 근로자에게 새 업무 알림 발송
        http://0.0.0.0:8000/employee/push_work?passer_id=307
    POST : json
        passer_id: 출입 신청 id
    response
        STATUS 200
        STATUS 422 # 개발자 수정사항
            {'message': ' 해당 신청자({})가 없습니다.'.format(passer_id)}
    log Error
            logError(get_api(request), ' 잘못된 비콘 양식: {} - {}'.format(e, beacon))
    PUSH
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['passer_id'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    passer_id = parameter_check['parameters']['passer_id']

    try:
        passer = Passer.objects.get(id=passer_id)
    except Exception as e:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': ' 해당 신청자({})가 없습니다.'.format(passer_id)})
    # push
    push_contents = {
        'target_list': [{'id': passer.id, 'token': passer.push_token, 'pType': passer.pType}],
        'func': 'user',
        'isSound': True,
        'badge': 1,
        # 'contents': None,
        'contents': {'title': '대덕테크 서버운영(3교대)',
                     'subtitle': '11/11~12:31 20~45 남성 월급제',
                     'body': {'work_place_name': '대덕테크',
                              'work_type': '서버운영(3교대)',
                              'ymd_begin': '2019/11/11',
                              'ymd_end': '2019/11/11',
                              'age': '20~45',
                              'sex': 'Man',
                              'work_time': '07:00 15:00 23:00',
                              'pay_type': '월급제',
                              }
                     }
    }
    response = notification(push_contents)

    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def reset_passer(request):
    """
    시험용: 근로자를 새로 등록할 수 있도록 정보를 삭제한다.
    - 상용서버에서는 사용할 수 없다.
        http://0.0.0.0:8000/employee/reset_passer?pNo=01025573555
    GET
        pNo: 전화번호  # 삭제할 근로자의 전화번호
    response
        STATUS 416
            {'message': '개발상태에서만 사용할 수 있습니다.'}
        STATUS 200
            {'message': '출입자가 이미 삭제 되었습니다.'}
            {'message': '근로자가 이미 삭제 되었습니다.'}
        STATUS 422 # 개발자 수정사항
    log Error
            logError(get_api(request), ' 잘못된 비콘 양식: {} - {}'.format(e, beacon))
    """
    if not settings.DEBUG:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '개발상태에서만 사용할 수 있습니다.'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['pNo'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    pNo = parameter_check['parameters']['pNo']

    passer_infor = {}
    # 기존 업무 알림 모두 삭제
    notification_list = Notification_Work.objects.filter(employee_pNo=pNo)
    if len(notification_list) > 0:
        for notification in notification_list:
            logSend('>>> delete notification work: {}'.format(notification.id))
            notification.delete()

    # 출입자 정보 삭제
    employee_id = -1
    try:
        passer = Passer.objects.get(pNo=pNo)
        passer_infor['pNo'] = passer.pNo
        passer_infor['pType'] = passer.pType
        passer_infor['app_version'] = passer.app_version
        passer.delete()
        employee_id = passer.employee_id
    except Exception as e:
        passer_infor['passer_delete'] = '>>> 출입자가 이미 삭제되었다.'
    logSend('>>> {}'.format(passer_infor))

    # 근로자 정보 삭제
    if employee_id != -1:
        try:
            employee = Employee.objects.get(id=employee_id)
            passer_infor['name'] = employee.name
            passer_infor['work_start_alarm'] = employee.work_start_alarm
            passer_infor['work_end_alarm'] = employee.work_end_alarm
            passer_infor['dt_reg'] = employee.dt_reg
            passer_infor['works'] = employee.get_works()
            employee.delete()
        except Exception as e:
            passer_infor['employee_delete'] = '>>> 근로자가 이미 삭제되었다'
    logSend('>>> {}'.format(passer_infor))

    # 새로 업무에 근로자로 등록한다.
    s = requests.session()
    login_data = {"login_id": "temp_20",
                  "login_pw": "happy_day!!!"
                  }
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    logSend({'url': r.url, 'POST': login_data, 'STATUS': r.status_code, 'R': r.json()})

    today = datetime.datetime.now()
    tomorrow = today + datetime.timedelta(days=1)
    str_tomorrow = dt_str(str_to_datetime(dt_str(tomorrow, "%Y-%m-%d") + " 19"), "%Y-%m-%d %H:%M:%S")
    after_tomorrow = today + datetime.timedelta(days=2)
    str_after_tomorrow = dt_str(after_tomorrow, "%Y-%m-%d")
    logSend('>>> {} {} {}'.format(today, str_tomorrow, str_after_tomorrow))
    employee_info = {
        'work_id': AES_ENCRYPT_BASE64('37'),
        'dt_answer_deadline': str_tomorrow,  # 업무 수락/거절 답변 시한
        'dt_begin': str_after_tomorrow,  # 등록하는 근로자의 실제 출근 시작 날짜 (업무의 시작 후에 추가되는 근로자를 위한 날짜)
        'phone_numbers':  [pNo],  # 업무에 배치할 근로자들의 전화번호
        }
    logSend('>>> {}'.format(employee_info))
    r = s.post(settings.CUSTOMER_URL + 'reg_employee', json=employee_info)
    result = {'url': r.url, 'POST': employee_info, 'STATUS': r.status_code, 'R': r.json()}

    logSend(result)

    return REG_200_SUCCESS.to_json_response({'passer_infor': passer_infor, 'R': r.json()})


@cross_origin_read_allow
def temp_test_post(request):
    """
    근로자 서버의 업무를 삭제한다.
    - 근로자 서버의 업무 id 를 고객서버의 업무 id로 바꾼다.
        http://0.0.0.0:8000/employee/temp_test_post
    GET
        work_id_list: 업무 id lsit
    response
        STATUS 416
            {'message': '개발상태에서만 사용할 수 있습니다.'}
        STATUS 200
            {'message': '출입자가 이미 삭제 되었습니다.'}
            {'message': '근로자가 이미 삭제 되었습니다.'}
        STATUS 422 # 개발자 수정사항
    log Error
            logError(get_api(request), ' 잘못된 비콘 양식: {} - {}'.format(e, beacon))
    """
    # if not settings.DEBUG:
    #     return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '개발상태에서만 사용할 수 있습니다.'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    result = []
    s = requests.session()
    parameter = {
        'pNo': '01025573555',
        'year_month': '2020-01'
    }
    r = s.post(settings.EMPLOYEE_URL + 'make_work_io', json=parameter)
    result.append({'url': r.url, 'POST': parameter, 'STATUS': r.status_code, 'R': r.json()})
    return REG_200_SUCCESS.to_json_response({'result': result})


@cross_origin_read_allow
def make_work_io(request):
    """
    시험용: 근로자를 새로 등록할 수 있도록 정보를 삭제한다.
    - 상용서버에서는 사용할 수 없다.
        http://0.0.0.0:8000/employee/make_work_io?pNo=01025573555&year_month=2019-12&overtime=0
    GET
        pNo: 전화번호               # 삭제할 근로자의 전화번호
        date_begin: 2020-03-23   # 출퇴근 기록을 만들 시작 날짜
        date_end: 2020-04-06     # 출퇴근 기록을 만들 마지막 날짜
        (아래는 선택적)
        is_no_paid_work: 1       # 무급 휴일 근무
        is_paid_work: 1         # 유급 휴일 근무
        overtime: 3           # 연장 근무 시간 추가: 1 ~ 8
    response
        STATUS 416
            {'message': '개발상태에서만 사용할 수 있습니다.'}
            {'message': '전화번호 {} 로 출입자를 찾을 수 없다.'}
            {'message': '전화번호 {} 로 근로자를 찾을 수 없다.'}
            {'message': '업무(56)를 찾을 수 없다.'}
        STATUS 200
            {'message': '출입자가 이미 삭제 되었습니다.'}
            {'message': '근로자가 이미 삭제 되었습니다.'}
        STATUS 422 # 개발자 수정사항
    log Error
            logError(get_api(request), ' 잘못된 비콘 양식: {} - {}'.format(e, beacon))
    """
    if not settings.DEBUG:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '개발상태에서만 사용할 수 있습니다.'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    overtime = 0
    if 'overtime' in rqst:
        try:
            overtime = int(rqst['overtime'])
        except Exception as e:
            logSend('  overtime value(\'{}\') not integer'.format(rqst['overtime']))

    parameter_check = is_parameter_ok(rqst, ['pNo', 'date_begin', 'date_end', 'is_no_paid_work_@', 'is_paid_work_@', 'overtime_@'])
    if not parameter_check['is_ok']:
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': parameter_check['results']})
    pNo = parameter_check['parameters']['pNo']
    is_no_paid_work = parameter_check['parameters']['is_no_paid_work']
    is_paid_work = parameter_check['parameters']['is_paid_work']
    #
    # 근로내역을 만들 날짜 설정
    #
    dt_begin = str_to_datetime(parameter_check['parameters']['date_begin'])
    dt_end = str_to_datetime(parameter_check['parameters']['date_end'])
    # dt_end = dt_begin + relativedelta(months=1) - timedelta(seconds=1)
    # logSend('... begin: {}, end {}'.format(dt_begin, dt_end))
    today = datetime.datetime.now()
    if today < dt_end:
        dt_end = today
    logSend('   > begin: {}, end {}'.format(dt_begin, dt_end))

    result = []
    s = requests.session()
    # get passer
    try:
        passer = Passer.objects.get(pNo=pNo)
    except Exception as e:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '전화번호 {} 로 출입자를 찾을 수 없다.'.format(pNo)})
    # get employee
    try:
        employee = Employee.objects.get(id=passer.employee_id)
    except Exception as e:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '전화번호 {} 로 근로자를 찾을 수 없다.'.format(pNo)})

    # get work
    works = Works(employee.get_works())
    day_work_id_dict = {}
    work_id_dict = {}
    dt = dt_begin
    while dt <= dt_end:
        work_info = works.find_work_by_date(dt)
        if work_info != None:
            logSend('  >> {}'.format(work_info))
            if work_info['id'] not in work_id_dict.keys():
                work_id_dict[work_info['id']] = work_info
        day_work_id_dict[dt_str(dt, "%Y-%m-%d")] = work_info['id']
        dt = dt + datetime.timedelta(days=1)
    work_dict = get_work_dict(list(work_id_dict.keys()))

    # 새로 만들기 위해 기존 데이터 삭제
    #
    pass_record_list = Pass_History.objects.filter(passer_id=passer.id, year_month_day__in=day_work_id_dict.keys()).order_by('year_month_day')
    for pass_record in pass_record_list:
        pass_record.delete()
    # return REG_200_SUCCESS.to_json_response({'day_work_id_dict': day_work_id_dict,
    #                                          'work_id_dict': work_id_dict,
    #                                          'work_dict': work_dict,
    #                                          'pass_record': [pass_record.year_month_day for pass_record in pass_record_list]})

    pass_reg_info = {
        'passer_id': AES_ENCRYPT_BASE64(str(passer.id)),
        'dt': '2020-01-26 08:30:00',
        'is_in': 1,
        'major': 11001,
        'beacons': [{'minor': 11001, 'dt_begin': '2020-01-26 08:30:00', 'rssi': -70, 'dt_end': '2020-01-26 08:30:00', 'count': 12}],
    }
    pass_verify_info = {
        'passer_id': AES_ENCRYPT_BASE64(str(passer.id)),
        'dt': '2020-01-26 08:30:00',
        'is_in': 1,
        'major': 11001,
        'beacons': [{'minor': 11001, 'dt_begin': '2020-01-26 08:30:00', 'rssi': -70, 'dt_end': '2020-01-26 08:30:00', 'count': 12}],
    }
    for year_month_day in day_work_id_dict.keys():
        work_dict_key = day_work_id_dict[year_month_day]
        logSend('   > {}'.format(work_dict_key))
        work_dict_value = work_dict[str(work_dict_key)]
        logSend('   > {}'.format(work_dict_value))
        dt = str_to_datetime(year_month_day + ' ' + work_dict[str(day_work_id_dict[year_month_day])]['time_info']['work_time_list'][0]['t_begin'])
        # 토일 휴일 처리 weekday() 0:월요일
        weekday = dt.weekday()
        # print('... {} {}'.format(dt_str(dt, "%Y-%m-%d"), weekday))
        if weekday == 5 and is_no_paid_work != '1':  # 토요일
            # print('... 토요일')
            continue
        if weekday == 6 and is_paid_work != '1':  # 일요일
            # print('... 일요일')
            continue
        # 비콘 인식 출근 시간 처리
        pass_reg_info['is_in'] = 1
        dt = dt.replace(hour=8, minute=32)
        pass_reg_info['dt'] = dt_str(dt, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(minute=27)
        pass_reg_info['beacons'][0]['dt_begin'] = dt_str(dt, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(minute=31)
        pass_reg_info['beacons'][0]['dt_end'] = dt_str(dt, "%Y-%m-%d %H:%M:%S")
        r = s.post(settings.EMPLOYEE_URL + 'pass_reg', json=pass_reg_info)
        # result.append({'url': r.url, 'POST': pass_reg_info, 'STATUS': r.status_code, 'R': r.json()})

        # 앱을 이용한 출근 시간 처리
        pass_verify_info['is_in'] = 1
        dt = dt.replace(hour=8, minute=29)
        pass_verify_info['dt'] = dt_str(dt, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(minute=27)
        pass_verify_info['beacons'][0]['dt_begin'] = dt_str(dt, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(minute=31)
        pass_verify_info['beacons'][0]['dt_end'] = dt_str(dt, "%Y-%m-%d %H:%M:%S")
        r = s.post(settings.EMPLOYEE_URL + 'pass_verify', json=pass_verify_info)
        parameter = copy.deepcopy(pass_verify_info)
        result.append({'url': r.url, 'POST': parameter, 'STATUS': r.status_code, 'R': r.json()})

        # 비콘 인식으로 퇴근 처리
        pass_reg_info['is_in'] = 0
        dt = dt.replace(hour=17, minute=32)
        pass_reg_info['dt'] = dt_str(dt, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(minute=31)
        pass_reg_info['beacons'][0]['dt_begin'] = dt_str(dt, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(minute=35)
        pass_reg_info['beacons'][0]['dt_end'] = dt_str(dt, "%Y-%m-%d %H:%M:%S")
        r = s.post(settings.EMPLOYEE_URL + 'pass_reg', json=pass_reg_info)
        # result.append({'url': r.url, 'POST': pass_reg_info, 'STATUS': r.status_code, 'R': r.json()})

        # 앱을 이용한 퇴근 처리
        pass_verify_info['is_in'] = 0
        dt = dt.replace(hour=17, minute=33)
        pass_verify_info['dt'] = dt_str(dt, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(minute=31)
        pass_verify_info['beacons'][0]['dt_begin'] = dt_str(dt, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(minute=35)
        pass_verify_info['beacons'][0]['dt_end'] = dt_str(dt, "%Y-%m-%d %H:%M:%S")
        r = s.post(settings.EMPLOYEE_URL + 'pass_verify', json=pass_verify_info)
        parameter = copy.deepcopy(pass_verify_info)
        result.append({'url': r.url, 'POST': parameter, 'STATUS': r.status_code, 'R': r.json()})

        if overtime > 0:
            employees_infor = {'employees': [AES_ENCRYPT_BASE64(str(passer.id))],
                               'year_month_day': year_month_day,
                               'work_id': AES_ENCRYPT_BASE64(str(work_dict_key)),
                               'overtime': overtime,
                               'overtime_staff_id': AES_ENCRYPT_BASE64('13'),
                               'comment': '',
                               }
            r = requests.post(settings.EMPLOYEE_URL + 'pass_record_of_employees_in_day_for_customer_v2',
                              json=employees_infor)
            parameter = copy.deepcopy(employees_infor)
            result.append({'url': r.url, 'POST': parameter, 'STATUS': r.status_code, 'R': r.json()})

    if overtime > 0:
        notification_info = {'passer_id': AES_ENCRYPT_BASE64(str(passer.id))}
        r = requests.post(settings.EMPLOYEE_URL + 'notification_list_v2', json=notification_info)
        parameter = copy.deepcopy(notification_info)
        result.append({'url': r.url, 'POST': parameter, 'STATUS': r.status_code, 'R': r.json()})
        notification_list = r.json()['notifications']

        for noti in notification_list:
            noti_info = {'passer_id': AES_ENCRYPT_BASE64(str(passer.id)),
                         'notification_id': noti['id'],
                         'is_accept': '1'
                         }
            r = requests.post(settings.EMPLOYEE_URL + 'notification_accept_v2', json=noti_info)
            parameter = copy.deepcopy(noti_info)
            result.append({'url': r.url, 'POST': parameter, 'STATUS': r.status_code, 'R': r.json()})
    return REG_200_SUCCESS.to_json_response({'result': result})


# @cross_origin_read_allow
def get_work_dict(id_list: list) -> dict:
    """
    고객서버에서 업무 목록의 업무를 가져온다.

    - 근로자 서버의 업무 id 를 고객서버의 업무 id로 바꾼다.
        http://0.0.0.0:8000/employee/work_remover?work_id_list=1&work_id_list=2
    GET
        work_id_list: 업무 id lsit
    response
        {'1': [...]}
    """
    logSend('>>> get_work_dict\n^ work_id_list: {}'.format(id_list))
    if len(id_list) == 0:
        return {}
    r = requests.post(settings.CUSTOMER_URL + 'list_work_from_employee_v2', json={'work_id_list': id_list})
    logSend('\nv work_dict: {}\nv {} {}\n<<< get_work_dict'.format(r.json()['work_dict'].keys(), r.status_code, r.json()['message']))
    if r.status_code != 200:
        return {}
    return r.json()['work_dict']


@cross_origin_read_allow
def work_remover(request):
    """
    근로자 서버의 업무를 삭제한다.
    - 근로자 서버의 업무 id 를 고객서버의 업무 id로 바꾼다.
        http://0.0.0.0:8000/employee/work_remover?work_id_list=1&work_id_list=2
    GET
        work_id_list: 업무 id lsit
    response
        STATUS 416
            {'message': '개발상태에서만 사용할 수 있습니다.'}
        STATUS 200
            {'message': '출입자가 이미 삭제 되었습니다.'}
            {'message': '근로자가 이미 삭제 되었습니다.'}
        STATUS 422 # 개발자 수정사항
    log Error
            logError(get_api(request), ' 잘못된 비콘 양식: {} - {}'.format(e, beacon))
    """
    # if not settings.DEBUG:
    #     return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '개발상태에서만 사용할 수 있습니다.'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    # 업무 목록 요청 시험
    #
    # if request.method == 'GET':
    #     work_id_list = rqst.getlist('work_id_list')
    # else:
    #     work_id_list = rqst['work_id_list']
    # print('  > {}'.format(work_id_list))
    # work_dict = get_work_dict(work_id_list)
    # print('  > {}'.format(work_dict))
    #
    # return REG_200_SUCCESS.to_json_response({'work_dict': work_dict})


    work_list = Work.objects.all()
    if len(work_list[0].customer_work_id) == 0:
        return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '이미 업무 변경이 끝났습니다.'.format(pNo)})

    work_dict = {work.id: int(AES_DECRYPT_BASE64(work.customer_work_id)) for work in work_list}

    result_dict = {}
    employee_list = Employee.objects.all()
    for employee in employee_list:
        works = employee.get_works()
        for work in works:
            if work['id'] not in work_dict.keys():
                result_dict['employee_{}'.format(employee.id)] = {'name': employee.name, 'work_id': work['id']}
                logSend('  > name: {}, id: {}'.format(employee.name, work['id']))
                continue
            # logSend('  > name: {}, id: {} >> {}'.format(employee.name, work['id'], work_dict[work['id']]))
            work['id'] = work_dict[work['id']]
        employee.set_works(works)
        employee.save()

    employee_backup_list = Employee_Backup.objects.all()
    for employee in employee_backup_list:
        logSend('  > name: {}, id: {} >> {}'.format(employee.name, employee.work_id, work_dict[employee.work_id]))
        employee.work_id = work_dict[employee.work_id]
        employee.save()

    noti_work_list = Notification_Work.objects.all()
    for noti_work in noti_work_list:
        if len(noti_work.customer_work_id) is not 0:
            logSend('  > {}: {} >> {}'.format(noti_work.employee_pNo, noti_work.work_id, work_dict[noti_work.work_id]))
            noti_work.work_id = work_dict[noti_work.work_id]
            noti_work.customer_work_id = ''
            noti_work.save()

    pass_history_list = Pass_History.objects.all()
    for pass_history in pass_history_list:
        if int(pass_history.work_id) not in work_dict.keys():
            result_dict['pass_history_{}'.format(pass_history.id)] = {'passer_id': pass_history.passer_id, 'work_id': pass_history.work_id}
            logSend('--- pass_history_id: {}, work_id: {}'.format(pass_history.passer_id, pass_history.work_id))
            continue
        # logSend('  > {}: {} >> {}'.format(pass_history.passer_id, pass_history.work_id, work_dict[int(pass_history.work_id)]))
        pass_history.work_id = work_dict[int(pass_history.work_id)]
        pass_history.save()

    for work in work_list:
        work.customer_work_id = ''
        work.save()
    return REG_200_SUCCESS.to_json_response({'work_dict': work_dict, 'result_dict': result_dict})


@cross_origin_read_allow
def beacon_remover(request):
    """
    - 일정기간이 지난 비콘 기록을 삭제한다.
    - 중복된 비콘정보를 삭제한다.
        http://0.0.0.0:8000/employee/beacon_remover?dt_last_day=2020-04-01
    GET
        work_id_list: 업무 id lsit
    response
        STATUS 416
            {'message': '개발상태에서만 사용할 수 있습니다.'}
        STATUS 200
            {'message': '출입자가 이미 삭제 되었습니다.'}
            {'message': '근로자가 이미 삭제 되었습니다.'}
        STATUS 422 # 개발자 수정사항
    log Error
            logError(get_api(request), ' 잘못된 비콘 양식: {} - {}'.format(e, beacon))
    """
    # if not settings.DEBUG:
    #     return REG_416_RANGE_NOT_SATISFIABLE.to_json_response({'message': '개발상태에서만 사용할 수 있습니다.'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    parameter_check = is_parameter_ok(rqst, ['dt_last_day'])
    if not parameter_check['is_ok']:
        return status422(get_api(request),
                         {'message': '{}'.format(''.join([message for message in parameter_check['results']]))})
    dt_last_day = str_to_datetime(parameter_check['parameters']['dt_last_day'])

    # noti_list = Notification_Work.objects.filter(dt_inout__startswith=dt_last_day.date())
    # print('>> no of noti: {}'.format(len(noti_list)))
    # for noti in noti_list:
    #     print('> {}: {}'.format(noti.comment, noti.dt_inout))
    # return REG_200_SUCCESS.to_json_response()

    dt_before_month = datetime.datetime.now() - timedelta(days=31)
    if dt_before_month < dt_last_day:
        return status422(get_api(request), {'message': '한달 이내의 데이터는 삭제할 수 없습니다.'})
    beacon_record_list = Beacon_Record.objects.filter(dt_begin__lt=dt_last_day)
    for beacon_record in beacon_record_list:
        # print('  > {}: {}/{}/{}'.format(beacon_record.id, beacon_record.major, beacon_record.minor, beacon_record.dt_end))
        beacon_record.delete()

    beacon_list = Beacon.objects.all()
    beacon_dict = {}
    for beacon in beacon_list:
        major_minor = '{0:05d}-{1:05d}'.format(beacon.major, beacon.minor)
        if major_minor in list(beacon_dict.keys()):
            # print('{}: {} vs {}'.format(major_minor, beacon_dict[major_minor].dt_last, beacon.dt_last))
            if beacon_dict[major_minor].dt_last < beacon.dt_last:
                beacon_dict[major_minor] = beacon
                beacon_dict[major_minor].delete()
            else:
                beacon.delete()
        else:
            beacon_dict[major_minor] = beacon
    # print('  > no of beacon: {}'.format(len(list(beacon_dict.keys()))))
    # for key in beacon_dict.keys():
    #     print('  > {}: {}'.format(key, beacon_dict[key].dt_last))
    return REG_200_SUCCESS.to_json_response({'no of beacon': len(list(beacon_dict.keys())), 'deleted record': len(beacon_record_list)})
