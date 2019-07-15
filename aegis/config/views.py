"""
Config view

Copyright 2019. DaeDuckTech Corp. All rights reserved.
"""

import json
import os
import time

from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from . import urls

APK_FILE_PATH = os.path.join(settings.MEDIA_ROOT, "APK")


def csrf_failure(request, reason=""):
    return JsonResponse({"message": "CSRF TOKEN ACCESS FAILURE"}, status=403)


class StringAppender:
    def __init__(self):
        self.str_list = []

    def append(self, str: str):
        self.str_list.append(str)

    def get(self) -> str:
        return ''.join(self.str_list)


class CategoryStringAppender:
    def __init__(self):
        self.category_map = {}

    def append(self, name: str, _str: str):
        if not name in self.category_map:
            self.category_map[name] = StringAppender()
        appender: StringAppender = self.category_map[name]
        appender.append(_str)

    def get(self):
        ret = StringAppender()
        for map in self.category_map:
            ret.append(self.category_map[map].get())
            ret.append('<br/>')
        return ret.get()


html_api_view_str = {}


def api_view(request):
    global html_api_view_str
    _filters = ["operation", "employee", "customer", "test"]
    _filter_names = ["운영 API", "근로자 API", "고객사 API", "테스트"]

    type = 'global'
    if 'filter' in request.GET:
        type = request.GET['filter']

    if not type in _filters:
        type = 'global'
    if type not in html_api_view_str or 'filter' in request.GET:
        try:
            from django.urls import URLResolver, URLPattern

            if 'filter' in request.GET and 'global' != type:
                _custom_filter = type
                for i in range(len(_filters)):
                    if _filters[i] == _custom_filter:
                        _filters = [_custom_filter]
                        _filter_names = [_filter_names[i]]
                        break

                if len(_filters) > 1:
                    _filters = [_custom_filter]
                    _filter_names = ['Unknown']

            titles = CategoryStringAppender()
            contents = CategoryStringAppender()
            for i in range(len(_filters)):
                titles.append(_filters[i],
                              "<p style='font-weight: bold; font-size: 1.2rem'>" + _filter_names[i] + '</p><br/>')

            def recursively_build__url_dict(_titles, _contents, root, d, urlpatterns):
                for i in urlpatterns:
                    if isinstance(i, URLResolver):
                        if not str(i.pattern) in d:
                            d[str(i.pattern)] = {}
                        recursively_build__url_dict(_titles, _contents,
                                                    root + str(i.pattern),
                                                    d[str(i.pattern)], i.url_patterns
                                                    )
                    elif isinstance(i, URLPattern):
                        d[str(i.pattern)] = {'name': i.callback.__name__, 'doc': i.callback.__doc__}
                        for _filter in _filters:
                            if str(i.pattern).startswith(_filter):
                                import uuid
                                doc_id = str(uuid.uuid4()).replace('-', '')
                                doc_str = i.callback.__doc__
                                str_title = ''

                                if doc_str is None:
                                    doc_str = "문서가 존재하지 않습니다."
                                else:
                                    flag = 0
                                    flag_change_cnt = 0
                                    document_blank_cnt = 0
                                    # 0 None
                                    # 1 response
                                    # 2 get or post
                                    doc_splited = doc_str.splitlines()
                                    for idx in range(len(doc_splited)):
                                        split_tmp = doc_splited[idx].strip()
                                        if split_tmp == 'response':
                                            flag = 1
                                            flag_change_cnt = 0
                                            doc_splited[idx] = '<p style="font-weight: bold">' + split_tmp + '</p>'
                                        elif (split_tmp.startswith('GET') or split_tmp.startswith(
                                                'POST')):
                                            flag = 2
                                            flag_change_cnt = 0
                                            doc_splited[idx] = '<p style="font-weight: bold">' + split_tmp + '</p>'
                                        else:
                                            if str_title == '' and doc_splited[idx].strip() != '':
                                                str_title = doc_splited[idx].strip()

                                            current_blank_cnt = 0
                                            flag_change_cnt += 1
                                            doc_splited[idx] = doc_splited[idx].replace('    ', '\t')

                                            for _chr in doc_splited[idx]:
                                                if _chr == '\t':
                                                    current_blank_cnt = current_blank_cnt + 1
                                                else:
                                                    break

                                            if flag_change_cnt == 1:
                                                document_blank_cnt = current_blank_cnt

                                            if 1 < document_blank_cnt <= current_blank_cnt:
                                                doc_splited[idx] = doc_splited[idx][document_blank_cnt - 1:]

                                            doc_splited[idx] = '<p>' + doc_splited[idx].replace('\t', '  ') + '</p>'
                                            # doc_splited[idx] = doc_splited[idx].replace('\t', '  ')
                                        # Tab 문자 기준이 back-space 4개로 간주
                                    doc_str = '<br/>'.join(doc_splited)
                                _contents.append(_filter,
                                                 '<br/><a name="' + doc_id + '"><p style="color:blue;font-size: 1.1rem">' + str(
                                                     i.pattern) + '</p></a><br/>' + doc_str + '<br/>')
                                _titles.append(_filter,
                                               '<p>- <a href="#' + doc_id + '">' + str(
                                                   i.pattern) + '</a> ' + str_title + '</p><br/>')
                                break

            d = {}
            recursively_build__url_dict(titles, contents, '', d, urls.urlpatterns)
            html_api_view_str[
                type] = '<body><style>body{  font-family: "Nanum Gothic Coding", monospace; font-size: 14px; } p{ ' \
                        'white-space: pre; margin: 0px; display: inline; }</style>' + titles.get() + contents.get() + \
                        '</body> '
        except:
            html_api_view_str[type] = '<b>Render Error<b/>'
    return HttpResponse(html_api_view_str[type])


# appLink           다운로드에 사용할 링크
def beta_employee_app_download(request):
    with open(os.path.join(APK_FILE_PATH, "desc_worker.txt")) as desc_file:
        return render(request, 'root/beta_app_download.html', json.loads(desc_file.read()))


# appLink           다운로드에 사용할 링크
def beta_manager_app_download(request):
    with open(os.path.join(APK_FILE_PATH, "desc_worker.txt")) as desc_file:
        return render(request, 'root/beta_app_mng_download.html', json.loads(desc_file.read()))


# appLink           약관
def tnc_privacy(request):
    with open(os.path.join(APK_FILE_PATH, "desc_worker.txt")) as desc_file:
        return render(request, 'root/tnc_privacy.html', json.loads(desc_file.read()))


# appLink           개인정보 처리방침
def privacy_policy(request):
    with open(os.path.join(APK_FILE_PATH, "desc_worker.txt")) as desc_file:
        return render(request, 'root/privacy_policy.html', json.loads(desc_file.read()))

# upload_app ( POST )
# -- Params
# type              worker(근로자) or admin(관리자)
# file              APK FILE
# version           APK VERSION
def app_upload_view(request):
    return render(request, 'root/beta_app_upload.html')


@csrf_exempt
def api_apk_upload(request):
    from shutil import copyfile
    if request.method == "POST":
        if not bool(request.FILES):
            return JsonResponse({"message": "파일이 없습니다.", "status": -1})

        p_version = request.POST['version']
        p_type = request.POST['type']

        if not os.path.exists(APK_FILE_PATH):
            os.makedirs(APK_FILE_PATH)

        desc_file_name = "desc_" + p_type + ".txt"
        tmp_apk_file_name = p_type + "_" + str(int(round(time.time() * 1000))) + ".apk"
        apk_file_name = "aegisFactory.apk"

        with open(os.path.join(APK_FILE_PATH, tmp_apk_file_name), 'wb+') as destination:
            for chunk in request.FILES['file'].chunks():
                destination.write(chunk)

        if os.path.exists(os.path.join(APK_FILE_PATH, apk_file_name)):
            os.remove(os.path.join(APK_FILE_PATH, apk_file_name))
        copyfile(os.path.join(APK_FILE_PATH, tmp_apk_file_name),
                 os.path.join(APK_FILE_PATH, apk_file_name))

        with open(os.path.join(APK_FILE_PATH, desc_file_name), 'w') as desc_file:
            desc_file.write(json.dumps({"version": p_version, "apkLink": settings.MEDIA_URL + "APK/" + apk_file_name}))
        return JsonResponse({"message": "업로드 되었습니다.", "status": 0})
    else:
        return JsonResponse({"message": "", "status": -1})
