import json

from django.http import JsonResponse, HttpResponse


class StatusCollection(object):
    def __init__(self, status, message):
        self.status = status
        self.message = message

    def to_json_response(self):
        resp = JsonResponse({"message": self.message})
        resp.status_code = self.status

    def to_response(self):
        resp = HttpResponse(json.dumps({"message": self.message}))
        resp.status_code = self.status
        return resp


REG_400_CUSTOMER_STAFF_ALREADY_REGISTERED = StatusCollection(400, '이미 등록되어 있는 고객업체의 담당자입니다.')
