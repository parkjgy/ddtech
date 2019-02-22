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
    bank = models.CharField(max_length = 20, default='')            # 급여 은행
    bank_account = models.CharField(max_length = 20, default='')    # 급여 계좌


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
    employee_id = models.IntegerField(default = -1) # 차후 개인정보를 분리했을 때 개인정보 id (email, pNo, email, pw, name, dt_reg)
    alert_id = models.IntegerField(default = -1)    # 출입을 알릴 id (발주사, 파견 도급사, 협력사)
    cn = models.IntegerField(default = 0)           # 인증 문자


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
    dt_begin = models.DateTimeField(auto_now_add = True)
    RSSI_begin = models.IntegerField()


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
    dt_last = models.DateTimeField(auto_now_add = True)
