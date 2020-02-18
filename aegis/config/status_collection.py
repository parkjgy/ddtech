import json

from django.http import JsonResponse, HttpResponse
from .common_json import DateTimeEncoder
from .log import logSend


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
        # logSend('  {} {}'.format(resp.status_code, response_body))
        logSend('v {} {}'.format(resp.status_code, response_body['message']))
        return resp

    def to_response(self, _body=None):
        response_body = {"message": self.message}
        if _body is not None and isinstance(_body, dict):
            response_body.update(_body)
        resp = HttpResponse(json.dumps(response_body, cls=DateTimeEncoder))
        resp.status_code = self.status
        logSend('<StatusCollection>', resp.status_code)
        return resp


REG_200_SUCCESS = StatusCollection(200, '정상적으로 처리되었습니다.')

REG_400_CUSTOMER_STAFF_ALREADY_REGISTERED = StatusCollection(400, '이미 등록되어 있는 고객업체의 담당자입니다.')
REG_401_UNAUTHORIZED = StatusCollection(401, '권한이 없습니다.')
REG_403_FORBIDDEN = StatusCollection(403, '로그아웃되었습니다.\n다시 로그인해주세요.')
REG_409_CONFLICT = StatusCollection(409, '처리 중에 다시 요청할 수 없습니다.(5초)')
REG_416_RANGE_NOT_SATISFIABLE = StatusCollection(416, '요청받은 범위에 대해서 서비스 할 수 없습니다.')
REG_422_UNPROCESSABLE_ENTITY = StatusCollection(422, '파라미터가 틀립니다.') # message 가 상세하게 바뀔 수 있다.

"""
시작
업그레이드가 필요합니다.
인증번호가 틀립니다. not enough time
"""
REG_552_NOT_ENOUGH_TIME = StatusCollection(551, '아직 시간이 남았습니다.')
REG_551_AN_UPGRADE_IS_REQUIRED = StatusCollection(551, '업그레이드가 필요합니다.')
REG_550_CERTIFICATION_NO_IS_INCORRECT = StatusCollection(550, '인증번호가 틀립니다.')

"""
등록
이미 등록되어 있습니다.
같은 상호와 담당자 전화번호로 등록된 업체가 있습니다.
전화번호나 아이디가 중복되었습니다.
등록이 안되어 있습니다.
등록에 실패했습니다.
"""
REG_544_EXISTED = StatusCollection(543, '이미 등록되어 있습니다.')
REG_543_EXIST_TO_SAME_NAME_AND_PHONE_NO = StatusCollection(543, '같은 상호와 담당자 전화번호로 등록된 업체가 있습니다.')
REG_542_DUPLICATE_PHONE_NO_OR_ID = StatusCollection(542, '전화번호나 아이디가 중복되었습니다.')
REG_541_NOT_REGISTERED = StatusCollection(541, '직원등록이 안되어 있습니다.')
REG_540_REGISTRATION_FAILED = StatusCollection(540, '등록에 실패했습니다.')
"""
로그인
아이디가 틀립니다.
비밀번호가 틀립니다.
아이디나 비밀번호가 틀립니다.
"""
REG_532_ID_IS_WRONG = StatusCollection(532, '아이디가 틀립니다.')
REG_531_PASSWORD_IS_INCORRECT = StatusCollection(531, '비밀번호가 틀립니다.')
REG_530_ID_OR_PASSWORD_IS_INCORRECT = StatusCollection(530, '아이디나 비밀번호가 틀립니다.')

"""
권한
수정 권한이 없습니다.
조회 권한이 없습니다.
담당자나 관리자만 변경 가능합니다.
관리자만 변경 가능합니다.
"""
REG_524_HAVE_NO_PERMISSION_TO_MODIFY = StatusCollection(524, '수정 권한이 없습니다.')
REG_523_HAVE_NO_PERMISSION_TO_VIEW = StatusCollection(523, '조회 권한이 없습니다.')
REG_522_MODIFY_SITE_OWNER_OR_MANAGER_ONLY = StatusCollection(522, '담당자나 관리자만 변경 가능합니다.')
REG_521_MODIFY_MANAGER_ONLY = StatusCollection(521, '관리자만 변경 가능합니다.')

REG_520_UNDEFINED = StatusCollection(520, '정의되지 않았습니다.')

