from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.models import WaitlistSignup


def staff_required(view_func):
    """Authenticated staff only; others redirect to home with a message."""

    @wraps(view_func)
    @login_required(login_url=settings.LOGIN_URL)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            messages.warning(
                request,
                "No tienes permisos para acceder al panel de administración.",
            )
            return redirect(reverse("core:home"))
        return view_func(request, *args, **kwargs)

    return _wrapped


@staff_required
def dashboard_view(request):
    waitlist_q = (request.GET.get("q") or "").strip()
    waitlist_qs = WaitlistSignup.objects.all().order_by("-created_at")
    if waitlist_q:
        waitlist_qs = waitlist_qs.filter(email__icontains=waitlist_q)
    waitlist_qs = list(waitlist_qs[:250])
    waitlist_headers = ["Correo", "WhatsApp", "Origen", "Fecha"]
    waitlist_rows = []
    for w in waitlist_qs:
        waitlist_rows.append(
            [
                w.email,
                w.whatsapp or "—",
                w.source or "—",
                timezone.localtime(w.created_at).strftime("%Y-%m-%d %H:%M"),
            ]
        )
    context = {
        "admin_section": "dashboard",
        "admin_page_title": "Panel de administración",
        "admin_demo_table_headers": ["ID", "Estado"],
        "admin_demo_table_rows": [],
        "waitlist_headers": waitlist_headers,
        "waitlist_rows": waitlist_rows,
        "waitlist_q": waitlist_q,
        "waitlist_total": WaitlistSignup.objects.count(),
    }
    if request.htmx:
        return render(request, "adminapp/fragments/dashboard_main.html", context)
    return render(request, "adminapp/dashboard.html", context)
