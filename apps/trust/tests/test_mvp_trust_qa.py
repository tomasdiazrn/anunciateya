"""
Pruebas automatizadas: restricciones de modelo, invalidación de caché de confianza,
sync_listing_flag y (opcional) re-ejecución del informe semilla vía Client.

Los mensajes de aserción están en español donde aportan contexto al fallo.
"""

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.utils import timezone

from apps.categories.models import Category
from apps.listings.models import Listing
from apps.trust.models import ListingReport, Review
from apps.trust.qa_mvp import (
    DEFAULT_SEED_PASSWORD,
    ejecutar_informe_semilla,
    tiene_datos_semilla,
)
from apps.trust.services import (
    TRUST_CACHE_KEY,
    bulk_seller_trust,
    invalidate_seller_trust_cache,
    seller_trust_bundle,
    sync_listing_flag,
)
from apps.users.models import User, UserVerification


class TrustModelConstraintsTests(TestCase):
    """Una reseña por par (revisor, vendedor); un reporte por par (usuario, anuncio)."""

    def setUp(self):
        self.cat = Category.objects.create(name="QA Cat", slug="qa-cat-trust")
        self.seller = User.objects.create_user(
            email="seller_qa@example.com",
            password="x",
        )
        self.reviewer = User.objects.create_user(
            email="buyer_qa@example.com",
            password="x",
        )
        self.listing = Listing.objects.create(
            title="Artículo QA",
            description="Desc",
            price_amount=10,
            currency="USD",
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            is_active=True,
        )

    def test_segunda_resena_mismo_par_integrity_error(self):
        Review.objects.create(
            listing=self.listing,
            reviewer=self.reviewer,
            seller=self.seller,
            rating=5,
            comment="ok",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Review.objects.create(
                    listing=self.listing,
                    reviewer=self.reviewer,
                    seller=self.seller,
                    rating=4,
                    comment="dup",
                )

    def test_segundo_reporte_mismo_usuario_integrity_error(self):
        ListingReport.objects.create(
            reporter=self.reviewer,
            listing=self.listing,
            reason=ListingReport.Reason.SPAM,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ListingReport.objects.create(
                    reporter=self.reviewer,
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
        self.listing = Listing.objects.create(
            title="Listado flag QA",
            description="D",
            price_amount=1,
            currency="USD",
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            is_active=True,
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


class TrustCacheInvalidationTests(TestCase):
    """La caché por vendedor se rellena con bulk_seller_trust y se invalida con señales."""

    def setUp(self):
        cache.clear()
        self.cat = Category.objects.create(name="QA Cache", slug="qa-cache-cat")
        self.seller = User.objects.create_user(
            email="cache_seller@example.com",
            password="x",
        )
        self.seller.date_joined = timezone.now() - timezone.timedelta(days=40)
        self.seller.save(update_fields=["date_joined"])
        self.reviewer = User.objects.create_user(
            email="cache_buyer@example.com",
            password="x",
        )
        self.listing = Listing.objects.create(
            title="Cache QA",
            description="D",
            price_amount=5,
            currency="USD",
            seller=self.seller,
            category=self.cat,
            status=Listing.Status.PUBLISHED,
            is_active=True,
        )

    def _key(self):
        return TRUST_CACHE_KEY.format(id=self.seller.pk)

    def test_resena_invalida_cache_y_regenera_bundle(self):
        bulk_seller_trust([self.seller.pk])
        self.assertIsNotNone(
            cache.get(self._key()),
            "Tras bulk_seller_trust la clave de caché debe existir.",
        )
        Review.objects.create(
            listing=self.listing,
            reviewer=self.reviewer,
            seller=self.seller,
            rating=5,
            comment="nueva",
        )
        self.assertIsNone(
            cache.get(self._key()),
            "Tras crear una reseña, la señal debe borrar la caché del vendedor.",
        )
        b = seller_trust_bundle(self.seller)
        self.assertEqual(b["review_count"], 1)
        self.assertIsNotNone(
            cache.get(self._key()),
            "seller_trust_bundle / bulk vuelve a poblar la caché.",
        )

    def test_verificacion_invalida_cache(self):
        bulk_seller_trust([self.seller.pk])
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
        seller_trust_bundle(self.seller)
        self.assertIsNotNone(cache.get(self._key()))

    def test_invalidate_manual(self):
        bulk_seller_trust([self.seller.pk])
        self.assertIsNotNone(cache.get(self._key()))
        invalidate_seller_trust_cache(self.seller.pk)
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
        report = ejecutar_informe_semilla(client, DEFAULT_SEED_PASSWORD)
        self.assertFalse(report.resultados[0].ok)
        self.assertEqual(report.resultados[0].codigo, "SEMILLA")

    def test_informe_semilla_cuando_hay_datos(self):
        if not tiene_datos_semilla():
            self.skipTest("Ejecute seed_mvp_data localmente para activar esta prueba.")
        client = Client()
        report = ejecutar_informe_semilla(client, DEFAULT_SEED_PASSWORD)
        fallos = [r for r in report.resultados if not r.ok]
        self.assertEqual(
            len(fallos),
            0,
            "Informe QA semilla con fallos: "
            + "; ".join(f"{x.codigo}: {x.mensaje}" for x in fallos[:12]),
        )
