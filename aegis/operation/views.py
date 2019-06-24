"""
Operation view

Copyright 2019. DaeDuckTech Corp. All rights reserved.
"""

import json
import datetime
from datetime import timedelta

import coreapi
from django.conf import settings
from rest_framework.decorators import api_view, schema
from rest_framework.schemas import AutoSchema
from rest_framework.views import APIView

from config.log import logSend, logError
from config.common import ReqLibJsonResponse
from config.common import func_begin_log, func_end_log
from config.common import hash_SHA256, no_only_phone_no, phone_format, is_parameter_ok
from config.common import rMin, str_to_datetime, str_to_dt, get_client_ip
from config.common import Works, status422
# secret import
from config.secret import AES_ENCRYPT_BASE64, AES_DECRYPT_BASE64
from config.decorator import cross_origin_read_allow, session_is_none_403_with_operation

from .models import Environment
from .models import Staff
from .models import Work_Place
from .models import Beacon
# from .models import Employee

import requests
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from config.status_collection import *

from config.error_handler import *

# from config.settings.base import CUSTOMER_URL

# Operation
# 1) request.method ='OPTIONS'
# 서버에서 Cross-Site 관련 옵션들을 확인
# 2) request.method == REAL_METHOD:
# 실제 사용할 데이터를 전송

# try: 다음에 code = 'argument incorrect'

import inspect


class Env(object):
    def __init__(self):
        # func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        self.is_running = False
        strToday = datetime.datetime.now().strftime("%Y-%m-%d ")
        str_dt_reload = strToday + '05:00:00'
        self.dt_reload = datetime.datetime.strptime(str_dt_reload, "%Y-%m-%d %H:%M:%S")
        self.start()
        # func_end_log(func_name)

    def __del__(self):
        # func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        logSend(' <<< Environment class delete')
        # func_end_log(func_name)

    def loadEnvironment(self):
        func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        if len(Environment.objects.filter()) == 0:
            newEnv = Environment(
                # dt=datetime.datetime.now() - timedelta(days=3),
                dt=datetime.datetime.strptime("2019-01-01 00:00:00", "%Y-%m-%d %H:%M:%S"),
                manager_id=0,
                dt_android_upgrade=datetime.datetime.strptime('2019-01-01 00:00:00', "%Y-%m-%d %H:%M:%S"),
                timeCheckServer="05:00:00",
            )
            newEnv.save()
        note = '   Env: ' + self.dt_reload.strftime("%Y-%m-%d %H:%M:%S") + ' 이전 환경변수를 기준으로 한다.'
        logSend(note)
        print(self.dt_reload)
        envs = Environment.objects.filter()
        for env in envs:
            print(env.id, env.dt)
        envs = Environment.objects.filter(dt__lt=self.dt_reload).order_by('-id')
        note = '    >>> no of environment = ' + str(len(envs))
        logSend(note)
        """
        i = 0
        for envCell in envs :
            logSend('   >>> ' + `i` + ' = ' + `envCell.id` + '' + `envCell.dt.strftime("%Y-%m-%d %H:%M:%S")`)
            i = i + 1
        """
        self.curEnv = envs[0]
        logSend('   Env: ')
        logSend('   >>> dt env = ' + self.curEnv.dt.strftime("%Y-%m-%d %H:%M:%S"))
        logSend('   >>> dt android = ' + self.curEnv.dt_android_upgrade.strftime("%Y-%m-%d %H:%M:%S"))
        logSend('   >>> timeCheckServer = ' + self.curEnv.timeCheckServer)
        logSend('   >>> request timee gap = ' + str(settings.REQUEST_TIME_GAP))
        strToday = datetime.datetime.now().strftime("%Y-%m-%d ")
        str_dt_reload = strToday + self.curEnv.timeCheckServer
        self.dt_reload = datetime.datetime.strptime(str_dt_reload, "%Y-%m-%d %H:%M:%S")
        if self.dt_reload < datetime.datetime.now():  # 다시 로딩해야할 시간이 현재 시간 이전이면 내일 시간으로 바꾼다.
            self.dt_reload = self.dt_reload + timedelta(days=1)
            logSend('       next load time + 24 hours')
        logSend('   >>> next load time = ' + self.dt_reload.strftime("%Y-%m-%d %H:%M:%S"))
        logSend('   >>> current time = ' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        settings.IS_TEST = False
        func_end_log(func_name)
        return

    def start(self):
        # func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        if not self.is_running:
            self.loadEnvironment()
            self.is_running = True
        # func_end_log(func_name)

    def stop(self):
        # func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        self.is_running = False
        # func_end_log(func_name)

    def current(self):
        # func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        if self.dt_reload < datetime.datetime.now():
            self.is_running = False
            self.loadEnvironment()
            self.is_running = True
        # func_end_log(func_name)
        return self.curEnv

    def self(self):
        # func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        # func_end_log(func_name)
        return self


env = Env()


@cross_origin_read_allow
def testEnv(request):
    """
    http://0.0.0.0:8000/operation/testEnv
    POST
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

    global env
    result = {}
    result['dt'] = env.current().dt.strftime("%Y-%m-%d %H:%M:%S")
    result['timeCheckServer'] = env.current().timeCheckServer

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def currentEnv(request):
    """
    현재 환경 값을 요청한다.
    currentEnv (current environment) 현재 환경 값을 요청한다.
    http://0.0.0.0:8000/operation/currentEnv
    POST
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

    envirenments = Environment.objects.filter().order_by('-dt')
    array_env = []
    for envirenment in envirenments:
        new_env = {
            'dt': envirenment.dt.strftime("%Y-%m-%d %H:%M:%S"),
            'dt_android_upgrade': envirenment.dt_android_upgrade.strftime("%Y-%m-%d %H:%M:%S"),
            'timeCheckServer': envirenment.timeCheckServer
        }
        array_env.append(new_env)
    current_env = {
        'dt': env.curEnv.dt.strftime("%Y-%m-%d %H:%M:%S"),
        'dt_android_upgrade': env.curEnv.dt_android_upgrade.strftime("%Y-%m-%d %H:%M:%S"),
        'timeCheckServer': env.curEnv.timeCheckServer
    }
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'current_env': current_env, 'env_list': array_env})


@cross_origin_read_allow
@session_is_none_403_with_operation
def updateEnv(request):
    """
    updateEnv (update environment) 환경 값을 변경한다.
    - 값이 없으면 처리하지 않는다.
    - 안드로이드 업그레이드 설정 dt_android_upgrade=2019-02-12 15:00:00 이후에 업그레이드를 받게 한다.
    http://0.0.0.0:8000/operation/updateEnv?dt_android_upgrade=2019-02-11 05:00:00&timeCheckServer=05:00:00
    POST
        {
            'dt_android_upgrade': '2019-02-11 05:00:00',
            'timeCheckServer': '05:00:00'
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

    global env

    worker_id = request.session['op_id'][5:]
    print(worker_id, worker_id[5:])

    worker = Staff.objects.get(id=worker_id)
    if not (worker.id in [1, 2]):
        print('524')
        func_end_log(func_name)
        return REG_524_HAVE_NO_PERMISSION_TO_MODIFY.to_json_response()

    is_update = False

    dt_android_upgrade = rqst['dt_android_upgrade']
    print(' 1 ', dt_android_upgrade)
    print(' 2 ', env.current().dt_android_upgrade)
    if len(dt_android_upgrade) == 0:
        dt_android_upgrade = env.current().dt_android_upgrade.strftime("%Y-%m-%d %H:%M:%S")
    else:
        is_update = True
    print(' 3 ', dt_android_upgrade)

    timeCheckServer = rqst['timeCheckServer']
    if len(timeCheckServer) == 0:
        timeCheckServer = env.current().timeCheckServer
    else:
        is_update = True

    print(dt_android_upgrade)
    if is_update:
        env.stop()
        newEnv = Environment(
            dt=datetime.datetime.now(),
            manager_id=worker.id,
            dt_android_upgrade=datetime.datetime.strptime(dt_android_upgrade, "%Y-%m-%d %H:%M:%S"),
            timeCheckServer=timeCheckServer,
        )
        newEnv.save()
        env.start()
    print('200')
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403_with_operation
def reg_staff(request):
    """
    운영 직원 등록
    - 파라미터가 빈상태를 검사하지 않는다. (호출하는 쪽에서 검사)
        http://0.0.0.0:8000/operation/reg_staff?pNo=010-2557-3555&id=thinking&pw=a~~~8282&master=0eT00W2FDHML2aLERQX2UA
        POST
            {
                'pNo': '010-1111-2222',
                'id': 'thinking',
                'pw': 'a~~~8282'
            }
        response
            STATUS 200
            STATUS 409
                {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])
    # logSend('  before func: {} now: {} vs last: {}'.format(request.session['func_name'], datetime.datetime.now(), request.session['dt_last']))
    if (request.session['func_name'] == func_name) and \
            (datetime.datetime.strptime(request.session['dt_last'], "%Y-%m-%d %H:%M:%S") + \
             datetime.timedelta(seconds=settings.REQUEST_TIME_GAP) > datetime.datetime.now()):
        logError('Error: {} 5초 이내에 [등록]이나 [수정]요청이 들어왔다.'.format(func_name))
        func_end_log(func_name)
        return REG_409_CONFLICT.to_json_response()
    request.session['func_name'] = func_name
    request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request.session.save()

    worker_id = request.session['op_id'][5:]
    worker = Staff.objects.get(id=worker_id)
    # try:
    #     if AES_DECRYPT_BASE64(rqst['master']) != '3355':
    #         func_end_log(func_name)
    #         return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '마스터 키 오류'})
    # except Exception as e:
    #     func_end_log(func_name)
    #     return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '마스터 키 오류 : ' + str(e)})

    phone_no = no_only_phone_no(rqst['pNo'])
    id_ = rqst['id']
    pw = rqst['pw']
    logSend('--- 등록 요청 id:{}, pw:{}'.format(id_, pw))

    staffs = Staff.objects.filter(pNo=phone_no, login_id=id_)
    if len(staffs) > 0:
        func_end_log(func_name)
        return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response()
    new_staff = Staff(
        login_id=id_,
        login_pw=hash_SHA256(pw),
        pNo=phone_no,
        dt_app_login=datetime.datetime.now(),
        dt_login=datetime.datetime.now(),
    )
    new_staff.save()
    logSend('--- 등록 완료 id:{}, pw:{}'.format(new_staff.login_id, new_staff.pNo))
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()

# class OperationView(APIView):
#     staff_login_form = AutoSchema(manual_fields=[
#         coreapi.Field("pNo", required=True, location="form", type="string", description="partner number field",
#                       example="010-2557-3555"),
#         coreapi.Field("id", required=True, location="form", type="string", description="id field", example="thinking"),
#         coreapi.Field("pw", required=True, location="form", type="string", description="password field",
#                       example="a~~~8282")]
#     )
#
#     @api_view(['POST'])
#     @schema(staff_login_form)
#     @cross_origin_read_allow
#     @session_is_none_403_with_operation
#     def reg_staff(request):
#         """
#         운영 직원 등록
#         - 파라미터가 빈상태를 검사하지 않는다. (호출하는 쪽에서 검사)
#             http://0.0.0.0:8000/operation/reg_staff?pNo=010-2557-3555&id=thinking&pw=a~~~8282&master=0eT00W2FDHML2aLERQX2UA
#             POST
#                 {
#                     'pNo': '010-1111-2222',
#                     'id': 'thinking',
#                     'pw': 'a~~~8282'
#                 }
#             response
#                 STATUS 200
#                 STATUS 409
#                     {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
#         """
#         func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
#         if request.method == 'POST':
#             rqst = json.loads(request.body.decode("utf-8"))
#         else:
#             rqst = request.GET
#         for key in rqst.keys():
#             logSend('  ', key, ': ', rqst[key])
#         # logSend('  before func: {} now: {} vs last: {}'.format(request.session['func_name'], datetime.datetime.now(), request.session['dt_last']))
#         if (request.session['func_name'] == func_name) and \
#                 (datetime.datetime.strptime(request.session['dt_last'], "%Y-%m-%d %H:%M:%S") + \
#                  datetime.timedelta(seconds=settings.REQUEST_TIME_GAP) > datetime.datetime.now()):
#             logError('Error: {} 5초 이내에 [등록]이나 [수정]요청이 들어왔다.'.format(func_name))
#             func_end_log(func_name)
#             return REG_409_CONFLICT.to_json_response()
#         request.session['func_name'] = func_name
#         request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         request.session.save()
#
#         worker_id = request.session['op_id'][5:]
#         worker = Staff.objects.get(id=worker_id)
#         # try:
#         #     if AES_DECRYPT_BASE64(rqst['master']) != '3355':
#         #         func_end_log(func_name)
#         #         return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '마스터 키 오류'})
#         # except Exception as e:
#         #     func_end_log(func_name)
#         #     return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '마스터 키 오류 : ' + str(e)})
#
#         phone_no = no_only_phone_no(rqst['pNo'])
#         id_ = rqst['id']
#         pw = rqst['pw']
#         logSend('--- 등록 요청 id:{}, pw:{}'.format(id_, pw))
#
#         staffs = Staff.objects.filter(pNo=phone_no, login_id=id_)
#         if len(staffs) > 0:
#             func_end_log(func_name)
#             return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response()
#         new_staff = Staff(
#             login_id=id_,
#             login_pw=hash_SHA256(pw),
#             pNo=phone_no
#         )
#         new_staff.save()
#         logSend('--- 등록 완료 id:{}, pw:{}'.format(new_staff.login_id, new_staff.pNo))
#         func_end_log(func_name)
#         return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403_with_operation
def logControl(request):
    """
    로그를 Start, Stop 한다.
    http://0.0.0.0:8000/operation/logControl?action=Stop
    POST
        {
            'action': 'Start'   # Stop
        }
    response
        STATUS 200
        STATUS 524
            {'message':'수정 권한이 없습니다.'}
        STATUS 422 # 개발자 수정사항
            {'message':'ClientError: parameter \'action\' 가 없어요'}
            {'message': '처리할 수 없는 action(%s) 입니다.' % action}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    worker_id = request.session['op_id'][5:]
    worker = Staff.objects.get(id=worker_id)

    if not worker.login_id == 'thinking':
        func_end_log(func_name)
        return REG_524_HAVE_NO_PERMISSION_TO_MODIFY.to_json_response()

    parameter_check = is_parameter_ok(rqst, ['action'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})
    action =  parameter_check['parameters']['action']
    if action == 'Start':
        settings.IS_LOG = True
    elif action == 'Stop':
        settings.IS_LOG = False
    # elif action == 'Remove':
    #     # aegis.log 파일 삭제
    else:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '처리할 수 없는 action(%s) 입니다.' % action})
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def login(request):
    """

    로그인
    http://0.0.0.0:8000/operation/login?id=thinking&pw=a~~~8282
    POST
        {
            'id': 'thinking',
            'pw': 'a~~~8282'
        }
    response
        STATUS 200
        STATUS 401
            {'message':'id 나 비밀번호가 틀립니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    id_ = rqst['id']
    pw_ = rqst['pw']

    staffs = Staff.objects.filter(login_id=id_, login_pw=hash_SHA256(pw_))
    if len(staffs) == 0:
        func_end_log(func_name)
        return REG_530_ID_OR_PASSWORD_IS_INCORRECT.to_json_response()
    staff = staffs[0]
    staff.is_login = True
    staff.dt_login = datetime.datetime.now()
    staff.save()

    # 추후 0000은 permission 에 할당
    request.session['op_id'] = 'O0000' + str(staff.id)
    request.session['func_name'] = func_name
    request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request.session.save()
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def logout(request):
    """
    로그아웃
    http://0.0.0.0:8000/operation/logout
    POST
    response
        STATUS 200
            {'message':'이미 로그아웃되었습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.session is None or 'op_id' not in request.session:
        func_end_log(func_name)
        return REG_200_SUCCESS.to_json_response({'message': '이미 로그아웃되었습니다.'})
    staff = Staff.objects.get(id=request.session['op_id'][5:])
    staff.is_login = False
    staff.dt_login = datetime.datetime.now()
    staff.save()
    del request.session['op_id']
    del request.session['dt_last']
    del request.session['func_name']
    request.session.save()

    # id를 None 으로 Setting 하면, 세션은 살아있으면서 값은 None 인 상태가 된다.
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403_with_operation
def update_staff(request):
    """
    직원 정보를 수정한다.
    - 로그인 되어 있지 않으면 수정할 수 없다.
    - 로그인 한 사람과 대상 직원이 다르면 암호 초기화만 가능하다. (다음 버전에서)
        주)    항목이 비어있으면 수정하지 않는 항목으로 간주한다.
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/operation/update_staff?login_id=thinking&before_pw=happy_day82&login_pw=&name=박종기&position=이사&department=개발&phone_no=&phone_type=10&push_token=unknown&email=thinking@ddtechi.com
    POST
        {
            'login_id': '변결할 id' # 중복되면 542
            'before_pw': '기존 비밀번호',     # 필수
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
            {'message': '비밀번호가 초기화 되었습니다.'}
        STATUS 409
            {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
        STATUS 531
            {'message': '비밀번호가 틀립니다.'}
        STATUS 542
            {'message': '아이디가 중복됩니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])
    # logSend('  before func: {} now: {} vs last: {}'.format(request.session['func_name'], datetime.datetime.now(), request.session['dt_last']))
    if (request.session['func_name'] == func_name) and \
            (datetime.datetime.strptime(request.session['dt_last'], "%Y-%m-%d %H:%M:%S") + \
             datetime.timedelta(seconds=settings.REQUEST_TIME_GAP) > datetime.datetime.now()):
        logError('Error: {} 5초 이내에 [등록]이나 [수정]요청이 들어왔다.'.format(func_name))
        func_end_log(func_name)
        return REG_409_CONFLICT.to_json_response()
    request.session['func_name'] = func_name
    request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request.session.save()

    worker_id = request.session['op_id'][5:]
    worker = Staff.objects.get(id=worker_id)

    login_id = rqst['login_id']  # id 로 사용
    before_pw = rqst['before_pw']  # 기존 비밀번호
    login_pw = rqst['login_pw']  # 변경하려는 비밀번호
    name = rqst['name']  # 이름
    position = rqst['position']  # 직책
    department = rqst['department']  # 부서 or 소속
    phone_no = no_only_phone_no(rqst['phone_no'])  # 전화번호
    phone_type = rqst['phone_type']  # 전화 종류    10:iPhone, 20: Android
    push_token = rqst['push_token']  # token
    email = rqst['email']  # id@ddtechi.co
    print(login_id, before_pw, login_pw, name, position, department, phone_no, phone_type, push_token, email)

    staff = worker
    # if worker.id != staff.id:
    #     staff.login_pw = hash_SHA256('happy_day82')
    #     func_end_log(func_name)
    #     return REG_200_SUCCESS.to_json_response({'message': '비밀번호가 초기화 되었습니다.'})

    if hash_SHA256(before_pw) != staff.login_pw:
        func_end_log(func_name)
        return REG_531_PASSWORD_IS_INCORRECT.to_json_response()

    if len(login_id) > 0:
        if (Staff.objects.filter(login_id=login_id)) > 0:
            func_end_log(func_name)
            return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response({'message': '아이디가 중복됩니다.'})
        staff.login_id = login_id
    if len(login_pw) > 0:
        staff.login_pw = hash_SHA256(login_pw)
    if len(name) > 0:
        staff.name = name
    if len(position) > 0:
        staff.position = position
    if len(department) > 0:
        staff.department = department
    if len(phone_no) > 0:
        staff.pNo = phone_no
    if len(phone_type) > 0:
        staff.phone_type = phone_type
    if len(push_token) > 0:
        staff.push_token = push_token
    if len(email) > 0:
        staff.email = email
    staff.save()
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
@session_is_none_403_with_operation
def list_staff(request):
    """
    직원 list 요청
        주)    항목이 비어있으면 수정하지 않는 항목으로 간주한다.
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/operation/list_staff
    response
        STATUS 200
            {'staffs': [{'name':'...', 'position':'...', 'department':'...', 'pNo':'...', 'pType':'...', 'email':'...'}, ...]}
        STATUS 503
            {'message': '직원이 아닙니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    worker_id = request.session['op_id'][5:]
    worker = Staff.objects.get(id=worker_id)

    # if rqst.get('master') is None:

    print(request.session.keys())
    for key in request.session.keys():
        print(key, ':', request.session[key])

    staffs = Staff.objects.filter()
    arr_staff = []
    for staff in staffs:
        r_staff = {
            'login_id': staff.login_id,
            'name': staff.name,
            'position': staff.position,
            'department': staff.department,
            'pNo': phone_format(staff.pNo),
            'pType': staff.pType,
            'email': staff.email,
            'is_worker': True if staff.id == worker.id else False
        }
        arr_staff.append(r_staff)
    print(arr_staff)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'staffs': arr_staff})


@cross_origin_read_allow
@session_is_none_403_with_operation
def reg_customer(request):
    """
    고객사를 등록한다.
    - 간단한 내용만 넣어서 등록하고 나머지는 고객사 담당자가 추가하도록 한다.
    - 담당자 전화번호로 SMS 에 id 와 pw 를 보낸다.
        주) 항목이 비어있으면 수정하지 않는 항목으로 간주한다.
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
        STATUS 409
            {'message': '처리 중에 다시 요청할 수 없습니다.(5초)'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])
    # logSend('  before func: {} now: {} vs last: {}'.format(request.session['func_name'], datetime.datetime.now(), request.session['dt_last']))
    if (request.session['func_name'] == func_name) and \
            (datetime.datetime.strptime(request.session['dt_last'], "%Y-%m-%d %H:%M:%S") + \
             datetime.timedelta(seconds=settings.REQUEST_TIME_GAP) > datetime.datetime.now()):
        logError('Error: {} 5초 이내에 [등록]이나 [수정]요청이 들어왔다.'.format(func_name))
        func_end_log(func_name)
        return REG_409_CONFLICT.to_json_response()
    request.session['func_name'] = func_name
    request.session['dt_last'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request.session.save()

    worker_id = request.session['op_id'][5:]
    worker = Staff.objects.get(id=worker_id)

    customer_name = rqst["customer_name"]
    staff_name = rqst["staff_name"]
    staff_pNo = no_only_phone_no(rqst["staff_pNo"])

    staff_email = rqst["staff_email"]

    new_customer_data = {
        'worker_id': AES_ENCRYPT_BASE64(str(worker.id)),
        'customer_name': customer_name,
        'staff_name': staff_name,
        'staff_pNo': staff_pNo,
        'staff_email': staff_email,
    }
    response_customer = requests.post(settings.CUSTOMER_URL + 'reg_customer_for_operation', json=new_customer_data)
    if response_customer.status_code != 200:
        func_end_log(func_name)
        return ReqLibJsonResponse(response_customer)
    response_customer_json = response_customer.json()

    if settings.IS_TEST:
        func_end_log(func_name)
        return REG_200_SUCCESS.to_json_response({'message': ['id/pw to SMS(실제로 보내지는 않음)', response_customer_json['login_id'], 'happy_day!!!']})

    rData = {
        'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
        'user_id': 'yuadocjon22',
        'sender': settings.SMS_SENDER_PN,
        'receiver': staff_pNo,  # '01025573555',
        'msg_type': 'SMS',
        'msg': '반갑습니다.\n'
               '\'이지체크\'예요~~\n'
               '아이디 ' + response_customer_json['login_id'] + '\n'
               '비밀번호 happy_day!!!'
    }
    r = requests.post('https://apis.aligo.in/send/', data=rData)
    logSend('SMS Result: ', r.json())

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'message': 'SMS 로 아이디와 초기회된 비밀번호를 보냈습니다.'})


@cross_origin_read_allow
@session_is_none_403_with_operation
def sms_customer_staff(request):
    """
    고객사 담당자에게 문자로 id 와 pw 를 보낸다.
    http://0.0.0.0:8000/operation/sms_customer_staff?staff_id=qgf6YHf1z2Fx80DR8o_Lvg&staff_pNo=010-2557-3555
    POST
        {
            'staff_id': 'cipher_id',
            'staff_pNo': 010-2557-3555
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

    worker_id = request.session['op_id'][5:]
    worker = Staff.objects.get(id=worker_id)

    new_customer_data = {
        'worker_id': AES_ENCRYPT_BASE64(str(worker.id)),
        'staff_id': rqst['staff_id']
    }
    response_customer = requests.post(settings.CUSTOMER_URL + 'sms_customer_staff_for_operation',
                                      json=new_customer_data)
    if response_customer.status_code != 200:
        func_end_log(func_name)
        return ReqLibJsonResponse(response_customer)
    response_customer_json = response_customer.json()

    if settings.IS_TEST:
        func_end_log(func_name)
        return REG_200_SUCCESS.to_json_response({'message': 'id/pw to SMS(실제로 보내지는 않음)', 'login_id':response_customer_json['login_id'], 'first_pw': 'happy_day!!!' })

    rData = {
        'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
        'user_id': 'yuadocjon22',
        'sender': settings.SMS_SENDER_PN,
        'receiver': rqst['staff_pNo'],  # '01025573555',
        'msg_type': 'SMS',
        'msg': '반갑습니다.\n'
               '\'이지체크\'예요~~\n'
               '아이디 ' + response_customer_json['login_id'] + '\n'
               '비밀번호 happy_day!!!'
    }
    r = requests.post('https://apis.aligo.in/send/', data=rData)
    logSend(r.json())

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'message': 'SMS 로 아이디와 초기회된 비밀번호를 보냈습니다.', 'login_id':response_customer_json['login_id']})


@cross_origin_read_allow
@session_is_none_403_with_operation
def list_customer(request):
    """
    고객사 리스트를 요청한다.
    - 2019/02/26 현재 parameter 는 처리하지 않음.
    - 차후 검색어로 사용: 지역, 업체명 포함, 담당자 이름 포함, 담당자 전화번호 일부 포함
    http://0.0.0.0:8000/operation/list_customer?customer_name=대덕테크&staff_name=박종기&staff_pNo=010-2557-3555&staff_email=thinking@ddtechi.com
    GET
        customer_name=대덕기공
        staff_name=홍길동
        staff_pNo=010-1111-2222
        staff_email=id@daeducki.com
    response
        STATUS 200
            {
              "message": "정상적으로 처리되었습니다.",
              "customers": [
                {
                  "name": "대덕테크",
                  "contract_no": "",
                  "dt_reg": "2019-01-17 08:09:08",
                  "dt_accept": null,
                  "type": "발주업체",
                  "staff_id": "_w8ZzqmpBf5xvsE2VPY2XzaY9zmregZXSKFBR-4cOts=",
                  "staff_name": "박종기",
                  "staff_pNo": "01025573555",
                  "staff_email": "thinking@ddtechi.com",
                  "manager_name": "이요셉",
                  "manager_pNo": "01024505942",
                  "manager_email": "hello@ddtechi.com",
                  "dt_payment": "2019-02-25 02:24:27"
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

    worker_id = request.session['op_id'][5:]
    worker = Staff.objects.get(id=worker_id)

    customer_name = rqst['customer_name']
    staff_name = rqst['staff_name']
    staff_pNo = no_only_phone_no(rqst['staff_pNo'])
    staff_email = rqst['staff_email']

    json_data = {
        'worker_id': AES_ENCRYPT_BASE64(str(worker.id)),
        'customer_name': customer_name,
        'staff_name': staff_name,
        'staff_pNo': staff_pNo,
        'staff_email': staff_email,
    }
    response_customer = requests.get(settings.CUSTOMER_URL + 'list_customer_for_operation', params=json_data)
    if response_customer.status_code != 200:
        func_end_log(func_name)
        return ReqLibJsonResponse(response_customer)
    customer_types = ['발주업체', '파견업체', '협력업체']
    arr_customer = response_customer.json()['customers']
    for customer in arr_customer:
        customer['name'] = customer['corp_name']
        del customer['corp_name']
        del customer['id']
        customer['type'] = customer_types[customer['type'] - 10]
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'customers': arr_customer})


@cross_origin_read_allow
@session_is_none_403_with_operation
def update_work_place(request):
    """
    사업장 내용을 수정한다.
    주)  항목이 비어있으면 수정하지 않는 항목으로 간주한다.
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
    response = HttpResponse()
    response.status_code = 200
    return response


@cross_origin_read_allow
@session_is_none_403_with_operation
def update_beacon(request):
    """
    비콘 내용을 수정한다.
        주)    항목이 비어있으면 수정하지 않는 항목으로 간주한다.
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
    response = HttpResponse()
    response.status_code = 200
    return response


@cross_origin_read_allow
@session_is_none_403_with_operation
def list_work_place(request):
    """
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

    response = HttpResponse()
    response.status_code = 200
    return response


@cross_origin_read_allow
@session_is_none_403_with_operation
def list_beacon(request):
    """
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
    response = HttpResponse()
    response.status_code = 200
    return response


@cross_origin_read_allow
@session_is_none_403_with_operation
def detail_beacon(request):
    """
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

    response = HttpResponse()
    response.status_code = 200
    return response


@cross_origin_read_allow
def dt_android_upgrade(request):
    """
    android 를 upgrade 할 날짜 시간 (
    http://0.0.0.0:8000/operation/dt_android_upgrade
    POST
    response
        STATUS 200
            { 'dt_update':'2019-02-11' }
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    # worker_id = request.session['op_id'][5:]
    # worker = Staff.objects.get(id=worker_id)

    global env
    result = {'dt_update': env.curEnv.dt_android_upgrade.strftime('%Y-%m-%d %H:%M:%S')}
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def customer_test_step_1(request):
    """
    [[고객 서버 시험]] Step 1: 고객 테이블 삭제
    - id reset $ python manage.py sqlsequencereset customer
    http://0.0.0.0:8000/operation/customer_test_step_1?key=
    GET
        { "key" : "사용 승인 key" }
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    # 고객서버 테이블 삭제 및 초기화
    key = {'key':rqst['key']}
    response = requests.post(settings.CUSTOMER_URL + 'table_reset_and_clear_for_operation', json=key)
    logSend(response.json())

    result = [{'message': 'Customer all tables deleted '}]

    new_staff = Staff(
        login_id='thinking',
        login_pw=hash_SHA256('parkjong'),
        pNo='01025573555',
        dt_app_login=datetime.datetime.now(),
        dt_login=datetime.datetime.now(),
    )
    new_staff.save()

    # # 운영 로그인
    # login_data = {"pNo": "010-2557-3555",
    #               "id": "thinking",
    #               "pw": "parkjong"
    #               }
    # s = requests.session()
    # r = s.post(settings.OPERATION_URL + 'reg_staff', json=login_data)
    # result.append({'url': r.url, 'POST':login_data, 'STATUS': r.status_code, 'R': r.json()})

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
def customer_test_step_2(request):
    """
    [[고객 서버 시험]] Step 2: 고객 생성
    - 운영 로그인
    - 고객업체 생성
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    result = []

    # 운영 로그인
    login_data = {"id": "thinking",
                  "pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.OPERATION_URL + 'login', json=login_data)
    result.append({'url': r.url, 'POST':login_data, 'STATUS': r.status_code, 'R': r.json()})
    if r.status_code == 530:
        staff = Staff.objects.get(id=1)
        staff.login_pw = hash_SHA256(login_data["pw"])
        staff.save()
        r = s.post(settings.OPERATION_URL + 'login', json=login_data)
        result.append({'url': r.url, 'POST': login_data, 'STATUS': r.status_code, 'R': r.json()})

    # 고객업체 생성
    customer_data = {'customer_name': '대덕테크',
                     'staff_name': '박종기',
                     'staff_pNo': '010-2557-3555',
                     'staff_email': 'thinking@ddtechi.com'
                     }
    settings.IS_TEST = True
    r = s.post(settings.OPERATION_URL + 'reg_customer', json=customer_data)
    settings.IS_TEST = False
    result.append({'url': r.url, 'POST':customer_data, 'STATUS': r.status_code, 'R': r.json()})

    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def customer_test_step_3(request):
    """
    [[고객 서버 시험]] Step 3: 운영에서 고객사 리스트, 고객사 담당자에게 비밀번호 초기화 문자 발송
    - 운영: 고객사 리스트
    - 운영: 고객사 담당자에게 비밀번호 초기화 문자 발송
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    result = []

    # 운영 : 로그인
    login_data = {"id": "thinking",
                  "pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.OPERATION_URL + 'login', json=login_data)
    result.append({'url': r.url, 'POST':login_data, 'STATUS': r.status_code, 'R': r.json()})

    # 운영 : 고객사 리스트
    customer_data = {'customer_name': '대덕테크',
                     'staff_name': '박종기',
                     'staff_pNo': '010-2557-3555',
                     'staff_email': 'thinking@ddtechi.com'
                     }
    r = s.post(settings.OPERATION_URL + 'list_customer', json=customer_data)
    result.append({'url': r.url, 'GET': customer_data, 'STATUS': r.status_code, 'R': r.json()})
    customer_list = r.json()['customers']
    for cust in customer_list:
        logSend(cust)
        if cust['corp_name'] == customer_data['customer_name']:
            logSend(cust['corp_name'])
            customer = cust
    logSend(customer['staff_id'], ' ', AES_DECRYPT_BASE64(customer['staff_id']))
    logSend(customer['staff_name'])
    customer_staff_id = customer['staff_id']

    # 운영 : 고객사 담당자 SMS 다시 보냄
    customer_data = {'staff_id': customer['staff_id'],
                     'staff_pNo': customer['staff_pNo']
                     }
    settings.IS_TEST = True
    r = s.post(settings.OPERATION_URL + 'sms_customer_staff', json=customer_data)
    settings.IS_TEST = False
    result.append({'url': r.url, 'POST': customer_data, 'STATUS': r.status_code, 'R': r.json()})
    logSend(r.json())
    login_id = r.json()['login_id']

    # 고객 : 로그인
    login_data = {"login_id": login_id,
                  "login_pw": "happy_day!!!"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url': r.url, 'POST':login_data, 'STATUS': r.status_code, 'R': r.json()})

    if r.status_code == 200:
        # 고객 : 자기 정보 수정 - login_id
        staff_data = {'staff_id':customer_staff_id,
                      'new_login_id': 'thinking',
                      'before_pw': 'happy_day!!!',
                      'login_pw': 'parkjong'
                      }
        r = s.post(settings.CUSTOMER_URL + 'update_staff', json=staff_data)
        result.append({'url': r.url, 'POST': staff_data, 'STATUS': r.status_code, 'R': r.json()})

    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def customer_test_step_4(request):
    """
    [[고객 서버 시험]] Step 4: 고객 웹 로그인, 고객사 담당자 정보 변경, 직원 리스트
    - 고객 웹 로그인
    - 담당자 정보 변경
    - 직원 추가 등록
    - 직원 리스트
    - 고객사 담당자 변경
    - 고객사 정보 수정
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    result = []

    # 고객 : 로그인
    login_data = {"login_id": "thinking",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url': r.url, 'POST':login_data, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 자기 정보 수정 - 직책
    staff_data = {'before_pw': 'parkjong',
                  'position': '이사',
                  }
    r = s.post(settings.CUSTOMER_URL + 'update_staff', json=staff_data)
    result.append({'url': r.url, 'POST':staff_data, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 직원 등록
    staff_data = {'name': '이요셉',
                  'login_id': 'hello',
                  'position': '책임연구원',     # option 비워서 보내도 됨
                  'department': '개발팀',  # option 비워서 보내도 됨
                  'pNo': '010-2450-5942', # '-'를 넣어도 삭제되어 저장 됨
                  'email': 'hello@ddtechi.com',
                  }
    r = s.post(settings.CUSTOMER_URL + 'reg_staff', json=staff_data)
    result.append({'url': r.url, 'POST':staff_data, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 직원 리스트
    staff_data = {}
    r = s.post(settings.CUSTOMER_URL + 'list_staff', json=staff_data)
    result.append({'url': r.url, 'GET':staff_data, 'STATUS': r.status_code, 'R': r.json()})
    logSend(r.json())
    logSend(r.json()['staffs'][1])
    # 고객 : 고객사 정보 수정
    customer_infor = {'staff_id': r.json()['staffs'][1]['id']}
    r = s.post(settings.CUSTOMER_URL + 'update_customer', json=customer_infor)
    result.append({'url': r.url, 'POST':customer_infor, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 고객사 정보 수정
    customer_infor = {'name': '주식회사 대덕테크',
                      'regNo': '894-88-00927',
                      'ceoName': '최진',
                      'address': '울산광역시 남구 봉월로 22, 309호(신정동, 임창베네시안)',
                      'business_type': '서비스업',
                      'business_item': '시스템개발 및 관리, 컴퓨터프로그래밍, 시스템종합관리업',
                      'dt_reg': '2018-03-12',
                      'dt_payment': '25'
                      }
    r = s.post(settings.CUSTOMER_URL + 'update_customer', json=customer_infor)
    result.append({'url': r.url, 'POST':customer_infor, 'STATUS': r.status_code, 'R': r.json()})

    print(result)
    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def customer_test_step_5(request):
    """
    [[고객 서버 시험]] Step 5: 발주사, 협력사 등록, 수정, 리스트
    - 발주사 등록
    - 협력사 등록
    - 발주, 협력사 리스트
    - 협력사 수정
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    result = []

    # 고객 : 로그인
    login_data = {"login_id": "thinking",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url': r.url, 'POST':login_data, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 발주사 등록
    relationship_infor = {'type': 10,    # 10 : 발주사, 12 : 협력사
                          'corp_name': '대덕기공',
                          'staff_name': '엄원섭',
                          'staff_pNo': '010-3877-4105',
                          'staff_email': 'wonsup.eom@daeducki.com',
                          }
    r = s.post(settings.CUSTOMER_URL + 'reg_relationship', json=relationship_infor)
    result.append({'url': r.url, 'POST':relationship_infor, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 협력사 등록
    relationship_infor = {'type': 12,    # 10 : 발주사, 12 : 협력사
                          'corp_name': '주식회사 살구',
                          'staff_name': '정소원',
                          'staff_pNo': '010-7620-5918',
                          'staff_email': 'salgoo.ceo@gmail.com',
                          }
    r = s.post(settings.CUSTOMER_URL + 'reg_relationship', json=relationship_infor)
    result.append({'url': r.url, 'POST':relationship_infor, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 발주, 협력사 리스트
    get_parameter = {'is_partner': 'YES',
                     'is_orderer': 'YES'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_relationship', json=get_parameter)
    result.append({'url': r.url, 'GET':get_parameter, 'STATUS': r.status_code, 'R': r.json()})
    partner_id = r.json()['partners'][0]['id']

    # 고객 : 협력사 수정
    relationship_infor = {'corp_id': 'ox9fRbgDQ-PxgCiqoDLYhQ==',    # 발주사 or 협력사 id 의 암호화된 값
                          'corp_name': '주식회사 살구',
                          'staff_name': '김미진 대리',
                          'staff_pNo': '010-8876-7614',
                          'staff_email': 'midal@salgooc.com',
                          'manager_name': '정소원',      # 선택
                          'manager_pNo': '010-7620-5918',  # 선택
                          'manager_email': 'salgoo.ceo@gmail.com', # 선택
                          'name':'(주)살구',      # 상호 - 선택
                          'regNo':'123-000000-12',    # 사업자등록번호 - 선택
                          'ceoName':'정소원',         # 이름(대표자) - 선택
                          'address':'울산시 중구 돋질로 20',   # 사업장소재지 - 선택
                          'business_type':'서비스',      # 업태 - 선택
                          'business_item':'정보통신',    # 종목 - 선택
                          'dt_reg':'2018-12-05',       # 사업자등록일 - 선택
                          }
    r = s.post(settings.CUSTOMER_URL + 'update_relationship', json=relationship_infor)
    result.append({'url': r.url, 'POST':relationship_infor, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 협력사 상세 정보
    get_parameter = {'relationship_id':partner_id}
    r = s.post(settings.CUSTOMER_URL + 'detail_relationship', json=get_parameter)
    result.append({'url': r.url, 'GET':get_parameter, 'STATUS': r.status_code, 'R': r.json()})

    print(result)
    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def customer_test_step_6(request):
    """
    [[고객 서버 시험]] Step 6: 사업장 등록, 리스트, 수정
    - 사업장 등록
    - 사업장 리스트
    - 사업장 수정
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    result = []
    settings.REQUEST_TIME_GAP = 0.
    # 고객 : 로그인
    login_data = {"login_id": "thinking",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url': r.url, 'POST':login_data, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 직원 리스트
    staff_data = {}
    r = s.post(settings.CUSTOMER_URL + 'list_staff', json=staff_data)
    result.append({'url': r.url, 'GET':staff_data, 'STATUS': r.status_code, 'R': r.json()})
    manager_id = r.json()['staffs'][0]['id']  # 박종기
    new_manager_id = r.json()['staffs'][1]['id']  # 이요셉

    # 고객 : 발주, 협력사 리스트
    get_parameter = {'is_partner': 'NO',
                     'is_orderer': 'YES'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_relationship', json=get_parameter)
    result.append({'url': r.url, 'GET':get_parameter, 'STATUS': r.status_code, 'R': r.json()})
    order_id = r.json()['orderers'][0]['id']  # 첫번째 발주사

    # 고객 : 사업장 등록
    work_place = {
        'name': '대덕기공 출입시스템',  # 이름
        'manager_id': manager_id,  # 관리자 id (암호화되어 있음)
        'order_id': order_id,  # 발주사 id (암호화되어 있음)
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_work_place', json=work_place)
    result.append({'url': r.url, 'POST': work_place, 'STATUS': r.status_code, 'R': r.json()})

    work_place['name'] = 'ITNJ 출입시스템'
    r = s.post(settings.CUSTOMER_URL + 'reg_work_place', json=work_place)
    result.append({'url': r.url, 'POST': work_place, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 사업장 리스트
    get_parameter = {'name':'ITNJ',
                     'manager_name':'',
                     'manager_phone':'',
                     'order_name':''
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=get_parameter)
    result.append({'url': r.url, 'GET':get_parameter, 'STATUS': r.status_code, 'R': r.json()})
    work_place_id = r.json()['work_places'][0]['id']

    # 고객 : 사업장 수정
    work_place = {
        'work_place_id': work_place_id,
        'name': 'ITNJ',  # 이름
        'manager_id': new_manager_id  # 이요셉
    }
    r = s.post(settings.CUSTOMER_URL + 'update_work_place', json=work_place)
    result.append({'url': r.url, 'POST': work_place, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 사업장 리스트
    get_parameter = {'name':'',
                     'manager_name':'',
                     'manager_phone':'',
                     'order_name':'대덕'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=get_parameter)
    result.append({'url': r.url, 'GET':get_parameter, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 사업장 수정
    work_place = {
        'work_place_id': work_place_id,
        'name': 'ITNJ',  # 이름
        'manager_id': manager_id  # 이요셉
    }
    r = s.post(settings.CUSTOMER_URL + 'update_work_place', json=work_place)
    result.append({'url': r.url, 'POST': work_place, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 사업장 리스트
    get_parameter = {'name':'',
                     'manager_name':'',
                     'manager_phone':'',
                     'order_name':'대덕'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=get_parameter)
    result.append({'url': r.url, 'GET':get_parameter, 'STATUS': r.status_code, 'R': r.json()})

    settings.REQUEST_TIME_GAP = 5.

    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def customer_test_step_7(request):
    """
    [[고객 서버 시험]] Step 7: 사업장 업무 등록, 리스트, 수정
    - 업무 등록
    - 업무 리스트
    - 업무 수정
    - 업무 리스트
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    settings.REQUEST_TIME_GAP = 0.

    result = []

    # 고객 : 로그인
    login_data = {"login_id": "thinking",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url': r.url, 'POST':login_data, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 사업장 리스트
    get_parameter = {'name':'',
                     'manager_name':'',
                     'manager_phone':'',
                     'order_name':'대덕'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=get_parameter)
    result.append({'url': r.url, 'GET':get_parameter, 'STATUS': r.status_code, 'R': r.json()})
    logSend(r.json())
    work_place_id = r.json()['work_places'][0]['id']

    # 고객 : 직원 리스트
    staff_data = {}
    r = s.post(settings.CUSTOMER_URL + 'list_staff', json=staff_data)
    result.append({'url': r.url, 'GET':staff_data, 'STATUS': r.status_code, 'R': r.json()})
    staff_id = r.json()['staffs'][1]['id']  # 첫번째 등록 직원

    # 고객 : 발주, 협력사 리스트
    get_parameter = {'is_partner': 'YES',
                     'is_orderer': 'NO'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_relationship', json=get_parameter)
    result.append({'url': r.url, 'GET':get_parameter, 'STATUS': r.status_code, 'R': r.json()})
    partner_id = r.json()['partners'][0]['id']  # 협력사 - 주식회사 살구

    today = datetime.datetime.now() + datetime.timedelta(days=2)
    next_3_day = (today + datetime.timedelta(days=3)).strftime("%Y-%m-%d")
    next_5_day = (today + datetime.timedelta(days=5)).strftime("%Y-%m-%d")
    today = today.strftime("%Y-%m-%d")

    # 고객 : 업무 등록
    work = {
        'name': '비콘 점검',  # 생산, 포장, 경비, 미화 등
        'work_place_id': work_place_id,
        'type': '주간 오전',  # 3교대, 주간, 야간, 2교대 등 (매번 입력하는 걸로)
        'dt_begin': today,  # 업무 시작 날짜 - 오늘 날짜
        'dt_end': next_3_day,  # 업무 종료 날짜 - 오늘로 3일 뒤
        'staff_id': staff_id,
        'partner_id': partner_id
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_work', json=work)
    result.append({'url': r.url, 'POST': work, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 업무 등록
    work = {
        'name': '비콘 시험',  # 생산, 포장, 경비, 미화 등
        'work_place_id': work_place_id,
        'type': '주간 오후',  # 3교대, 주간, 야간, 2교대 등 (매번 입력하는 걸로)
        'dt_begin': next_3_day,  # 업무 시작 날짜 - 오늘로 3일 뒤
        'dt_end': next_5_day,  # 업무 종료 날짜 - 오늘로 5일 뒤
        'staff_id': staff_id,
        'partner_id': partner_id
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_work', json=work)
    result.append({'url': r.url, 'POST': work, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 업무 리스트
    get_parameter = {'name'            : '',
                     'work_place_name' : '',
                     'type'            : '',
                     'contractor_name' : '',
                     'staff_name'      : '',
                     'staff_pNo'       : '',
                     'dt_begin'        : '',
                     'dt_end'          : '',
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work', json=get_parameter)
    result.append({'url': r.url, 'GET':get_parameter, 'STATUS': r.status_code, 'R': r.json()})

    work_id_1 = r.json()['works'][0]['id']
    work_id_2 = r.json()['works'][1]['id']
    # 고객 : 업무 수정
    work = {
        'work_id': work_id_1,
        'dt_end': next_5_day,  # 업무 종료 날짜
        'partner_id': partner_id
    }
    r = s.post(settings.CUSTOMER_URL + 'update_work', json=work)
    result.append({'url': r.url, 'POST': work, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 업무 수정
    work = {
        'work_id': work_id_2,
        'dt_end': next_3_day,  # 업무 종료 날짜
        'partner_id': 'gDoPqy_Pea6imtYYzWrEXQ=='
    }
    r = s.post(settings.CUSTOMER_URL + 'update_work', json=work)
    result.append({'url': r.url, 'POST': work, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 업무 리스트
    get_parameter = {'work_place_id': work_place_id,
                     'dt_begin':'2019-02-25',
                     'dt_end':today,
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_from_work_place', json=get_parameter)
    result.append({'url': r.url, 'GET':get_parameter, 'STATUS': r.status_code, 'R': r.json()})

    settings.REQUEST_TIME_GAP = 5.

    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def customer_test_step_8(request):
    """
    [[고객 서버 시험]] Step 8: 근로자 등록
    - 근로자 등록 (고객 서버)
    - 근로자 알림 확인 (근로자 서버)
    - 근로자 수락 / 거부 (근로자 서버)
    -
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    settings.REQUEST_TIME_GAP = 0.
    result = []

    # 고객 : 로그인
    login_data = {"login_id": "thinking",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url': r.url, 'POST':login_data, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 사업장 리스트
    get_parameter = {'name':'',
                     'manager_name':'',
                     'manager_phone':'',
                     'order_name':'대덕'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=get_parameter)
    result.append({'url': r.url, 'POST':get_parameter, 'STATUS': r.status_code, 'R': r.json()})
    logSend(result)
    logSend(result)
    work_place_id = r.json()['work_places'][0]['id']

    # 고객 : 업무 리스트
    get_parameter = {'work_place_id':work_place_id,
                     'dt_begin':'2019-02-25',
                     'dt_end':'2019-02-27',
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_from_work_place', json=get_parameter)
    result.append({'url': r.url, 'POST':get_parameter, 'STATUS': r.status_code, 'R': r.json()})
    work_id = r.json()['works'][0]['id']

    # 업무 시작 날짜 수정 - 근로자 응답 확인을 시험하기 위해 업무 시작 날짜를 오늘 이후로 변경
    begin_day = (datetime.datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    end_day = (datetime.datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
    update_work = {
        'work_id': work_id,  # 필수
        'dt_begin': begin_day,  # 근무 시작일
        'dt_end': end_day,  # 근로자 한명의 업무 종료일을 변경한다. (업무 인원 전체는 업무에서 변경한다.)
    }
    r = s.post(settings.CUSTOMER_URL + 'update_work', json=update_work)
    result.append({'url': r.url, 'POST':update_work, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 근로자 등록
    next_4_day = datetime.datetime.now() + datetime.timedelta(days=4)
    next_4_day = next_4_day.strftime('%Y-%m-%d') + ' 19:00:00'
    employee = {
        'work_id':work_id,
        'dt_answer_deadline':next_4_day,
        'phone_numbers':['010-2557-3555', '010-1111-2222', '010-3333-44', '010-4444-5555', '010-1111-3333', '010-4444-7777']
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_employee', json=employee)
    result.append({'url': r.url, 'POST':employee, 'STATUS': r.status_code, 'R': r.json()})

    names = ["양만춘", "강감찬", "이순신", "안중근"]
    arr_phone_no = ['010-1111-2222', '010-4444-5555', '010-1111-3333', '010-4444-7777']
    for pNo in arr_phone_no:
        # 근로자 : 인증번호 요청
        phone_no = {'phone_no' : pNo}
        settings.IS_TEST = True
        r = s.post(settings.EMPLOYEE_URL + 'certification_no_to_sms', json=phone_no)
        settings.IS_TEST = False
        result.append({'url': r.url, 'POST':phone_no, 'STATUS': r.status_code, 'R': r.json()})

        # 근로자 : 근로자 확인
        certification_data = {
                'phone_no' : pNo,
                'cn' : '201903',
                'phone_type' : 'A', # 안드로이드 폰
                'push_token' : 'push token'
            }
        settings.IS_TEST = True
        r = s.post(settings.EMPLOYEE_URL + 'reg_from_certification_no', json=certification_data)
        settings.IS_TEST = False
        result.append({'url': r.url, 'POST':certification_data, 'STATUS': r.status_code, 'R': r.json()})
        logSend(r.json())

        employee_info = {
            'passer_id': r.json()['id'],
            'name': names[arr_phone_no.index(pNo)],
            'bank': '기업은행',
            'bank_account': '12300000012000',
            'pNo': pNo,  # 추후 SMS 확인 절차 추가
        }
        r = s.post(settings.EMPLOYEE_URL + 'update_my_info', json=employee_info)
        result.append({'url': r.url, 'POST':employee_info, 'STATUS': r.status_code, 'R': r.json()})

    # 근로자 리스트 - 전화번호에 1111 가 포함된 근로자
    phone_no = {
        'phone_no':'1111'
    }
    r = s.post(settings.EMPLOYEE_URL + 'passer_list', json=phone_no)
    result.append({'url': r.url, 'POST':phone_no, 'STATUS': r.status_code, 'R': r.json()})
    passers = r.json()['passers']

    if len(passers) > 0:
        for ex_passer in passers:
            # 근로자 : 알림 확인
            passer = {'passer_id': ex_passer['id']}
            r = s.post(settings.EMPLOYEE_URL + 'notification_list', json=passer)
            result.append({'url': r.url, 'GET': passer, 'STATUS': r.status_code, 'R': r.json()})
            print(r.json())
            if len(r.json()['notifications']) == 0:
                # 알림이 없는 출입자 - 대상이 아님
                continue
            notification_id = r.json()['notifications'][0]['id']

            # 근로자 : 업무 수락 / 거절
            accept = {
                'passer_id': ex_passer['id'],  # 암호화된 값임
                'notification_id': notification_id,
                'is_accept': 0  # 1 : 업무 수락, 0 : 업무 거부
            }
            r = s.post(settings.EMPLOYEE_URL + 'notification_accept', json=accept)
            result.append({'url': r.url, 'POST':accept, 'STATUS': r.status_code, 'R': r.json()})

    # # 근로자 리스트
    # phone_no = {
    #     'phone_no':'3555'
    # }
    # r = s.post(settings.EMPLOYEE_URL + 'passer_list', json=phone_no)
    # result.append({'url': r.url, 'POST':phone_no, 'STATUS': r.status_code, 'R': r.json()})
    # passer_id = r.json()['passers'][0]['id']
    #
    # #
    # # 근로자 등록과정
    # #
    # # << work : end 날짜 때문에 work 없는 경우 처리 필요
    # #
    #
    # # 근로자 : 알림 확인
    # passer = {'passer_id':passer_id}
    # r = s.post(settings.EMPLOYEE_URL + 'notification_list', json=passer)
    # result.append({'url': r.url, 'GET':passer, 'STATUS': r.status_code, 'R': r.json()})
    # notification_id = r.json()['notifications'][0]['id']
    #
    # # 근로자 : 업무 수락 / 거절
    # accept = {
    #     'passer_id': passer_id,  # 암호화된 값임
    #     'notification_id': notification_id,
    #     'is_accept': 0  # 1 : 업무 수락, 0 : 업무 거부
    # }
    # r = s.post(settings.EMPLOYEE_URL + 'notification_accept', json=accept)
    # result.append({'url': r.url, 'POST':accept, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 근로자 리스트
    work = {'work_id': work_id,
            'is_working_history':'YES'
            }
    r = s.post(settings.CUSTOMER_URL + 'list_employee', json=work)
    result.append({'url': r.url, 'POST': work, 'STATUS': r.status_code, 'R': r.json()})

    # 근로자 리스트 - 전화번호에 4444 가 포함된 근로자
    phone_no = {
        'phone_no':'4444'
    }
    r = s.post(settings.EMPLOYEE_URL + 'passer_list', json=phone_no)
    result.append({'url': r.url, 'POST':phone_no, 'STATUS': r.status_code, 'R': r.json()})
    passers = r.json()['passers']

    if len(passers) > 0:
        for ex_passer in passers:
            # 근로자 : 알림 확인
            passer = {'passer_id':ex_passer['id']}
            r = s.post(settings.EMPLOYEE_URL + 'notification_list', json=passer)
            result.append({'url': r.url, 'GET':passer, 'STATUS': r.status_code, 'R': r.json()})
            print(r.json())
            if len(r.json()['notifications']) == 0:
                # 알림이 없는 출입자 - 대상이 아님
                continue
            notification_id = r.json()['notifications'][0]['id']

            # 근로자 : 업무 수락 / 거절
            accept = {
                'passer_id': ex_passer['id'],  # 암호화된 값임
                'notification_id': notification_id,
                'is_accept': 1  # 1 : 업무 수락, 0 : 업무 거부
            }
            r = s.post(settings.EMPLOYEE_URL + 'notification_accept', json=accept)
            result.append({'url': r.url, 'POST': accept, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 근로자 리스트
    work = {'work_id': work_id,
            'is_working_history':'YES'
            }
    r = s.post(settings.CUSTOMER_URL + 'list_employee', json=work)
    result.append({'url': r.url, 'POST': work, 'STATUS': r.status_code, 'R': r.json()})
    employees = r.json()['employees']

    employee_id: int
    for employee in employees:
        # print('--- ', employee)
        if employee['pNo'] == '010-33-3344':
            employee_id = employee['id']
            # employee_dt_begin = employee['dt_begin']
            break
    # print(employee_id, employee_dt_begin)
    # 근로자 정보 수정 - 잘못된 화번호 수정
    update_employee = {
        'employee_id': employee_id,  # 필수
        'phone_no': '010-3333-4444',  # 전화번호가 잘못되었을 때 변경
        'dt_answer_deadline': (datetime.datetime.now() + datetime.timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S"), # 전화번호 바꿀 때 필수
        # 'dt_begin': '2019-03-09',  # 근무 시작일
        # 'dt_end': '2019-05-31',  # 근로자 한명의 업무 종료일을 변경한다. (업무 인원 전체는 업무에서 변경한다.)
    }
    r = s.post(settings.CUSTOMER_URL + 'update_employee', json=update_employee)
    result.append({'url': r.url, 'POST': update_employee, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 근로자 리스트
    work = {'work_id': work_id,
            'is_working_history':'YES'
            }
    r = s.post(settings.CUSTOMER_URL + 'list_employee', json=work)
    result.append({'url': r.url, 'POST': work, 'STATUS': r.status_code, 'R': r.json()})

    # 업무 시작 날짜 수정 - 근로자 응답 확인을 시험하기 위해 업무 시작 날짜를 오늘 이전으로 변경
    begin_day = (datetime.datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    update_work = {
        'work_id': work_id,  # 필수
        'dt_begin': begin_day,  # 근무 시작일
    }
    r = s.post(settings.CUSTOMER_URL + 'update_work', json=update_work)
    result.append({'url': r.url, 'POST': update_work, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 근로자 리스트
    work = {'work_id': work_id,
            'is_working_history':'YES'
            }
    r = s.post(settings.CUSTOMER_URL + 'list_employee', json=work)
    result.append({'url': r.url, 'POST': work, 'STATUS': r.status_code, 'R': r.json()})

    settings.REQUEST_TIME_GAP = 5.
    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def customer_test_step_9(request):
    """
    [[고객 서버 시험]] Step 8: 근로자 시험 디버깅
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    settings.REQUEST_TIME_GAP = 0.
    result = []

    # 고객 : 로그인
    login_data = {"login_id": "thinking",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    # result.append({'url': r.url, 'POST':login_data, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 사업장 리스트
    get_parameter = {'name': '',
                     'manager_name': '',
                     'manager_phone': '',
                     'order_name': '대덕'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=get_parameter)
    # result.append({'url': r.url, 'POST':get_parameter, 'STATUS': r.status_code, 'R': r.json()})
    # 첫번째 사업장을 시험 대상으로 설정
    work_place_id = r.json()['work_places'][0]['id']

    # 고객 : 업무 리스트
    get_parameter = {'work_place_id': work_place_id,
                     'dt_begin': '2019-02-25',
                     'dt_end': '2019-02-27',
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_from_work_place', json=get_parameter)
    # result.append({'url': r.url, 'POST':get_parameter, 'STATUS': r.status_code, 'R': r.json()})
    # 두번째 업무를 시험 대상으로 설정
    work_id = r.json()['works'][1]['id']

    # 업무 시작 날짜 수정 - 근로자 응답 확인을 시험하기 위해 업무 시작 날짜를 오늘 이후로 변경
    begin_day = (datetime.datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    end_day = (datetime.datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
    update_work = {
        'work_id': work_id,  # 필수
        'dt_begin': begin_day,  # 근무 시작일
        'dt_end': end_day,  # 근로자 한명의 업무 종료일을 변경한다. (업무 인원 전체는 업무에서 변경한다.)
    }
    r = s.post(settings.CUSTOMER_URL + 'update_work', json=update_work)
    result.append({'url': r.url, 'POST':update_work, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 근로자 등록
    next_4_day = datetime.datetime.now() + datetime.timedelta(days=4)
    next_4_day = next_4_day.strftime('%Y-%m-%d') + ' 19:00:00'
    employee = {
        'work_id':work_id,
        'dt_answer_deadline':next_4_day,
        'phone_numbers':['010-3333-44', '01-1111-4444']
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_employee', json=employee)
    result.append({'url': r.url, 'POST':employee, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 근로자 리스트
    work = {'work_id': work_id,
            'is_working_history':'YES'
            }
    r = s.post(settings.CUSTOMER_URL + 'list_employee', json=work)
    result.append({'url': r.url, 'POST': work, 'STATUS': r.status_code, 'R': r.json()})
    employees = r.json()['employees']

    employee_dic = {'010333344':'', '0111114444':''}
    employee_pNo = {'010333344':'010-3333-4444', '0111114444':'010-1111-4444'}
    for employee in employees:
        print('--- ', employee)
        if no_only_phone_no(employee['pNo']) in employee_dic.keys():
            employee_dic[no_only_phone_no(employee['pNo'])] = employee['id']
    print(employee_dic)

    # 근로자 정보 수정 - 잘못된 전화번호 수정
    dt_answer_deadline = (datetime.datetime.now() + datetime.timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")  # 전화번호 바꿀 때 필수
    for employee_key in employee_dic.keys():
        update_employee = {
            'employee_id': employee_dic[employee_key],  # 필수
            'phone_no': employee_pNo[employee_key],  # 전화번호가 잘못되었을 때 변경
            'dt_answer_deadline':dt_answer_deadline
            # 'dt_begin': '2019-03-09',  # 근무 시작일
            # 'dt_end': '2019-05-31',  # 근로자 한명의 업무 종료일을 변경한다. (업무 인원 전체는 업무에서 변경한다.)
        }
        r = s.post(settings.CUSTOMER_URL + 'update_employee', json=update_employee)
        result.append({'url': r.url, 'POST': update_employee, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 근로자 리스트
    work = {'work_id': work_id,
            'is_working_history':'YES'
            }
    r = s.post(settings.CUSTOMER_URL + 'list_employee', json=work)
    result.append({'url': r.url, 'POST': work, 'STATUS': r.status_code, 'R': r.json()})

    settings.REQUEST_TIME_GAP = 5.
    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def customer_test_step_A(request):
    """
    [[고객 서버 시험]] Step 10: 8명의 근로자를 업무에 등록, 앱설치, 업무 확인, 업무 수락하는 과정 시험
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    settings.REQUEST_TIME_GAP = 0.
    result = []

    # 고객 : 로그인
    login_data = {"login_id": "thinking",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    # result.append({'url': r.url, 'POST':login_data, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 사업장 리스트
    get_parameter = {'name':'',
                     'manager_name':'',
                     'manager_phone':'',
                     'order_name':'대덕'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=get_parameter)
    # result.append({'url': r.url, 'POST':get_parameter, 'STATUS': r.status_code, 'R': r.json()})
    work_place_id = r.json()['work_places'][0]['id']

    # 고객 : 업무 리스트
    get_parameter = {'work_place_id':work_place_id,
                     'dt_begin':'2019-02-25',
                     'dt_end':'2019-02-27',
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_from_work_place', json=get_parameter)
    result.append({'url': r.url, 'POST':get_parameter, 'STATUS': r.status_code, 'R': r.json()})
    work_id = r.json()['works'][1]['id']

    # 업무 시작 날짜 수정 - 업무가 시작된 것으로 처리하기 위하여 시간을 수정
    begin_day = (datetime.datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d") # 10일 전부터 일을 하고 있음
    end_day = (datetime.datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
    update_work = {
        'work_id': work_id,  # 필수
        'dt_begin': begin_day,  # 근무 시작일
        'dt_end': end_day,  # 근로자 한명의 업무 종료일을 변경한다. (업무 인원 전체는 업무에서 변경한다.)
    }
    r = s.post(settings.CUSTOMER_URL + 'update_work', json=update_work)
    result.append({'url': r.url, 'POST':update_work, 'STATUS': r.status_code, 'R': r.json()})

    # 근로자 모두 등록 상태에 업무 수락 상태로 변경
    names = ["김좌진", "윤봉", "안창호", "이시영", "계백", "을지문덕", "권율", "최영"]
    arr_phone_no = ['010-3355-1001', '010-3355-1002', '010-3355-1003', '010-3355-1004', '010-3355-2001', '010-3355-2002', '010-3355-2003', '010-3355-2004']

    # 고객 : 고객웹에서 근로자 등록
    next_4_day = datetime.datetime.now() + datetime.timedelta(days=4)
    next_4_day = next_4_day.strftime('%Y-%m-%d') + ' 19:00:00'
    employee = {
        'work_id':work_id,
        'dt_answer_deadline':next_4_day,
        'phone_numbers':arr_phone_no
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_employee', json=employee)
    result.append({'url': r.url, 'POST':employee, 'STATUS': r.status_code, 'R': r.json()})
    duplicate_pNo = r.json()['duplicate_pNo']
    print(duplicate_pNo)

    for pNo in arr_phone_no:

        # 근로자 : 앱 설치 후 인증번호 요청
        phone_no = {'phone_no' : pNo}
        settings.IS_TEST = True
        r = s.post(settings.EMPLOYEE_URL + 'certification_no_to_sms', json=phone_no)
        settings.IS_TEST = False
        # result.append({'url': r.url, 'POST':phone_no, 'STATUS': r.status_code, 'R': r.json()})

        # 근로자 : 인증
        certification_data = {
                'phone_no' : pNo,
                'cn' : '201903',
                'phone_type' : 'A', # 안드로이드 폰
                'push_token' : 'push token'
            }
        r = s.post(settings.EMPLOYEE_URL + 'reg_from_certification_no', json=certification_data)
        # result.append({'url': r.url, 'POST':certification_data, 'STATUS': r.status_code, 'R': r.json()})
        employee = r.json()
        employee_id = employee['id'] # 등록 근로자 id (passer_id)
        print(employee)

        if (not 'name' in employee) and ('bank_list' in employee):
            # 처음 설치한 경우 : 자기 정보 수정
            employee_info = {
                'passer_id': employee_id,
                'name': names[arr_phone_no.index(pNo)],
                'bank': '기업은행',
                'bank_account': '1230000001200%d' % arr_phone_no.index(pNo),
                'pNo': pNo,  # 추후 SMS 확인 절차 추가
            }
            r = s.post(settings.EMPLOYEE_URL + 'update_my_info', json=employee_info)
            # result.append({'url': r.url, 'POST':employee_info, 'STATUS': r.status_code, 'R': r.json()})

        # 근로자 : 알림 확인
        passer = {'passer_id': employee_id}
        r = s.post(settings.EMPLOYEE_URL + 'notification_list', json=passer)
        result.append({'url': r.url, 'GET': passer, 'STATUS': r.status_code, 'R': r.json()})
        print(r.json())
        if len(r.json()['notifications']) == 0:
            # 알림이 없는 출입자 - 대상이 아님
            continue
        notification_id = r.json()['notifications'][0]['id']

        # 근로자 : 업무 수락 / 거절
        accept = {
            'passer_id': employee_id,  # 암호화된 값임
            'notification_id': notification_id,
            'is_accept': 1  # 1 : 업무 수락, 0 : 업무 거부
        }
        r = s.post(settings.EMPLOYEE_URL + 'notification_accept', json=accept)
        result.append({'url': r.url, 'POST': accept, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 근로자 리스트
    work = {'work_id': work_id,
            'is_working_history':'YES'
            }
    r = s.post(settings.CUSTOMER_URL + 'list_employee', json=work)
    result.append({'url': r.url, 'POST': work, 'STATUS': r.status_code, 'R': r.json()})

    settings.REQUEST_TIME_GAP = 5.
    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


def check_test_key(rqst) ->bool:
    return True


@cross_origin_read_allow
def employee_test_step_1(request):
    """
    [[근로자 시험]] Step 1: 근로자 서버 table all clear
    - check version
    - 전화번호 인증 reg_employee
    -
    http://0.0.0.0:8000/operation/employee_test_step_1?key=vChLo3rsRAl0B4NNuaZOsg
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    result = []

    # 근로자 서버 테이블 삭제 및 초기화
    key = {'key':rqst['key']}
    r = requests.post(settings.EMPLOYEE_URL + 'table_reset_and_clear_for_operation', json=key)
    result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})

    print(result)
    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def employee_test_step_2(request):
    """
    [[근로자 서버 시험]] Step 2: 고객사 생성 및 담당자 생성, 로그인, 담당자 정보 수정
    1. 근로자 table all deleted, 고객사 table all deleted
    2. 고객사 생성 : 이제체크
    3. 담당자 정보 변경: think / parkjong / 이사
    http://0.0.0.0:8000/operation/employee_test_step_2?key=vChLo3rsRAl0B4NNuaZOsg
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    result = []

    # 운영 로그인
    login_data = {"id": "thinking",
                  "pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.OPERATION_URL + 'login', json=login_data)
    result.append({'url': r.url, 'POST':login_data, 'STATUS': r.status_code, 'R': r.json()})
    if r.status_code == 530:
        staff = Staff.objects.get(id=1)
        staff.login_pw = hash_SHA256(login_data["pw"])
        staff.save()
        r = s.post(settings.OPERATION_URL + 'login', json=login_data)
        result.append({'url': r.url, 'POST': login_data, 'STATUS': r.status_code, 'R': r.json()})

    # 고객업체 생성
    customer_data = {'customer_name': '이지체크',
                     'staff_name': '박종기',
                     'staff_pNo': '010-2557-3555',
                     'staff_email': 'thinking@ddtechi.com'
                     }
    settings.IS_TEST = True  # sms pass
    r = s.post(settings.OPERATION_URL + 'reg_customer', json=customer_data)
    settings.IS_TEST = False  # sms pass
    result.append({'url': r.url, 'POST':customer_data, 'STATUS': r.status_code, 'R': r.json()})
    init_login_id = r.json()['message'][1]
    logSend(init_login_id)
    # 고객 : 로그인
    login_data = {"login_id": init_login_id,
                  "login_pw": "happy_day!!!"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url': r.url, 'POST':login_data, 'STATUS': r.status_code, 'R': r.json()})

    r = s.post(settings.CUSTOMER_URL + 'list_staff', json={})
    result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})
    staffs = r.json()['staffs']
    for staff in staffs:
        if staff['login_id'] == init_login_id:
            owner_staff_id = staff['id']
            break

    if r.status_code == 200:
        # 고객 : 자기 정보 수정 - login_id,
        staff_data = {'staff_id':owner_staff_id,
                      'new_login_id': 'think',
                      'before_pw': 'happy_day!!!',
                      'login_pw':'parkjong',
                      'position':'이사'
                      }
        r = s.post(settings.CUSTOMER_URL + 'update_staff', json=staff_data)
        result.append({'url': r.url, 'POST': staff_data, 'STATUS': r.status_code, 'R': r.json()})

        # 고객 : 로그인
        login_data = {"login_id": "think",
                      "login_pw": "parkjong"
                      }
        s = requests.session()
        r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
        result.append({'url': r.url, 'POST': login_data, 'STATUS': r.status_code, 'R': r.json()})

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def employee_test_step_3(request):
    """
    [[근로자 서버 시험]] Step 3: 발주사 등록, 직원 등록
    1. 발주사 등록 : 울산광역시
    2. 직원 등록 : ...
    3. 사업장 등록 : 태화강
    4. 업무 등록 : 공원 감시(3/1), 공원 청소(next_5 day)

    http://0.0.0.0:8000/operation/employee_test_step_3?key=vChLo3rsRAl0B4NNuaZOsg
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    result = []
    # 고객 : 로그인
    login_data = {"login_id": "think",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url': r.url, 'POST': login_data, 'STATUS': r.status_code, 'R': r.json()})
    co_id = r.json()['company_general']['co_id']
    # 고객 : 발주사 등록
    relationship_infor = {'type': 10,    # 10 : 발주사, 12 : 협력사
                          'corp_name': '울산광역시',
                          'staff_name': '송철호',
                          'staff_pNo': '052-120',
                          'staff_email': 'ulsan@email.com',
                          }
    r = s.post(settings.CUSTOMER_URL + 'reg_relationship', json=relationship_infor)
    result.append({'url': r.url, 'POST':relationship_infor, 'STATUS': r.status_code, 'R': r.json()})

    r = s.post(settings.CUSTOMER_URL + 'list_relationship', json={'is_orderer':'YES', 'is_partner':'NO'})
    result.append({'url': r.url, 'POST':{'is_orderer':'YES', 'is_partner':'NO'}, 'STATUS': r.status_code, 'R': r.json()})
    order_id = r.json()['orderers'][0]['id']

    # 고객 : 직원 등록
    # staffs = [['최   진', '010-2073-6959', '경영지원실장', '대덕기공']]

    staffs = [['최재환', '010-4871-8362', '전무이사', '대덕기공'],
              ['이석호', '010-3544-6840', '상무이사', '대덕기공'],
              ['엄원섭', '010-3877-4105', '총무이사', '대덕기공'],
              ['최   진', '010-2073-6959', '경영지원실장', '대덕기공'],
              ['우종복', '010-2436-6966', '경영지원실 차장', '대덕기공'],
              ['서경화', '010-8594-3858', '경리차장', '대덕기공'],
              ['김진오', '010-8513-3300', '관리과장', '대덕기공'],
              ['김정석', '010-9323-5627', '총무과장', '대덕기공'],
              ['황지민', '010-5197-6214', '총무사원', '대덕기공'],
              ['권호택', '010-5359-6869', '관리이사', '대덕산업'],
              ['신철관', '010-7542-4017', '관리차장', '대덕산업'],
              ['김기홍', '010-7151-1119', '관리차장', '대덕산업'],
              ['김동욱', '010-5280-3275', '솔베이 관리차장', '대덕산업'],
              ['김현정', '010-5583-8021', '총무사원', '대덕산업'],
              ['엄상경', '010-8538-4106', '관리부장', 'TS'],
              ['김종민', '010-7290-8113', '관리차장', 'TS'],
              ['임유빈', '010-7255-4888', '총무사원', 'TS'],
              ['박용수', '010-2100-9864', '상무이사', 'F&S'],
              ['전미숙', '010-5556-0163', '관리차장', 'F&S'],
              ['김유신', '010-7725-9293', '대      리', 'F&S'],
              ['김윤정', '010-9305-8981', '경리사원', 'F&S'],
              ['신선경', '010-3127-4024', '롯데케미칼1공장', 'F&S'],
              ['전애리', '010-4224-8640', '롯데케미칼2공장', 'F&S'],
              ['김유경', '010-9342-0997', '후     성', 'F&S'],
              ['김미경', '010-2397-6143', 'BASF-화성', 'F&S'],
              ['김은영', '010-2061-9677', 'BASF-안료', 'F&S']]
    index = 1
    for staff in staffs:
        staff_data = {'name': staff[0].replace(' ', ''),
                      'login_id': 'staff_' + str(index),
                      'position': staff[2].replace(' ', ''),
                      'department': staff[3],  # option 비워서 보내도 됨
                      'pNo': staff[1],
                      'email': 'unknown@email.com',
                      }
        r = s.post(settings.CUSTOMER_URL + 'reg_staff', json=staff_data)
        index += 1
        result.append({'url': r.url, 'POST':staff_data, 'STATUS': r.status_code, 'R': r.json()})

    r = s.post(settings.CUSTOMER_URL + 'list_staff', json={})
    # result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})
    staffs = r.json()['staffs']
    for staff in staffs:
        if staff['name'] == '최진':
            manager_id = staff['id']
            break

    # 고객 : 사업장 등록
    work_place = {
        'name': '태화강',  # 이름
        'manager_id': manager_id,
        'order_id': order_id
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_work_place', json=work_place)
    result.append({'url': r.url, 'POST': work_place, 'STATUS': r.status_code, 'R': r.json()})

    work_place_infor = { 'name':'',
                         'manager_name':'',
                         'manager_phone':'',
                         'order_name':''
                         }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=work_place_infor)
    result.append({'url': r.url, 'POST': work_place_infor, 'STATUS': r.status_code, 'R': r.json()})
    work_place_id = r.json()['work_places'][0]['id']

    today = datetime.datetime.now() + datetime.timedelta(days=2)
    next_3_day = (today + datetime.timedelta(days=3)).strftime("%Y-%m-%d")
    next_5_day = (today + datetime.timedelta(days=5)).strftime("%Y-%m-%d")
    today = today.strftime("%Y-%m-%d")

    for staff in staffs:
        if staff['name'] == '박종기':
            staff_id = staff['id']
            break

    # 고객 : 업무 등록
    work = {
        'name': '공원 감시',
        'work_place_id': work_place_id,
        'type': '주간 오전',
        'dt_begin': '2019-03-01',
        'dt_end': '2019-07-31',  # 업무 종료 날짜 - 오늘로 3일 뒤
        'staff_id': staff_id,
        'partner_id': co_id,
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_work', json=work)
    result.append({'url': r.url, 'POST': work, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 업무 등록
    work = {
        'name': '공원 청소',
        'work_place_id': work_place_id,
        'type': '주간 오후',
        'dt_begin': next_5_day,
        'dt_end': '2019-07-31',  # 업무 종료 날짜 - 오늘로 3일 뒤
        'staff_id': staff_id,
        'partner_id': co_id,
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_work', json=work)
    result.append({'url': r.url, 'POST': work, 'STATUS': r.status_code, 'R': r.json()})
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def employee_test_step_4(request):
    """
    [[근로자 서버 시험]] Step 4: 근로자 등록
    1. 고객사 웹에서 전화번호로 근로자 등록
    2. 각 근로자 인증번호 요청
    3. 각 근로자 인증 후 자기 정보 변경
    4. 각 근로자 업무 요청 수락

    http://0.0.0.0:8000/operation/employee_test_step_4?key=vChLo3rsRAl0B4NNuaZOsg
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    result = []
    # 고객 : 로그인
    login_data = {"login_id": "think",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url': r.url, 'POST': login_data, 'STATUS': r.status_code, 'R': r.json()})

    work_place_infor = { 'name':'',
                         'manager_name':'',
                         'manager_phone':'',
                         'order_name':''
                         }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=work_place_infor)
    result.append({'url': r.url, 'POST': work_place_infor, 'STATUS': r.status_code, 'R': r.json()})
    work_place_id = r.json()['work_places'][0]['id']

    work_infor = {'work_place_id':work_place_id,
                  'dt_begin':'',
                  'dt_end':''
                  }
    r = s.post(settings.CUSTOMER_URL + 'list_work_from_work_place', json=work_infor)
    result.append({'url': r.url, 'POST': work_infor, 'STATUS': r.status_code, 'R': r.json()})
    work_id = r.json()['works'][0]['id']

    # 근로자 등록
    # employees = [['최   진', '010-2073-6959', '경영지원실장', '대덕기공']]

    employees = [['최재환', '010-4871-8362', '전무이사', '대덕기공'],
              ['이석호', '010-3544-6840', '상무이사', '대덕기공'],
              ['엄원섭', '010-3877-4105', '총무이사', '대덕기공'],
              ['최   진', '010-2073-6959', '경영지원실장', '대덕기공'],
              ['우종복', '010-2436-6966', '경영지원실 차장', '대덕기공'],
              ['서경화', '010-8594-3858', '경리차장', '대덕기공'],
              ['김진오', '010-8513-3300', '관리과장', '대덕기공'],
              ['김정석', '010-9323-5627', '총무과장', '대덕기공'],
              ['황지민', '010-5197-6214', '총무사원', '대덕기공'],
              ['권호택', '010-5359-6869', '관리이사', '대덕산업'],
              ['신철관', '010-7542-4017', '관리차장', '대덕산업'],
              ['김기홍', '010-7151-1119', '관리차장', '대덕산업'],
              ['김동욱', '010-5280-3275', '솔베이 관리차장', '대덕산업'],
              ['김현정', '010-5583-8021', '총무사원', '대덕산업'],
              ['엄상경', '010-8538-4106', '관리부장', 'TS'],
              ['김종민', '010-7290-8113', '관리차장', 'TS'],
              ['임유빈', '010-7255-4888', '총무사원', 'TS'],
              ['박용수', '010-2100-9864', '상무이사', 'F&S'],
              ['전미숙', '010-5556-0163', '관리차장', 'F&S'],
              ['김유신', '010-7725-9293', '대      리', 'F&S'],
              ['김윤정', '010-9305-8981', '경리사원', 'F&S'],
              ['신선경', '010-3127-4024', '롯데케미칼1공장', 'F&S'],
              ['전애리', '010-4224-8640', '롯데케미칼2공장', 'F&S'],
              ['김유경', '010-9342-0997', '후     성', 'F&S'],
              ['김미경', '010-2397-6143', 'BASF-화성', 'F&S'],
              ['김은영', '010-2061-9677', 'BASF-안료', 'F&S']]

    # 고객 : 고객웹에서 근로자 등록
    next_4_day = datetime.datetime.now() + datetime.timedelta(days=4)
    next_4_day = next_4_day.strftime('%Y-%m-%d') + ' 19:00:00'
    arr_phone_no = [employee[1] for employee in employees]
    settings.IS_TEST = True
    employee = {
        'work_id':work_id,
        'dt_answer_deadline':next_4_day,
        'phone_numbers':arr_phone_no
    }
    settings.IS_TEST = True
    r = s.post(settings.CUSTOMER_URL + 'reg_employee', json=employee)
    settings.IS_TEST = False
    result.append({'url': r.url, 'POST':employee, 'STATUS': r.status_code, 'R': r.json()})

    settings.IS_LOG = False
    for employee_ex in employees:
        # 근로자 : 앱 설치 후 인증번호 요청
        phone_no = {'phone_no' : employee_ex[1]}
        settings.IS_TEST = True
        r = s.post(settings.EMPLOYEE_URL + 'certification_no_to_sms', json=phone_no)
        settings.IS_TEST = False
        # result.append({'url': r.url, 'POST':phone_no, 'STATUS': r.status_code, 'R': r.json()})

        # 근로자 : 인증
        certification_data = {
                'phone_no' : employee_ex[1],
                'cn' : '201903',
                'phone_type' : 'A', # 안드로이드 폰
                'push_token' : 'push token'
            }
        r = s.post(settings.EMPLOYEE_URL + 'reg_from_certification_no', json=certification_data)
        # result.append({'url': r.url, 'POST':certification_data, 'STATUS': r.status_code, 'R': r.json()})
        employee = r.json()
        employee_id = employee['id'] # 등록 근로자 id (passer_id)

        if (not 'name' in employee) and ('bank_list' in employee):
            # 처음 설치한 경우 : 자기 정보 수정
            employee_info = {
                'passer_id': employee_id,
                'name': employee_ex[0],
                'bank': '기업은행',
                'bank_account': '12300000012%03d' % employees.index(employee_ex),
                'pNo': employee_ex[1],  # 추후 SMS 확인 절차 추가
                'work_start': '08:30',  # 오전 오후로 표시하지 않는다.
                'working_time': '09',  # 시간 4 - 12
                'work_start_alarm': 'X',  # '-60'(한시간 전), '-30'(30분 전), 'X'(없음) 셋중 하나로 보낸다.
                'work_end_alarm': 'X',  # '-30'(30분 전), '0'(정각), 'X'(없음) 셋중 하나로 보낸다.
            }
            r = s.post(settings.EMPLOYEE_URL + 'update_my_info', json=employee_info)
            # result.append({'url': r.url, 'POST':employee_info, 'STATUS': r.status_code, 'R': r.json()})

        # 근로자 : 알림 확인
        passer = {'passer_id': employee_id}
        r = s.post(settings.EMPLOYEE_URL + 'notification_list', json=passer)
        result.append({'url': r.url, 'GET': passer, 'STATUS': r.status_code, 'R': r.json()})
        print(r.json())
        if len(r.json()['notifications']) == 0:
            # 알림이 없는 출입자 - 대상이 아님
            continue
        notification_id = r.json()['notifications'][0]['id']

        # 근로자 : 업무 수락 / 거절
        accept = {
            'passer_id': employee_id,  # 암호화된 값임
            'notification_id': notification_id,
            'is_accept': 1  # 1 : 업무 수락, 0 : 업무 거부
        }
        r = s.post(settings.EMPLOYEE_URL + 'notification_accept', json=accept)
        result.append({'url': r.url, 'POST': accept, 'STATUS': r.status_code, 'R': r.json()})

        # 근로자 출근 기록 만들기
        # 3월
        # months = {3:[32, [3, 10, 17, 24, 31]], 4:[31, [7, 14, 21, 28]], 5:[32, [5, 12, 19, 26]]}
        months = {4:[31, [7, 14, 21, 28]], 5:[32, [5, 12, 19, 26]]}
        for m_key in months.keys():
            month = m_key
            month_range = months[m_key][0]
            month_holidays = months[m_key][1]
            for day in range(1, month_range):
                if day in month_holidays:
                    continue
                beacon_data = {
                    'passer_id': employee_id,
                    'dt': '2019-%02d-%02d 08:%02d:00'%(month, day, rMin(20)),
                    'is_in': 1,  # 0: out, 1 : in
                    'major': 11001,  # 11 (지역) 001(사업장)
                    'beacons': [
                        {'minor': 11001, 'dt_begin': '2019-{}-{} 08:{}:00'.format(month, day, rMin(25)), 'rssi': -70},
                        {'minor': 11002, 'dt_begin': '2019-{}-{} 08:{}:00'.format(month, day, rMin(25)), 'rssi': -70},
                        {'minor': 11003, 'dt_begin': '2019-{}-{} 08:{}:00'.format(month, day, rMin(25)), 'rssi': -70}
                    ]
                    }
                r = s.post(settings.EMPLOYEE_URL + 'pass_reg', json=beacon_data)
                #result.append({'url': r.url, 'POST': beacon_data, 'STATUS': r.status_code, 'R': r.json()})

                button_data = {
                    'passer_id': employee_id,
                    'dt': '2019-{}-{} 08:{}:00'.format(month, day, rMin(29)),
                    'is_in': 1,  # 0: out, 1 : in
                }
                r = s.post(settings.EMPLOYEE_URL + 'pass_verify', json=button_data)
                #result.append({'url': r.url, 'POST': button_data, 'STATUS': r.status_code, 'R': r.json()})

                button_data = {
                    'passer_id': employee_id,
                    'dt': '2019-{}-{} 08:{}:00'.format(month, day, rMin(31)),
                    'is_in': 0,  # 0: out, 1 : in
                }
                r = s.post(settings.EMPLOYEE_URL + 'pass_verify', json=button_data)
                #result.append({'url': r.url, 'POST': button_data, 'STATUS': r.status_code, 'R': r.json()})

                beacon_data = {
                    'passer_id': employee_id,
                    'dt': '2019-%02d-%02d 17:%02d:00'%(month, day, rMin(40)),
                    'is_in': 0,  # 0: out, 1 : in
                    'major': 11001,  # 11 (지역) 001(사업장)
                    'beacons': [
                        {'minor': 11001, 'dt_begin': '2019-{}-{} 08:{}:00'.format(month, day, rMin(35)), 'rssi': -70},
                        {'minor': 11002, 'dt_begin': '2019-{}-{} 08:{}:00'.format(month, day, rMin(35)), 'rssi': -70},
                        {'minor': 11003, 'dt_begin': '2019-{}-{} 08:{}:00'.format(month, day, rMin(35)), 'rssi': -70}
                    ]
                    }
                r = s.post(settings.EMPLOYEE_URL + 'pass_reg', json=beacon_data)
                #result.append({'url': r.url, 'POST': beacon_data, 'STATUS': r.status_code, 'R': r.json()})
    settings.IS_LOG = True

    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def employee_test_step_5(request):
    """
    [[고객 서버 시험]] Step 9: ?
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    result = []

    login_data = {"login_id": "think",
                  "login_pw": "parkjong"
                  }
    # login_data = {"login_id": "staff_4",
    #               "login_pw": "happy_day!!!"
    #               }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url': r.url, 'POST': login_data, 'STATUS': r.status_code, 'R': r.json()})

    # 로그인한 본인의 정보 수정 기능 시험
    #
    # r = s.post(settings.CUSTOMER_URL + 'list_staff', json={})
    # result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})
    # staffs = r.json()['staffs']
    # for staff in staffs:
    #     if staff['login_id'] == login_data['login_id']:
    #         update_staff_id = staff['id']
    #         break
    #
    # # staff_data = {'staff_id': update_staff_id,
    # #               'new_login_id': 'think',
    # #               'before_pw': 'happy_day!!!',
    # #               'login_pw': 'parkjong',
    # #               'position': '이사'
    # #               }
    # staff_data = {'staff_id': update_staff_id,
    #               'new_login_id': 'ddtech_ceo',
    #               'before_pw': 'happy_day!!!',
    #               # 'login_pw': 'parkjong',
    #               'position': '대표'
    #               }
    # r = s.post(settings.CUSTOMER_URL + 'update_staff', json=staff_data)
    # result.append({'url': r.url, 'POST': staff_data, 'STATUS': r.status_code, 'R': r.json()})

    work_place_infor = { 'name':'',
                         'manager_name':'',
                         'manager_phone':'',
                         'order_name':''
                         }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=work_place_infor)
    result.append({'url': r.url, 'POST': work_place_infor, 'STATUS': r.status_code, 'R': r.json()})
    work_place_id = r.json()['work_places'][0]['id']

    work_infor = {'work_place_id':work_place_id,
                  'dt_begin':'',
                  'dt_end':''
                  }
    r = s.post(settings.CUSTOMER_URL + 'list_work_from_work_place', json=work_infor)
    result.append({'url': r.url, 'POST': work_infor, 'STATUS': r.status_code, 'R': r.json()})
    work_id = r.json()['works'][1]['id']
    logSend('work_id = ', work_id)

    # 근로자 등록
    # employees = [['최   진', '010-2073-6959', '경영지원실장', '대덕기공']]

    employees = [['최재환', '010-4871-8362', '전무이사', '대덕기공'],
              ['이석호', '010-3544-6840', '상무이사', '대덕기공'],
              ['엄원섭', '010-3877-4105', '총무이사', '대덕기공'],
              ['최   진', '010-2073-6959', '경영지원실장', '대덕기공'],
              ['우종복', '010-2436-6966', '경영지원실 차장', '대덕기공'],
              ['서경화', '010-8594-3858', '경리차장', '대덕기공'],
              ['김진오', '010-8513-3300', '관리과장', '대덕기공'],
              ['김정석', '010-9323-5627', '총무과장', '대덕기공'],
              ['황지민', '010-5197-6214', '총무사원', '대덕기공'],
              ['권호택', '010-5359-6869', '관리이사', '대덕산업'],
              ['신철관', '010-7542-4017', '관리차장', '대덕산업'],
              ['김기홍', '010-7151-1119', '관리차장', '대덕산업'],
              ['김동욱', '010-5280-3275', '솔베이 관리차장', '대덕산업'],
              ['김현정', '010-5583-8021', '총무사원', '대덕산업'],
              ['엄상경', '010-8538-4106', '관리부장', 'TS'],
              ['김종민', '010-7290-8113', '관리차장', 'TS'],
              ['임유빈', '010-7255-4888', '총무사원', 'TS'],
              ['박용수', '010-2100-9864', '상무이사', 'F&S'],
              ['전미숙', '010-5556-0163', '관리차장', 'F&S'],
              ['김유신', '010-7725-9293', '대      리', 'F&S'],
              ['김윤정', '010-9305-8981', '경리사원', 'F&S'],
              ['신선경', '010-3127-4024', '롯데케미칼1공장', 'F&S'],
              ['전애리', '010-4224-8640', '롯데케미칼2공장', 'F&S'],
              ['김유경', '010-9342-0997', '후     성', 'F&S'],
              ['김미경', '010-2397-6143', 'BASF-화성', 'F&S'],
              ['김은영', '010-2061-9677', 'BASF-안료', 'F&S']]

    # 고객 : 고객웹에서 근로자 등록
    next_4_day = datetime.datetime.now() + datetime.timedelta(days=4)
    next_4_day = next_4_day.strftime('%Y-%m-%d') + ' 19:00:00'
    arr_phone_no = [employee[1] for employee in employees]
    settings.IS_TEST = True
    employee = {
        'work_id':work_id,
        'dt_answer_deadline':next_4_day,
        'phone_numbers':arr_phone_no
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_employee', json=employee)
    result.append({'url': r.url, 'POST':employee, 'STATUS': r.status_code, 'R': r.json()})
    settings.IS_TEST = False

    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def employee_test_step_A(request):
    """
    [[근로자 서버 시험]] Step A:
    1. 사업장 생성
    2. 업무 생성
    3. 근로자 생성
    4. 근로자 beacon
    5. 근로자 touch
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    result = []
    # 고객 : 로그인
    login_data = {"login_id": "think",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url': r.url, 'POST': login_data, 'STATUS': r.status_code, 'R': r.json()})
    co_id = r.json()['company_general']['co_id']
    # 고객 : 발주사 등록
    relationship_infor = {'type': 10,    # 10 : 발주사, 12 : 협력사
                          'corp_name': '울산광역시',
                          'staff_name': '송철호',
                          'staff_pNo': '052-120',
                          'staff_email': 'ulsan@email.com',
                          }
    r = s.post(settings.CUSTOMER_URL + 'reg_relationship', json=relationship_infor)
    result.append({'url': r.url, 'POST':relationship_infor, 'STATUS': r.status_code, 'R': r.json()})

    r = s.post(settings.CUSTOMER_URL + 'list_relationship', json={'is_orderer':'YES', 'is_partner':'NO'})
    result.append({'url': r.url, 'POST':{'is_orderer':'YES', 'is_partner':'NO'}, 'STATUS': r.status_code, 'R': r.json()})
    order_id = r.json()['orderers'][0]['id']

    # 고객 : 직원 등록
    staffs = [['박종기_알', '010-8433-3579', '이사', '대덕테크'],
              ];
    index = 1
    for staff in staffs:
        staff_data = {'name': staff[0].replace(' ', ''),
                      'login_id': 'dream',
                      'position': staff[2].replace(' ', ''),
                      'department': staff[3],  # option 비워서 보내도 됨
                      'pNo': staff[1],
                      'email': 'unknown@email.com',
                      }
        r = s.post(settings.CUSTOMER_URL + 'reg_staff', json=staff_data)
        index += 1
        result.append({'url': r.url, 'POST':staff_data, 'STATUS': r.status_code, 'R': r.json()})

    r = s.post(settings.CUSTOMER_URL + 'list_staff', json={})
    # result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})
    staffs = r.json()['staffs']
    for staff in staffs:
        if staff['name'] == '박종기_알':
            manager_id = staff['id']
            break

    # 고객 : 사업장 등록
    work_place = {
        'name': '대왕암',  # 이름
        'manager_id': manager_id,
        'order_id': order_id
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_work_place', json=work_place)
    result.append({'url': r.url, 'POST': work_place, 'STATUS': r.status_code, 'R': r.json()})

    work_place_infor = { 'name':'대왕암',
                         'manager_name':'',
                         'manager_phone':'',
                         'order_name':''
                         }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=work_place_infor)
    result.append({'url': r.url, 'POST': work_place_infor, 'STATUS': r.status_code, 'R': r.json()})
    work_place_id = r.json()['work_places'][0]['id']

    for staff in staffs:
        if staff['name'] == '박종기':
            staff_id = staff['id']
            break

    # 고객 : 업무 등록
    work = {
        'name': '공원 청소',
        'work_place_id': work_place_id,
        'type': '주간 오전',
        'dt_begin': '2019-05-01',
        'dt_end': '2019-05-31',
        'staff_id': staff_id,
        'partner_id': co_id,
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_work', json=work)
    result.append({'url': r.url, 'POST': work, 'STATUS': r.status_code, 'R': r.json()})

    today = datetime.datetime.now() + datetime.timedelta(days=2)
    next_3_day = (today + datetime.timedelta(days=3)).strftime("%Y-%m-%d")
    next_5_day = (today + datetime.timedelta(days=5)).strftime("%Y-%m-%d")
    today = today.strftime("%Y-%m-%d")

    # 고객 : 업무 등록
    work = {
        'name': '공원 안내',
        'work_place_id': work_place_id,
        'type': '주간 오후',
        'dt_begin': next_5_day,
        'dt_end': '2019-05-31',
        'staff_id': staff_id,
        'partner_id': co_id,
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_work', json=work)
    result.append({'url': r.url, 'POST': work, 'STATUS': r.status_code, 'R': r.json()})

    work_infor = {'work_place_id':work_place_id,
                  'dt_begin':'',
                  'dt_end':''
                  }
    r = s.post(settings.CUSTOMER_URL + 'list_work_from_work_place', json=work_infor)
    result.append({'url': r.url, 'POST': work_infor, 'STATUS': r.status_code, 'R': r.json()})
    work_id = r.json()['works'][0]['id']
    work_id_after = r.json()['works'][1]['id']
    logSend('work_id = ', work_id)

    # 근로자 등록 - 업무 시작 전인 업무(공원 안내)
    employees = [['박종기_알', '010-8433-3579', '근로자', '대덕기공'],
                 ['박종기', '010-2557-3555', '대덕산업'],
                 ]

    # 고객 : 고객웹에서 근로자 등록
    next_4_day = datetime.datetime.now() + datetime.timedelta(days=4)
    next_4_day = next_4_day.strftime('%Y-%m-%d') + ' 19:00:00'
    arr_phone_no = [employee[1] for employee in employees]
    settings.IS_TEST = True
    employee = {
        'work_id':work_id_after,
        'dt_answer_deadline':next_4_day,
        'phone_numbers':arr_phone_no
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_employee', json=employee)
    result.append({'url': r.url, 'POST':employee, 'STATUS': r.status_code, 'R': r.json()})
    settings.IS_TEST = False

    # 근로자 등록 - 업무 시작 후인 업무(공원 청소)
    employees = [['박종기_알', '010-8433-3579', '근로자', '대덕기공'],
                 ['박종기', '010-2557-3555', '대덕산업'],
                 ]

    # 고객 : 고객웹에서 근로자 등록
    arr_phone_no = [employee[1] for employee in employees]
    settings.IS_TEST = True
    employee = {
        'work_id':work_id,
        'dt_answer_deadline':'2019-04-29 19:00:00',
        'phone_numbers':arr_phone_no
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_employee', json=employee)
    result.append({'url': r.url, 'POST':employee, 'STATUS': r.status_code, 'R': r.json()})
    settings.IS_TEST = False

    for employee_ex in employees:
        # 근로자 : 앱 설치 후 인증번호 요청
        phone_no = {'phone_no': employee_ex[1]}
        settings.IS_TEST = True
        r = s.post(settings.EMPLOYEE_URL + 'certification_no_to_sms', json=phone_no)
        settings.IS_TEST = False
        # result.append({'url': r.url, 'POST':phone_no, 'STATUS': r.status_code, 'R': r.json()})

        # 근로자 : 인증
        certification_data = {
                'phone_no' : employee_ex[1],
                'cn' : '201903',
                'phone_type' : 'A', # 안드로이드 폰
                'push_token' : 'push token'
            }
        r = s.post(settings.EMPLOYEE_URL + 'reg_from_certification_no', json=certification_data)
        # result.append({'url': r.url, 'POST':certification_data, 'STATUS': r.status_code, 'R': r.json()})
        employee = r.json()
        employee_id = employee['id'] # 등록 근로자 id (passer_id)

        if (not 'name' in employee) and ('bank_list' in employee):
            # 처음 설치한 경우 : 자기 정보 수정
            employee_info = {
                'passer_id': employee_id,
                'name': employee_ex[0],
                'bank': '기업은행',
                'bank_account': '12300000012%03d' % employees.index(employee_ex),
                'pNo': employee_ex[1],  # 추후 SMS 확인 절차 추가
                'work_start': '08:30',  # 오전 오후로 표시하지 않는다.
                'working_time': '09',  # 시간 4 - 12
                'work_start_alarm': 'X',  # '-60'(한시간 전), '-30'(30분 전), 'X'(없음) 셋중 하나로 보낸다.
                'work_end_alarm': 'X',  # '-30'(30분 전), '0'(정각), 'X'(없음) 셋중 하나로 보낸다.
            }
            r = s.post(settings.EMPLOYEE_URL + 'update_my_info', json=employee_info)
            # result.append({'url': r.url, 'POST':employee_info, 'STATUS': r.status_code, 'R': r.json()})

        # 근로자 : 알림 확인
        passer = {'passer_id': employee_id}
        r = s.post(settings.EMPLOYEE_URL + 'notification_list', json=passer)
        result.append({'url': r.url, 'GET': passer, 'STATUS': r.status_code, 'R': r.json()})
        if len(r.json()['notifications']) == 0:
            # 알림이 없는 출입자 - 대상이 아님
            continue
        notification_id = r.json()['notifications'][1]['id']

        # 근로자 : 업무 수락 / 거절
        accept = {
            'passer_id': employee_id,  # 암호화된 값임
            'notification_id': notification_id,
            'is_accept': 1  # 1 : 업무 수락, 0 : 업무 거부
        }
        r = s.post(settings.EMPLOYEE_URL + 'notification_accept', json=accept)
        result.append({'url': r.url, 'POST': accept, 'STATUS': r.status_code, 'R': r.json()})

        # 근로자 출근 기록 만들기
        # 3월
        # months = {5:[32, [5, 12, 19, 26]]}
        months = {5:[9, [4, 5, 6, 11, 12, 18, 19, 25, 26]]}
        for m_key in months.keys():
            month = m_key
            month_range = months[m_key][0]
            month_holidays = months[m_key][1]
            for day in range(1, month_range):
                if day in month_holidays:
                    continue
                beacon_data = {
                    'passer_id': employee_id,
                    'dt': '2019-%02d-%02d 08:%02d:00'%(month, day, rMin(20)),
                    'is_in': 1,  # 0: out, 1 : in
                    'major': 11001,  # 11 (지역) 001(사업장)
                    'beacons': [
                        {'minor': 11001, 'dt_begin': '2019-%02d-%02d 08:%02d:00'%(month, day, rMin(25)), 'rssi': -70},
                        {'minor': 11002, 'dt_begin': '2019-%02d-%02d 08:%02d:00'%(month, day, rMin(25)), 'rssi': -70},
                        {'minor': 11003, 'dt_begin': '2019-%02d-%02d 08:%02d:00'%(month, day, rMin(25)), 'rssi': -70}
                    ]
                    }
                r = s.post(settings.EMPLOYEE_URL + 'pass_reg', json=beacon_data)
                #result.append({'url': r.url, 'POST': beacon_data, 'STATUS': r.status_code, 'R': r.json()})

                button_data = {
                    'passer_id': employee_id,
                    'dt': '2019-%02d-%02d 08:%02d:00'%(month, day, rMin(25)),
                    'is_in': 1,  # 0: out, 1 : in
                }
                r = s.post(settings.EMPLOYEE_URL + 'pass_verify', json=button_data)
                #result.append({'url': r.url, 'POST': button_data, 'STATUS': r.status_code, 'R': r.json()})

                button_data = {
                    'passer_id': employee_id,
                    'dt': '2019-%02d-%02d 17:%02d:00'%(month, day, rMin(35)),
                    'is_in': 0,  # 0: out, 1 : in
                }
                r = s.post(settings.EMPLOYEE_URL + 'pass_verify', json=button_data)
                #result.append({'url': r.url, 'POST': button_data, 'STATUS': r.status_code, 'R': r.json()})

                beacon_data = {
                    'passer_id': employee_id,
                    'dt': '2019-%02d-%02d 17:%02d:00'%(month, day, rMin(40)),
                    'is_in': 0,  # 0: out, 1 : in
                    'major': 11001,  # 11 (지역) 001(사업장)
                    'beacons': [
                        {'minor': 11001, 'dt_begin': '2019-%02d-%02d 17:%02d:00'%(month, day, rMin(40)), 'rssi': -70},
                        {'minor': 11002, 'dt_begin': '2019-%02d-%02d 17:%02d:00'%(month, day, rMin(40)), 'rssi': -70},
                        {'minor': 11003, 'dt_begin': '2019-%02d-%02d 17:%02d:00'%(month, day, rMin(40)), 'rssi': -70}
                    ]
                    }
                r = s.post(settings.EMPLOYEE_URL + 'pass_reg', json=beacon_data)
                #result.append({'url': r.url, 'POST': beacon_data, 'STATUS': r.status_code, 'R': r.json()})

    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def employee_test_step_B(request):
    """
    [근로자 서버 시험]] Step B:
    1. 사업장 생성
    2. 업무 생성
    3. 근로자 생성
    4. 근로자 beacon
    5. 근로자 touch
    6. overtime, force dt_in_verify, force dt_in_verify
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    result = []

    login_data = {"login_id": "thinking",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url': r.url, 'POST': login_data, 'STATUS': r.status_code, 'R': r.json()})

    # ---------------------------------------------------------------------------------------
    # TEST: my_work_records 근로자의 월별 근로 내용 요청 시험
    # ---------------------------------------------------------------------------------------
    # my_work_histories_infor = {
    #     'passer_id': AES_ENCRYPT_BASE64('2'),
    #     'dt': '2019-05'
    # }
    # r = s.post(settings.EMPLOYEE_URL + 'my_work_records', json=my_work_histories_infor)
    # result.append({'url': r.url, 'POST': my_work_histories_infor, 'STATUS': r.status_code, 'R': r.json()})

    # ---------------------------------------------------------------------------------------
    # TEST: pass_sms SMS 로 업무 수락/거부 시험
    # ---------------------------------------------------------------------------------------
    # reg_employee_infor = {
    #     'work_id': AES_ENCRYPT_BASE64('1'),
    #     'dt_answer_deadline': '2019-05-17 19:00:00',
    #     'phone_numbers': ['010-2557-3555']
    # }
    # r = s.post(settings.CUSTOMER_URL + 'reg_employee', json=reg_employee_infor)
    # result.append({'url': r.url, 'POST': reg_employee_infor, 'STATUS': r.status_code, 'R': r.json()})
    #
    # sms_infor = {
    #         'phone_no': '010-2557-3555',
    #         'dt': '2019-05-17 07:00:00',
    #         'sms': '출근!!!',
    #     }
    # r = s.post(settings.EMPLOYEE_URL + 'pass_sms', json=sms_infor)
    # result.append({'url': r.url, 'POST': sms_infor, 'STATUS': r.status_code, 'R': r.json()})
    #
    # ---------------------------------------------------------------------------------------
    # TEST: pass_verify 출퇴근 버튼 처리 시험
    # ---------------------------------------------------------------------------------------
    # pass_data = {
    #         'passer_id': AES_ENCRYPT_BASE64('1'),  # '암호화된 출입자 id',
    #         'dt': '2018-05-14 08:30:00',
    #         'is_in': 1,  # 0: out, 1 : in
    #     }
    # r = s.post(settings.EMPLOYEE_URL + 'pass_verify', json=pass_data)
    # result.append({'url': r.url, 'POST': pass_data, 'STATUS': r.status_code, 'R': r.json()})

    # pass_data = {
    #         'passer_id': AES_ENCRYPT_BASE64('1'),  # '암호화된 출입자 id',
    #         'dt': '2018-05-14 20:30:00',
    #         'is_in': 0,  # 0: out, 1 : in
    #     }
    # r = s.post(settings.EMPLOYEE_URL + 'pass_verify', json=pass_data)
    # result.append({'url': r.url, 'POST': pass_data, 'STATUS': r.status_code, 'R': r.json()})

    # pass_data = {
    #         'passer_id': AES_ENCRYPT_BASE64('1'),  # '암호화된 출입자 id',
    #         'dt': '2018-05-14 21:30:00',
    #         'is_in': 0,  # 0: out, 1 : in
    #     }
    # r = s.post(settings.EMPLOYEE_URL + 'pass_verify', json=pass_data)
    # result.append({'url': r.url, 'POST': pass_data, 'STATUS': r.status_code, 'R': r.json()})

    # pass_data = {
    #         'passer_id': AES_ENCRYPT_BASE64('1'),  # '암호화된 출입자 id',
    #         'dt': '2018-05-15 17:30:00',
    #         'is_in': 0,  # 0: out, 1 : in
    #     }
    # r = s.post(settings.EMPLOYEE_URL + 'pass_verify', json=pass_data)
    # result.append({'url': r.url, 'POST': pass_data, 'STATUS': r.status_code, 'R': r.json()})

    # ---------------------------------------------------------------------------------------
    # TEST: update_work 고객웹에서 업무를 업데이트 했을 때 연관 데이터(근로자 서버의 업무, 근로자 업무 시작일/종료일) 동기화
    # ---------------------------------------------------------------------------------------
    # reg_employee_infor = {
    #     'work_id': AES_ENCRYPT_BASE64('1'),
    #     'dt_answer_deadline': '2019-05-16 19:00:00',
    #     'phone_numbers': ['010-2557-3555']
    # }
    # r = s.post(settings.CUSTOMER_URL + 'reg_employee', json=reg_employee_infor)
    # result.append({'url': r.url, 'POST': reg_employee_infor, 'STATUS': r.status_code, 'R': r.json()})
    #
    # work_infor = {
    #     'work_id': AES_ENCRYPT_BASE64('1'),
    #     'name': '비콘 교체',
    #     'work_place_id': AES_ENCRYPT_BASE64('1'),
    #     'type': '주간 3교대',
    #     'dt_begin': '2019-05-16',  # 업무 시작 날짜
    #     'dt_end': '2019-07-31',  # 업무 종료 날짜
    #     'staff_id': AES_ENCRYPT_BASE64('2'),
    #     'partner_id': AES_ENCRYPT_BASE64('1'),
    # }
    # r = s.post(settings.CUSTOMER_URL + 'update_work', json=work_infor)
    # result.append({'url': r.url, 'POST': work_infor, 'STATUS': r.status_code, 'R': r.json()})

    # ---------------------------------------------------------------------------------------
    # TEST: report_of_employee
    # ---------------------------------------------------------------------------------------
    report_infor = {
        'work_id': '_LdMng5jDTwK-LMNlj22Vw',
        'employee_id': 'iZ_rkELjhh18ZZauMq2vQw',
        'year_month': '2019-04',
    }
    # http://0.0.0.0:8000/customer/report_of_employee?work_id=_LdMng5jDTwK-LMNlj22Vw&employee_id=iZ_rkELjhh18ZZauMq2vQw&year_month=2019-04
    # GET
    #     work_id = 업무 id         # 사업장에서 선택된 업무의 id
    #     employee_id = 근로자 id    # 업무에서 선택된 근로자의 id
    #     year_month = "2019-04"   # 근태내역의 연월
    r = s.post(settings.CUSTOMER_URL + 'report_of_employee', json=report_infor)
    result.append({'url': r.url, 'POST': report_infor, 'STATUS': r.status_code, 'R': r.json()})

    r = s.post(settings.CUSTOMER_URL + 'logout', json={})
    result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})

    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})

    """
    pass_record_of_employees_in_day_for_customer
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
    """
    employees_infor = {'employees': [AES_ENCRYPT_BASE64('1'), AES_ENCRYPT_BASE64('2')],
                       'year_month_day': '2019-05-08',
                       'work_id': 'qgf6YHf1z2Fx80DR8o_Lvg',
                       }
    logSend(employees_infor)
    r = s.post(settings.EMPLOYEE_URL + 'pass_record_of_employees_in_day_for_customer', json=employees_infor)
    result.append({'url': r.url, 'POST': employees_infor, 'STATUS': r.status_code, 'R': r.json()})

    employees_infor = {'employees': [AES_ENCRYPT_BASE64('1'), AES_ENCRYPT_BASE64('2')],
                       'year_month_day': '2019-05-08',
                       'work_id': 'qgf6YHf1z2Fx80DR8o_Lvg',
                       'overtime': -2,
                       'overtime_staff_id': 'qgf6YHf1z2Fx80DR8o_Lv',
                       'dt_in_verify': '008:30',
                       'in_staff_id': 'qgf6YHf1z2Fx80DR8o_Lv',
                       'dt_out_verify': '017:30',
                       'out_staff_id': 'qgf6YHf1z2Fx80DR8o_Lv',
                       }
    logSend(employees_infor)
    r = s.post(settings.EMPLOYEE_URL + 'pass_record_of_employees_in_day_for_customer', json=employees_infor)
    result.append({'url': r.url, 'POST': employees_infor, 'STATUS': r.status_code, 'R': r.json()})

    employees_infor = {'employees': [AES_ENCRYPT_BASE64('1'), AES_ENCRYPT_BASE64('2')],
                       'year_month_day': '2019-05-08',
                       'work_id': 'qgf6YHf1z2Fx80DR8o_Lvg',
                       'overtime': 6,
                       'overtime_staff_id': AES_ENCRYPT_BASE64('1'),
                       'dt_in_verify': '08:35',
                       'in_staff_id': AES_ENCRYPT_BASE64('1'),
                       'dt_out_verify': '20:25',
                       'out_staff_id': AES_ENCRYPT_BASE64('1'),
                       }
    logSend(employees_infor)
    r = s.post(settings.EMPLOYEE_URL + 'pass_record_of_employees_in_day_for_customer', json=employees_infor)
    result.append({'url': r.url, 'POST': employees_infor, 'STATUS': r.status_code, 'R': r.json()})

    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def sms_install_mng(request):

    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    # msg = '이지체크\n'\
    #       '새로운 업무를 앱에서 확인해주세요.\n'\
    #       '앱 설치\n'\
    #       'https://api-dev.aegisfac.com/app'
    #
    # rData = {
    #     'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
    #     'user_id': 'yuadocjon22',
    #     'sender': settings.SMS_SENDER_PN,
    #     'receiver': '01025573555',
    #     'msg_type': 'SMS',
    #     'msg': msg,
    # }
    # r = requests.post('https://apis.aligo.in/send/', data=rData)
    # func_end_log(func_name)
    # return REG_200_SUCCESS.to_json_response({'result':result})

    if not 'id' in rqst:
        func_end_log(func_name)
        return REG_200_SUCCESS.to_json_response({'result': 'parameter: id?'})

    result = []

    login_data = {"login_id": "think",
                  "login_pw": "parkjong"
                  }
    # login_data = {"login_id": "staff_4",
    #               "login_pw": "happy_day!!!"
    #               }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    # result.append({'url': r.url, 'POST': login_data, 'STATUS': r.status_code, 'R': r.json()})

    #
    # SMS 출근 시험
    #
    # sms_infor = {
    #     "phone_no": "01074648939",
    #     "dt": "2019-05-13 15:25:52",
    #     "sms": "출근합니다"
    # }
    # r = s.post(settings.EMPLOYEE_URL + 'pass_sms', json=sms_infor)
    # result.append({'url': r.url, 'POST': sms_infor, 'STATUS': r.status_code, 'R': r.json()})

    r = s.post(settings.CUSTOMER_URL + 'list_staff', json={})
    # result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})
    staffs = r.json()['staffs']
    rData = {
        'key': 'bl68wp14jv7y1yliq4p2a2a21d7tguky',
        'user_id': 'yuadocjon22',
        'sender': settings.SMS_SENDER_PN,
        'msg_type': 'SMS',
    }

    # rSMS = requests.post('https://apis.aligo.in/send/', data=rData)
    for staff in staffs:
        msg = '이지체크\n'
        msg += '관리자 앱을 설치하십시요.\n'
        msg += 'id: %s\n' % staff['login_id']
        msg += 'https://api-dev.aegisfac.com/apm'
        rData['receiver'] = staff['pNo']
        rData['msg'] = msg
        # logSend(staff['login_id'], ' ', staff['pNo'])
        # result.append({'login_id':staff['login_id'], 'pNo':staff['pNo']})
        r = requests.post('https://apis.aligo.in/send/', data=rData)
        result.append({'url': r.url, 'POST': rData, 'STATUS': r.status_code, 'R': r.json()})
        # logSend('SMS result', rSMS.json())

    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def employee_beacon_step_1(request):
    """
    [[고객 서버 시험]] Step 9: ?
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    parameter_check = is_parameter_ok(rqst, ['key_!'])
    if not parameter_check['is_ok']:
        func_end_log(func_name)
        return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message':parameter_check['results']})

    result = []

    pass_info = {"passer_id": "OhV-mZKPmDYAQvMoBY6zGQ",
                  "dt":"2019-05-06 08:30",
                  "is_in":True,
                  "major":11001,
                  "beacons":[
                      {
                          "minor":11001,
                          "dt_begin": "2019-05-06 08:25:00",
                          "rssi": -70
                      },
                      {
                          "minor": 11002,
                          "dt_begin": "2019-05-06 08:24:00",
                          "rssi": -30
                      },
                      {
                          "minor": 11003,
                          "dt_begin": "2019-05-06 08:26:00",
                          "rssi": -15
                      },
                  ],
                  }
    s = requests.session()
    r = s.post(settings.EMPLOYEE_URL + 'pass_reg', json=pass_info)
    result.append({'url': r.url, 'POST': pass_info, 'STATUS': r.status_code, 'R': r.json()})


    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})

    # 로그인한 본인의 정보 수정 기능 시험
    #
    # r = s.post(settings.CUSTOMER_URL + 'list_staff', json={})
    # result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})
    # staffs = r.json()['staffs']
    # for staff in staffs:
    #     if staff['login_id'] == login_data['login_id']:
    #         update_staff_id = staff['id']
    #         break
    #
    # # staff_data = {'staff_id': update_staff_id,
    # #               'new_login_id': 'think',
    # #               'before_pw': 'happy_day!!!',
    # #               'login_pw': 'parkjong',
    # #               'position': '이사'
    # #               }
    # staff_data = {'staff_id': update_staff_id,
    #               'new_login_id': 'ddtech_ceo',
    #               'before_pw': 'happy_day!!!',
    #               # 'login_pw': 'parkjong',
    #               'position': '대표'
    #               }
    # r = s.post(settings.CUSTOMER_URL + 'update_staff', json=staff_data)
    # result.append({'url': r.url, 'POST': staff_data, 'STATUS': r.status_code, 'R': r.json()})

    work_place_infor = { 'name':'',
                         'manager_name':'',
                         'manager_phone':'',
                         'order_name':''
                         }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=work_place_infor)
    result.append({'url': r.url, 'POST': work_place_infor, 'STATUS': r.status_code, 'R': r.json()})
    work_place_id = r.json()['work_places'][0]['id']

    work_infor = {'work_place_id':work_place_id,
                  'dt_begin':'',
                  'dt_end':''
                  }
    r = s.post(settings.CUSTOMER_URL + 'list_work_from_work_place', json=work_infor)
    result.append({'url': r.url, 'POST': work_infor, 'STATUS': r.status_code, 'R': r.json()})
    work_id = r.json()['works'][1]['id']
    logSend('work_id = ', work_id)

    # 근로자 등록
    # employees = [['최   진', '010-2073-6959', '경영지원실장', '대덕기공']]

    employees = [['최재환', '010-4871-8362', '전무이사', '대덕기공'],
              ['이석호', '010-3544-6840', '상무이사', '대덕기공'],
              ['엄원섭', '010-3877-4105', '총무이사', '대덕기공'],
              ['최   진', '010-2073-6959', '경영지원실장', '대덕기공'],
              ['우종복', '010-2436-6966', '경영지원실 차장', '대덕기공'],
              ['서경화', '010-8594-3858', '경리차장', '대덕기공'],
              ['김진오', '010-8513-3300', '관리과장', '대덕기공'],
              ['김정석', '010-9323-5627', '총무과장', '대덕기공'],
              ['황지민', '010-5197-6214', '총무사원', '대덕기공'],
              ['권호택', '010-5359-6869', '관리이사', '대덕산업'],
              ['신철관', '010-7542-4017', '관리차장', '대덕산업'],
              ['김기홍', '010-7151-1119', '관리차장', '대덕산업'],
              ['김동욱', '010-5280-3275', '솔베이 관리차장', '대덕산업'],
              ['김현정', '010-5583-8021', '총무사원', '대덕산업'],
              ['엄상경', '010-8538-4106', '관리부장', 'TS'],
              ['김종민', '010-7290-8113', '관리차장', 'TS'],
              ['임유빈', '010-7255-4888', '총무사원', 'TS'],
              ['박용수', '010-2100-9864', '상무이사', 'F&S'],
              ['전미숙', '010-5556-0163', '관리차장', 'F&S'],
              ['김유신', '010-7725-9293', '대      리', 'F&S'],
              ['김윤정', '010-9305-8981', '경리사원', 'F&S'],
              ['신선경', '010-3127-4024', '롯데케미칼1공장', 'F&S'],
              ['전애리', '010-4224-8640', '롯데케미칼2공장', 'F&S'],
              ['김유경', '010-9342-0997', '후     성', 'F&S'],
              ['김미경', '010-2397-6143', 'BASF-화성', 'F&S'],
              ['김은영', '010-2061-9677', 'BASF-안료', 'F&S']]

    # 고객 : 고객웹에서 근로자 등록
    next_4_day = datetime.datetime.now() + datetime.timedelta(days=4)
    next_4_day = next_4_day.strftime('%Y-%m-%d') + ' 19:00:00'
    arr_phone_no = [employee[1] for employee in employees]
    settings.IS_TEST = True
    employee = {
        'work_id':work_id,
        'dt_answer_deadline':next_4_day,
        'phone_numbers':arr_phone_no
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_employee', json=employee)
    result.append({'url': r.url, 'POST':employee, 'STATUS': r.status_code, 'R': r.json()})
    settings.IS_TEST = False

    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def test_go_go(request):
    """
    [[ 서버 시험]] 단순한 기능 시험
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'사용 권한이 없습니다.'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    result = []
    s = requests.session()

    login_data = {"login_id": "thinking",
                  "login_pw": "parkjong"
                  }
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    # result.append({'url': r.url, 'POST': login_data, 'STATUS': r.status_code, 'R': r.json()})

    # recognize_data = {"dt_leave": "",
    #              "staff_id": "qgf6YHf1z2Fx80DR8o_Lvg",
    #              "employee_id": "_LdMng5jDTwK-LMNlj22Vw",
    #              "dt_arrive": "2019-05-21 08:30:38",
    #              }
    # r = s.post(settings.CUSTOMER_URL + 'staff_recognize_employee', json=recognize_data)
    # result.append({'url': r.url, 'POST': recognize_data, 'STATUS': r.status_code, 'R': r.json()})

    # ---------------------------------------------------------------------------------------
    # TEST: reg_staff 운영 직원 등록 시험
    # ---------------------------------------------------------------------------------------
    # login_data = {"id": "thinking",
    #               "pw": "parkjong"
    #               }
    # r = s.post(settings.OPERATION_URL + 'login', json=login_data)
    # result.append({'url': r.url, 'POST': login_data, 'STATUS': r.status_code, 'R': r.json()})
    #
    # new_staff = {"pNo": "01084333579",
    #              "id": "parkjke",
    #              "pw": "parkjong"
    #              }
    # r = s.post(settings.OPERATION_URL + 'reg_staff', json=new_staff)
    # result.append({'url': r.url, 'POST': new_staff, 'STATUS': r.status_code, 'R': r.json()})
    # ---------------------------------------------------------------------------------------
    # TEST: my_work_records 근로자의 월별 근로 내용 요청 시험
    # ---------------------------------------------------------------------------------------
    # my_work_histories_infor = {
    #     'passer_id': AES_ENCRYPT_BASE64('2'),
    #     'dt': '2019-05'
    # }
    # r = s.post(settings.EMPLOYEE_URL + 'my_work_records', json=my_work_histories_infor)
    # result.append({'url': r.url, 'POST': my_work_histories_infor, 'STATUS': r.status_code, 'R': r.json()})

    # ---------------------------------------------------------------------------------------
    # TEST: pass_sms SMS 로 업무 수락/거부 시험 (+ reg_employee )
    # ---------------------------------------------------------------------------------------
    # reg_employee_infor = {
    #     'work_id': AES_ENCRYPT_BASE64('1'),
    #     'dt_answer_deadline': '2019-05-25 19:00',
    #     'phone_numbers': ['010-2557-3555', '010-9999-99', '010-1111-99', '010-2222-99']
    # }
    # r = s.post(settings.CUSTOMER_URL + 'reg_employee', json=reg_employee_infor)
    # result.append({'url': r.url, 'POST': reg_employee_infor, 'STATUS': r.status_code, 'R': r.json()})

    # sms_infor = {
    #         'phone_no': '010-8433 3579',
    #         'dt': '2019-05-23 15:33:00:00',
    #         'sms': '   수락 박종    ',
    #     }
    # r = s.post(settings.EMPLOYEE_URL + 'pass_sms', json=sms_infor)
    # result.append({'url': r.url, 'POST': sms_infor, 'STATUS': r.status_code, 'R': r.json()})

    # ---------------------------------------------------------------------------------------
    # TEST: pass_verify 출퇴근 버튼 처리 시험
    # ---------------------------------------------------------------------------------------
    # pass_data = {
    #         'passer_id': AES_ENCRYPT_BASE64('1'),  # '암호화된 출입자 id',
    #         'dt': '2018-05-14 08:30:00',
    #         'is_in': 1,  # 0: out, 1 : in
    #     }
    # r = s.post(settings.EMPLOYEE_URL + 'pass_verify', json=pass_data)
    # result.append({'url': r.url, 'POST': pass_data, 'STATUS': r.status_code, 'R': r.json()})

    # pass_data = {
    #         'passer_id': AES_ENCRYPT_BASE64('1'),  # '암호화된 출입자 id',
    #         'dt': '2018-05-14 20:30:00',
    #         'is_in': 0,  # 0: out, 1 : in
    #     }
    # r = s.post(settings.EMPLOYEE_URL + 'pass_verify', json=pass_data)
    # result.append({'url': r.url, 'POST': pass_data, 'STATUS': r.status_code, 'R': r.json()})

    # pass_data = {
    #         'passer_id': AES_ENCRYPT_BASE64('1'),  # '암호화된 출입자 id',
    #         'dt': '2018-05-14 21:30:00',
    #         'is_in': 0,  # 0: out, 1 : in
    #     }
    # r = s.post(settings.EMPLOYEE_URL + 'pass_verify', json=pass_data)
    # result.append({'url': r.url, 'POST': pass_data, 'STATUS': r.status_code, 'R': r.json()})

    # pass_data = {
    #         'passer_id': AES_ENCRYPT_BASE64('1'),  # '암호화된 출입자 id',
    #         'dt': '2018-05-15 17:30:00',
    #         'is_in': 0,  # 0: out, 1 : in
    #     }
    # r = s.post(settings.EMPLOYEE_URL + 'pass_verify', json=pass_data)
    # result.append({'url': r.url, 'POST': pass_data, 'STATUS': r.status_code, 'R': r.json()})

    # ---------------------------------------------------------------------------------------
    # TEST: update_work 고객웹에서 업무를 업데이트 했을 때 연관 데이터(근로자 서버의 업무, 근로자 업무 시작일/종료일) 동기화
    # ---------------------------------------------------------------------------------------
    # reg_employee_infor = {
    #     'work_id': AES_ENCRYPT_BASE64('1'),
    #     'dt_answer_deadline': '2019-05-16 19:00:00',
    #     'phone_numbers': ['010-2557-3555']
    # }
    # r = s.post(settings.CUSTOMER_URL + 'reg_employee', json=reg_employee_infor)
    # result.append({'url': r.url, 'POST': reg_employee_infor, 'STATUS': r.status_code, 'R': r.json()})
    #
    # work_infor = {
    #     'work_id': AES_ENCRYPT_BASE64('1'),
    #     'name': '비콘 교체',
    #     'work_place_id': AES_ENCRYPT_BASE64('1'),
    #     'type': '주간 3교대',
    #     'dt_begin': '2019-05-16',  # 업무 시작 날짜
    #     'dt_end': '2019-07-31',  # 업무 종료 날짜
    #     'staff_id': AES_ENCRYPT_BASE64('2'),
    #     'partner_id': AES_ENCRYPT_BASE64('1'),
    # }
    # r = s.post(settings.CUSTOMER_URL + 'update_work', json=work_infor)
    # result.append({'url': r.url, 'POST': work_infor, 'STATUS': r.status_code, 'R': r.json()})

    # ---------------------------------------------------------------------------------------
    # TEST: report_of_employee
    # ---------------------------------------------------------------------------------------
    # report_infor = {
    #     'work_id': '_LdMng5jDTwK-LMNlj22Vw',
    #     'employee_id': 'iZ_rkELjhh18ZZauMq2vQw',
    #     'year_month': '2019-04',
    # }
    # r = s.post(settings.CUSTOMER_URL + 'report_of_employee', json=report_infor)
    # result.append({'url': r.url, 'POST': report_infor, 'STATUS': r.status_code, 'R': r.json()})

    # ---------------------------------------------------------------------------------------
    # TEST: /operation/reg_customer 운영 웹에서 고객사 등록
    # ---------------------------------------------------------------------------------------
    # customer_data = {
    #     're_sms': 'NO',
    #     'customer_name': '대덕 서울',
    #     'staff_name': '박종기',
    #     'staff_pNo': '01084333579',
    #     'staff_email': 'thinking@ddtech.com',
    # }
    # r = s.post(settings.OPERATION_URL + 'reg_customer', json=customer_data)
    # result.append({'url': r.url, 'POST': customer_data, 'STATUS': r.status_code, 'R': r.json()})
    #
    # customer_data = {
    #     're_sms': 'NO',
    #     'customer_name': '대덕 서울',
    #     'staff_name': '박종기',
    #     'staff_pNo': '01084333479',
    #     'staff_email': 'parkjgy@daam.co.kr',
    # }
    # r = s.post(settings.OPERATION_URL + 'reg_customer', json=customer_data)
    # result.append({'url': r.url, 'POST': customer_data, 'STATUS': r.status_code, 'R': r.json()})
    #
    # customer_data = {
    #     'customer_name': '대덕기공',
    #     'staff_name': '홍길동',
    #     'staff_pNo': '010-1111-2222',
    #     'staff_email': 'id@daeducki.com',
    # }
    # r = s.post(settings.OPERATION_URL + 'list_customer', json=customer_data)
    # result.append({'url': r.url, 'POST': customer_data, 'STATUS': r.status_code, 'R': r.json()})

    # ---------------------------------------------------------------------------------------
    # TEST: /customer/reg_employee 고객웹에서 근로자 등록 시험
    # ---------------------------------------------------------------------------------------
    # settings.IS_TEST = True
    # employee_data = {
    #     'work_id': 'qgf6YHf1z2Fx80DR8o_Lvg',
    #     'dt_answer_deadline': '2019-06-07 18:00',
    #     'dt_begin': '2019-06-08',
    #     'phone_numbers':  # 업무에 배치할 근로자들의 전화번호
    #         [
    #             '+82 010-2557-3555', '010-2557-355', '011-8888-999', '+82 10 8433 3579'
    #         ]
    #     }
    # r = s.post(settings.CUSTOMER_URL + 'reg_employee', json=employee_data)
    # result.append({'url': r.url, 'POST': employee_data, 'STATUS': r.status_code, 'R': r.json()})
    # settings.IS_TEST = False

    beacon_data = {
        'passer_id': AES_ENCRYPT_BASE64('2'),
        'dt': '2019-06-14 08:30:00',
        'is_in': 1,  # 0: out, 1 : in
        'major': 11001,  # 11 (지역) 001(사업장)
        'beacons': [
            {'minor': 11001, 'dt_begin': '2019-06-14 08:21:00', 'rssi': -60},
            {'minor': 11002, 'dt_begin': '2019-06-14 08:23:00', 'rssi': -65},
            {'minor': 11003, 'dt_begin': '2019-06-14 08:25:00', 'rssi': -70}
        ]
    }
    r = s.post(settings.EMPLOYEE_URL + 'pass_reg', json=beacon_data)
    result.append({'url': r.url, 'POST': beacon_data, 'STATUS': r.status_code, 'R': r.json()})

    # ---------------------------------------------------------------------------------------
    # TEST: /customer/reg_staff, update_staff 고객웹에서 관리자 등록, 정보 수정 시험
    # ---------------------------------------------------------------------------------------
    # staff_data = {
    #         'name': '홍길동',
    #         'login_id': 'hong_guel_dong',
    #         'position': '',	   # option 비워서 보내도 됨
    #         'department': '',	# option 비워서 보내도 됨
    #         'pNo': '010-8433-3579', # '-'를 넣어도 삭제되어 저장 됨
    #         'email': 'id@ddtechi.com',
    #     }
    # r = s.post(settings.CUSTOMER_URL + 'reg_staff', json=staff_data)
    # result.append({'url': r.url, 'POST': staff_data, 'STATUS': r.status_code, 'R': r.json()})
    #
    # r = s.post(settings.CUSTOMER_URL + 'logout', json={})
    #
    # login_data = {"login_id": "hong_guel_dong",
    #               "login_pw": "happy_day!!!"
    #               }
    # r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    # result.append({'url': r.url, 'POST': login_data, 'STATUS': r.status_code, 'R': r.json()})
    #
    # r = s.post(settings.CUSTOMER_URL + 'staff_fg', json=login_data)
    # result.append({'url': r.url, 'POST': login_data, 'STATUS': r.status_code, 'R': r.json()})
    # staff_id = r.json()['staff_id']
    #
    # r = s.post(settings.CUSTOMER_URL + 'staff_background', json={'staff_id': staff_id})
    # result.append({'url': r.url, 'POST': {'staff_id': staff_id}, 'STATUS': r.status_code, 'R': r.json()})

    # staff_infor = {'staff_id': AES_ENCRYPT_BASE64('3'),
    #                # 'new_login_id': 'think',
    #                'before_pw': 'happy_day!!!',
    #                'login_pw': 'parkjong_1',
    #                'name': '박종기',
    #                'position': '직책',
    #                'department': '부서 or 소속',
    #                'phone_no': '010-1111-2222',
    #                'email': 'id@ddtechi.com'
    #                }
    # r = s.post(settings.CUSTOMER_URL + 'update_staff', json=staff_infor)
    # result.append({'url': r.url, 'POST': staff_infor, 'STATUS': r.status_code, 'R': r.json()})

    # ---------------------------------------------------------------------------------------
    # TEST: /customer/update_customer 고객웹에서 고객사 정보 수정
    # ---------------------------------------------------------------------------------------
    # customer_data = {
    #         'staff_id': AES_ENCRYPT_BASE64('1'),  #'서버에서 받은 암호화된 id', # 담당자를 변경할 때만 (담당자, 관리자만 변경 가능)
    #         'manager_id': AES_ENCRYPT_BASE64('1'),  #'서버에서 받은 암호화된 id', # 관리자를 변경할 때만 (관리자만 변경 가능)
    #         'name': '대덕테크',
    #         'regNo': '123-00-12345',    # 사업자등록번호
    #         'ceoName': '대표자',           # 성명
    #         'address': '사업장 소재지',
    #         'business_type': '업태',
    #         'business_item': '종목',
    #         'dt_reg': '2018-03-01',  # 사업자등록일
    #         'dt_payment': '25',  # 유료고객의 결제일 (5, 10, 15, 20, 25 중 에서 선택) 담당자, 관리자만 변경 가능
    # 	}
    # r = s.post(settings.CUSTOMER_URL + 'update_customer', json=customer_data)
    # result.append({'url': r.url, 'POST': customer_data, 'STATUS': r.status_code, 'R': r.json()})

    # ---------------------------------------------------------------------------------------
    # TEST: /customer/update_relationship 고객웹에서 협력사나 발주사 정보 수정
    # ---------------------------------------------------------------------------------------
    # relationship_data = {'corp_id': 'qgf6YHf1z2Fx80DR8o_Lvg',
    #                      'corp_name': '울산테크_change',
    #                      'staff_name': '이울산',
    #                      'staff_pNo': '010-2450-5942',
    #                      'staff_email': 'hello@ddtechi.com',
    #                      'manager_name': '이울산',
    #                      'manager_pNo': '010-2450-5942',
    #                      'manager_email': 'hello@ddtechi.com',
    #                      'name': '울산테크',
    #                      'regNo': '',
    #                      'ceoName': '',
    #                      'address': '',
    #                      'business_type': '',
    #                      'business_item': '',
    #                      'dt_reg': '',
    #                      'is_reg': 'False',
    #                      'type': '12',
    #                      'type_name': '협력사',
    #                      }
    # r = s.post(settings.CUSTOMER_URL + 'update_relationship', json=relationship_data)
    # result.append({'url': r.url, 'POST': relationship_data, 'STATUS': r.status_code, 'R': r.json()})

    # ---------------------------------------------------------------------------------------
    # TEST: /customer/staff_recognize_employee 관리자 앱에서 근로자 출퇴근 시간 강제 조정
    # ---------------------------------------------------------------------------------------
    # recognize_data = {
    #     'staff_id': 'qgf6YHf1z2Fx80DR8o_Lvg',
    #     'employee_id': '_LdMng5jDTwK-LMNlj22Vw',
    #     'dt_arrive': '2019-05-29 12:30:39',
    #     'dt_leave': '',
    # }
    # r = s.post(settings.CUSTOMER_URL + 'staff_recognize_employee', json=recognize_data)
    # result.append({'url': r.url, 'POST': recognize_data, 'STATUS': r.status_code, 'R': r.json()})

    # ---------------------------------------------------------------------------------------
    # TEST: /employee/certification_no_to_sms 인증번호 요청
    # ---------------------------------------------------------------------------------------
    # passer_data = {
    #     'phone_no': '+i82 10 2557 355 5',
    #     'passer_id': 'tuqB7wUIVoIKH0pz2J9IfQ',
    # }
    # r = s.post(settings.EMPLOYEE_URL + 'certification_no_to_sms', json=passer_data)
    # result.append({'url': r.url, 'POST': passer_data, 'STATUS': r.status_code, 'R': r.json()})

    # r = s.post(settings.OPERATION_URL + 'logout', json={})
    r = s.post(settings.CUSTOMER_URL + 'logout', json={})
    result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})

    # ---------------------------------------------------------------------------------------
    # TEST: /config.common Works 근로자 업무 처리 class
    # ---------------------------------------------------------------------------------------
    # work_1 = {"id": 1, "begin": "2019/05/01", "end": "2019/05/30"}
    # work_2 = {"id": 2, "begin": "2019/06/01", "end": "2019/06/30"}
    # work_3 = {"id": 3, "begin": "2019/07/01", "end": "2019/07/30"}
    # work_4 = {"id": 4, "begin": "2019/06/15", "end": "2019/07/15"}
    #
    # w = Works([work_2])
    # logSend(w.data)
    # is_overlap = w.is_overlap(work_4)
    # logSend(' {} '.format(is_overlap))
    # w.add(work_3)
    # logSend(w.data)
    #
    # employee = Employee(
    #     name='근로자',
    #     # work=w.data,
    # )
    # employee.set_works(w.data)
    # employee.save()

    # employee = Employee.objects.get(id=1)
    # w = employee.get_works()
    # logSend(' len: {}'.format(len(w)))
    # logSend(' {} - {}'.format(w, w[0]))
    # ww = Works(w)
    # logSend(ww.data, '**', ww.data[0], "==", ww.data[1])

    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result': result})


@cross_origin_read_allow
def fjfjieie(request):
    """
    [[ 서버 시험]] 단순한 기능 시험
    GET
        { "key" : "사용 승인 key"
    response
        STATUS 200
        STATUS 403
            {'message':'저리가!!!'}
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if get_client_ip(request) not in settings.ALLOWED_HOSTS:
        return REG_403_FORBIDDEN.to_json_response({'result': '저리가!!!'})

    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET
    for key in rqst.keys():
        logSend('  ', key, ': ', rqst[key])

    result = []
    s = requests.session()

    if 'pNo' in rqst:
        pNo = no_only_phone_no(rqst['pNo'])
    else:
        pNo = ""
    if 'name' in rqst:
        name = rqst['name']
    else:
        name = ""
    parameter = {"pNo": pNo,
                 "name": name,
                }
    r = s.post(settings.EMPLOYEE_URL + 'fjfjieie', json=parameter)
    result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})
    # login_data = {"login_id": "thinking",
    #               "login_pw": "parkjong"
    #               }
    # r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    # result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})
    #
    # r = s.post(settings.CUSTOMER_URL + 'logout', json={})
    # result.append({'url': r.url, 'POST': {}, 'STATUS': r.status_code, 'R': r.json()})

    logSend(result)
    func_end_log(func_name)
    return REG_200_SUCCESS.to_json_response({'result': result})
