import datetime
from datetime import timedelta

from django.views.decorators.csrf import csrf_exempt  # POST 에서 사용

# log import
from config.common import CRSHttpResponse
from config.common import logError, logSend
from .models import Customer
from .models import Staff
from .status_collection import *


##### JSON Processor

def ValuesQuerySetToDict(vqs):
    return [item for item in vqs]


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            if obj.utcoffset() is not None:
                obj = obj - obj.utcoffset() + timedelta(0, 0, 0, 0, 0, 9)
                # logSend('DateTimeEncoder >>> utcoffset() = ' + str(obj.utcoffset()) + ', obj = ' + str(obj))
            encoded_object = obj.strftime('%Y-%m-%d %H:%M:%S')
            # logSend('DateTimeEncoder >>> is YES >>>' + str(encoded_object))
        else:
            encoded_object = json.JSONEncoder.default(self, obj)
            # logSend('DateTimeEncoder >>> is NO >>>' + str(encoded_object))
        return encoded_object


# try: 다음에 code = 'argument incorrect'

def exceptionError(funcName, code=503, e=Exception(), crs=False):
    logError(funcName + ' >>> ' + str(code) + ' ERROR: ' + str(e))
    logSend(funcName + ' >>> ' + str(code) + ' ERROR: ' + str(e))
    result = {'msg': str(e)}
    if crs:
        return CRSHttpResponse(json.dumps(result, cls=DateTimeEncoder), status=code)
    else:
        return HttpResponse(json.dumps(result, cls=DateTimeEncoder), status=code)


"""
/customer/reg_customer
고객사를 등록한다.
간단한 내용만 넣어서 등록하고 나머지는 고객사 담당자가 추가하도록 한다.
입력한 전화번호로 SMS 에 id 와 pw 를 보낸다.
	주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
		response 는 추후 추가될 예정이다.
http://0.0.0.0:8000/customer/reg_customer?customer_name=대덕테크&staff_name=박종기&staff_pNo=010-2557-3555&staff_email=thinking@ddtechi.com
POST 
	{
		'customer_name': '대덕기공',
		'staff_name': '홍길동',
		'staff_pNo': '010-1111-2222',
		'staff_email': 'id@daeducki.com'
	}
response
	STATUS 200
"""


@csrf_exempt
def reg_customer(request):
    try:
        if request.method == 'POST':
            rqst = json.loads(request.body.decode("utf-8"))
        else:
            rqst = request.GET

        customer_name = rqst["customer_name"]
        staff_name = rqst["staff_name"]
        staff_pNo = rqst["staff_pNo"]
        staff_email = rqst["staff_email"]

        print(customer_name, staff_name, staff_pNo, staff_email)
        customers = Customer.objects.filter(name=customer_name, staff_name=staff_name)
        if len(customers) > 0:
            staff = Staff.objects.get(id=customers[0].staff_id)
            return REG_400_CUSTOMER_STAFF_ALREADY_REGISTERED.to_response()
        customer = Customer(
            name=customer_name,
            staff_name=staff_name,
            staff_pNo=staff_pNo,
            staff_email=staff_email
        )
        customer.save()
        staff = Staff(
            name=staff_name,
            login_id='temp_' + str(customer.id),
            login_pw='happy_day!!!',
            co_id=customer.id,
            co_name=customer.name,
            pNo=staff_pNo,
            email=staff_email
        )
        staff.save()
        print('staff id = ', staff.id)
        customer.staff_id = staff.id

        print(customer_name, staff_name, staff_pNo, staff_email)
        customer.save()

        result = {'msg': '정상처리되었습니다.',
                  'login_id': staff.login_id,
                  'login_pw': staff.login_pw}
        return HttpResponse(json.dumps(result, cls=DateTimeEncoder))
    except Exception as e:
        return exceptionError('reg_customer', 503, e)


"""
/customer/reg_staff
고객사 직원을 등록한다.
	주)	항목이 비어있으면 수정하지 않는 항목으로 간주한다.
		response 는 추후 추가될 예정이다.
POST 
	{
		'staff_name': '홍길동',
		'staff_pNo': '010-1111-2222',
		'staff_email': 'id@daeducki.com'
	}
response
	STATUS 200
"""


def reg_staff(request):
    try:
        response = HttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        return exceptionError('reg_customer', 503, e)
