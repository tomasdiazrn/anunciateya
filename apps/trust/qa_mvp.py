"""
Comprobaciones de QA para la capa de confianza, anuncios marcados y HTMX de contacto.

Usado por `manage.py qa_mvp_trust` y por los tests automatizados.
Los mensajes de resultado están en español.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from django.core.cache import cache
from django.test import Client

from apps.listings.models import Listing
from apps.trust.models import ListingReport, Review
from apps.trust.services import (
    TRUST_CACHE_KEY,
    bulk_seller_trust,
    seller_trust_bundle,
)
from apps.users.models import User, UserVerification

# Mismo dominio que seed_mvp_data (evita tocar cuentas reales).
SEED_EMAIL_DOMAIN = "mvp-seed.local"

def _trust_label_card() -> dict[str, str]:
    return {"high": "Alta", "medium": "Media", "low": "Baja"}


def _trust_label_detail() -> dict[str, str]:
    return {
        "high": "Confianza alta",
        "medium": "Confianza media",
        "low": "Confianza baja",
    }


def _banner_flagged_text() -> str:
    return (
        "⚠️ Este anuncio ha sido reportado por varios usuarios. Ten precaución antes "
        "de contactar al vendedor."
    )


def _microcopy_safety() -> str:
    return "Nunca envíes dinero por adelantado sin verificar al vendedor."


def _contact_cta() -> str:
    return "Contactar por"


def _contact_submit() -> str:
    return "Enviar mensaje seguro"


def _pager_next_label() -> str:
    return "Siguiente"


@dataclass
class CheckResult:
    """Una fila del informe de QA."""

    codigo: str
    ok: bool
    mensaje: str
    detalle: str = ""


@dataclass
class QaReport:
    resultados: list[CheckResult] = field(default_factory=list)

    def add(self, codigo: str, ok: bool, mensaje: str, detalle: str = "") -> None:
        self.resultados.append(CheckResult(codigo, ok, mensaje, detalle))

    @property
    def fallos(self) -> list[CheckResult]:
        return [r for r in self.resultados if not r.ok]

    @property
    def pasados(self) -> int:
        return sum(1 for r in self.resultados if r.ok)


def seed_user_queryset():
    return User.objects.filter(email__endswith=f"@{SEED_EMAIL_DOMAIN}")


def seed_listing_queryset():
    return Listing.objects.published().filter(seller__email__endswith=f"@{SEED_EMAIL_DOMAIN}")


def tiene_datos_semilla() -> bool:
    return seed_listing_queryset().exists()


def _hx_headers() -> dict[str, str]:
    return {"HTTP_HX_REQUEST": "true"}


def _extraer_bloques_tarjeta(html: str) -> list[str]:
    """Fragmentos HTML por cada <article class="card"> del listado."""
    return re.findall(r'<article class="card">(.*?)</article>', html, re.DOTALL)


def _slug_desde_tarjeta(card_html: str) -> str | None:
    m = re.search(r'href="/listings/([^/"]+)/"', card_html)
    return m.group(1) if m else None


def comprobar_etiquetas_en_listados(client: Client, report: QaReport) -> None:
    """
    Cada anuncio semilla en el listado paginado debe mostrar Alta/Media/Baja
    alineada con bulk_seller_trust (sin número trust_score en el HTML de tarjeta).
    """
    pagina = 1
    vistos_slugs: set[str] = set()
    total_esperado = seed_listing_queryset().count()
    card_score_fails = 0
    label_mismatch: list[str] = []

    while True:
        r = client.get("/listings/", {"page": pagina})
        if r.status_code != 200:
            report.add(
                "LIST_HTTP",
                False,
                f"Listado página {pagina} no responde 200.",
                f"código {r.status_code}",
            )
            break

        body = r.content.decode()
        bloques = _extraer_bloques_tarjeta(body)
        if not bloques:
            if pagina == 1:
                report.add(
                    "LIST_EMPTY",
                    total_esperado == 0,
                    "Primera página del listado sin tarjetas.",
                    "¿Hay datos semilla?",
                )
            break

        for card in bloques:
            if "trust_score" in card.lower():
                card_score_fails += 1
            slug = _slug_desde_tarjeta(card)
            if not slug:
                continue
            try:
                listing = Listing.objects.published().get(slug=slug)
            except Listing.DoesNotExist:
                continue
            if not listing.seller.email.endswith(f"@{SEED_EMAIL_DOMAIN}"):
                continue

            vistos_slugs.add(slug)
            bundle = bulk_seller_trust([listing.seller_id]).get(listing.seller_id)
            if not bundle:
                label_mismatch.append(f"{slug}:sin_bundle")
                continue

            label = bundle["trust_label"]
            esperado = _trust_label_card()[label]
            if esperado not in card:
                label_mismatch.append(f"{slug}:esperado_{esperado}")

        if f">{_pager_next_label()}</a>" not in body:
            break
        pagina += 1
        if pagina > 200:
            break

    report.add(
        "CARD_TRUST_SCORE",
        card_score_fails == 0,
        "Ninguna tarjeta del listado expone la cadena trust_score.",
        f"tarjetas afectadas: {card_score_fails}" if card_score_fails else "",
    )
    report.add(
        "CARD_LABELS_ALL",
        len(label_mismatch) == 0,
        "Todas las tarjetas semilla muestran Alta/Media/Baja coherente con el servicio."
        if not label_mismatch
        else f"{len(label_mismatch)} tarjetas con etiqueta incorrecta o sin bundle.",
        "; ".join(label_mismatch[:8]) + ("…" if len(label_mismatch) > 8 else ""),
    )

    semilla_slugs = set(seed_listing_queryset().values_list("slug", flat=True))
    faltan = semilla_slugs - vistos_slugs
    report.add(
        "LIST_COBERTURA",
        len(faltan) == 0,
        "Todos los anuncios semilla aparecen en el listado paginado."
        if not faltan
        else f"Faltan {len(faltan)} anuncios semilla en páginas recorridas.",
        ", ".join(sorted(faltan)[:5]) + ("…" if len(faltan) > 5 else ""),
    )


def comprobar_ficha_detalle(client: Client, report: QaReport) -> None:
    """Ficha: sin trust_score visible, bloque vendedor, microcopy; bandera si is_flagged."""
    trust_score_slugs: list[str] = []
    detail_issues: list[str] = []
    banner_issues: list[str] = []

    for listing in seed_listing_queryset().order_by("pk"):
        slug = listing.slug
        r = client.get(f"/listings/{slug}/")
        if r.status_code != 200:
            detail_issues.append(f"{slug}:http_{r.status_code}")
            continue

        text = r.content.decode()
        if "trust_score" in text:
            trust_score_slugs.append(slug)

        bundle = seller_trust_bundle(listing.seller)
        det_label = _trust_label_detail()[bundle["trust_label"]]
        if _microcopy_safety() not in text:
            detail_issues.append(f"{slug}:microcopy")
        if det_label not in text:
            detail_issues.append(f"{slug}:etiqueta_confianza")
        member_line = f"Miembro desde {listing.seller.date_joined.year}"
        if member_line not in text and "Cuenta nueva" not in text:
            detail_issues.append(f"{slug}:antigüedad")
        if bundle["verified"]:
            if "Verificado" not in text or "✔" not in text:
                detail_issues.append(f"{slug}:verificado")
        if bundle["review_count"]:
            if "opiniones" not in text:
                detail_issues.append(f"{slug}:opiniones")
            if "⭐" not in text:
                detail_issues.append(f"{slug}:estrella")
        else:
            if "Sin opiniones aún" not in text:
                detail_issues.append(f"{slug}:sin_opiniones")

        flagged_en_html = _banner_flagged_text() in text
        if listing.is_flagged and not flagged_en_html:
            banner_issues.append(f"{slug}:falta_banner")
        if not listing.is_flagged and flagged_en_html:
            banner_issues.append(f"{slug}:banner_indebido")

    report.add(
        "DETAIL_ALL_NO_TRUST_SCORE",
        len(trust_score_slugs) == 0,
        "Ninguna ficha HTML contiene la cadena trust_score (puntuación solo en admin/caché).",
        ", ".join(trust_score_slugs[:6]) + ("…" if len(trust_score_slugs) > 6 else ""),
    )
    report.add(
        "DETAIL_SELLER_BLOCK",
        len(detail_issues) == 0,
        "Bloque vendedor: microcopy, etiqueta Confianza alta/media/baja, antigüedad y reseñas/verificado."
        if not detail_issues
        else f"{len(detail_issues)} incidencias en fichas.",
        "; ".join(detail_issues[:10]) + ("…" if len(detail_issues) > 10 else ""),
    )
    report.add(
        "BANNER_FLAGGED_CONSISTENT",
        len(banner_issues) == 0,
        "Banner de reportes solo si is_flagged (coherente con ≥3 reportes)."
        if not banner_issues
        else "Incoherencia banner ↔ is_flagged.",
        "; ".join(banner_issues),
    )


def comprobar_contacto_htmx(client: Client, report: QaReport) -> None:
    """
    Flujo HTMX del panel de contacto: anónimo, sin teléfono verificado, verificado.
    Valida URLs y textos del flujo en español.
    """
    listing = seed_listing_queryset().first()
    if not listing:
        report.add("CONTACT_SETUP", False, "Sin anuncios semilla para probar contacto.", "")
        return

    # Anuncio de un vendedor distinto de vendedor01 (comprador verificado en semilla)
    alt = (
        seed_listing_queryset()
        .exclude(seller__email="vendedor01@mvp-seed.local")
        .first()
    )
    if alt:
        listing = alt

    url = f"/listings/{listing.slug}/contact/"
    # Anónimo GET + HX → formulario directo sin exponer datos del vendedor
    r = client.get(url, **_hx_headers())
    anon_body = r.content.decode()
    report.add(
        "CONTACT_ANON_HX",
        r.status_code == 200
        and _contact_cta() in anon_body
        and _contact_submit() in anon_body
        and listing.seller.email not in anon_body,
        "Anónimo + HX: respuesta 200 con formulario directo sin email del vendedor.",
        f"código {r.status_code}",
    )
    report.add(
        "CONTACT_ANON_FORM",
        _contact_submit() in anon_body,
        "Anónimo: formulario seguro visible.",
        "",
    )

    # POST sin sesión, sin HX → envío válido y redirect al anuncio
    r_post = client.post(
        url,
        {
            "buyer_name": "Comprador QA",
            "buyer_email": "comprador.qa@example.com",
            "message": "Hola, ¿sigue disponible este anuncio?",
        },
    )
    report.add(
        "CONTACT_POST_DIRECT",
        r_post.status_code in (301, 302) and "login" not in r_post.headers.get("Location", ""),
        "POST sin autenticación procesa contacto y redirige al anuncio.",
        f"{r_post.status_code} {r_post.headers.get('Location', '')}",
    )

    # Comprador semilla sin verificación también ve formulario directo
    buyer_unverified = User.objects.filter(
        email="vendedor05@mvp-seed.local"
    ).first()
    seller_id = listing.seller_id
    if buyer_unverified and buyer_unverified.pk == seller_id:
        buyer_unverified = (
            User.objects.filter(email__endswith=f"@{SEED_EMAIL_DOMAIN}")
            .exclude(pk=seller_id)
            .first()
        )
    if buyer_unverified:
        client.force_login(buyer_unverified)
        r = client.get(url, **_hx_headers())
        body = r.content.decode()
        ok_verify = (
            r.status_code == 200
            and _contact_submit() in body
            and "/accounts/verify-phone/" not in body
        )
        report.add(
            "CONTACT_UNVERIFIED_HX",
            ok_verify,
            "Usuario autenticado sin teléfono verificado: formulario directo.",
            "",
        )
        client.logout()

    # Comprador verificado distinto del vendedor
    buyer_ok = User.objects.filter(
        email="vendedor01@mvp-seed.local"
    ).first()
    if buyer_ok and buyer_ok.pk == listing.seller_id:
        buyer_ok = User.objects.filter(email="vendedor02@mvp-seed.local").first()

    if buyer_ok:
        client.force_login(buyer_ok)
        r = client.get(url, **_hx_headers())
        body = r.content.decode()
        report.add(
            "CONTACT_FORM_HX",
            r.status_code == 200
            and _contact_cta() in body
            and _contact_submit() in body,
            "Usuario verificado: CTA y botón del formulario en español.",
            "",
        )
        client.logout()


def comprobar_cache_semilla(report: QaReport) -> None:
    """Tras bulk_seller_trust, cada vendedor semilla con anuncio debe tener clave en caché."""
    seller_ids = sorted(
        set(seed_listing_queryset().values_list("seller_id", flat=True))
    )
    if not seller_ids:
        report.add("CACHE_SELLERS", False, "No hay vendedores semilla.", "")
        return

    bulk_seller_trust(seller_ids)
    for sid in seller_ids:
        key = TRUST_CACHE_KEY.format(id=sid)
        hit = cache.get(key)
        report.add(
            f"CACHE_KEY_{sid}",
            hit is not None,
            f"Caché poblada para vendedor id={sid}.",
            "" if hit is not None else f"clave {key}",
        )


def comprobar_integridad_datos_semilla(report: QaReport) -> None:
    """
    Solo lectura: no duplicados (revisor, vendedor) ni (reporter, listing);
    is_flagged coherente con conteo de reportes.
    """
    from django.db.models import Count

    dup_reviews = (
        Review.objects.values("reviewer_id", "seller_id")
        .annotate(c=Count("id"))
        .filter(c__gt=1)
        .exists()
    )
    report.add(
        "DATA_REVIEW_UNIQUE",
        not dup_reviews,
        "En BD no hay pares duplicados (revisor, vendedor) en reseñas.",
        "",
    )

    dup_reports = (
        ListingReport.objects.values("reporter_id", "listing_id")
        .annotate(c=Count("id"))
        .filter(c__gt=1)
        .exists()
    )
    report.add(
        "DATA_REPORT_UNIQUE",
        not dup_reports,
        "En BD no hay pares duplicados (usuario, anuncio) en reportes.",
        "",
    )

    flag_issues: list[str] = []
    for listing in seed_listing_queryset():
        n = ListingReport.objects.filter(listing=listing).count()
        esperado = n >= 3
        if listing.is_flagged != esperado:
            flag_issues.append(f"{listing.slug}:reportes={n},flag={listing.is_flagged}")

    report.add(
        "DATA_FLAG_VS_REPORTS",
        len(flag_issues) == 0,
        "is_flagged coincide con ≥3 reportes en todos los anuncios semilla."
        if not flag_issues
        else "Algún anuncio semilla tiene flag incoherente con reportes.",
        "; ".join(flag_issues[:6]),
    )


def ejecutar_informe_semilla(client: Client) -> QaReport:
    """Todas las comprobaciones que dependen de datos semilla + HTTP."""
    report = QaReport()
    if not tiene_datos_semilla():
        report.add(
            "SEMILLA",
            False,
            f"No hay anuncios publicados de @{SEED_EMAIL_DOMAIN}. Ejecute seed_mvp_data primero.",
            "",
        )
        return report

    comprobar_etiquetas_en_listados(client, report)
    comprobar_ficha_detalle(client, report)
    comprobar_contacto_htmx(client, report)
    comprobar_cache_semilla(report)
    comprobar_integridad_datos_semilla(report)
    return report


def html_informe(report: QaReport, titulo: str = "Informe QA MVP — confianza") -> str:
    filas = []
    for r in report.resultados:
        cls = "ok" if r.ok else "fail"
        filas.append(
            f'<tr class="{cls}"><td>{r.codigo}</td><td>{"OK" if r.ok else "FALLO"}</td>'
            f"<td>{r.mensaje}</td><td>{r.detalle}</td></tr>"
        )
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>{titulo}</title>
<style>body{{font-family:system-ui,sans-serif;margin:2rem;}}
table{{border-collapse:collapse;width:100%;}}
td,th{{border:1px solid #ccc;padding:0.5rem;text-align:left;}}
tr.ok{{background:#e8f5e9;}} tr.fail{{background:#ffebee;}}
</style></head><body>
<h1>{titulo}</h1>
<p>Total: {len(report.resultados)} · Pasados: {report.pasados} · Fallos: {len(report.fallos)}</p>
<table><thead><tr><th>Código</th><th>Estado</th><th>Mensaje</th><th>Detalle</th></tr></thead>
<tbody>{"".join(filas)}</tbody></table>
</body></html>"""
