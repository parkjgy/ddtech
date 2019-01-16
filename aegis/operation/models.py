from django.db import models

"""
직원 (관리자, 담당자)
id 
login_id
login_pw
이름
직위
소속
전화 번호 : phone_no
전화 종류 : phone_type 
push_token
이메일
"""
class Staff(models.Model):
    login_id = models.CharField(max_length=55) # 로그인 id
    login_pw = models.CharField(max_length=55) # 로그인 pw
    name = models.CharField(max_length=127, default='unknown') # 이름
    position = models.CharField(max_length=33, default='') # 직위, 직책
    department = models.CharField(max_length=33, default='') # 소속, 부서
    pNo = models.CharField(max_length = 19) # 전화번호
    pType = models.IntegerField(default=0, default=0) # 전화 종류
    # 10:iPhone, 20:Android
    push_token = models.CharField(max_length = 255, default='unknown')
    email = models.CharField(max_length = 320, default='unknown') # 이메일

"""
사업장
id
major
staff_id
staff_name
staff_pNo
사업장 이름 - (주)효성용연 1공장
파견업체 id
파견업체 상호
관리자 id
관리자 이름 - 이석호 상무
관리자 전화번호
관리자 이메일
발주사 id
발주사 이름 - (주)효성
발주사 담당자 id
발주사 담당자 이름 - 이석호 상무
발주사 담당자 전화번호
발주사 담당자 이메일
"""
class Work_Place(models.Model):
    major = models.IntegerField(default=0) # beacon major
    order_staff_id = models.IntegerField(default=-1) # 담당자 id
    order_staff_name = models.CharField(max_length=127, default='unknown') # 담당자 이름
    order_staff_pNo = models.CharField(max_length = 19, default='') # 담당자 전화번호

    place_name = models.CharField(max_length=127, default='unknown') # 현장 이름
    contractor_id = models.IntegerField(default=-1) # 파견업체, 도급업체 id
    contractor_name = models.CharField(max_length=127, default='unknown') # 파견업체, 도급업체 상호

    manager_id = models.IntegerField(default=-1) # 관리자 id
    manager_name = models.CharField(max_length=127, default='unknown') # 관리자 이름
    manager_pNo = models.CharField(max_length = 19, default='') # 관리자 전화번호
    manager_email = models.CharField(max_length = 320, default='') # 관리자 이메일

    order_id = models.IntegerField(default=-1) # 발주사 id
    order_name = models.CharField(max_length=127, default='unknown') # 발주사 상호
    order_staff_id = models.IntegerField(default=-1) # 발주사 담당자 id
    order_staff_name = models.CharField(max_length=127, default='unknown') # 발주사 담당자 이름
    order_staff_pNo = models.CharField(max_length = 19, default='') # 발주사 담당자 전화번호
    order_staff_email = models.CharField(max_length = 320, default='') # 발주사 담당자 이메일

"""
비콘
id
major
minor
work_place_id
dt_last
uuid
"""
class Beacon(models.Model):
    uuid = models.CharField(max_length = 36, default='12345678-0000-0000-123456789012') # 8-4-4-4-12
    major = models.IntegerField(default=0)
    minor = models.IntegerField(default=0)
    dt_last = models.DateTimeField(auto_now_add = True)
    dt_battery = models.DateTimeField(auto_now_add = True)
    work_place_id = models.IntegerField(default=-1) # 사업장 id

