import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .models import Event

_MAX_TYPE = 120
_MAX_DETAIL = 255
_MAX_PATH = 512


@ratelimit(key="ip", rate="10/m", method="POST")
@require_POST
def track_event(request):
    """
    POST /events/track/
    JSON o form: event_type (requerido), event_detail (opcional), path (opcional, página del clic).
    """
    if request.content_type.startswith("application/json"):
        try:
            data = json.loads(request.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)
    else:
        data = request.POST

    event_type = (data.get("event_type") or "").strip()[:_MAX_TYPE]
    if not event_type:
        return JsonResponse({"ok": False, "error": "event_type_required"}, status=400)

    event_detail = (data.get("event_detail") or "").strip()[:_MAX_DETAIL]
    path = (data.get("path") or request.META.get("HTTP_REFERER") or "")[:_MAX_PATH]
    if not path:
        path = "/"

    Event.objects.create(
        event_type=event_type,
        event_detail=event_detail,
        user=request.user if request.user.is_authenticated else None,
        path=path,
    )
    return JsonResponse({"ok": True})
