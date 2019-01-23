import json
import os
import time

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from django.conf import settings

APK_FILE_PATH = os.path.join(settings.MEDIA_ROOT, "APK")


def csrf_failure(request, reason=""):
    return JsonResponse({"msg": "CSRF TOKEN ACCESS FAILURE"}, status=403)


def api_view(request):
    text_data = open(settings.BASE_DIR + "/../API.txt", "r", encoding='UTF8').read()
    return HttpResponse(text_data, content_type="text/plain; charset=utf-8")


# appLink           다운로드에 사용할 링크
def beta_employee_app_download(request):
    with open(os.path.join(APK_FILE_PATH, "desc_worker.txt")) as desc_file:
        return render(request, 'root/beta_app_download.html', json.loads(desc_file.read()))


# upload_app ( POST )
# -- Params
# type              worker(근로자) or admin(관리자)
# file              APK FILE
# version           APK VERSION
def app_upload_view(request):
    return render(request, 'root/beta_app_upload.html')


@csrf_exempt
def api_apk_upload(request):
    if request.method == "POST":
        if not bool(request.FILES):
            return JsonResponse({"msg": "파일이 없습니다.", "status": -1})

        p_version = request.POST['version']
        p_type = request.POST['type']

        if not os.path.exists(APK_FILE_PATH):
            os.makedirs(APK_FILE_PATH)

        desc_file_name = "desc_" + p_type + ".txt"
        apk_file_name = p_type + "_" + str(int(time.time_ns() / 1000)) + ".apk"

        with open(os.path.join(APK_FILE_PATH, apk_file_name), 'wb+') as destination:
            for chunk in request.FILES['file'].chunks():
                destination.write(chunk)

        with open(os.path.join(APK_FILE_PATH, desc_file_name), 'w') as desc_file:
            desc_file.write(json.dumps({"version": p_version, "apkLink": base.MEDIA_URL + "APK/" + apk_file_name}))
        return JsonResponse({"msg": "업로드 되었습니다.", "status": 0})
    else:
        return JsonResponse({"msg": "", "status": -1})
