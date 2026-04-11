"""
Ejecuta comprobaciones de QA sobre la capa de confianza, HTMX de contacto y datos semilla.

Requisito: haber cargado datos con `python manage.py seed_mvp_data` (opcional para parte de tests unitarios).

Uso:
  python manage.py qa_mvp_trust
  python manage.py qa_mvp_trust --password seedpass123
  python manage.py qa_mvp_trust --html-report /tmp/informe_qa_mvp.html

Las capturas de pantalla opcionales no están incluidas (evita dependencia de Playwright);
use el informe HTML o pruebas manuales en navegador para revisión visual.
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.test import Client

from apps.trust.qa_mvp import (
    DEFAULT_SEED_PASSWORD,
    ejecutar_informe_semilla,
    html_informe,
    tiene_datos_semilla,
)


class Command(BaseCommand):
    help = (
        "Informe pass/fail en español: confianza en listado/ficha, contacto HTMX, "
        "caché, coherencia de reportes y datos semilla."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEFAULT_SEED_PASSWORD,
            help="Contraseña de usuarios @mvp-seed.local (la misma que en seed_mvp_data).",
        )
        parser.add_argument(
            "--html-report",
            default="",
            metavar="RUTA",
            help="Si se indica, escribe un informe HTML con todas las filas.",
        )
        parser.add_argument(
            "--screenshots",
            default="",
            metavar="DIR",
            help="Reservado: no implementado (evitar dependencias de navegador headless).",
        )

    def handle(self, *args, **options):
        if options["screenshots"]:
            self.stderr.write(
                self.style.WARNING(
                    "La opción --screenshots no genera archivos en esta versión. "
                    "Use --html-report o el navegador con datos semilla."
                )
            )

        client = Client()
        report = ejecutar_informe_semilla(client, options["password"])

        for r in report.resultados:
            estado = "OK" if r.ok else "FALLO"
            line = f"[{estado}] {r.codigo}: {r.mensaje}"
            if r.detalle:
                line += f" | {r.detalle}"
            style = self.style.SUCCESS if r.ok else self.style.ERROR
            self.stdout.write(style(line))

        self.stdout.write("")
        self.stdout.write(
            f"Resumen: {report.pasados}/{len(report.resultados)} correctas, "
            f"{len(report.fallos)} fallos."
        )

        html_path = options["html_report"]
        if html_path:
            path = Path(html_path)
            path.write_text(html_informe(report), encoding="utf-8")
            self.stdout.write(f"Informe HTML: {path.resolve()}")

        if not tiene_datos_semilla() and report.fallos:
            self.stderr.write(
                self.style.WARNING(
                    "Sin datos semilla: muchas comprobaciones pueden fallar; "
                    "ejecute seed_mvp_data primero."
                )
            )

        if report.fallos:
            raise CommandError(
                f"QA MVP: {len(report.fallos)} comprobación(es) fallida(s). "
                "Revise el listado anterior."
            )
