from django.db import models
import json

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

    # contractor_id = models.IntegerField(default=-1) # 협력업체일 경우 파견업체(도급업체) id
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
    is_contractor = models.BooleanField(default=False) # 도급업체(우리고객사)인가? 


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
    name = models.CharField(max_length=127, null=True) # 상호
    regNo = models.CharField(max_length=127, null=True) # 사업자등록번호
    ceoName = models.CharField(max_length=127, null=True) # 성명(대표자)
    address = models.CharField(max_length=1024, null=True) # 사업장소재지
    business_type = models.CharField(max_length=1024, null=True) # 업태
    business_item = models.CharField(max_length=1024, null=True) # 종목
    dt_reg = models.DateTimeField(null=True, blank=True) # 사업자등록일


class Staff(models.Model):
    """
    사원(관리자, 담당자)
    """
    name = models.CharField(max_length=127) # 이름
    login_id = models.CharField(max_length=128) # 로그인 id
    login_pw = models.CharField(max_length=128) # 로그인 pw
    co_id = models.IntegerField(default=-1) # 소속사 id
    co_name = models.CharField(max_length=127, default='unknown') # 소속사 이름
    position = models.CharField(max_length=127, default='') # 직위, 직책
    department = models.CharField(max_length=127, default='') # 소속, 부서
    pNo = models.CharField(max_length = 19, default='') # 전화번호
    pType = models.IntegerField(default=0) # 전화 종류 10:iPhone, 20:Android
    push_token = models.CharField(max_length = 255, default='unknown')
    email = models.CharField(max_length = 320, default='') # 이메일
    is_app_login = models.BooleanField(default=False) # 현장소장용 앱에서 로그인이 되었는가?
    dt_app_login = models.DateTimeField(null=True, blank=True) # 마지막 로그인 시간 (마지막 로그인 시간으로 부터 15분이 지나면 id pw 확인)
    is_login = models.BooleanField(default=False) # 로그인이 되었는가?
    dt_login = models.DateTimeField(null=True, blank=True) # 마지막 로그인 시간 (마지막 로그인 시간으로 부터 15분이 지나면 id pw 확인)
    is_site_owner = models.BooleanField(default=False) # 고객사 담당자 인가?
    is_manager = models.BooleanField(default=False) # 고객사 관리자 인가?
    is_push_touch = models.BooleanField(default=False) # 근로자의 출퇴근을 푸시로 받는다?
    app_version = models.CharField(max_length=20, default='') # 관리자 앱 버전


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
    address = models.CharField(max_length=256, default='') # 사업장 주소 - beacon 을 설치할 주소

    x = models.FloatField(null=True, default=None) # 위도 latitude
    y = models.FloatField(null=True, default=None) # 경도 longitude


class Work(models.Model):
    """
    업무 (사업장별)
    """
    name = models.CharField(max_length=127) # 이름
    work_place_id = models.IntegerField() # 사업장 id
    work_place_name = models.CharField(max_length=127) # 사업장 이름
    type = models.CharField(max_length=127) # 업무 형태 (주간, 야간, 3교대, 2교대, ...)
    contractor_id = models.IntegerField() # 파견업체, 도급업체 id
    contractor_name = models.CharField(max_length=127) # 파견업체, 도급업체 이름

    dt_begin = models.DateTimeField(null=True, blank=True) # 작업 시작일
    dt_end = models.DateTimeField(null=True, blank=True) # 작업 종료일

    staff_id = models.IntegerField() # 담당자 id
    staff_name = models.CharField(max_length=127) # 담당자 이름
    staff_pNo = models.CharField(max_length = 19) # 담당자 전화번호
    staff_email = models.CharField(max_length = 320) # 담당자 이메일

    enable_post = models.BooleanField(default=False)    # 채용 알림 사용 여부
    is_recruiting = models.BooleanField(default=False)  # 채용 중인가?

    time_info = models.CharField(max_length=8191, default='{}')  # 급여형태, 소정근로시간, 소정근로일, 유급휴일, 무급휴일 계산방법, 근무시간(09:00~18:00 0 12:00~13:00)

    def set_time_info(self, x):
        self.time_info = json.dumps(x)
        # print(len(self.time_info))

    def get_time_info(self):
        if self.time_info is None or len(self.time_info) == 0:
            self.time_info = "{}"
        return json.loads(self.time_info)


class Employee(models.Model):
    """
    근로자 (업무별)
    """
    is_accept_work = models.BooleanField(null=True, blank=True) # null : 선택하지 않음, True: 업무에 승락, False: 업무를 거부
    is_active = models.BooleanField(default=False) # 0 (False) 근무 중이 아님, 1 (True) 근무 중
    dt_accept = models.DateTimeField(auto_now_add = True) # 등록 일

    dt_begin = models.DateTimeField(null=True, blank=True) # 근무 시작일
    dt_end = models.DateTimeField(null=True, blank=True) # 근무 종료일

    work_id = models.IntegerField() # 업무 id

    employee_id = models.IntegerField(default=-1) # 출입 서버의 근로자 id (실제 근로자 서버에서는 passer_id)
    name = models.CharField(max_length=127, default='-----') # 근로자 이름
    pNo = models.CharField(max_length = 19)

    dt_answer_deadline = models.DateTimeField(null=True, blank=True) # 업무 수락 / 거부 한계시간
    # dt_begin_beacon = models.DateTimeField(null=True, blank=True) # beacon 으로 확인된 출근시간
    # dt_end_beacon = models.DateTimeField(null=True, blank=True) # beacon 으로 확인된 퇴근시간

    # dt_begin_touch = models.DateTimeField(null=True, blank=True) # touch 으로 확인된 출근시간
    # dt_end_touch = models.DateTimeField(null=True, blank=True) # touch 으로 확인된 퇴근시간

    # overtime = models.IntegerField(default=0)       # 연장 근무 -2: 휴무, -1: 업무 끝나면 퇴근, 0: 정상 근무, 1~18: 연장 근무 시간( 1:30분, 2:1시간, 3:1:30, 4:2:00, 5:2:30, 6:3:00 7: 3:30, 8: 4:00, 9: 4:30, 10: 5:00, 11: 5:30, 12: 6:00, 13: 6:30, 14: 7:00, 15: 7:30, 16: 8:00, 17: 8:30, 18: 9:00)

    x = models.FloatField(null=True, default=None) # 위도 latitude
    y = models.FloatField(null=True, default=None) # 경도 longitude

    the_zone_code = models.CharField(max_length=20, default='') # 더존 사원 코드


class Employee_Backup(models.Model):    
    """업무가 끝난 근로자 backup"""
    dt_begin = models.DateTimeField(null=True, blank=True) # 근무 시작일
    dt_end = models.DateTimeField(null=True, blank=True) # 근무 종료일

    work_id = models.IntegerField() # 업무 id

    employee_id = models.IntegerField(default=-1) # 출입 서버의 근로자 id (실제 근로자 서버에서는 passer_id)
    name = models.CharField(max_length=127, default='-----') # 근로자 이름
    pNo = models.CharField(max_length = 19)
        

