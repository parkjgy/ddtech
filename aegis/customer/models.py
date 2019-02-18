from django.db import models

# Create your models here.
class Customer(models.Model):
    """
    고객사(수요기업, 파견업체, 도급업체)
    """
    corp_name = models.CharField(max_length = 255, default = 'Not_Enter') # 암호화 한다.
    contract_no = models.CharField(max_length=33, blank=True) # 계약서 번호
    dt_reg = models.DateTimeField(auto_now_add = True) # 등록 일
    dt_accept = models.DateTimeField(null=True, blank=True) # 승인 일
    type = models.IntegerField(default=10) # 10 : 발주업체, 11 : 파견업체, 12 : 협력업체

    # contractor_id = models.IntegerField(default=-1) # 파견업체, 도급업체 id
    # contractor_name = models.CharField(max_length=127, default='') # 파견업체, 도급업체 이름

    staff_id = models.IntegerField(default=-1) # 담당자 id
    staff_name = models.CharField(max_length=127) # 담당자 이름
    staff_pNo = models.CharField(max_length = 19) # 담당자 전화번호
    staff_email = models.CharField(max_length = 320) # 담당자 이메일

    manager_id = models.IntegerField(default=-1) # 관리자 id
    manager_name = models.CharField(max_length=127, default='') # 관리자 이름
    manager_pNo = models.CharField(max_length = 19, default='') # 관리자 전화번호
    manager_email = models.CharField(max_length = 320, default='') # 관리자 이메일

    business_reg_id = models.IntegerField(default=-1) # 사업자등록 id
    dt_payment = models.DateTimeField(null=True, blank=True) # 결재일


class Relationship(models.Model):
    """
    고객사의 협력사 or 발주사
    """
    contractor_id = models.IntegerField(default=-1) # 고객사, 수요기업 파견업체, 도급업체 id
    type = models.IntegerField(default=10) # 10 : 발주업체, 11 : 파견업체, 12 : 협력업체

    corp_id = models.IntegerField(default=-1) # 협력사 나 발주사 id
    corp_name = models.CharField(max_length=127, default='None') # 협력사 나 발주사 이름
        

class Business_Registration(models.Model):
    """
    사업자 등록 자료
    """
    customer_id = models.IntegerField(default=-1) # 고객 id
    name = models.CharField(max_length=127, blank=True) # 상호
    regNo = models.CharField(max_length=127, blank=True) # 사업자등록번호
    ceoName = models.CharField(max_length=127, blank=True) # 성명(대표자)
    address = models.CharField(max_length=1024, blank=True) # 사업장소재지
    business_type = models.CharField(max_length=1024, blank=True) # 업태
    business_item = models.CharField(max_length=1024, blank=True) # 종목
    dt_reg = models.DateTimeField(auto_now_add = False, blank=True) # 사업자등록일


class Staff(models.Model):
    """
    사원(관리자, 담당자)
    """
    name = models.CharField(max_length=127) # 이름
    login_id = models.CharField(max_length=128, default='') # 로그인 id
    login_pw = models.CharField(max_length=128, default='happy_day!!!') # 로그인 pw
    co_id = models.IntegerField(default=-1) # 소속사 id
    co_name = models.CharField(max_length=127, default='unknown') # 소속사 이름
    position = models.CharField(max_length=127, default='') # 직위, 직책
    department = models.CharField(max_length=127, default='') # 소속, 부서
    pNo = models.CharField(max_length = 19, default='') # 전화번호
    pType = models.IntegerField(default=0) # 전화 종류 10:iPhone, 20:Android
    push_token = models.CharField(max_length = 255, default='unknown')
    email = models.CharField(max_length = 320, default='') # 이메일
    is_app_login = models.BooleanField(default=False) # 현장소장용 앱에서 로그인이 되었는가?
    dt_app_login = models.DateTimeField(auto_now_add=True, blank=True) # 마지막 로그인 시간 (마지막 로그인 시간으로 부터 15분이 지나면 id pw 확인)
    is_login = models.BooleanField(default=False) # 로그인이 되었는가?
    dt_login = models.DateTimeField(auto_now_add=True, blank=True) # 마지막 로그인 시간 (마지막 로그인 시간으로 부터 15분이 지나면 id pw 확인)
    is_site_owner = models.BooleanField(default=False) # 고객사 담당자 인가?
    is_manager = models.BooleanField(default=False) # 고객사 관리자 인가?


class Work_Place(models.Model):
    """
    사업장
    """
    name = models.CharField(max_length=127) # 이름
    contractor_id = models.IntegerField() # 파견업체, 도급업체 id
    contractor_name = models.CharField(max_length=127) # 파견업체, 도급업체 이름
    place_name = models.CharField(max_length=127) # 현장 이름
    manager_id = models.IntegerField() # 관리자 id
    manager_name = models.CharField(max_length=127) # 관리자 이름
    manager_pNo = models.CharField(max_length = 19) # 관리자 전화번호
    manager_email = models.CharField(max_length = 320) # 관리자 이메일
    order_id = models.IntegerField() # 발주사 id
    order_name = models.CharField(max_length=127) # 발주사 상호


class Work(models.Model):
    """
    업무 (사업장별)
    """
    name = models.CharField(max_length=127) # 이름
    work_place_id = models.IntegerField() # 사업장 id
    work_place_name = models.CharField(max_length=127) # 사업장 이름
    type = models.CharField(max_length=127) # 업무 형태
    contractor_id = models.IntegerField() # 파견업체, 도급업체 id
    contractor_name = models.CharField(max_length=127) # 파견업체, 도급업체 이름

    dt_begin = models.DateTimeField(auto_now_add = True) # 작업 시작일
    dt_end = models.DateTimeField(null=True, blank=True) # 작업 종료일

    staff_id = models.IntegerField() # 담당자 id
    staff_name = models.CharField(max_length=127) # 담당자 이름
    staff_pNo = models.CharField(max_length = 19) # 담당자 전화번호
    staff_email = models.CharField(max_length = 320) # 담당자 이메일


class Employee(models.Model):
    """
    근로자 (업무별)
    """
    is_active = models.BooleanField(default=False) # 0 (NO) 근무 중이 아님, 1 (YES) 근무 중

    dt_begin = models.DateTimeField(auto_now_add = True) # 근무 시작일
    dt_end = models.DateTimeField(null=True, blank=True) # 근무 종료일

    work_id = models.IntegerField() # 업무 id
    work_name = models.CharField(max_length=127) # 업무 이름
    work_place_name = models.CharField(max_length=127) # 사업장 이름

    employee_id = models.IntegerField(default=-1) # 근로자 id
    name = models.CharField(max_length=127, default='unknown') # 근로자 이름
    pNo = models.CharField(max_length = 19)
