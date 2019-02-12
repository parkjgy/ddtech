import json
import datetime
from datetime import timedelta
from django.conf import settings

from config.common import logSend, logError
from config.common import DateTimeEncoder, ValuesQuerySetToDict, exceptionError
from config.common import HttpResponse, ReqLibJsonResponse
from config.common import func_begin_log, func_end_log
from config.common import hash_SHA256
# secret import
from config.secret import AES_ENCRYPT_BASE64, AES_DECRYPT_BASE64
from config.decorator import cross_origin_read_allow

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


# @cross_origin_read_allow
class Env(object):
    def __init__(self):
        func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        self.is_running = False
        strToday = datetime.datetime.now().strftime("%Y-%m-%d ")
        str_dt_reload = strToday + '05:00:00'
        self.dt_reload = datetime.datetime.strptime(str_dt_reload, "%Y-%m-%d %H:%M:%S")
        self.start()
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])

    def __del__(self):
        func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        logSend(' <<< Environment class delete')
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])

    def loadEnvironment(self) :
        func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        if len(Environment.objects.filter()) == 0:
            newEnv = Environment(
                dt=datetime.datetime.now() - timedelta(days=3),
                manager_id=0,
                dt_android_upgrade=datetime.datetime.strptime('2019-01-01 00:00:00', "%Y-%m-%d %H:%M:%S"),
                timeCheckServer="05:00:00",
            )
            newEnv.save()
        note = '   Env: ' + self.dt_reload.strftime("%Y-%m-%d %H:%M:%S") + ' 이전 환경변수를 기준으로 한다.'
        print(note)
        logSend(note)
        envs = Environment.objects.filter(dt__lt = self.dt_reload).order_by('-id')
        note = '>>> no of environment = ' + str(len(envs))
        print(note)
        logSend(note)
        """
        i = 0
        for envCell in envs :
            logSend('   >>> ' + `i` + ' = ' + `envCell.id` + '' + `envCell.dt.strftime("%Y-%m-%d %H:%M:%S")`)
            i = i + 1
        """
        self.curEnv = envs[0]
        print('   Env: ')
        print('   >>> dt env = ' + self.curEnv.dt.strftime("%Y-%m-%d %H:%M:%S"))
        print('   >>> dt android = ' + self.curEnv.dt_android_upgrade.strftime("%Y-%m-%d %H:%M:%S"))
        print('   >>> timeCheckServer = ' + self.curEnv.timeCheckServer)
        strToday = datetime.datetime.now().strftime("%Y-%m-%d ")
        str_dt_reload = strToday + self.curEnv.timeCheckServer
        self.dt_reload = datetime.datetime.strptime(str_dt_reload, "%Y-%m-%d %H:%M:%S")
        if self.dt_reload < datetime.datetime.now() :  # 다시 로딩해야할 시간이 현재 시간 이전이면 내일 시간으로 바꾼다.
            self.dt_reload = self.dt_reload + timedelta(days = 1)
            logSend('       next load time + 24 hours')
        print('   >>> next load time = ' + self.dt_reload.strftime("%Y-%m-%d %H:%M:%S"))
        print('   >>> current time = ' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return

    def start(self):
        func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        if not self.is_running:
            self.loadEnvironment()
            self.is_running = True
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])

    def stop(self):
        func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        self.is_running = False
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])

    def current(self) :
        func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        if self.dt_reload < datetime.datetime.now() :
            self.is_running = False
            self.loadEnvironment()
            self.is_running = True
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return self.curEnv

    def self(self) :
        func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return self


env = Env()


@cross_origin_read_allow
@csrf_exempt
def testEnv(request) :
    """
    http://0.0.0.0:8000/operation/testEnv
    POST
    response
        STATUS 200
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    global env
    result = {}
    result['dt'] = env.current().dt.strftime("%Y-%m-%d %H:%M:%S")
    result['timeCheckServer'] = env.current().timeCheckServer

    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response(result)


@cross_origin_read_allow
@csrf_exempt
def currentEnv(request):
    """
    현재 환경 값을 요청한다.
    currentEnv (current environment) 현재 환경 값을 요청한다.
    http://0.0.0.0:8000/operation/currentEnv
    POST
    response
        STATUS 200
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    envirenments = Environment.objects.filter().order_by('-dt')
    array_env = []
    for envirenment in envirenments:
        new_env = {
            'dt': envirenment.dt.strftime("%Y-%m-%d %H:%M:%S"),
            'dt_android_upgrade':envirenment.dt_android_upgrade.strftime("%Y-%m-%d %H:%M:%S"),
            'timeCheckServer':envirenment.timeCheckServer
        }
        array_env.append(new_env)
    current_env = {
            'dt': env.curEnv.dt.strftime("%Y-%m-%d %H:%M:%S"),
            'dt_android_upgrade':env.curEnv.dt_android_upgrade.strftime("%Y-%m-%d %H:%M:%S"),
            'timeCheckServer':env.curEnv.timeCheckServer
        }
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response({'current_env':current_env, 'env_list':array_env})


@cross_origin_read_allow
@csrf_exempt
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    global env

    worker_id = request.session['id']
    if worker_id is None:
        print('403')
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_403_FORBIDDEN.to_json_response()
    worker = Staff.objects.get(id=worker_id)
    if not(worker.id in [1, 2]):
        print('524')
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_524_HAVE_NO_PERMISSION_TO_MODIFY.to_json_response()

    is_update = False

    dt_android_upgrade = rqst['dt_android_upgrade']
    print(' 1 ', dt_android_upgrade)
    print(' 2 ', env.current().dt_android_upgrade)
    if len(dt_android_upgrade) == 0 :
        dt_android_upgrade = env.current().dt_android_upgrade.strftime("%Y-%m-%d %H:%M:%S")
    else :
        is_update = True
    print(' 3 ', dt_android_upgrade)

    timeCheckServer = rqst['timeCheckServer']
    if len(timeCheckServer) == 0 :
        timeCheckServer = env.current().timeCheckServer
    else :
        is_update = True

    print(dt_android_upgrade)
    if is_update :
        env.stop()
        newEnv = Environment(
            dt = datetime.datetime.now(),
            manager_id = worker.id,
            dt_android_upgrade = datetime.datetime.strptime(dt_android_upgrade, "%Y-%m-%d %H:%M:%S"),
            timeCheckServer = timeCheckServer,
            )
        newEnv.save()
        env.start()
    print('200')
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
def reg_staff(request):
    """
    운영 직원 등록
    - 파라미터가 빈상태를 검사하지 않는다. (호출하는 쪽에서 검사)
    http://0.0.0.0:8000/operation/reg_staff?pNo=010-2557-3555&id=thinking&pw=a~~~8282&master=0eT00W2FDHML2aLERQX2UA
    POST
        {
            'pNo': '010-1111-2222',
            'id': 'thinking',
            'pw': 'a~~~8282'    # SHA256
        }
    response
        STATUS 200
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    if rqst.get('master') is None:
        worker_id = request.session['id']
        if worker_id is None:
            func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
            return REG_403_FORBIDDEN.to_json_response()
        worker = Staff.objects.get(id=worker_id)
    else:
        try:
            if AES_DECRYPT_BASE64(rqst['master']) != '3355':
                func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
                return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '마스터 키 오류'})
        except Exception as e:
            func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
            return REG_422_UNPROCESSABLE_ENTITY.to_json_response({'message': '마스터 키 오류 : ' + str(e)})

    phone_no = rqst['pNo']
    id_ = rqst['id']
    pw = rqst['pw']

    phone_no = phone_no.replace('-', '')
    phone_no = phone_no.replace(' ', '')
    print(phone_no)

    staffs = Staff.objects.filter(pNo=phone_no, login_id=id_)
    if len(staffs) > 0:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_542_DUPLICATE_PHONE_NO_OR_ID.to_json_response()
    new_staff = Staff(
        login_id=id_,
        login_pw=hash_SHA256(pw),
        pNo=phone_no
    )
    new_staff.save()
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    id_ = rqst['id']
    pw = rqst['pw']
    # staff = Staff.objects.get(id=1)
    # staff.login_pw = hash_SHA256(pw)
    # staff.save()

    staffs = Staff.objects.filter(login_id=id_, login_pw=hash_SHA256(pw))
    if len(staffs) == 0:
        print('530')
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_530_ID_OR_PASSWORD_IS_INCORRECT.to_json_response()
    staff = staffs[0]
    staff.is_login = True
    staff.dt_login = datetime.datetime.now()
    staff.save()

    request.session['id'] = staff.id
    request.session.save()
    print('200')
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.session['id'] is None:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_200_SUCCESS.to_json_response({'message':'이미 로그아웃되었습니다.'})
    staff = Staff.objects.get(id=request.session['id'])
    staff.is_login = False
    staff.dt_login = datetime.datetime.now()
    staff.save()
    request.session['id'] = None
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    if worker_id is None:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_403_FORBIDDEN.to_json_response()
    worker = Staff.objects.get(id=worker_id)

    login_id = rqst['login_id']  # id 로 사용
    before_pw = rqst['before_pw']  # 기존 비밀번호
    login_pw = rqst['login_pw']  # 변경하려는 비밀번호
    name = rqst['name']  # 이름
    position = rqst['position']  # 직책
    department = rqst['department']  # 부서 or 소속
    phone_no = rqst['phone_no']  # 전화번호
    phone_type = rqst['phone_type']  # 전화 종류    10:iPhone, 20: Android
    push_token = rqst['push_token']  # token
    email = rqst['email']  # id@ddtechi.co
    print(login_id, before_pw, login_pw, name, position, department, phone_no, phone_type, push_token, email)

    if len(phone_no) > 0:
        phone_no = phone_no.replace('-', '')
        phone_no = phone_no.replace(' ', '')
        print(phone_no)

    staff = worker
    # if worker.id != staff.id:
    #     staff.login_pw = hash_SHA256('happy_day82')
    #     func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    #     return REG_200_SUCCESS.to_json_response({'message': '비밀번호가 초기화 되었습니다.'})

    if hash_SHA256(before_pw) != staff.login_pw:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_531_PASSWORD_IS_INCORRECT.to_json_response()

    if len(login_id) > 0:
        if (Staff.objects.filter(login_id=login_id)) > 0:
            func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
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
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response()


@cross_origin_read_allow
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    if worker_id is None:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_403_FORBIDDEN.to_json_response()
    worker = Staff.objects.get(id=worker_id)

    # if rqst.get('master') is None:

    print(request.session.keys())
    for key in request.session.keys():
        print(key, ':', request.session[key])

    staffs = Staff.objects.filter()
    arr_staff = []
    for staff in staffs:
        r_staff = {
            'name':staff.name,
            'position':staff.position,
            'department':staff.department,
            'pNo':staff.pNo,
            'pType':staff.pType,
            'email':staff.email,
            'is_worker': True if staff.id == worker.id else False
        }
        arr_staff.append(r_staff)
    print(arr_staff)
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response({'staffs': arr_staff})


@cross_origin_read_allow
@csrf_exempt
def reg_customer(request):
    """
    고객사를 등록한다.
    - 간단한 내용만 넣어서 등록하고 나머지는 고객사 담당자가 추가하도록 한다.
    - 입력한 전화번호로 SMS 에 id 와 pw 를 보낸다. (회사 이름과 전화번호가 동일해야한다.)
        주) 항목이 비어있으면 수정하지 않는 항목으로 간주한다.
            response 는 추후 추가될 예정이다.
    http://0.0.0.0:8000/operation/reg_customer?re_sms=NO&customer_name=대덕테크&staff_name=박종기&staff_pNo=010-2557-3555&staff_email=thinking@ddtechi.com
    POST
        {
            're_sms': 'YES', # 문자 재요청인지 여부 (YES : SMS 재요청, NO : 신규 등록)
            'customer_name': '대덕기공',    # 문자 재전송 필수
            'staff_name': '홍길동',
            'staff_pNo': '010-1111-2222',   # 문자 재전송 필수
            'staff_email': 'id@daeducki.com'
        }
    response
        STATUS 200
    """
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    if worker_id is None:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_403_FORBIDDEN.to_json_response()
    worker = Staff.objects.get(id=worker_id)

    re_sms = rqst['re_sms']
    customer_name = rqst["customer_name"]
    staff_name = rqst["staff_name"]
    staff_pNo = rqst["staff_pNo"]
    staff_email = rqst["staff_email"]

    new_customer_data = {
        're_sms': re_sms,
        'customer_name': customer_name,
        'staff_name': staff_name,
        'staff_pNo': staff_pNo,
        'staff_email': staff_email,
        'worker_id': worker.id
    }
    response_customer = requests.post(settings.CUSTOMER_URL + 'reg_customer', json=new_customer_data)
    print('status', response_customer.status_code, response_customer.json())
    if response_customer.status_code != 200:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return ReqLibJsonResponse(response_customer)
    response_customer_json = response_customer.json()
    print('아이디 ' + response_customer_json['login_id'] + '\n' + '비밀번호 ' + response_customer_json['login_pw'])
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

    print(r.json())

    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response({'message': 'SMS 로 아이디와 초기회된 비밀번호를 보냈습니다.'})


@cross_origin_read_allow
@csrf_exempt
def list_customer(request):
    """
    고객사 리스트를 요청한다.
    http://0.0.0.0:8000/operation/list_customer?customer_name=대덕테크&staff_name=박종기&staff_pNo=010-2557-3555&staff_email=thinking@ddtechi.com
    GET
        customer_name=대덕기공
        staff_name=홍길동
        staff_pNo=010-1111-2222
        staff_email=id@daeducki.com
    response
        STATUS 200
    """
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    worker_id = request.session['id']
    if worker_id is None:
        func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
        return REG_403_FORBIDDEN.to_json_response()
    worker = Staff.objects.get(id=worker_id)

    customer_name = rqst['customer_name']
    staff_name = rqst['staff_name']
    staff_pNo = rqst['staff_pNo']
    staff_email = rqst['staff_email']

    json_data = {
        'customer_name': customer_name,
        'staff_name': staff_name,
        'staff_pNo': staff_pNo,
        'staff_email': staff_email,
        'worker_id': worker.id
    }
    response_customer = requests.get(settings.CUSTOMER_URL + 'list_customer', params=json_data)
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return ReqLibJsonResponse(response_customer)


@cross_origin_read_allow
def update_work_place(request):
    """
    사업장 내용을 수정한다.
        주)    항목이 비어있으면 수정하지 않는 항목으로 간주한다.
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
    func_begin_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    if request.method == 'POST':
        rqst = json.loads(request.body.decode("utf-8"))
    else:
        rqst = request.GET

    # worker_id = request.session['id']
    # worker = Staff.objects.get(id=worker_id)

    global env
    result = {'dt_update':env.curEnv.dt_android_upgrade.strftime('%Y-%m-%d %H:%M:%S')}
    func_end_log(__package__.rsplit('.', 1)[-1], inspect.stack()[0][3])
    return REG_200_SUCCESS.to_json_response(result)
