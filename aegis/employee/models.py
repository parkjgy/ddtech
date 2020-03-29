from django.db import models

import json

class Employee(models.Model):
    """
     근로자
    id
    이름 : name
    급여 은행 : bank
    급여 계좌 : bank_account
    """
    name = models.CharField(max_length = 127, default = 'unknown')  # 암호화 한다.

    work_start = models.CharField(max_length = 20, default='')         # 출근 시간 23:00
    working_time = models.CharField(max_length = 20, default='')       # 근무 시간 04 ~ 12
    rest_time = models.CharField(max_length = 7, default='-1')          # 근무 시간 00:30 ~ 06:00
    work_start_alarm = models.CharField(max_length = 20, default='')   # 출근 알람 1:00, 30, X
    work_end_alarm = models.CharField(max_length = 20, default='')     # 퇴근 알람 30, 0, X
    
    bank = models.CharField(max_length = 20, default='')            # 급여 은행
    bank_account = models.CharField(max_length=20, default='')    # 급여 계좌

    works = models.CharField(max_length=1024, default='[]')  # data type: json: [ {'id': 99, 'begin': '2019/05/05', 'end': '2019/06/06'}, {'id': 999, 'begin': '2019/06/06', 'end': '2019/07/07'} ]
    dt_reg = models.DateTimeField(auto_now_add=True) # 등록 일

    def set_works(self, x):
        self.works = json.dumps(x)

    def get_works(self):
        if len(self.works) == 0:
            self.works = "[]"
        return json.loads(self.works)


class Employee_Backup(models.Model):    
    """업무가 끝난 근로자 backup"""
    dt_begin = models.DateTimeField(null=True, blank=True) # 근무 시작일
    dt_end = models.DateTimeField(null=True, blank=True) # 근무 종료일

    work_id = models.IntegerField() # 업무 id

    passer_id = models.IntegerField() # 업무 id
    employee_id = models.IntegerField(default=-1) # 출입 서버의 근로자 id (실제 근로자 서버에서는 passer_id)
    name = models.CharField(max_length=127, default='-----') # 근로자 이름
    pNo = models.CharField(max_length = 19)


class Notification_Work(models.Model):
    """
    근로자 앱이 처음 시작될 때 배정받은 업무가 있는지 저장하고 있는 table
    """
    work_id = models.IntegerField()  # employee server work id
    customer_work_id = models.CharField(max_length = 127, default='') # 암호화된 Customer 의 Work id 
    employee_id = models.IntegerField(default=-1)           # 해당 근로자 id
    employee_pNo = models.CharField(max_length = 19)        # 해당 근로자 전화번호
    dt_answer_deadline = models.DateTimeField(null=True, blank=True) # 업무 수락 / 거부 한계시간
    dt_begin = models.DateTimeField(null=True, blank=True)  # 해당 근로자의 업무 시작 날짜
    dt_end = models.DateTimeField(null=True, blank=True)  # 해당 근로자의 업무 종료 날짜

    dt_reg = models.DateTimeField(auto_now_add=True)    # 등록이 요청된 날짜 : 시스템 관리용
    work_place_name = models.CharField(max_length=127)  # 사업장 이름 : 시스템 관리용
    work_name_type = models.CharField(max_length=255)   # 업무 이름 : 시스템 관리용
    is_x = models.IntegerField(default=False)           # 0: 알림 답변 전 상태, 1: 알림 확인 적용된 상태, 2: 알림 내용 거절, 3: 알림 확인 시한 지남

    notification_type = models.IntegerField(default=-30)        # 알림 종류: -30: 새업무 알림, -21: 퇴근시간 수정, -20: 출근시간 수정, -4: 유급휴일 해제, -3: 유급휴일 지정, -2: 연차휴무, -1: 조기퇴근, 0:정상근무, 1~18: 연장근무 시간
    comment = models.CharField(max_length=512, default = "")    # -3 ~ -1: 관리자가 근로자에게 전달할 사유
    staff_id = models.IntegerField(default=-1)                  # 알림을 보내는 관리자 id
    dt_inout = models.DateTimeField(null=True, blank=True)      # 변경된 출퇴근시간이 저장된다.

        
class Work(models.Model):
    """
    고객 서버로 부터 받은 업무 내역
    - 사용: Notification_Work, Employee
    """
    customer_work_id = models.CharField(max_length = 127, default='') # 암호화된 Customer 의 Work id 

    work_place_name = models.CharField(max_length=127) # 사업장 이름
    work_name_type = models.CharField(max_length=255) # 업무 이름
    begin = models.CharField(max_length=127) # 근무 시작 날짜
    end = models.CharField(max_length=127) # 근무 종료 날짜
    staff_name = models.CharField(max_length=127) # 담당자 이름
    staff_pNo = models.CharField(max_length = 19) # 담당자 전화번호

    time_info = models.CharField(max_length=8191, default='{}')  # 급여형태, 소정근로시간, 소정근로일, 유급휴일, 무급휴일 계산방법, 근무시간(09:00~18:00 0 12:00~13:00)

    def set_time_info(self, x):
        self.time_info = json.dumps(x)
        print(len(self.time_info))

    def get_time_info(self):
        if self.time_info is None or len(self.time_info) == 0:
            self.time_info = "{}"
        return json.loads(self.time_info)

    major = models.IntegerField(default=-1)
    minor = models.IntegerField(default=-1)


class Passer(models.Model):
    """
    출입자
    id
    전화 번호 : phone_no
    전화 종류 : phone_type 
    push_token
    근로자 id : null (근로자 아님)
    """
    pNo = models.CharField(max_length = 19)
    pType = models.IntegerField(default = 0)        # 0:unkown, 10:iPhone, 20:Android, 30:피쳐폰
    push_token = models.CharField(max_length = 255, default='')
    uuid = models.CharField(max_length = 64, default=None)  # 앱이 하나의 폰에만 설치되서 사용하도록 하기위한 기기 고유 값을 서버에서 만들어 보내는 값
    app_version = models.CharField(max_length = 20, default=None)  # 앱 버전

    employee_id = models.IntegerField(default = -1) # 근로자 id -2:전화번호로 출입만 관리되는 사용자, -1: 근로자 정보가 없는 근로자, 1 이상: 근로자 정보가 있는 근로자
    notification_id = models.IntegerField(default = -1)    # 출입을 알릴 id (발주사, 파견 도급사, 협력사)
    cn = models.IntegerField(default = 0)           # 인증 번호 숫자 6자리
    dt_cn = models.DateTimeField(null=True, blank=True) # 인증 번호 유효시간
    user_agent = models.CharField(max_length = 512, default=None) # HTTP_USER_AGENT
    is_recruiting = models.BooleanField(default=False)     # 카메라 사용 금지 toggle

    notification_count = models.IntegerField(default=0)     # 미응답 알림 갯수


class Pass(models.Model):
    """
    출입
    id
    출입자 id
    is_in   # 0:out, 1:in
    출입 등록 시간 : dt_reg 
    출입자 확인 시간 : dt_verify
    """
    passer_id = models.IntegerField(default=-1)
    is_in = models.BooleanField(null=True, blank=True)
    is_beacon = models.BooleanField(null=True, blank=True)
    # dt_reg = models.DateTimeField(null=True, blank=True)
    # dt_verify = models.DateTimeField(null=True, blank=True)
    dt = models.DateTimeField(null=True, blank=True)

    x = models.FloatField(null=True, default=None) # 위도 latitude
    y = models.FloatField(null=True, default=None) # 경도 longitude


class Pass_History(models.Model):
    """
    일자별 출퇴근 기록
    """
    passer_id = models.IntegerField()
    year_month_day = models.CharField(max_length=11, blank=True)

    action = models.IntegerField(default=0)                     # ( 0 : 출근 안함, 100 : 정상 출근, 200 : 지각 출근, 110 : 정상 퇴근, 120 : 조퇴 퇴근, 112 : 정상 출퇴근 외출 2회 )
    work_id = models.IntegerField()                             # Work id 

    dt_in = models.DateTimeField(null=True, blank=True)         # 최초로 들어온 시간
    dt_in_em = models.DateTimeField(null=True, blank=True)      # 근로자가 출근 버튼을 누른 시간
    dt_in_verify = models.DateTimeField(null=True, blank=True)  # 관리자가 수정한 시간 포함 최종 출근 시간
    in_staff_id = models.IntegerField(default=-1)               # 출근 시간이 수정한 현장 관리자 id

    dt_out = models.DateTimeField(null=True, blank=True)        # 최종 나간 시간
    dt_out_em = models.DateTimeField(null=True, blank=True)     # 근로자가 퇴근 버튼을 누른 시간
    dt_out_verify = models.DateTimeField(null=True, blank=True) # 관리자가 수정한 시간 포함 최종 퇴근 시간
    out_staff_id = models.IntegerField(default=-1)              # 퇴근 시간을 수정한 현장 관리자 id

    overtime = models.IntegerField(default=0)                   # 연장 근무 -3: 유급휴일, -2: 연차휴무, -1: 조기퇴근, 0: 정상 근무, 1~18: 연장 근무 시간( 1:30분, 2:1시간, 3:1:30, 4:2:00, 5:2:30, 6:3:00 7: 3:30, 8: 4:00, 9: 4:30, 10: 5:00, 11: 5:30, 12: 6:00, 13: 6:30, 14: 7:00, 15: 7:30, 16: 8:00, 17: 8:30, 18: 9:00)
    overtime_staff_id = models.IntegerField(default=-1)         # 연장 근무 현장 관리자 id (기본: -1 (현장 소장이 dt_in_verify, dt_out_verify 를 수정하지 않았을 때))

    # rest_time = models.CharField(max_length = 20, default='')          # 휴계시간 0:30, 1:30, 2:00, 2:30, 3:00, 3:30, 4:00, 4:30, 5:00

    dt_accept = models.DateTimeField(null=True, blank=True)     # 변경된 근태정보에 대한 확인이 이루어진 시간

    is_not_paid_holiday = models.IntegerField(default=2)        # 0: 유급휴일, 1 무급휴일, 2: 소정근로일
    paid_holiday_staff_id = models.IntegerField(default=-1)     # 유급휴일을 부여한 현장 관리자 id

    x = models.FloatField(null=True, default=None) # 위도 latitude
    y = models.FloatField(null=True, default=None) # 경도 longitude



class Beacon(models.Model):
    """
    설치된 비콘 정보
    """
    uuid = models.CharField(max_length = 38) # 8-4-4-4-12
    major = models.IntegerField(default=-1)
    minor = models.IntegerField(default=-1)
    dt_last = models.DateTimeField(null=True, blank=True)       # 비콘이 마지막 인식된 날짜
    last_passer_id = models.IntegerField(default=-1)            # 마지막으로 비콘 인식된 근로자 id - 비콘의 위치가 바뀌었거나 변경되는 등의 문제가 발생했을 때 파악이 목적

    # 아래는 설치시 저장
    dt_battery = models.DateTimeField(null=True, blank=True)    # 마지막 배터리 교체일
    dt_install = models.DateTimeField(null=True, blank=True)    # 비콘이 설치된 날짜
    customer_order_id = models.IntegerField(default=-1)         # 비콘이 설치된 발주사 id
    operation_staff_id = models.IntegerField(default=-1)        # 비콘 관리직원 id

    x = models.FloatField(null=True, default=None) # 위도 latitude
    y = models.FloatField(null=True, default=None) # 경도 longitude


class Beacon_Record(models.Model):
    """
    pass_reg 에서 들어온 beacon 값을 모두 저장 - 참고용
    """
    major = models.IntegerField(default=-1)
    minor = models.IntegerField(default=-1)
    passer_id = models.IntegerField(default=-1)
    dt_begin = models.DateTimeField(null=True, blank=True)
    rssi = models.IntegerField(default=-1)
    dt_end = models.DateTimeField(null=True, blank=True)
    count = models.IntegerField(default=-1)
    is_test = models.BooleanField(default=False)

    x = models.FloatField(null=True, default=None) # 위도 latitude
    y = models.FloatField(null=True, default=None) # 경도 longitude

# class IO_Pass(models.Model):
#     passer_id = models.IntegerField(default=-1)
#     name = models.CharField(max_length = 127, default = 'unknown')  # 암호화 한다.
#     pNo = models.CharField(max_length = 19)
#     contents = models.CharField(max_length = 127)  # 암호화 한다.
#     dt = models.DateTimeField(null=True, blank=True)
#     is_accept = models.BooleanField(blank=True)
#     why = models.CharField(max_length = 127, default = '')  # 암호화 한다.


