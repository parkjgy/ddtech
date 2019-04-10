import json
import datetime
from datetime import timedelta

import coreapi
from django.conf import settings
from rest_framework.decorators import api_view, schema
from rest_framework.schemas import AutoSchema
from rest_framework.views import APIView

from config.common import logSend, logError
from config.common import DateTimeEncoder, ValuesQuerySetToDict
from config.common import HttpResponse, ReqLibJsonResponse
from config.common import func_begin_log, func_end_log
from config.common import hash_SHA256, no_only_phone_no, phone_format
# secret import
from config.secret import AES_ENCRYPT_BASE64, AES_DECRYPT_BASE64
from config.decorator import cross_origin_read_allow, session_is_none_403_with_operation

from .models import Environment
from .models import Staff
from .models import Work_Place
from .models import Beacon

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
        # func_end_log(func_name, 'OK')

    def __del__(self):
        # func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        logSend(' <<< Environment class delete')
        # func_end_log(func_name, 'OK')

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
        strToday = datetime.datetime.now().strftime("%Y-%m-%d ")
        str_dt_reload = strToday + self.curEnv.timeCheckServer
        self.dt_reload = datetime.datetime.strptime(str_dt_reload, "%Y-%m-%d %H:%M:%S")
        if self.dt_reload < datetime.datetime.now():  # 다시 로딩해야할 시간이 현재 시간 이전이면 내일 시간으로 바꾼다.
            self.dt_reload = self.dt_reload + timedelta(days=1)
            logSend('       next load time + 24 hours')
        logSend('   >>> next load time = ' + self.dt_reload.strftime("%Y-%m-%d %H:%M:%S"))
        logSend('   >>> current time = ' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        func_end_log(func_name, 'OK')
        return

    def start(self):
        # func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        if not self.is_running:
            self.loadEnvironment()
            self.is_running = True
        # func_end_log(func_name, 'OK')

    def stop(self):
        # func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        self.is_running = False
        # func_end_log(func_name, 'OK')

    def current(self):
        # func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        if self.dt_reload < datetime.datetime.now():
            self.is_running = False
            self.loadEnvironment()
            self.is_running = True
        # func_end_log(func_name, 'OK')
        return self.curEnv

    def self(self):
        # func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        # func_end_log(func_name, 'OK')
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

    global env
    result = {}
    result['dt'] = env.current().dt.strftime("%Y-%m-%d %H:%M:%S")
    result['timeCheckServer'] = env.current().timeCheckServer

    func_end_log(func_name, 'OK')
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
    func_end_log(func_name, 'OK')
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

    global env

    worker_id = request.session['op_id'][5:]
    print(worker_id, worker_id[5:])

    worker = Staff.objects.get(id=worker_id)
    if not (worker.id in [1, 2]):
        print('524')
        func_end_log(func_name, 'OK')
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
    func_end_log(func_name, 'OK')
    return REG_200_SUCCESS.to_json_response()


class OperationView(APIView):
    staff_login_form = AutoSchema(manual_fields=[
        coreapi.Field("pNo", required=True, location="form", type="string", description="partner number field",
                      example="010-2557-3555"),
        coreapi.Field("id", required=True, location="form", type="string", description="id field", example="thinking"),
        coreapi.Field("pw", required=True, location="form", type="string", description="password field",
                      example="a~~~8282")]
    )

    @api_view(['POST'])
    @schema(staff_login_form)
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
                    'pw': 'a~~~8282'    # AES 256
                }
            response
                STATUS 200
        """
        func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        worker_id = request.session['op_id'][5:]
        worker = Staff.objects.get(id=worker_id)
        # try:
        #     if AES_DECRYPT_BASE64(rqst['master']) != '3355':
        #         func_end_log(func_name, 'OK')
        #         return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '마스터 키 오류'})
        # except Exception as e:
        #     func_end_log(func_name, 'OK')
        #     return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '마스터 키 오류 : ' + str(e)})

        phone_no = no_only_phone_no(rqst['pNo'])
        id_ = rqst['id']
        pw = rqst['pw']

        staffs = Staff.objects.filter(pNo=phone_no, login_id=id_)
        if len(staffs) > 0:
            func_end_log(func_name, 'OK')
            return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response()
        new_staff = Staff(
            login_id=id_,
            login_pw=hash_SHA256(pw),
            pNo=phone_no
        )
        new_staff.save()
        func_end_log(func_name, 'OK')
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

    id_ = rqst['id']
    pw_ = rqst['pw']

    staffs = Staff.objects.filter(login_id=id_, login_pw=hash_SHA256(pw_))
    if len(staffs) == 0:
        print('530')
        func_end_log(func_name, 'OK')
        return REG_530_ID_OR_PASSWORD_IS_INCORRECT.to_json_response()
    staff = staffs[0]
    staff.is_login = True
    staff.dt_login = datetime.datetime.now()
    staff.save()

    # 추후 0000은 permission 에 할당
    request.session['op_id'] = 'O0000' + str(staff.id)
    request.session.save()
    print('200')
    func_end_log(func_name, 'OK')
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
        func_end_log(func_name, 'OK')
        return REG_200_SUCCESS.to_json_response({'message': '이미 로그아웃되었습니다.'})
    staff = Staff.objects.get(id=request.session['op_id'][5:])
    staff.is_login = False
    staff.dt_login = datetime.datetime.now()
    staff.save()
    del request.session['op_id']
    # id를 None 으로 Setting 하면, 세션은 살아있으면서 값은 None 인 상태가 된다.
    func_end_log(func_name, 'OK')
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
    #     func_end_log(func_name, 'OK')
    #     return REG_200_SUCCESS.to_json_response({'message': '비밀번호가 초기화 되었습니다.'})

    if hash_SHA256(before_pw) != staff.login_pw:
        func_end_log(func_name, 'OK')
        return REG_531_PASSWORD_IS_INCORRECT.to_json_response()

    if len(login_id) > 0:
        if (Staff.objects.filter(login_id=login_id)) > 0:
            func_end_log(func_name, 'OK')
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
        staff.phone_no = phone_no
    if len(phone_type) > 0:
        staff.phone_type = phone_type
    if len(push_token) > 0:
        staff.push_token = push_token
    if len(email) > 0:
        staff.email = email
    staff.save()
    func_end_log(func_name, 'OK')
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
            'pNo': staff.pNo,
            'pType': staff.pType,
            'email': staff.email,
            'is_worker': True if staff.id == worker.id else False
        }
        arr_staff.append(r_staff)
    print(arr_staff)
    func_end_log(func_name, 'OK')
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
    """
    func_name = func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

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
        'staff_email': staff_email
    }
    response_customer = requests.post(settings.CUSTOMER_URL + 'reg_customer_for_operation', json=new_customer_data)
    if response_customer.status_code != 200:
        func_end_log(func_name, 'OK')
        return ReqLibJsonResponse(response_customer)
    response_customer_json = response_customer.json()
    # print('아이디 ' + response_customer_json['login_id'] + '\n' + '비밀번호 ' + response_customer_json['login_pw'])
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
    if settings.DEBUG:
        rData['testmode_yn'] = 'Y'

    r = requests.post('https://apis.aligo.in/send/', data=rData)
    # print(r.json())

    func_end_log(func_name, 'OK')
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

    worker_id = request.session['op_id'][5:]
    worker = Staff.objects.get(id=worker_id)

    new_customer_data = {
        'worker_id': AES_ENCRYPT_BASE64(str(worker.id)),
        'staff_id': rqst['staff_id']
    }
    response_customer = requests.post(settings.CUSTOMER_URL + 'sms_customer_staff_for_operation',
                                      json=new_customer_data)
    if response_customer.status_code != 200:
        func_end_log(func_name, 'OK')
        return ReqLibJsonResponse(response_customer)
    response_customer_json = response_customer.json()
    print('아이디 ' + response_customer_json['login_id'])
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
    print(r.json())

    func_end_log(func_name, 'OK')
    return REG_200_SUCCESS.to_json_response({'message': 'SMS 로 아이디와 초기회된 비밀번호를 보냈습니다.'})


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
    print(response_customer.json())
    if response_customer.status_code != 200:
        func_end_log(func_name, 'OK')
        return ReqLibJsonResponse(response_customer)
    arr_customer = response_customer.json()['customers']
    print(arr_customer)
    op_arr_customer = []
    for customer in arr_customer:
        customer['name'] = customer['corp_name']
        print(customer['corp_name'], customer['name'])
        op_customer = customer
        del op_customer['id']
        if op_customer['type'] == 12:
            continue
        op_customer['type'] = '발주업체' if op_customer['type'] == 10 else '파견업체'
        op_arr_customer.append(op_customer)
    logSend(op_arr_customer)
    func_end_log(func_name, 'OK')
    return REG_200_SUCCESS.to_json_response({'customers': op_arr_customer})


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

    # worker_id = request.session['op_id'][5:]
    # worker = Staff.objects.get(id=worker_id)

    global env
    result = {'dt_update': env.curEnv.dt_android_upgrade.strftime('%Y-%m-%d %H:%M:%S')}
    func_end_log(func_name, 'OK')
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
    if (not 'key' in rqst) or (len(rqst['key']) == 0) or (AES_DECRYPT_BASE64(rqst['key']) != 'thinking'):
        result = {'message':'사용 권한이 없습니다.'}
        logSend(result['message'])
        func_end_log(func_name, 'OK')
        return REG_403_FORBIDDEN.to_json_response(result)

    # 고객서버 테이블 삭제 및 초기화
    key = {'key':rqst['key']}
    response = requests.post(settings.CUSTOMER_URL + 'table_reset_and_clear_for_operation', json=key)
    logSend(response.json())

    result = {'message': 'Customer all tables deleted$ '}
    logSend(result['message'])
    func_end_log(func_name, 'OK')
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
    if (not 'key' in rqst) or (len(rqst['key']) == 0) or (AES_DECRYPT_BASE64(rqst['key']) != 'thinking'):
        result = {'message':'사용 권한이 없습니다.'}
        logSend(result['message'])
        func_end_log(func_name, 'OK')
        return REG_403_FORBIDDEN.to_json_response(result)
    result = []

    # 운영 로그인
    login_data = {"id": "thinking",
                  "pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.OPERATION_URL + 'login', json=login_data)
    result.append({'url':r.url, 'POST':login_data, 'STATUS':r.status_code, 'R':r.json()})
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
    r = s.post(settings.OPERATION_URL + 'reg_customer', json=customer_data)
    result.append({'url':r.url, 'POST':customer_data, 'STATUS':r.status_code, 'R':r.json()})

    print(result)
    logSend(result)
    func_end_log(func_name, 'OK')
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
    if (not 'key' in rqst) or (len(rqst['key']) == 0) or (AES_DECRYPT_BASE64(rqst['key']) != 'thinking'):
        result = {'message':'사용 권한이 없습니다.'}
        logSend(result['message'])
        func_end_log(func_name, 'OK')
        return REG_403_FORBIDDEN.to_json_response(result)

    result = []

    # 운영 : 로그인
    login_data = {"id": "thinking",
                  "pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.OPERATION_URL + 'login', json=login_data)
    result.append({'url':r.url, 'POST':login_data, 'STATUS':r.status_code, 'R':r.json()})

    # 운영 : 고객사 리스트
    customer_data = {'customer_name': '대덕테크',
                     'staff_name': '박종기',
                     'staff_pNo': '010-2557-3555',
                     'staff_email': 'thinking@ddtechi.com'
                     }
    r = s.post(settings.OPERATION_URL + 'list_customer', json=customer_data)
    result.append({'url':r.url, 'GET':customer_data, 'STATUS':r.status_code, 'R':r.json()})

    customer = r.json()['customers'][0]

    # 운영 : 고객사 담당자 SMS 다시 보냄
    customer_data = {'staff_id': customer['staff_id'],
                     'staff_pNo': customer['staff_pNo']
                     }
    r = s.post(settings.OPERATION_URL + 'sms_customer_staff', json=customer_data)
    result.append({'url':r.url, 'POST':customer_data, 'STATUS':r.status_code, 'R':r.json()})

    print(result)
    logSend(result)
    func_end_log(func_name, 'OK')
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
    if (not 'key' in rqst) or (len(rqst['key']) == 0) or (AES_DECRYPT_BASE64(rqst['key']) != 'thinking'):
        result = {'message':'사용 권한이 없습니다.'}
        logSend(result['message'])
        func_end_log(func_name, 'OK')
        return REG_403_FORBIDDEN.to_json_response(result)

    result = []

    # 고객 : 로그인
    login_data = {"login_id": "temp_1",
                  "login_pw": "happy_day!!!"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url':r.url, 'POST':login_data, 'STATUS':r.status_code, 'R':r.json()})

    if r.status_code == 200:
        # 고객 : 자기 정보 수정 - login_id
        staff_data = {'new_login_id': 'thinking',
                      'before_pw': 'happy_day!!!',
                      }
        r = s.post(settings.CUSTOMER_URL + 'update_staff', json=staff_data)
        result.append({'url': r.url, 'POST': staff_data, 'STATUS': r.status_code, 'R': r.json()})

        # 고객 : 로그인
        login_data = {"login_id": "thinking",
                      "login_pw": "happy_day!!!"
                      }
        s = requests.session()
        r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
        result.append({'url': r.url, 'POST': login_data, 'STATUS': r.status_code, 'R': r.json()})

        # 고객 : 자기 정보 수정 - login_pw
        staff_data = {'before_pw': 'happy_day!!!',
                      'login_pw': 'parkjong',
                      }
        r = s.post(settings.CUSTOMER_URL + 'update_staff', json=staff_data)
        result.append({'url': r.url, 'POST': login_data, 'STATUS': r.status_code, 'R': r.json()})

    # 고객 : 로그인
    login_data = {"login_id": "thinking",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url':r.url, 'POST':login_data, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 자기 정보 수정 - 직책
    staff_data = {'before_pw': 'parkjong',
                  'position': '이사',
                  }
    r = s.post(settings.CUSTOMER_URL + 'update_staff', json=staff_data)
    result.append({'url':r.url, 'POST':staff_data, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 직원 등록
    staff_data = {'name': '이요셉',
                  'login_id': 'hello',
                  'position': '책임연구원',     # option 비워서 보내도 됨
                  'department': '개발팀',  # option 비워서 보내도 됨
                  'pNo': '010-2450-5942', # '-'를 넣어도 삭제되어 저장 됨
                  'email': 'hello@ddtechi.com',
                  }
    r = s.post(settings.CUSTOMER_URL + 'reg_staff', json=staff_data)
    result.append({'url':r.url, 'POST':staff_data, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 직원 리스트
    staff_data = {}
    r = s.post(settings.CUSTOMER_URL + 'list_staff', json=staff_data)
    result.append({'url':r.url, 'GET':staff_data, 'STATUS':r.status_code, 'R':r.json()})

    print(r.json()['staffs'][1])
    # 고객 : 고객사 정보 수정
    customer_infor = {'staff_id': r.json()['staffs'][1]['id']}
    r = s.post(settings.CUSTOMER_URL + 'update_customer', json=customer_infor)
    result.append({'url':r.url, 'POST':customer_infor, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 고객사 정보 수정
    customer_infor = {'name':'주식회사 대덕테크',
                      'regNo':'894-88-00927',
                      'ceoName':'최진',
                      'address':'울산광역시 남구 봉월로 22, 309호(신정동, 임창베네시안)',
                      'business_type':'서비스업',
                      'business_item':'시스템개발 및 관리, 컴퓨터프로그래밍, 시스템종합관리업',
                      'dt_reg':'2018-03-12',
                      'dt_payment':'25'
                      }
    r = s.post(settings.CUSTOMER_URL + 'update_customer', json=customer_infor)
    result.append({'url':r.url, 'POST':customer_infor, 'STATUS':r.status_code, 'R':r.json()})

    print(result)
    logSend(result)
    func_end_log(func_name, 'OK')
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
    if (not 'key' in rqst) or (len(rqst['key']) == 0) or (AES_DECRYPT_BASE64(rqst['key']) != 'thinking'):
        result = {'message':'사용 권한이 없습니다.'}
        logSend(result['message'])
        func_end_log(func_name, 'OK')
        return REG_403_FORBIDDEN.to_json_response(result)

    result = []

    # 고객 : 로그인
    login_data = {"login_id": "thinking",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url':r.url, 'POST':login_data, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 발주사 등록
    relationship_infor = {'type': 10,    # 10 : 발주사, 12 : 협력사
                          'corp_name': '대덕기공',
                          'staff_name': '엄원섭',
                          'staff_pNo': '010-3877-4105',
                          'staff_email': 'wonsup.eom@daeducki.com',
                          }
    r = s.post(settings.CUSTOMER_URL + 'reg_relationship', json=relationship_infor)
    result.append({'url':r.url, 'POST':relationship_infor, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 협력사 등록
    relationship_infor = {'type': 12,    # 10 : 발주사, 12 : 협력사
                          'corp_name': '주식회사 살구',
                          'staff_name': '정소원',
                          'staff_pNo': '010-7620-5918',
                          'staff_email': 'salgoo.ceo@gmail.com',
                          }
    r = s.post(settings.CUSTOMER_URL + 'reg_relationship', json=relationship_infor)
    result.append({'url':r.url, 'POST':relationship_infor, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 발주, 협력사 리스트
    get_parameter = {'is_partner': 'YES',
                     'is_orderer': 'YES'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_relationship', json=get_parameter)
    result.append({'url':r.url, 'GET':get_parameter, 'STATUS':r.status_code, 'R':r.json()})
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
    result.append({'url':r.url, 'POST':relationship_infor, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 협력사 상세 정보
    get_parameter = {'relationship_id':partner_id}
    r = s.post(settings.CUSTOMER_URL + 'detail_relationship', json=get_parameter)
    result.append({'url':r.url, 'GET':get_parameter, 'STATUS':r.status_code, 'R':r.json()})

    print(result)
    logSend(result)
    func_end_log(func_name, 'OK')
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
    if (not 'key' in rqst) or (len(rqst['key']) == 0) or (AES_DECRYPT_BASE64(rqst['key']) != 'thinking'):
        result = {'message':'사용 권한이 없습니다.'}
        logSend(result['message'])
        func_end_log(func_name, 'OK')
        return REG_403_FORBIDDEN.to_json_response(result)

    result = []

    # 고객 : 로그인
    login_data = {"login_id": "thinking",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url':r.url, 'POST':login_data, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 직원 리스트
    staff_data = {}
    r = s.post(settings.CUSTOMER_URL + 'list_staff', json=staff_data)
    result.append({'url':r.url, 'GET':staff_data, 'STATUS':r.status_code, 'R':r.json()})
    manager_id = r.json()['staffs'][0]['id']  # 박종기
    new_manager_id = r.json()['staffs'][1]['id']  # 이요셉

    # 고객 : 발주, 협력사 리스트
    get_parameter = {'is_partner': 'NO',
                     'is_orderer': 'YES'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_relationship', json=get_parameter)
    result.append({'url':r.url, 'GET':get_parameter, 'STATUS':r.status_code, 'R':r.json()})
    order_id = r.json()['orderers'][0]['id']  # 첫번째 발주사

    # 고객 : 사업장 등록
    work_place = {
        'name': '대덕기공 출입시스템',  # 이름
        'manager_id': manager_id,  # 관리자 id (암호화되어 있음)
        'order_id': order_id,  # 발주사 id (암호화되어 있음)
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_work_place', json=work_place)
    result.append({'url':r.url, 'POST':work_place, 'STATUS':r.status_code, 'R':r.json()})

    work_place['name'] = 'ITNJ 출입시스템'
    r = s.post(settings.CUSTOMER_URL + 'reg_work_place', json=work_place)
    result.append({'url':r.url, 'POST':work_place, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 사업장 리스트
    get_parameter = {'name':'ITNJ',
                     'manager_name':'',
                     'manager_phone':'',
                     'order_name':''
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=get_parameter)
    result.append({'url':r.url, 'GET':get_parameter, 'STATUS':r.status_code, 'R':r.json()})
    work_place_id = r.json()['work_places'][0]['id']

    # 고객 : 사업장 수정
    work_place = {
        'work_place_id': work_place_id,
        'name': 'ITNJ',  # 이름
        'manager_id': new_manager_id  # 이요셉
    }
    r = s.post(settings.CUSTOMER_URL + 'update_work_place', json=work_place)
    result.append({'url':r.url, 'POST':work_place, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 사업장 리스트
    get_parameter = {'name':'',
                     'manager_name':'',
                     'manager_phone':'',
                     'order_name':'대덕'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=get_parameter)
    result.append({'url':r.url, 'GET':get_parameter, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 사업장 수정
    work_place = {
        'work_place_id': work_place_id,
        'name': 'ITNJ',  # 이름
        'manager_id': manager_id  # 이요셉
    }
    r = s.post(settings.CUSTOMER_URL + 'update_work_place', json=work_place)
    result.append({'url':r.url, 'POST':work_place, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 사업장 리스트
    get_parameter = {'name':'',
                     'manager_name':'',
                     'manager_phone':'',
                     'order_name':'대덕'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=get_parameter)
    result.append({'url':r.url, 'GET':get_parameter, 'STATUS':r.status_code, 'R':r.json()})

    print(result)
    logSend(result)
    func_end_log(func_name, 'OK')
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
    if (not 'key' in rqst) or (len(rqst['key']) == 0) or (AES_DECRYPT_BASE64(rqst['key']) != 'thinking'):
        result = {'message':'사용 권한이 없습니다.'}
        logSend(result['message'])
        func_end_log(func_name, 'OK')
        return REG_403_FORBIDDEN.to_json_response(result)

    result = []

    # 고객 : 로그인
    login_data = {"login_id": "thinking",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url':r.url, 'POST':login_data, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 사업장 리스트
    get_parameter = {'name':'',
                     'manager_name':'',
                     'manager_phone':'',
                     'order_name':'대덕'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=get_parameter)
    result.append({'url':r.url, 'GET':get_parameter, 'STATUS':r.status_code, 'R':r.json()})
    print(r.json())
    work_place_id = r.json()['work_places'][0]['id']

    # 고객 : 직원 리스트
    staff_data = {}
    r = s.post(settings.CUSTOMER_URL + 'list_staff', json=staff_data)
    result.append({'url':r.url, 'GET':staff_data, 'STATUS':r.status_code, 'R':r.json()})
    staff_id = r.json()['staffs'][1]['id']  # 첫번째 등록 직원

    # 고객 : 발주, 협력사 리스트
    get_parameter = {'is_partner': 'YES',
                     'is_orderer': 'NO'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_relationship', json=get_parameter)
    result.append({'url':r.url, 'GET':get_parameter, 'STATUS':r.status_code, 'R':r.json()})
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
    result.append({'url':r.url, 'POST':work, 'STATUS':r.status_code, 'R':r.json()})

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
    result.append({'url':r.url, 'POST':work, 'STATUS':r.status_code, 'R':r.json()})

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
    result.append({'url':r.url, 'GET':get_parameter, 'STATUS':r.status_code, 'R':r.json()})

    work_id_1 = r.json()['works'][0]['id']
    work_id_2 = r.json()['works'][1]['id']
    # 고객 : 업무 수정
    work = {
        'work_id': work_id_1,
        'dt_end': next_5_day,  # 업무 종료 날짜
        'partner_id': partner_id
    }
    r = s.post(settings.CUSTOMER_URL + 'update_work', json=work)
    result.append({'url':r.url, 'POST':work, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 업무 수정
    work = {
        'work_id': work_id_2,
        'dt_end': next_3_day,  # 업무 종료 날짜
        'partner_id': 'gDoPqy_Pea6imtYYzWrEXQ=='
    }
    r = s.post(settings.CUSTOMER_URL + 'update_work', json=work)
    result.append({'url':r.url, 'POST':work, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 업무 리스트
    get_parameter = {'work_place_id': work_place_id,
                     'dt_begin':'2019-02-25',
                     'dt_end':today,
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_from_work_place', json=get_parameter)
    result.append({'url':r.url, 'GET':get_parameter, 'STATUS':r.status_code, 'R':r.json()})

    print(result)
    logSend(result)
    func_end_log(func_name, 'OK')
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
    if (not 'key' in rqst) or (len(rqst['key']) == 0) or (AES_DECRYPT_BASE64(rqst['key']) != 'thinking'):
        result = {'message':'사용 권한이 없습니다.'}
        logSend(result['message'])
        func_end_log(func_name, 'OK')
        return REG_403_FORBIDDEN.to_json_response(result)

    result = []

    # 고객 : 로그인
    login_data = {"login_id": "thinking",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    result.append({'url':r.url, 'POST':login_data, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 사업장 리스트
    get_parameter = {'name':'',
                     'manager_name':'',
                     'manager_phone':'',
                     'order_name':'대덕'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=get_parameter)
    result.append({'url':r.url, 'POST':get_parameter, 'STATUS':r.status_code, 'R':r.json()})
    logSend(result)
    logSend(result)
    work_place_id = r.json()['work_places'][0]['id']

    # 고객 : 업무 리스트
    get_parameter = {'work_place_id':work_place_id,
                     'dt_begin':'2019-02-25',
                     'dt_end':'2019-02-27',
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_from_work_place', json=get_parameter)
    result.append({'url':r.url, 'POST':get_parameter, 'STATUS':r.status_code, 'R':r.json()})
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
    result.append({'url':r.url, 'POST':update_work, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 근로자 등록
    next_4_day = datetime.datetime.now() + datetime.timedelta(days=4)
    next_4_day = next_4_day.strftime('%Y-%m-%d') + ' 19:00:00'
    employee = {
        'work_id':work_id,
        'dt_answer_deadline':next_4_day,
        'phone_numbers':['010-2557-3555', '010-1111-2222', '010-3333-44', '010-4444-5555', '010-1111-3333', '010-4444-7777']
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_employee', json=employee)
    result.append({'url':r.url, 'POST':employee, 'STATUS':r.status_code, 'R':r.json()})

    names = ["양만춘", "강감찬", "이순신", "안중근"]
    arr_phone_no = ['010-1111-2222', '010-4444-5555', '010-1111-3333', '010-4444-7777']
    for pNo in arr_phone_no:
        # 근로자 : 인증번호 요청
        phone_no = {'phone_no' : pNo}
        settings.IS_TEST = True
        r = s.post(settings.EMPLOYEE_URL + 'certification_no_to_sms', json=phone_no)
        settings.IS_TEST = False
        result.append({'url':r.url, 'POST':phone_no, 'STATUS':r.status_code, 'R':r.json()})

        # 근로자 : 근로자 확인
        certification_data = {
                'phone_no' : pNo,
                'cn' : '201903',
                'phone_type' : 'A', # 안드로이드 폰
                'push_token' : 'push token'
            }
        r = s.post(settings.EMPLOYEE_URL + 'reg_from_certification_no', json=certification_data)
        result.append({'url':r.url, 'POST':certification_data, 'STATUS':r.status_code, 'R':r.json()})
        print(r.json())

        employee_info = {
            'passer_id': r.json()['id'],
            'name': names[arr_phone_no.index(pNo)],
            'bank': '기업은행',
            'bank_account': '12300000012000',
            'pNo': pNo,  # 추후 SMS 확인 절차 추가
        }
        r = s.post(settings.EMPLOYEE_URL + 'update_my_info', json=employee_info)
        result.append({'url':r.url, 'POST':employee_info, 'STATUS':r.status_code, 'R':r.json()})

    # 근로자 리스트 - 전화번호에 1111 가 포함된 근로자
    phone_no = {
        'phone_no':'1111'
    }
    r = s.post(settings.EMPLOYEE_URL + 'passer_list', json=phone_no)
    result.append({'url':r.url, 'POST':phone_no, 'STATUS':r.status_code, 'R':r.json()})
    passers = r.json()['passers']

    if len(passers) > 0:
        for ex_passer in passers:
            # 근로자 : 알림 확인
            passer = {'passer_id':ex_passer['id']}
            r = s.post(settings.EMPLOYEE_URL + 'notification_list', json=passer)
            result.append({'url':r.url, 'GET':passer, 'STATUS':r.status_code, 'R':r.json()})
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
            result.append({'url':r.url, 'POST':accept, 'STATUS':r.status_code, 'R':r.json()})

    # # 근로자 리스트
    # phone_no = {
    #     'phone_no':'3555'
    # }
    # r = s.post(settings.EMPLOYEE_URL + 'passer_list', json=phone_no)
    # result.append({'url':r.url, 'POST':phone_no, 'STATUS':r.status_code, 'R':r.json()})
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
    # result.append({'url':r.url, 'GET':passer, 'STATUS':r.status_code, 'R':r.json()})
    # notification_id = r.json()['notifications'][0]['id']
    #
    # # 근로자 : 업무 수락 / 거절
    # accept = {
    #     'passer_id': passer_id,  # 암호화된 값임
    #     'notification_id': notification_id,
    #     'is_accept': 0  # 1 : 업무 수락, 0 : 업무 거부
    # }
    # r = s.post(settings.EMPLOYEE_URL + 'notification_accept', json=accept)
    # result.append({'url':r.url, 'POST':accept, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 근로자 리스트
    work = {'work_id': work_id,
            'is_working_history':'YES'
            }
    r = s.post(settings.CUSTOMER_URL + 'list_employee', json=work)
    result.append({'url':r.url, 'POST':work, 'STATUS':r.status_code, 'R':r.json()})

    # 근로자 리스트 - 전화번호에 4444 가 포함된 근로자
    phone_no = {
        'phone_no':'4444'
    }
    r = s.post(settings.EMPLOYEE_URL + 'passer_list', json=phone_no)
    result.append({'url':r.url, 'POST':phone_no, 'STATUS':r.status_code, 'R':r.json()})
    passers = r.json()['passers']

    if len(passers) > 0:
        for ex_passer in passers:
            # 근로자 : 알림 확인
            passer = {'passer_id':ex_passer['id']}
            r = s.post(settings.EMPLOYEE_URL + 'notification_list', json=passer)
            result.append({'url':r.url, 'GET':passer, 'STATUS':r.status_code, 'R':r.json()})
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
            result.append({'url':r.url, 'POST':accept, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 근로자 리스트
    work = {'work_id': work_id,
            'is_working_history':'YES'
            }
    r = s.post(settings.CUSTOMER_URL + 'list_employee', json=work)
    result.append({'url':r.url, 'POST':work, 'STATUS':r.status_code, 'R':r.json()})
    employees = r.json()['employees']

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
        'dt_answer_deadline':(datetime.datetime.now() + datetime.timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S"), # 전화번호 바꿀 때 필수
        # 'dt_begin': '2019-03-09',  # 근무 시작일
        # 'dt_end': '2019-05-31',  # 근로자 한명의 업무 종료일을 변경한다. (업무 인원 전체는 업무에서 변경한다.)
    }
    r = s.post(settings.CUSTOMER_URL + 'update_employee', json=update_employee)
    result.append({'url':r.url, 'POST':update_employee, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 근로자 리스트
    work = {'work_id': work_id,
            'is_working_history':'YES'
            }
    r = s.post(settings.CUSTOMER_URL + 'list_employee', json=work)
    result.append({'url':r.url, 'POST':work, 'STATUS':r.status_code, 'R':r.json()})

    # 업무 시작 날짜 수정 - 근로자 응답 확인을 시험하기 위해 업무 시작 날짜를 오늘 이전으로 변경
    begin_day = (datetime.datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    update_work = {
        'work_id': work_id,  # 필수
        'dt_begin': begin_day,  # 근무 시작일
    }
    r = s.post(settings.CUSTOMER_URL + 'update_work', json=update_work)
    result.append({'url':r.url, 'POST':update_work, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 근로자 리스트
    work = {'work_id': work_id,
            'is_working_history':'YES'
            }
    r = s.post(settings.CUSTOMER_URL + 'list_employee', json=work)
    result.append({'url':r.url, 'POST':work, 'STATUS':r.status_code, 'R':r.json()})

    print(result)
    logSend(result)
    func_end_log(func_name, 'OK')
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
    if (not 'key' in rqst) or (len(rqst['key']) == 0) or (AES_DECRYPT_BASE64(rqst['key']) != 'thinking'):
        result = {'message':'사용 권한이 없습니다.'}
        logSend(result['message'])
        func_end_log(func_name, 'OK')
        return REG_403_FORBIDDEN.to_json_response(result)

    result = []

    # 고객 : 로그인
    login_data = {"login_id": "thinking",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    # result.append({'url':r.url, 'POST':login_data, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 사업장 리스트
    get_parameter = {'name':'',
                     'manager_name':'',
                     'manager_phone':'',
                     'order_name':'대덕'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=get_parameter)
    # result.append({'url':r.url, 'POST':get_parameter, 'STATUS':r.status_code, 'R':r.json()})
    # 첫번째 사업장을 시험 대상으로 설정
    work_place_id = r.json()['work_places'][0]['id']

    # 고객 : 업무 리스트
    get_parameter = {'work_place_id':work_place_id,
                     'dt_begin':'2019-02-25',
                     'dt_end':'2019-02-27',
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_from_work_place', json=get_parameter)
    # result.append({'url':r.url, 'POST':get_parameter, 'STATUS':r.status_code, 'R':r.json()})
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
    result.append({'url':r.url, 'POST':update_work, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 근로자 등록
    next_4_day = datetime.datetime.now() + datetime.timedelta(days=4)
    next_4_day = next_4_day.strftime('%Y-%m-%d') + ' 19:00:00'
    employee = {
        'work_id':work_id,
        'dt_answer_deadline':next_4_day,
        'phone_numbers':['010-3333-44', '01-1111-4444']
    }
    r = s.post(settings.CUSTOMER_URL + 'reg_employee', json=employee)
    result.append({'url':r.url, 'POST':employee, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 근로자 리스트
    work = {'work_id': work_id,
            'is_working_history':'YES'
            }
    r = s.post(settings.CUSTOMER_URL + 'list_employee', json=work)
    result.append({'url':r.url, 'POST':work, 'STATUS':r.status_code, 'R':r.json()})
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
        result.append({'url':r.url, 'POST':update_employee, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 근로자 리스트
    work = {'work_id': work_id,
            'is_working_history':'YES'
            }
    r = s.post(settings.CUSTOMER_URL + 'list_employee', json=work)
    result.append({'url':r.url, 'POST':work, 'STATUS':r.status_code, 'R':r.json()})

    logSend(result)
    func_end_log(func_name, 'OK')
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
    if (not 'key' in rqst) or (len(rqst['key']) == 0) or (AES_DECRYPT_BASE64(rqst['key']) != 'thinking'):
        result = {'message':'사용 권한이 없습니다.'}
        logSend(result['message'])
        func_end_log(func_name, 'OK')
        return REG_403_FORBIDDEN.to_json_response(result)

    result = []

    # 고객 : 로그인
    login_data = {"login_id": "thinking",
                  "login_pw": "parkjong"
                  }
    s = requests.session()
    r = s.post(settings.CUSTOMER_URL + 'login', json=login_data)
    # result.append({'url':r.url, 'POST':login_data, 'STATUS':r.status_code, 'R':r.json()})

    # 고객 : 사업장 리스트
    get_parameter = {'name':'',
                     'manager_name':'',
                     'manager_phone':'',
                     'order_name':'대덕'
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_place', json=get_parameter)
    # result.append({'url':r.url, 'POST':get_parameter, 'STATUS':r.status_code, 'R':r.json()})
    work_place_id = r.json()['work_places'][0]['id']

    # 고객 : 업무 리스트
    get_parameter = {'work_place_id':work_place_id,
                     'dt_begin':'2019-02-25',
                     'dt_end':'2019-02-27',
                     }
    r = s.post(settings.CUSTOMER_URL + 'list_work_from_work_place', json=get_parameter)
    result.append({'url':r.url, 'POST':get_parameter, 'STATUS':r.status_code, 'R':r.json()})
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
    result.append({'url':r.url, 'POST':update_work, 'STATUS':r.status_code, 'R':r.json()})

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
    result.append({'url':r.url, 'POST':employee, 'STATUS':r.status_code, 'R':r.json()})
    duplicate_pNo = r.json()['duplicate_pNo']
    print(duplicate_pNo)

    for pNo in arr_phone_no:

        # 근로자 : 앱 설치 후 인증번호 요청
        phone_no = {'phone_no' : pNo}
        settings.IS_TEST = True
        r = s.post(settings.EMPLOYEE_URL + 'certification_no_to_sms', json=phone_no)
        settings.IS_TEST = False
        # result.append({'url':r.url, 'POST':phone_no, 'STATUS':r.status_code, 'R':r.json()})

        # 근로자 : 인증
        certification_data = {
                'phone_no' : pNo,
                'cn' : '201903',
                'phone_type' : 'A', # 안드로이드 폰
                'push_token' : 'push token'
            }
        r = s.post(settings.EMPLOYEE_URL + 'reg_from_certification_no', json=certification_data)
        # result.append({'url':r.url, 'POST':certification_data, 'STATUS':r.status_code, 'R':r.json()})
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
            # result.append({'url':r.url, 'POST':employee_info, 'STATUS':r.status_code, 'R':r.json()})

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
    result.append({'url':r.url, 'POST':work, 'STATUS':r.status_code, 'R':r.json()})

    logSend(result)
    func_end_log(func_name, 'OK')
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def employee_test_step_1(request):
    """
    [[고객 서버 시험]] Step 9: check_version
    - check version
    - 전화번호 인증 reg_employee
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
    if (not 'key' in rqst) or (len(rqst['key']) == 0) or (AES_DECRYPT_BASE64(rqst['key']) != 'thinking'):
        result = {'message':'사용 권한이 없습니다.'}
        logSend(result['message'])
        func_end_log(func_name, 'OK')
        return REG_403_FORBIDDEN.to_json_response(result)

    result = []

    # 근로자 : 로그인
    version = {"v": "A.1.0.0.190111"}
    s = requests.session()
    r = s.post(settings.EMPLOYEE_URL + 'check_version', json=version)
    result.append({'url':r.url, 'GET':version, 'STATUS':r.status_code, 'R':r.json()})

    # 근로자 : 인증번호 요청
    phone_no = {'phone_no' : '010-3355-8282'}
    settings.IS_TEST = True
    r = s.post(settings.EMPLOYEE_URL + 'certification_no_to_sms', json=phone_no)
    settings.IS_TEST = False
    result.append({'url':r.url, 'POST':phone_no, 'STATUS':r.status_code, 'R':r.json()})

    # 근로자 : 근로자 확인
    certification_data = {
            'phone_no' : '010-3355-8282',
            'cn' : '201903',
            'phone_type' : 'A', # 안드로이드 폰
            'push_token' : 'push token'
        }
    r = s.post(settings.EMPLOYEE_URL + 'reg_from_certification_no', json=certification_data)
    result.append({'url':r.url, 'POST':certification_data, 'STATUS':r.status_code, 'R':r.json()})

    employee_info = {
        'passer_id': r.json()['id'],
        'name': '손석희',
        'bank': '기업은행',
        'bank_account': '12300000012000',
        'pNo': '010-2222-3333',  # 추후 SMS 확인 절차 추가
    }
    r = s.post(settings.EMPLOYEE_URL + 'update_my_info', json=employee_info)
    result.append({'url':r.url, 'POST':employee_info, 'STATUS':r.status_code, 'R':r.json()})

    print(result)
    logSend(result)
    func_end_log(func_name, 'OK')
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def employee_test_step_2(request):
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
    if (not 'key' in rqst) or (len(rqst['key']) == 0) or (AES_DECRYPT_BASE64(rqst['key']) != 'thinking'):
        result = {'message':'사용 권한이 없습니다.'}
        logSend(result['message'])
        func_end_log(func_name, 'OK')
        return REG_403_FORBIDDEN.to_json_response(result)

    result = []

    print(result)
    logSend(result)
    func_end_log(func_name, 'OK')
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def employee_test_step_3(request):
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
    if (not 'key' in rqst) or (len(rqst['key']) == 0) or (AES_DECRYPT_BASE64(rqst['key']) != 'thinking'):
        result = {'message':'사용 권한이 없습니다.'}
        logSend(result['message'])
        func_end_log(func_name, 'OK')
        return REG_403_FORBIDDEN.to_json_response(result)

    result = []

    print(result)
    logSend(result)
    func_end_log(func_name, 'OK')
    return REG_200_SUCCESS.to_json_response({'result':result})


@cross_origin_read_allow
def employee_test_step_4(request):
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
    if (not 'key' in rqst) or (len(rqst['key']) == 0) or (AES_DECRYPT_BASE64(rqst['key']) != 'thinking'):
        result = {'message':'사용 권한이 없습니다.'}
        logSend(result['message'])
        func_end_log(func_name, 'OK')
        return REG_403_FORBIDDEN.to_json_response(result)

    result = []

    print(result)
    logSend(result)
    func_end_log(func_name, 'OK')
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
    if (not 'key' in rqst) or (len(rqst['key']) == 0) or (AES_DECRYPT_BASE64(rqst['key']) != 'thinking'):
        result = {'message':'사용 권한이 없습니다.'}
        logSend(result['message'])
        func_end_log(func_name, 'OK')
        return REG_403_FORBIDDEN.to_json_response(result)

    result = []

    print(result)
    logSend(result)
    func_end_log(func_name, 'OK')
    return REG_200_SUCCESS.to_json_response({'result':result})



