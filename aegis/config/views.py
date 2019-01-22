from django.http import JsonResponse, HttpResponse
from .settings.base import BASE_DIR

from django.shortcuts import render


def csrf_failure(request, reason=""):
    return JsonResponse({"msg": "CSRF TOKEN ACCESS FAILURE"}, status=403)


def api_view(request):
    text_data = open(BASE_DIR + "/../API.txt", "r").read()
    return HttpResponse(text_data, content_type="text/plain; charset=utf-8")


# appLink           다운로드에 사용할 링크
def beta_employee_app_download(request):
    return render(request, 'root/beta_app_download.html', {"appLink": "test.apk"})


# upload_app ( POST )
# -- Params
# type              worker(근로자) or admin(관리자)
# file              APK FILE
# version           APK VERSION
def app_upload_view(request):
    return render(request, 'root/beta_app_upload.html')
