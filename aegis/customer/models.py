from django.db import models

# Create your models here.
"""
고객 업체
id
업체이름
계약서 번호
dt_등록
dt_승인
type - 발주업체, 파견업체, 협력업체 
파견업체 id
파견업체 이름 
담당자 id
담당자 이름 
담당자 전화번호 
담당자 이메일 
관리자 id
관리자 이름 
관리자 전화번호 
관리자 이메일 
사업자등록 id
dt_결재일
"""
class Customer(models.Model):
    name = models.CharField(max_length = 255, default = 'Not_Enter') # 암호화 한다.
    contract_no = models.CharField(max_length=33, default='') # 계약서 번호
    dt_reg = models.DateTimeField(auto_now_add = True) # 등록 일
    dt_accept = models.DateTimeField(null=True, blank=True) # 승인 일
    type = models.IntegerField(default=10) # 10 : 발주업체, 11 : 파견업체, 12 : 협력업체

    contractor_id = models.IntegerField(default=-1) # 파견업체, 도급업체 id
    contractor_name = models.CharField(max_length=127, default='') # 파견업체, 도급업체 이름

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
"""
사업자등록
    업체명
    사업자 등록번호 
    대표자 이름 
    사업장 주소 
    업태
    종목
    설립 연월일
"""
class Business_Registration(models.Model):
    name = models.CharField(max_length=127) # 상호
    regNo = models.CharField(max_length=127) # 사업자등록번호
    ceoName = models.CharField(max_length=127) # 성명(대표자)
    address = models.CharField(max_length=1024) # 사업장소재지
    business_type = models.CharField(max_length=1024) # 업태
    business_item = models.CharField(max_length=1024) # 종목
    dt_reg = models.DateTimeField(auto_now_add = True) # 사업자등록일
    customer_id = models.IntegerField() # 고객 id
"""
직원 (관리자, 담당자)
id 
파견업체 id 
이름
직위
소속
전화 번호 : phone_no
전화 종류 : phone_type 
push_token
이메일
"""
class Staff(models.Model):
    name = models.CharField(max_length=127) # 이름
    login_id = models.CharField(max_length=55, default='') # 로그인 id
    login_pw = models.CharField(max_length=55, default='happy_day!!!') # 로그인 pw
    co_id = models.IntegerField() # 소속사 id
    co_name = models.CharField(max_length=127) # 소속사 이름
    position = models.CharField(max_length=127) # 직위, 직책
    department = models.CharField(max_length=127) # 소속, 부서
    pNo = models.CharField(max_length = 19) # 전화번호
    pType = models.IntegerField(default=0) # 전화 종류
    # 10:iPhone, 20:Android
    push_token = models.CharField(max_length = 255, default='unknown')
    email = models.CharField(max_length = 320) # 이메일
"""
사업장
id
파견업체 id
사업장 이름 - (주)효성용연 1공장 
관리자 id
관리자 이름 - 이석호 상무
관리자 전화번호
발주사 id
발주사 이름 - (주)효성
"""
class Work_Place(models.Model):
    name = models.CharField(max_length=127) # 이름
    contractor_id = models.IntegerField() # 파견업체, 도급업체 id
    contractor_name = models.CharField(max_length=127) # 파견업체, 도급업체 이름
    place_name = models.CharField(max_length=127) # 현장 이름
    manager_id = models.IntegerField() # 관리자 id
    manager_name = models.CharField(max_length=127) # 관리자 이름
    manager_pNo = models.CharField(max_length = 19) # 관리자 전화번호
    manager_email = models.CharField(max_length = 320) # 관리자 이메일
    order_id = models.IntegerField() # 발주사 id
    order_name = models.IntegerField() # 발주사 상호
"""
업무 (사업장별)
id
사업장 id
사업장 이름 - (주)효성용연 2공장 업무 - 일반경비
형태-3교대
파견업체 이름 - 대덕기공 
파견업체 id
dt_begin
dt_end
담당자 id
담당자 이름
"""
class Work(models.Model):
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
"""
근로자 (업무별)
id
근로자 id
이름
전화 번호 : phone_no 
전화 종류 : phone_type 
push_token
"""
class Employee(models.Model):
    employee_id = models.IntegerField(default=-1) # 근로자 id
    employee_name = models.CharField(max_length=127, default='unknown') # 담당자 이름
    pNo = models.CharField(max_length = 19)
    pType = models.IntegerField(default=0)
    # 10:iPhone, 20:Android
    push_token = models.CharField(max_length = 255, default='unknown')
