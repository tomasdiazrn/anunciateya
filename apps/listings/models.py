from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class MarketBrand(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True, db_index=True)

    def __str__(self):
        return self.name


class MarketModel(models.Model):
    brand = models.ForeignKey(
        MarketBrand,
        on_delete=models.CASCADE,
        related_name="models",
    )
    category_slug = models.SlugField(max_length=32, db_index=True)
    item_type = models.CharField(max_length=40, blank=True, db_index=True)
    name = models.CharField(max_length=100)
    slug = models.SlugField()
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["brand", "category_slug", "item_type", "name"],
                name="market_model_unique_scope",
            )
        ]
        indexes = [
            models.Index(fields=["category_slug", "item_type", "brand", "name"]),
            models.Index(fields=["brand", "name"]),
        ]
        ordering = ["brand__name", "sort_order", "name"]

    def __str__(self):
        return f"{self.brand.name} {self.name}"

    @property
    def is_other_model(self) -> bool:
        return self.name == "Otro"
class ListingQuerySet(models.QuerySet):
    def published(self):
        """Listados públicos: el estado publicado es la única condición de visibilidad."""
        return self.filter(status=Listing.Status.PUBLISHED)


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
    published_by_platform = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Marks listings created by staff on behalf of the marketplace.",
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
            models.Index(
                fields=["status", "-created_at"],
                name="listing_status_created_idx",
            ),
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

    @property
    def is_platform_listing(self) -> bool:
        return bool(self.published_by_platform)

    @property
    def public_publisher_label(self) -> str:
        if not self.is_platform_listing:
            return ""
        brand = getattr(settings, "SEO_BRAND_NAME", "AnunciateYa")
        return f"Publicado por {brand}"


class ListingLead(models.Model):
    """Contacto recibido por un anuncio, base para seguimiento y métricas futuras."""

    class Source(models.TextChoices):
        FORM = "form", "Formulario"
        WHATSAPP = "whatsapp", "WhatsApp"

    class EmailStatus(models.TextChoices):
        NOT_APPLICABLE = "not_applicable", "No aplica"
        PENDING = "pending", "Pendiente"
        SENT = "sent", "Enviado"
        FAILED = "failed", "Falló"

    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="leads",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="listing_leads_received",
    )
    buyer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="listing_leads_sent",
        null=True,
        blank=True,
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.FORM,
        db_index=True,
    )
    buyer_name = models.CharField(max_length=120, blank=True)
    buyer_email = models.EmailField(blank=True)
    message = models.TextField(blank=True)
    email_status = models.CharField(
        max_length=20,
        choices=EmailStatus.choices,
        default=EmailStatus.NOT_APPLICABLE,
        db_index=True,
    )
    email_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["seller", "-created_at"]),
            models.Index(fields=["listing", "-created_at"]),
            models.Index(fields=["source", "-created_at"]),
            models.Index(fields=["email_status", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.get_source_display()} lead for listing {self.listing_id}"


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
    brand_fk = models.ForeignKey(
        MarketBrand,
        on_delete=models.PROTECT,
        related_name="vehicle_listings",
    )
    model_fk = models.ForeignKey(
        MarketModel,
        on_delete=models.PROTECT,
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
        return f"{self.brand_fk.name} {self.model_fk.name} ({self.year})"


class PropertyListing(models.Model):
    """Detalle específico para categoría Inmuebles (1:1 con Listing)."""

    class PropertyType(models.TextChoices):
        CASA = "casa", "Casa"
        DEPARTAMENTO = "departamento", "Departamento"
        SUITE = "suite", "Suite"
        TERRENO_LOTE = "terreno_lote", "Terreno / Lote"
        OFICINA_COMERCIAL = "oficina_comercial", "Oficina comercial"
        LOCAL_COMERCIAL = "local_comercial", "Local comercial"
        BODEGA_GALPON = "bodega_galpon", "Bodega / Galpón"
        HACIENDA_QUINTA = "hacienda_quinta", "Hacienda / Quinta"
        HABITACION = "habitacion", "Habitación"

    class OperationType(models.TextChoices):
        VENTA = "venta", "Venta"
        ALQUILER = "alquiler", "Alquiler"
        ALQUILER_TEMPORAL = "alquiler_temporal", "Alquiler temporal"

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
    brand_fk = models.ForeignKey(
        MarketBrand,
        on_delete=models.PROTECT,
        related_name="motorcycle_listings",
    )
    model_fk = models.ForeignKey(
        MarketModel,
        on_delete=models.PROTECT,
        related_name="motorcycle_listings",
    )
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
            models.Index(fields=["brand_fk", "model_fk"]),
        ]

    def __str__(self):
        return f"{self.brand_fk.name} {self.model_fk.name} ({self.year})"


class ElectronicsItemType(models.TextChoices):
    """Tipo de producto para electrónica, curado para el mercado Ecuador."""

    CELULARES = "celulares", "Celulares"
    LAPTOPS_COMPUTADORAS = "laptops_computadoras", "Laptops y computadoras"
    TV_AUDIO_VIDEO = "tv_audio_video", "TV, audio y video"
    CONSOLAS_VIDEOJUEGOS = "consolas_videojuegos", "Consolas y videojuegos"
    TABLETS_WEARABLES = "tablets_wearables", "Tablets y wearables"
    CAMARAS_SEGURIDAD = "camaras_seguridad", "Cámaras y seguridad"
    IMPRESORAS_MONITORES = "impresoras_monitores", "Impresoras y monitores"
    REDES_ACCESORIOS = "redes_accesorios", "Redes y accesorios"
    OTROS = "otros", "Otros electrónicos"


class ElectronicsListing(models.Model):
    """Detalle para categoría Electrónica."""

    listing = models.OneToOneField(
        Listing,
        on_delete=models.CASCADE,
        related_name="electronics",
    )
    item_type = models.CharField(
        "Tipo de producto",
        max_length=32,
        choices=ElectronicsItemType.choices,
        blank=True,
    )
    brand_fk = models.ForeignKey(
        MarketBrand,
        on_delete=models.PROTECT,
        related_name="electronics_listings",
    )
    model_fk = models.ForeignKey(
        MarketModel,
        on_delete=models.PROTECT,
        related_name="electronics_listings",
    )
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
            models.Index(fields=["item_type"]),
            models.Index(fields=["brand_fk", "model_fk"]),
        ]

    def __str__(self):
        return f"{self.brand_fk.name} {self.model_fk.name}"


class HomeItemType(models.TextChoices):
    """Tipo de artículo para categoría Hogar, curado para el mercado Ecuador."""

    FURNITURE = "furniture", "Muebles"
    APPLIANCES = "appliances", "Electrodomésticos / cocina"
    DECOR = "decor", "Decoración"
    KITCHENWARE = "kitchenware", "Menaje y cocina"
    MATTRESSES_BEDS = "mattresses_beds", "Colchones y camas"
    OUTDOOR_GARDEN = "outdoor_garden", "Patio y jardín"


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
    brand_fk = models.ForeignKey(
        MarketBrand,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="homegoods_listings",
    )
    model_fk = models.ForeignKey(
        MarketModel,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="homegoods_listings",
    )
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
            models.Index(fields=["brand_fk", "model_fk"]),
        ]

    def __str__(self):
        return f"Hogar · {self.get_condition_display()}"


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
    # Optimized variants (optional; original remains source of truth)
    image_thumb = models.ImageField(upload_to="listings/%Y/%m/variants/", blank=True, null=True)
    image_thumb_webp = models.ImageField(upload_to="listings/%Y/%m/variants/", blank=True, null=True)
    image_medium = models.ImageField(upload_to="listings/%Y/%m/variants/", blank=True, null=True)
    image_medium_webp = models.ImageField(upload_to="listings/%Y/%m/variants/", blank=True, null=True)
    image_large = models.ImageField(upload_to="listings/%Y/%m/variants/", blank=True, null=True)
    image_large_webp = models.ImageField(upload_to="listings/%Y/%m/variants/", blank=True, null=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def delete(self, *args, **kwargs):
        for field_name in (
            "image",
            "image_thumb",
            "image_thumb_webp",
            "image_medium",
            "image_medium_webp",
            "image_large",
            "image_large_webp",
        ):
            field_file = getattr(self, field_name, None)
            if field_file:
                field_file.delete(save=False)
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"Image for {self.listing_id}"
