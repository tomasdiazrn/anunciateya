"""
Pruebas automatizadas: restricciones de reportes, invalidación de caché de confianza,
sync_listing_flag y (opcional) re-ejecución del informe semilla vía Client.

Los mensajes de aserción están en español donde aportan contexto al fallo.
"""

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.utils import timezone

from apps.categories.models import Category
from apps.listings.models import Listing, MarketZone
from apps.trust.models import ListingReport
from apps.trust.qa_mvp import (
    ejecutar_informe_semilla,
    tiene_datos_semilla,
)
from apps.trust.services import (
    VERIFICATION_CACHE_KEY,
    bulk_seller_verification,
    invalidate_seller_verification_cache,
    seller_verification_bundle,
    sync_listing_flag,
)
from apps.users.models import User, UserVerification


class TrustModelConstraintsTests(TestCase):
    """Un reporte por par (usuario, anuncio)."""

    def setUp(self):
        self.cat = Category.objects.create(name="QA Cat", slug="qa-cat-trust")
        self.seller = User.objects.create_user(
            email="seller_qa@example.com",
            password="x",
        )
        self.reporter = User.objects.create_user(
            email="buyer_qa@example.com",
            password="x",
        )
        self.zone = MarketZone.objects.get(slug="otro-guayaquil")
        self.listing = Listing.objects.create(
            title="Artículo QA",
            description="Desc",
            price_amount=10,
            currency="USD",
            zone=self.zone,
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
        )

    def test_segundo_reporte_mismo_usuario_integrity_error(self):
        ListingReport.objects.create(
            reporter=self.reporter,
            listing=self.listing,
            reason=ListingReport.Reason.SPAM,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ListingReport.objects.create(
                    reporter=self.reporter,
                    listing=self.listing,
                    reason=ListingReport.Reason.SCAM,
                )


class SyncListingFlagTests(TestCase):
    """Tras ≥3 reportes de usuarios distintos, sync_listing_flag pone is_flagged=True."""

    def setUp(self):
        self.cat = Category.objects.create(name="QA Flag", slug="qa-flag-cat")
        self.seller = User.objects.create_user(
            email="flag_seller@example.com",
            password="x",
        )
        self.reporters = [
            User.objects.create_user(email=f"flag_rep{i}@example.com", password="x")
            for i in range(3)
        ]
        self.zone = MarketZone.objects.get(slug="otro-guayaquil")
        self.listing = Listing.objects.create(
            title="Listado flag QA",
            description="D",
            price_amount=1,
            currency="USD",
            zone=self.zone,
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            is_flagged=False,
        )

    def test_tres_reportes_marcan_anuncio(self):
        for u in self.reporters:
            ListingReport.objects.create(
                reporter=u,
                listing=self.listing,
                reason=ListingReport.Reason.INCORRECT,
            )
        sync_listing_flag(self.listing.pk)
        self.listing.refresh_from_db()
        self.assertTrue(
            self.listing.is_flagged,
            "Con 3 reportes, is_flagged debe ser True.",
        )

    def test_dos_reportes_no_marcan(self):
        for u in self.reporters[:2]:
            ListingReport.objects.create(
                reporter=u,
                listing=self.listing,
                reason=ListingReport.Reason.SPAM,
            )
        sync_listing_flag(self.listing.pk)
        self.listing.refresh_from_db()
        self.assertFalse(
            self.listing.is_flagged,
            "Con menos de 3 reportes, is_flagged debe ser False.",
        )

    def test_reportes_descartados_no_cuentan_para_marca(self):
        for u in self.reporters:
            ListingReport.objects.create(
                reporter=u,
                listing=self.listing,
                reason=ListingReport.Reason.SPAM,
            )
        self.listing.refresh_from_db()
        self.assertTrue(self.listing.is_flagged)

        report = ListingReport.objects.filter(listing=self.listing).first()
        report.status = ListingReport.Status.DISMISSED
        report.save(update_fields=["status", "updated_at"])

        self.listing.refresh_from_db()
        self.assertFalse(
            self.listing.is_flagged,
            "Un reporte descartado no debe contar para el umbral de 3 reportes activos.",
        )


class TrustCacheInvalidationTests(TestCase):
    """La caché por vendedor se rellena con bulk_seller_verification y se invalida con señales."""

    def setUp(self):
        cache.clear()
        self.cat = Category.objects.create(name="QA Cache", slug="qa-cache-cat")
        self.seller = User.objects.create_user(
            email="cache_seller@example.com",
            password="x",
        )

    def _key(self):
        return VERIFICATION_CACHE_KEY.format(id=self.seller.pk)

    def test_bundle_no_expone_campos_de_resenas(self):
        bulk_seller_verification([self.seller.pk])
        self.assertIsNotNone(
            cache.get(self._key()),
            "Tras bulk_seller_verification la clave de caché debe existir.",
        )
        b = seller_verification_bundle(self.seller)
        self.assertEqual(
            set(b),
            {
                "verified",
            },
        )
        self.assertIsNotNone(
            cache.get(self._key()),
            "seller_verification_bundle / bulk vuelve a poblar la caché.",
        )

    def test_verificacion_invalida_cache(self):
        bulk_seller_verification([self.seller.pk])
        self.assertIsNotNone(cache.get(self._key()))
        UserVerification.objects.create(
            user=self.seller,
            phone_number="+593990000000",
            phone_verified=True,
            verification_date=timezone.now(),
        )
        self.assertIsNone(
            cache.get(self._key()),
            "Tras guardar UserVerification, la caché del vendedor debe invalidarse.",
        )
        seller_verification_bundle(self.seller)
        self.assertIsNotNone(cache.get(self._key()))

    def test_invalidate_manual(self):
        bulk_seller_verification([self.seller.pk])
        self.assertIsNotNone(cache.get(self._key()))
        invalidate_seller_verification_cache(self.seller.pk)
        self.assertIsNone(cache.get(self._key()))


class SeedMvpIntegrationTests(TestCase):
    """
    Si existe BD semilla (@mvp-seed.local), reutiliza el mismo informe que el comando de gestión.
    Se salta en bases vacías (CI sin seed).
    """

    def test_informe_semilla_sin_datos_no_rompe(self):
        if tiene_datos_semilla():
            self.skipTest("Hay datos semilla; el otro test cubre el informe completo.")
        client = Client()
        report = ejecutar_informe_semilla(client)
        self.assertFalse(report.resultados[0].ok)
        self.assertEqual(report.resultados[0].codigo, "SEMILLA")

    def test_informe_semilla_cuando_hay_datos(self):
        if not tiene_datos_semilla():
            self.skipTest("Ejecute seed_mvp_data localmente para activar esta prueba.")
        client = Client()
        report = ejecutar_informe_semilla(client)
        fallos = [r for r in report.resultados if not r.ok]
        self.assertEqual(
            len(fallos),
            0,
            "Informe QA semilla con fallos: "
            + "; ".join(f"{x.codigo}: {x.mensaje}" for x in fallos[:12]),
        )
