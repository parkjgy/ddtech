from django.http import JsonResponse


# todo redefine ( 최초작성 : 곽명석 )
def csrf_failure(request, reason=""):
    return JsonResponse({"R": 'ERROR', "MSG": "CSRF TOKEN ACCESS FAILURE"}, status=999)
