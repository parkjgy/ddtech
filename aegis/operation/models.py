from django.db import models

import json

# 환경 저장
class Environment(models.Model):
    dt = models.DateTimeField(null=True, blank=True) 
    dt_android_upgrade = models.DateTimeField(auto_now_add = False)     # 이 날짜 이전 '이지체크 안드로이드 근로자 앱' 은 업그레이드 필요
    dt_android_mng_upgrade = models.DateTimeField(auto_now_add = False) # 이 날짜 이전 '이지체크 안드로이드 관리자 앱' 은 업그레이드 필요
    dt_iOS_upgrade = models.DateTimeField(auto_now_add = False)         # 이 날짜 이전 '이지체크 아이폰 근로자 앱' 은 업그레이드 필요
    dt_iOS_mng_upgrade = models.DateTimeField(auto_now_add = False)     # 이 날짜 이전 '이지체크 아이폰 관리자 앱' 은 업그레이드 필요
    manager_id = models.IntegerField(default = 0)                   # 환경 변경 직원 id
    timeCheckServer =  models.CharField(max_length = 15)            # 서버 점검 시간 (09:00:00 형식의 문자열)


class Staff(models.Model):
    """
    직원
    """
    login_id = models.CharField(max_length=128) # 로그인 id
    login_pw = models.CharField(max_length=128) # 로그인 pw
    name = models.CharField(max_length=128, default='unknown') # 이름
    position = models.CharField(max_length=64, default='') # 직위, 직책
    department = models.CharField(max_length=64, default='') # 소속, 부서
    pNo = models.CharField(max_length = 24) # 전화번호
    pType = models.IntegerField(default=0) # 전화 종류 # 10:iPhone, 20:Android
    push_token = models.CharField(max_length = 256, default='unknown')
    email = models.CharField(max_length = 512, default='unknown') # 이메일
    is_app_login = models.BooleanField(default=False) # 앱에서 로그인이 되었는가?
    dt_app_login = models.DateTimeField(blank=True, null=True) # 마지막 로그인 시간 (마지막 로그인 시간으로 부터 15분이 지나면 id pw 확인)
    is_login = models.BooleanField(default=False) # 로그인이 되었는가?
    dt_login = models.DateTimeField(blank=True, null=True) # 마지막 로그인 시간 (마지막 로그인 시간으로 부터 15분이 지나면 id pw 확인)


class Work_Place(models.Model):
    """
    사업장
    """
    major = models.IntegerField(default=0) # beacon major
    staff_id = models.IntegerField(default=-1) # 담당자 id
    staff_name = models.CharField(max_length=127, default='unknown') # 담당자 이름
    staff_pNo = models.CharField(max_length = 19, default='') # 담당자 전화번호

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


class Beacon(models.Model):
    """
    비콘
    """
    uuid = models.CharField(max_length = 36, default='12345678-0000-0000-123456789012') # 8-4-4-4-12
    major = models.IntegerField(default=0)
    minor = models.IntegerField(default=0)
    dt_last = models.DateTimeField(null=True, blank=True)
    dt_battery = models.DateTimeField(null=True, blank=True)
    work_place_id = models.IntegerField(default=-1) # 사업장 id


# class Employee(models.Model):
#     """
#     직원 시험
#     """
#     name = models.CharField(max_length=127, default='unknown')
#     work = models.CharField(max_length=1024)

#     def set_works(self, x):
#         self.work = json.dumps(x)

#     def get_works(self):
#         return json.loads(self.work)

