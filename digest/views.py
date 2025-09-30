from django.http import JsonResponse


# Create your views here.
def health(request):
    return JsonResponse({"ok": True, "app": "squid-digest"})
