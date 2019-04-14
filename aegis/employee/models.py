from django.db import models

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
    work_start_alarm = models.CharField(max_length = 20, default='')   # 출근 알람 1:00, 30, X
    work_end_alarm = models.CharField(max_length = 20, default='')     # 퇴근 알람 30, 0, X
    bank = models.CharField(max_length = 20, default='')            # 급여 은행
    bank_account = models.CharField(max_length = 20, default='')    # 급여 계좌
    work_id = models.IntegerField(default=-1)  # employee server work id
    work_id_2 = models.IntegerField(default=-1)  # employee server work id (투잡이나 아직 업무기간이 남았을 때)


class Notification_Work(models.Model):
    """
    근로자 앱이 처음 시작될 때 배정받은 업무가 있는지 저장하고 있는 table
    """
    work_id = models.IntegerField()  # employee server work id
    customer_work_id = models.CharField(max_length = 127, default='') # 암호화된 Customer 의 Work id 
    employee_id = models.IntegerField(default=-1) # 해당 근로자 id
    employee_pNo = models.CharField(max_length = 19) # 해당 근로자 전화번호
    dt_answer_deadline = models.DateTimeField(null=True, blank=True) # 업무 수락 / 거부 한계시간


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
    pType = models.IntegerField(default = 0)        # 0:unkown, 10:iPhone, 20:Android
    push_token = models.CharField(max_length = 255, default='')
    employee_id = models.IntegerField(default = -1) # 근로자 id -2:전화번호로 출입만 관리되는 사용자, -1: 근로자 정보가 없는 근로자, 1 이상: 근로자 정보가 있는 근로자
    notification_id = models.IntegerField(default = -1)    # 출입을 알릴 id (발주사, 파견 도급사, 협력사)
    cn = models.IntegerField(default = 0)           # 인증 번호 숫자 6자리
    dt_cn = models.DateTimeField(null=True, blank=True) # 인증 번호 유효시간


class Pass(models.Model):
    """
    출입
    id
    출입자 id
    action ( 0 : 출근 안함, 100 : 정상 출근, 200 : 지각 출근, 110 : 정상 퇴근, 120 : 조퇴 퇴근, 112 : 정상 출퇴근 외출 2회 )
    출입 등록 시간 : dt_reg 
    출입자 확인 시간 : dt_verify
    """
    passer_id = models.IntegerField()
    is_in = models.IntegerField(default=10) # ( 0 : 출근 안함, 100 : 정상 출근, 200 : 지각 출근, 110 : 정상 퇴근, 120 : 조퇴 퇴근, 112 : 정상 출퇴근 외출 2회 )
    dt_reg = models.DateTimeField(null=True, blank=True)
    dt_verify = models.DateTimeField(null=True, blank=True)

    x = models.FloatField(null=True, default=None) # 위도 latitude
    y = models.FloatField(null=True, default=None) # 경도 longitude


class Pass_History(models.Model):
    """
    일자별 출퇴근 기록
    """
    passer_id = models.IntegerField()
    action = models.IntegerField(default=10) # ( 0 : 출근 안함, 100 : 정상 출근, 200 : 지각 출근, 110 : 정상 퇴근, 120 : 조퇴 퇴근, 112 : 정상 출퇴근 외출 2회 )
    dt_in = models.DateTimeField(null=True, blank=True)         # 최초로 들어온 시간
    dt_in_verify = models.DateTimeField(null=True, blank=True)  # 근로자가 출근 버튼을 누른 시간
    dt_out = models.DateTimeField(null=True, blank=True)        # 최종 나간 시간
    dt_out_verify = models.DateTimeField(null=True, blank=True) # 근로자가 퇴근 버튼을 누른 시간
    minor = models.IntegerField()                               # 외출 횟수


class Beacon_History(models.Model):
    """
    비콘 history (날짜별)
    id
    major
    minor 
    출입자 id 
    begin_dt 
    begin_RSSI
    """
    major = models.IntegerField()
    minor = models.IntegerField()
    passer_id = models.IntegerField()
    dt_begin = models.DateTimeField(null=True, blank=True)
    RSSI_begin = models.IntegerField()

    x = models.FloatField(null=True, default=None) # 위도 latitude
    y = models.FloatField(null=True, default=None) # 경도 longitude


class Beacon(models.Model):
    """
    비콘
    uuid 
    major 
    minor 
    dt_last
    """
    uuid = models.CharField(max_length = 38) # 8-4-4-4-12
    major = models.IntegerField()
    minor = models.IntegerField()
    dt_last = models.DateTimeField(null=True, blank=True)

    x = models.FloatField(null=True, default=None) # 위도 latitude
    y = models.FloatField(null=True, default=None) # 경도 longitude

