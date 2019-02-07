import json

from django.http import JsonResponse, HttpResponse
from config.common import DateTimeEncoder


class StatusCollection(object):
    def __init__(self, status, message):
        self.status = status
        self.message = message

    def to_json_response(self, _body=None):
        response_body = {"message": self.message}
        if _body is not None and isinstance(_body, dict):
            response_body.update(_body)
        resp = JsonResponse(response_body)
        resp.status_code = self.status
        return resp

    def to_response(self, _body=None):
        response_body = {"message": self.message}
        if _body is not None and isinstance(_body, dict):
            response_body.update(_body)
        resp = HttpResponse(json.dumps(response_body, cls=DateTimeEncoder))
        resp.status_code = self.status
        return resp


REG_400_CUSTOMER_STAFF_ALREADY_REGISTERED = StatusCollection(400, '이미 등록되어 있는 고객업체의 담당자입니다.')

"""
시작
업그레이드가 필요합니다.
인증번호가 틀립니다.
"""
REG_600_AN_UPGRADE_IS_REQUIRED = StatusCollection(600, '업그레이드가 필요합니다.')
REG_601_CERTIFICATION_NO_IS_INCORRECT = StatusCollection(601, '인증번호가 틀립니다.')

"""
등록
같은 상호와 담당자 전화번호로 등록된 업체가 있습니다.
전화번호나 아이디가 중복되었습니다.
등록이 안되어 있습니다.
등록에 실패했습니다.
"""
REG_610_EXIST_TO_SAME_NAME_AND_PHONE_NO = StatusCollection(610, '같은 상호와 담당자 전화번호로 등록된 업체가 있습니다.')
REG_611_DUPLICATE_PHONE_NO_OR_ID = StatusCollection(611, '전화번호나 아이디가 중복되었습니다.')
REG_612_NOT_REGISTERED = StatusCollection(612, '직원등록이 안되어 있습니다.')
REG_613_REGISTRATION_FAILED = StatusCollection(613, '등록에 실패했습니다.')
"""
로그인
아이디가 틀립니다.
비밀번호가 틀립니다.
아이디나 비밀번호가 틀립니다.
"""
REG_620_ID_IS_WRONG = StatusCollection(620, '아이디가 틀립니다.')
REG_621_PASSWORD_IS_INCORRECT = StatusCollection(621, '비밀번호가 틀립니다.')
REG_622_ID_OR_PASSWORD_IS_INCORRECT = StatusCollection(622, '아이디나 비밀번호가 틀립니다.')

"""
권한
수정 권한이 없습니다.
조회 권한이 없습니다.
담당자나 관리자만 변경 가능합니다.
관리자만 변경 가능합니다.
"""
REG_630_HAVE_NO_PERMISSION_TO_MODIFY = StatusCollection(630, '수정 권한이 없습니다.')
REG_631_HAVE_NO_PERMISSION_TO_VIEW = StatusCollection(631, '조회 권한이 없습니다.')
REG_632_MODIFY_SITE_OWNER_OR_MANAGER_ONLY = StatusCollection(632, '담당자나 관리자만 변경 가능합니다.')
REG_633_MODIFY_MANAGER_ONLY = StatusCollection(633, '관리자만 변경 가능합니다.')

REG_666_UNDEFINED = StatusCollection(666, '정의되지 않았습니다.')
"""
REG_400_CUSTOMER_STAFF_ALREADY_REGISTERED = StatusCollection(400, '이미 등록되어 있는 고객업체의 담당자입니다.')
            {'message': '직원이 아닙니다.'}
        STATUS 503
            {'message': '사업장을 수정할 권한이 없는 직원입니다.'}
        STATUS 503
            {'message': '사업장을 수정할 권한이 없는 직원입니다.'}
        STATUS 509
            {"msg": "??? matching query does not exist."} # ??? 을 찾을 수 없다.(op_staff_id, work_id 를 찾을 수 없을 때)
        STATUS 509
        {'message': '검사하려는 버전 값이 양식에 맞지 않습니다.'}
        STATUS 605  # 필수 입력 항목이 비었다.
            {'message': '전화번호가 없습니다.'}
        STATUS 606  # 값이 잘못되어 있습니다.
            {'message': '직원등록이 안 되어 있습니다.\n웹에서 전화번호가 틀리지 않았는지 확인해주세요.'}

601 StatusCollection(601, '이미 등록되어 있는 고객업체의 담당자입니다.')
"""
