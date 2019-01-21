from django.http import JsonResponse, HttpResponse
from .settings.base import BASE_DIR

def csrf_failure(request, reason=""):
    return JsonResponse({"MSG": "CSRF TOKEN ACCESS FAILURE"}, status=403)

def api_view(request):
    text_data = open(BASE_DIR + "/../API.txt", "r").read()
    return HttpResponse(text_data, content_type="text/plain; charset=utf-8")
