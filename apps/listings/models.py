from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class VehicleBrand(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class VehicleModel(models.Model):
    brand = models.ForeignKey(
        VehicleBrand,
        on_delete=models.CASCADE,
        related_name="models",
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField()

    class Meta:
        unique_together = ("brand", "name")
        indexes = [
            models.Index(fields=["brand", "name"]),
        ]

    def __str__(self):
        return f"{self.brand.name} {self.name}"
class ListingQuerySet(models.QuerySet):
    def published(self):
        """Listados públicos: publicado y activo (alineado con detalle y SEO)."""
        return self.filter(
            status=Listing.Status.PUBLISHED,
            is_active=True,
        )


class Listing(models.Model):
    """Anuncio con slug SEO y relaciones normalizadas."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        PUBLISHED = "published", "Publicado"
        ARCHIVED = "archived", "Archivado"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, db_index=True)
    description = models.TextField()
    price_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    location = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="listings",
    )
    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.PROTECT,
        related_name="listings",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    is_flagged = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Set when multiple users report this listing.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    featured_until = models.DateTimeField(null=True, blank=True, db_index=True)
    boost_score = models.IntegerField(default=0, db_index=True)
    quality_score = models.FloatField(default=0.0, db_index=True)

    objects = ListingQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status", "is_active", "-created_at"]),
            models.Index(fields=["seller", "-created_at"]),
            models.Index(fields=["category", "-created_at"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        from apps.listings.services import compute_listing_quality_score

        self.quality_score = compute_listing_quality_score(self)
        if not self.slug:
            base = slugify(self.title)[:200] or "listing"
            candidate = base
            n = 0
            while True:
                qs = Listing.objects.filter(slug=candidate)
                if self.pk:
                    qs = qs.exclude(pk=self.pk)
                if not qs.exists():
                    self.slug = candidate[:220]
                    break
                n += 1
                candidate = f"{base}-{n}"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse(
            "listing_detail_seo",
            kwargs={
                "category_slug": self.category.slug,
                "listing_slug": self.slug,
            },
        )


class VehicleListing(models.Model):
    """Detalle específico para categoría Autos (1:1 con Listing)."""

    class Transmission(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTOMATICO = "automatico", "Automático"
        CVT = "cvt", "CVT"
        OTRO = "otro", "Otro / no especificado"

    class FuelType(models.TextChoices):
        GASOLINA = "gasolina", "Gasolina"
        DIESEL = "diesel", "Diésel"
        HIBRIDO = "hibrido", "Híbrido"
        ELECTRICO = "electrico", "Eléctrico"

    listing = models.OneToOneField(
        Listing,
        on_delete=models.CASCADE,
        related_name="vehicle",
    )
    brand = models.CharField(max_length=80)
    model = models.CharField("Modelo", max_length=80)
    brand_fk = models.ForeignKey(
        VehicleBrand,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vehicle_listings",
    )
    model_fk = models.ForeignKey(
        VehicleModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vehicle_listings",
    )
    year = models.PositiveSmallIntegerField("Año")
    mileage = models.PositiveIntegerField("Kilometraje", null=True, blank=True)
    doors = models.PositiveSmallIntegerField("Puertas")
    transmission = models.CharField(
        "Transmisión",
        max_length=20,
        choices=Transmission.choices,
    )
    fuel_type = models.CharField(
        "Combustible",
        max_length=20,
        choices=FuelType.choices,
        blank=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["listing"]),
            models.Index(fields=["brand_fk", "model_fk"]),
            models.Index(fields=["year"]),
        ]

    def __str__(self):
        return f"{self.brand} {self.model} ({self.year})"


class PropertyListing(models.Model):
    """Detalle específico para categoría Inmuebles (1:1 con Listing)."""

    class PropertyType(models.TextChoices):
        CASA = "casa", "Casa"
        DEPARTAMENTO = "departamento", "Departamento"

    class OperationType(models.TextChoices):
        VENTA = "venta", "Venta"
        ALQUILER = "alquiler", "Alquiler"

    class PropertyConditionChoice(models.TextChoices):
        NUEVO = "nuevo", "Nuevo"
        USADO = "usado", "Usado"

    listing = models.OneToOneField(
        Listing,
        on_delete=models.CASCADE,
        related_name="property",
    )
    property_type = models.CharField(
        "Tipo",
        max_length=20,
        choices=PropertyType.choices,
    )
    operation_type = models.CharField(
        "Operación",
        max_length=20,
        choices=OperationType.choices,
        blank=True,
        null=True,
    )
    rooms = models.PositiveSmallIntegerField("Habitaciones")
    bathrooms = models.PositiveSmallIntegerField("Baños")
    area_m2 = models.PositiveIntegerField("Superficie (m²)")
    parking_spaces = models.PositiveSmallIntegerField(
        "Parqueaderos",
        blank=True,
        null=True,
    )
    furnished = models.BooleanField("Amoblado", default=False)
    property_condition = models.CharField(
        "Estado",
        max_length=20,
        choices=PropertyConditionChoice.choices,
        blank=True,
        null=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["listing"]),
            models.Index(fields=["property_type"]),
            models.Index(fields=["operation_type"]),
            models.Index(fields=["area_m2"]),
        ]

    def __str__(self):
        return f"{self.get_property_type_display()} · {self.area_m2} m²"


class ItemCondition(models.TextChoices):
    """Condición común para artículos (motos, electrónica, hogar)."""

    NUEVO = "nuevo", "Nuevo / nueva"
    USADO = "usado", "Usado / usada"
    REFURBISHED = "refurbished", "Reacondicionado"


class MotorcycleListing(models.Model):
    """Detalle para categoría Motos (1:1 con Listing)."""

    class Transmission(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTOMATICO = "automatico", "Automático"
        OTRO = "otro", "Otro"

    class FuelType(models.TextChoices):
        GASOLINA = "gasolina", "Gasolina"
        NAFTA = "nafta", "Nafta"
        ELECTRICA = "electrica", "Eléctrica"
        OTRO = "otro", "Otro"

    listing = models.OneToOneField(
        Listing,
        on_delete=models.CASCADE,
        related_name="motorcycle",
    )
    brand = models.CharField(max_length=80)
    model = models.CharField("Modelo", max_length=80)
    year = models.PositiveIntegerField("Año")
    mileage = models.PositiveIntegerField(
        "Kilometraje",
        null=True,
        blank=True,
    )
    engine_cc = models.PositiveIntegerField(
        "Cilindrada (cc)",
        null=True,
        blank=True,
    )
    transmission = models.CharField(
        "Transmisión",
        max_length=20,
        choices=Transmission.choices,
        default=Transmission.MANUAL,
    )
    fuel_type = models.CharField(
        "Combustible",
        max_length=20,
        choices=FuelType.choices,
        default=FuelType.GASOLINA,
    )
    condition = models.CharField(
        "Condición",
        max_length=20,
        choices=ItemCondition.choices,
    )

    class Meta:
        indexes = [
            models.Index(fields=["listing"]),
            models.Index(fields=["year"]),
            models.Index(fields=["brand"]),
            models.Index(fields=["model"]),
        ]

    def __str__(self):
        return f"{self.brand} {self.model} ({self.year})"


class ElectronicsListing(models.Model):
    """Detalle para categoría Electrónica."""

    listing = models.OneToOneField(
        Listing,
        on_delete=models.CASCADE,
        related_name="electronics",
    )
    brand = models.CharField(max_length=80)
    model = models.CharField("Modelo", max_length=120)
    condition = models.CharField(
        "Condición",
        max_length=20,
        choices=ItemCondition.choices,
    )
    warranty = models.BooleanField(
        "Tiene garantía vigente",
        default=False,
    )
    warranty_months = models.PositiveSmallIntegerField(
        "Meses de garantía",
        null=True,
        blank=True,
    )
    specs_json = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["listing"]),
            models.Index(fields=["brand"]),
        ]

    def __str__(self):
        return f"{self.brand} {self.model}"


class HomeItemType(models.TextChoices):
    """Tipo de artículo para categoría Hogar (sin taxonomía compleja)."""

    FURNITURE = "furniture", "Muebles"
    APPLIANCES = "appliances", "Electrodomésticos / cocina"
    DECOR = "decor", "Decoración"


class HomeGoodsListing(models.Model):
    """Detalle 1:1 para categoría Hogar (slug `hogar`)."""

    listing = models.OneToOneField(
        Listing,
        on_delete=models.CASCADE,
        related_name="homegoods",
    )
    item_type = models.CharField(
        "Tipo de artículo",
        max_length=20,
        choices=HomeItemType.choices,
        blank=True,
    )
    condition = models.CharField(
        "Condición",
        max_length=20,
        choices=ItemCondition.choices,
    )
    brand = models.CharField(max_length=80, blank=True)
    material = models.CharField(max_length=120, blank=True)
    dimensions = models.CharField(
        "Dimensiones aprox.",
        max_length=120,
        blank=True,
    )
    specs_json = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["listing"]),
            models.Index(fields=["item_type"]),
        ]

    def __str__(self):
        return f"Hogar · {self.get_condition_display()}"


# Nombre canónico del spec (mismo modelo / tabla que HomeGoodsListing).
HomeListing = HomeGoodsListing


class ListingPromotion(models.Model):
    """Promoción monetizable (destacado / impulso); ventana temporal + id externo de pago."""

    class PromotionType(models.TextChoices):
        FEATURED = "featured", "Destacado"
        BOOST = "boost", "Impulso"

    listing = models.ForeignKey(
        "Listing",
        on_delete=models.CASCADE,
        related_name="promotions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="listing_promotions",
    )
    type = models.CharField(max_length=20, choices=PromotionType.choices)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(db_index=True)
    is_active = models.BooleanField(default=True)
    external_payment_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["listing", "type", "is_active", "ends_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_type_display()} · {self.listing_id}"


class ListingImage(models.Model):
    """One image file per row; display order via sort_order."""

    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="listings/%Y/%m/")
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"Image for {self.listing_id}"
