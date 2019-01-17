from django.db import models

"""
 근로자
id
이름 : name
급여 은행 : bank
급여 계좌 : bank_account
"""
class Employee(models.Model):
    name = models.CharField(max_length = 127, default = 'unknown') # 암호화 한다.
    va_bank = models.CharField(max_length = 20, default='') # 급여 은행
    va_account = models.CharField(max_length = 20, default='') # 급여 계좌
    def __unicode__(self):
        return self.name

"""
출입자
id
전화 번호 : phone_no
전화 종류 : phone_type 
push_token
근로자 id : null (근로자 아님)
"""
class Passer(models.Model):
    pNo = models.CharField(max_length = 19)
    pType = models.IntegerField(default = 0)
    # 0:unkown, 10:iPhone, 20:Android
    push_token = models.CharField(max_length = 255, default='')
    employee_id = models.IntegerField(default = -1) # 차후 개인정보를 분리했을 때 개인정보 id (email, pNo, email, pw, name, dt_reg)
    alert_id = models.IntegerField(default = -1) # 출입을 알릴 id (발주사, 파견 도급사, 협력사)
    cn = models.IntegerField(default = 0) # 인증 문자
"""
출입
id
출입자 id
action ( 10 : 출근 11 : 지각 20 : 외출 30 : 퇴근 31 : 조퇴 )  
출입 등록 시간 : dt_reg 
출입자 확인 시간 : dt_verify
"""

class Pass(models.Model):
    passer_id = models.IntegerField()
    action = models.IntegerField(default=10) # ( 10 : 출근 11 : 지각 20 : 외출 30 : 퇴근 31 : 조퇴 )
    dt_reg = models.DateTimeField(auto_now_add = True)
    dt_verify = models.DateTimeField(auto_now_add = True)

"""
비콘 history (날짜별)
id
major
minor 
출입자 id 
begin_dt 
begin_RSSI
"""
class Beacon_History(models.Model):
    major = models.IntegerField()
    minor = models.IntegerField()
    passer_id = models.IntegerField()
    dt_begin = models.DateTimeField(auto_now_add = True)
    RSSI_begin = models.IntegerField()

"""
비콘
uuid 
major 
minor 
dt_last
"""

class Beacon(models.Model):
    uuid = models.CharField(max_length = 32) # 8-4-4-4-12
    major = models.IntegerField()
    minor = models.IntegerField()
    dt_last = models.DateTimeField(auto_now_add = True)
