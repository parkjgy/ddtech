from django.http import JsonResponse

def csrf_failure(request, reason=""):
    return JsonResponse({"MSG": "CSRF TOKEN ACCESS FAILURE"}, status=403)
