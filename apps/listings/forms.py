from datetime import date
from decimal import Decimal

from django import forms
from django.utils.safestring import mark_safe

from apps.trust.models import ListingReport

from .category_extensions import (
    ELECTRONICS_SLUG,
    HOMEGOODS_SLUG,
    MOTORCYCLE_SLUG,
    PROPERTY_SLUG,
    VEHICLE_SLUG,
)
from .location_geocoding import (
    MAPBOX_PROVIDER,
    apply_mapbox_geocoding_metadata,
    coordinates_within_ecuador,
)
from .models import (
    ElectronicsItemType,
    ElectronicsListing,
    HomeGoodsListing,
    HomeItemType,
    ItemCondition,
    Listing,
    MarketBrand,
    MarketModel,
    MarketZone,
    MotorcycleListing,
    PropertyListing,
    VehicleListing,
)
from .market_taxonomy import (
    market_brand_queryset,
    market_model_belongs_to_brand,
    market_model_queryset,
)

# Mensajes de error cortos (alineados a signup / UX en español).
_MSG_REQUIRED = "Este campo es obligatorio."
DEFAULT_CONTACT_MESSAGE = (
    "¡Hola! Quiero que se comuniquen conmigo por este anuncio que vi en AnunciateYa."
)

_DEFAULT_LISTING_PLACEHOLDERS = {
    "title": "Artículo en buen estado, listo para entregar",
    "description": "Estado, medidas, uso, entrega o retiro, forma de pago…",
    "price_amount": "120",
    "location_reference": "Ej. frente al parque o punto de encuentro",
}

_CATEGORY_LISTING_PLACEHOLDERS = {
    VEHICLE_SLUG: {
        "title": "Toyota Corolla 2018 automático, excelente estado",
        "description": "Kilometraje, mantenimiento, extras, papeles y forma de pago…",
        "price_amount": "18500",
        "location_reference": "Ej. cerca de San Marino",
    },
    PROPERTY_SLUG: {
        "title": "Casa 3 habitaciones en Samborondón",
        "description": (
            "Ambientes, metros, amenities, estado del inmueble y condiciones…"
        ),
        "price_amount": "85000",
        "location_reference": "Ej. conjunto cerrado, km 5",
    },
    MOTORCYCLE_SLUG: {
        "title": "Honda CB 190R 2021, papeles al día",
        "description": "Cilindrada, kilometraje, mantenimiento, accesorios y papeles…",
        "price_amount": "3200",
        "location_reference": "Ej. retiro en centro comercial",
    },
    ELECTRONICS_SLUG: {
        "title": "iPhone 13 Pro 128 GB en excelente estado",
        "description": "Estado, accesorios incluidos, garantía, batería y detalles…",
        "price_amount": "520",
        "location_reference": "Ej. entrega en mall o parque",
    },
    HOMEGOODS_SLUG: {
        "title": "Sofá de 3 cuerpos en buen estado",
        "description": "Medidas, material, estado, tiempo de uso, retiro o entrega…",
        "price_amount": "180",
        "location_reference": "Ej. retirar en edificio con ascensor",
    },
}


_DIGITS_ONLY_ATTRS = {
    "inputmode": "numeric",
    "pattern": "[0-9]*",
    "data-digits-only": "true",
    "autocomplete": "off",
}


def _with_empty_choice(label, choices):
    return [("", label)] + list(choices)


def _raw_digits_only(form, field_name):
    raw = form.data.get(form.add_prefix(field_name), "")
    if raw in (None, ""):
        return True
    return str(raw).strip().isdigit()


class ListingInterestForm(forms.Form):
    """Mensaje validado en servidor cuando un comprador contacta (parcial HTMX)."""

    buyer_name = forms.CharField(
        label="Tu nombre",
        max_length=120,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "name",
                "placeholder": "Ej.: Ana Pérez",
            }
        ),
        error_messages={"required": _MSG_REQUIRED},
    )
    buyer_email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "autocomplete": "email",
                "placeholder": "tu@email.com",
            }
        ),
        error_messages={"required": _MSG_REQUIRED},
    )
    message = forms.CharField(
        label="Mensaje al vendedor",
        initial=DEFAULT_CONTACT_MESSAGE,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "class": "form-control",
                "placeholder": (
                    "Ej.: Hola, ¿sigue disponible? ¿Podemos verlo en Guayaquil?"
                ),
            }
        ),
        min_length=10,
        max_length=500,
    )
    accept_terms = forms.BooleanField(
        required=True,
        initial=True,
        label=mark_safe(
            'Acepto los <a href="/terminos/" target="_blank" rel="noopener">términos</a> '
            'y la <a href="/privacidad/" target="_blank" rel="noopener">política de privacidad</a>.'
        ),
        widget=forms.CheckboxInput(attrs={"class": "checkbox-input"}),
        error_messages={
            "required": "Debes aceptar los términos y la política de privacidad para continuar.",
        },
    )


class BaseListingForm(forms.ModelForm):
    """Campos comunes del anuncio (sin categoría; la fija la URL o la vista)."""

    add_location = forms.BooleanField(
        label="Agregar ubicación",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "account-contact-checkbox__input"}),
    )
    zone = forms.ModelChoiceField(
        label="Ubicación",
        queryset=MarketZone.objects.none(),
        empty_label="Selecciona ubicación",
        required=False,
        error_messages={
            "invalid_choice": "Elige una ubicación válida.",
        },
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    publish_state = forms.ChoiceField(
        label="Publicación",
        choices=[
            (Listing.Status.PUBLISHED, "Publicar"),
            (Listing.Status.DRAFT, "Guardar como borrador"),
        ],
        required=True,
        error_messages={
            "required": "Indicá si publicás o guardás como borrador.",
            "invalid_choice": "Elegí una opción válida.",
        },
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Listing
        fields = [
            "title",
            "description",
            "price_amount",
            "currency",
            "zone",
            "location_reference",
        ]
        labels = {
            "title": "Título del anuncio",
            "description": "Descripción",
            "price_amount": "Precio",
            "currency": "Moneda",
            "zone": "Ubicación",
            "location_reference": "Referencia",
        }
        help_texts = {
            "title": (
                "Se genera automáticamente a partir de los datos. Puedes editarlo."
            ),
            "description": "Describe el artículo, defectos, entrega o retiro.",
            "price_amount": "",
            "zone": "",
            "location_reference": "Opcional: punto de encuentro o referencia cercana.",
        }
        error_messages = {
            "title": {
                "required": _MSG_REQUIRED,
                "max_length": "El título no puede superar %(limit_value)d caracteres.",
            },
            "description": {
                "required": _MSG_REQUIRED,
            },
            "price_amount": {
                "required": _MSG_REQUIRED,
                "invalid": "Introduce un precio válido.",
            },
            "location_reference": {
                "max_length": "La referencia no puede superar %(limit_value)d caracteres.",
            },
        }
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "off",
                    "data-autofill": "true",
                    "placeholder": (
                        _DEFAULT_LISTING_PLACEHOLDERS["title"]
                    ),
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": (
                        _DEFAULT_LISTING_PLACEHOLDERS["description"]
                    ),
                }
            ),
            "price_amount": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "min": "0.01",
                    "placeholder": _DEFAULT_LISTING_PLACEHOLDERS["price_amount"],
                    **_DIGITS_ONLY_ATTRS,
                }
            ),
            "location_reference": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _DEFAULT_LISTING_PLACEHOLDERS["location_reference"],
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        category_slug = kwargs.pop("category_slug", None)
        super().__init__(*args, **kwargs)
        title_f = Listing._meta.get_field("title")
        self.fields["title"].widget.attrs["maxlength"] = title_f.max_length
        ref_f = Listing._meta.get_field("location_reference")
        self.fields["location_reference"].widget.attrs["maxlength"] = ref_f.max_length
        self.fields["zone"].queryset = MarketZone.objects.filter(is_active=True)
        self.fields["currency"].widget = forms.HiddenInput()
        self.fields["currency"].required = False
        if not self.instance.pk:
            self.fields["currency"].initial = "USD"
            self.fields["publish_state"].initial = Listing.Status.PUBLISHED
        else:
            self.fields["publish_state"].initial = (
                self.instance.status or Listing.Status.DRAFT
            )
        self.fields["add_location"].initial = bool(
            self.instance.pk
            and (
                getattr(self.instance, "zone_id", None)
                or (self.instance.location_reference or "").strip()
            )
        )
        if not category_slug and getattr(self.instance, "category_id", None):
            category_slug = getattr(self.instance.category, "slug", None)
        self._apply_category_placeholders(category_slug)

    def _apply_category_placeholders(self, category_slug):
        placeholders = {
            **_DEFAULT_LISTING_PLACEHOLDERS,
            **_CATEGORY_LISTING_PLACEHOLDERS.get(category_slug, {}),
        }
        for name, placeholder in placeholders.items():
            if name in self.fields:
                self.fields[name].widget.attrs["placeholder"] = placeholder

    def clean_price_amount(self):
        if not _raw_digits_only(self, "price_amount"):
            raise forms.ValidationError("Introduce un precio usando solo números.")
        value = self.cleaned_data["price_amount"]
        if value is not None and value <= 0:
            raise forms.ValidationError("Ingresa un precio mayor que cero.")
        return value

    def clean_location_reference(self):
        return (self.cleaned_data.get("location_reference") or "").strip()

    def clean(self):
        cleaned = super().clean()
        explicit_location_toggle = "add_location_present" in self.data
        add_location = bool(cleaned.get("add_location"))
        zone = cleaned.get("zone")
        reference = (cleaned.get("location_reference") or "").strip()
        if not explicit_location_toggle and (zone is not None or reference):
            add_location = True
            cleaned["add_location"] = True
        if not add_location:
            cleaned["zone"] = None
            cleaned["location_reference"] = ""
            return cleaned
        if zone is None:
            self.add_error("zone", "Elige la ubicación del anuncio.")
        return cleaned


class ListingForm(BaseListingForm):
    """Crear o editar anuncio con selector de categoría (flujo genérico / edición mixta)."""

    class Meta(BaseListingForm.Meta):
        fields = [
            "title",
            "description",
            "price_amount",
            "currency",
            "category",
            "zone",
            "location_reference",
        ]
        labels = {
            **BaseListingForm.Meta.labels,
            "category": "Categoría",
        }
        help_texts = {
            **BaseListingForm.Meta.help_texts,
            "category": "Selecciona la categoría que mejor describe tu anuncio.",
        }
        error_messages = {
            **BaseListingForm.Meta.error_messages,
            "category": {"required": "Elige una categoría."},
        }
        widgets = {
            **BaseListingForm.Meta.widgets,
            "category": forms.Select(attrs={"class": "form-control"}),
        }


class VehicleListingForm(forms.ModelForm):
    brand_fk = forms.ModelChoiceField(
        label="Marca",
        queryset=MarketBrand.objects.none(),
        required=False,
        empty_label="Selecciona marca",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "hx-get": "/api/vehicle-models/",
                "hx-target": "#id_model_fk",
                "hx-swap": "innerHTML",
                "hx-trigger": "change",
                "hx-sync": "closest form:replace",
            }
        ),
    )
    model_fk = forms.ModelChoiceField(
        label="Modelo",
        queryset=MarketModel.objects.none(),
        required=False,
        empty_label="Selecciona modelo",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = VehicleListing
        fields = [
            "brand_fk",
            "model_fk",
            "year",
            "mileage",
            "transmission",
            "fuel_type",
            "doors",
        ]
        labels = {
            "year": "Año",
            "mileage": "Kilometraje",
            "doors": "Puertas",
            "transmission": "Transmisión",
            "fuel_type": "Combustible",
        }
        help_texts = {}
        error_messages = {
            "year": {
                "required": _MSG_REQUIRED,
                "invalid": "Introduce un año válido.",
            },
            "mileage": {"invalid": "Introduce un kilometraje válido."},
            "doors": {
                "required": _MSG_REQUIRED,
                "invalid": "Introduce un número de puertas válido.",
            },
            "transmission": {
                "required": _MSG_REQUIRED,
                "invalid_choice": "Elegí una opción válida.",
            },
            "fuel_type": {"invalid_choice": "Elegí una opción válida."},
        }
        widgets = {
            "year": forms.TextInput(
                attrs={
                    "class": "form-control vehicle-input-year",
                    "min": "1980",
                    "max": "2100",
                    "step": "1",
                    "placeholder": "2018",
                    **_DIGITS_ONLY_ATTRS,
                }
            ),
            "mileage": forms.TextInput(
                attrs={
                    "class": "form-control vehicle-input-mileage",
                    "min": "0",
                    "max": "9999999",
                    "step": "1",
                    "placeholder": "85000",
                    **_DIGITS_ONLY_ATTRS,
                }
            ),
            "doors": forms.TextInput(
                attrs={
                    "class": "form-control vehicle-input-doors",
                    "min": "2",
                    "max": "9",
                    "step": "1",
                    "placeholder": "4",
                    **_DIGITS_ONLY_ATTRS,
                }
            ),
            "transmission": forms.Select(attrs={"class": "form-control"}),
            "fuel_type": forms.Select(
                attrs={"class": "form-control vehicle-select-fuel"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["brand_fk"].queryset = market_brand_queryset(VEHICLE_SLUG)

        for _name, field in self.fields.items():
            field.help_text = ""

        # Creación: preselecciones típicas (no en edición)
        if not self.instance.pk and not self.is_bound:
            self.fields["transmission"].initial = VehicleListing.Transmission.MANUAL
            self.fields["fuel_type"].initial = VehicleListing.FuelType.GASOLINA

        brand_id = None
        if self.is_bound:
            raw = self.data.get("brand_fk")
            if raw:
                try:
                    brand_id = int(raw)
                except (TypeError, ValueError):
                    brand_id = None
        else:
            if getattr(self.instance, "brand_fk_id", None):
                brand_id = self.instance.brand_fk_id

        if brand_id:
            self.fields["model_fk"].queryset = (
                market_model_queryset(VEHICLE_SLUG, brand_id)
            )
            self.fields["model_fk"].widget.attrs.pop("disabled", None)
        else:
            self.fields["model_fk"].queryset = MarketModel.objects.none()
            self.fields["model_fk"].empty_label = "Primero selecciona una marca"
            # UX: no se puede escoger modelo sin marca.
            self.fields["model_fk"].widget.attrs["disabled"] = "disabled"

    def clean_year(self):
        if not _raw_digits_only(self, "year"):
            raise forms.ValidationError("Introduce un año usando solo números.")
        y = self.cleaned_data["year"]
        current = date.today().year
        if y < 1980 or y > current + 1:
            raise forms.ValidationError(
                f"Ingresa un año entre 1980 y {current + 1}."
            )
        return y

    def clean_mileage(self):
        if not _raw_digits_only(self, "mileage"):
            raise forms.ValidationError("Introduce un kilometraje usando solo números.")
        v = self.cleaned_data.get("mileage")
        if v is not None and v < 0:
            raise forms.ValidationError("El kilometraje debe ser 0 o mayor.")
        return v

    def clean_doors(self):
        if not _raw_digits_only(self, "doors"):
            raise forms.ValidationError("Introduce puertas usando solo números.")
        d = self.cleaned_data["doors"]
        if d < 2 or d > 9:
            raise forms.ValidationError("Indica un número de puertas entre 2 y 9.")
        return d

    def clean(self):
        cleaned = super().clean()
        b = cleaned.get("brand_fk")
        m = cleaned.get("model_fk")
        if not b:
            self.add_error("brand_fk", "Selecciona una marca.")
        elif not m:
            self.add_error("model_fk", "Selecciona un modelo.")
        elif not market_model_belongs_to_brand(VEHICLE_SLUG, b, m):
            self.add_error("model_fk", "El modelo seleccionado no pertenece a la marca.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class PropertyListingForm(forms.ModelForm):
    class Meta:
        model = PropertyListing
        fields = [
            "property_type",
            "operation_type",
            "rooms",
            "bathrooms",
            "area_m2",
            "parking_spaces",
            "furnished",
            "property_condition",
            "address_line",
            "address_place_label",
            "location_precision",
            "latitude",
            "longitude",
            "geocoding_provider",
            "geocoding_place_id",
        ]
        labels = {
            "property_type": "Tipo de propiedad",
            "operation_type": "Operación",
            "rooms": "Habitaciones",
            "bathrooms": "Baños",
            "area_m2": "Superficie (m²)",
            "parking_spaces": "Parqueaderos",
            "furnished": "Amoblado",
            "property_condition": "Estado",
            "address_line": "Dirección del inmueble",
            "address_place_label": "Nombre del lugar o edificio",
            "location_precision": "Visibilidad de ubicación",
            "latitude": "Latitud",
            "longitude": "Longitud",
        }
        help_texts = {name: "" for name in fields}
        error_messages = {
            "property_type": {
                "required": _MSG_REQUIRED,
                "invalid_choice": "Elegí una opción válida.",
            },
            "rooms": {
                "required": _MSG_REQUIRED,
                "invalid": "Introduce un número válido.",
            },
            "bathrooms": {
                "required": _MSG_REQUIRED,
                "invalid": "Introduce un número válido.",
            },
            "area_m2": {
                "required": _MSG_REQUIRED,
                "invalid": "Introduce una superficie válida.",
            },
            "operation_type": {"invalid_choice": "Elegí una opción válida."},
            "property_condition": {"invalid_choice": "Elegí una opción válida."},
            "parking_spaces": {"invalid": "Introduce un número válido."},
            "location_precision": {"invalid_choice": "Elegí una opción válida."},
            "latitude": {"invalid": "Introduce una latitud válida."},
            "longitude": {"invalid": "Introduce una longitud válida."},
        }
        widgets = {
            "property_type": forms.Select(attrs={"class": "form-control"}),
            "operation_type": forms.Select(attrs={"class": "form-control"}),
            "rooms": forms.TextInput(
                attrs={
                    "class": "form-control property-input-compact",
                    "min": "1",
                    "max": "99",
                    "step": "1",
                    "placeholder": "3",
                    **_DIGITS_ONLY_ATTRS,
                }
            ),
            "bathrooms": forms.TextInput(
                attrs={
                    "class": "form-control property-input-compact",
                    "min": "1",
                    "max": "99",
                    "step": "1",
                    "placeholder": "2",
                    **_DIGITS_ONLY_ATTRS,
                }
            ),
            "area_m2": forms.TextInput(
                attrs={
                    "class": "form-control property-input-compact",
                    "min": "1",
                    "max": "999999",
                    "step": "1",
                    "placeholder": "120",
                    **_DIGITS_ONLY_ATTRS,
                }
            ),
            "parking_spaces": forms.TextInput(
                attrs={
                    "class": "form-control property-input-compact",
                    "min": "0",
                    "max": "99",
                    "step": "1",
                    "placeholder": "1",
                    **_DIGITS_ONLY_ATTRS,
                }
            ),
            "furnished": forms.CheckboxInput(
                attrs={"class": "checkbox-input"}
            ),
            "property_condition": forms.Select(attrs={"class": "form-control"}),
            "address_line": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "street-address",
                    "placeholder": "Ej. Av. Samborondón km 5, conjunto privado",
                }
            ),
            "address_place_label": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej. Edificio Central Park",
                }
            ),
            "location_precision": forms.HiddenInput(),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "geocoding_provider": forms.HiddenInput(),
            "geocoding_place_id": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["property_type"].choices = _with_empty_choice(
            "Selecciona el tipo de propiedad",
            PropertyListing.PropertyType.choices,
        )
        op = self.fields["operation_type"]
        op.required = False
        op.choices = _with_empty_choice(
            "Selecciona la operación",
            PropertyListing.OperationType.choices,
        )
        cond = self.fields["property_condition"]
        cond.required = False
        cond.choices = _with_empty_choice(
            "Selecciona el estado del inmueble",
            PropertyListing.PropertyConditionChoice.choices,
        )
        self.fields["parking_spaces"].required = False
        self.fields["address_line"].required = False
        self.fields["address_place_label"].required = False
        self.fields["latitude"].required = False
        self.fields["longitude"].required = False
        self.fields["location_precision"].required = False
        self.fields["geocoding_provider"].required = False
        self.fields["geocoding_place_id"].required = False
        self.fields["location_precision"].choices = PropertyListing.LocationPrecision.choices

    def clean_operation_type(self):
        v = self.cleaned_data.get("operation_type")
        if v in (None, ""):
            return None
        return v

    def clean_property_condition(self):
        v = self.cleaned_data.get("property_condition")
        if v in (None, ""):
            return None
        return v

    def clean_parking_spaces(self):
        if not _raw_digits_only(self, "parking_spaces"):
            raise forms.ValidationError("Introduce parqueaderos usando solo números.")
        v = self.cleaned_data.get("parking_spaces")
        if v in (None, ""):
            return None
        return v

    def clean_rooms(self):
        if not _raw_digits_only(self, "rooms"):
            raise forms.ValidationError("Introduce habitaciones usando solo números.")
        v = self.cleaned_data["rooms"]
        if v < 1:
            raise forms.ValidationError("Indica al menos 1 habitación.")
        return v

    def clean_bathrooms(self):
        if not _raw_digits_only(self, "bathrooms"):
            raise forms.ValidationError("Introduce baños usando solo números.")
        v = self.cleaned_data["bathrooms"]
        if v < 1:
            raise forms.ValidationError("Indica al menos 1 baño.")
        return v

    def clean_area_m2(self):
        if not _raw_digits_only(self, "area_m2"):
            raise forms.ValidationError("Introduce superficie usando solo números.")
        v = self.cleaned_data["area_m2"]
        if v < 1:
            raise forms.ValidationError("La superficie debe ser mayor que cero.")
        return v

    def clean_address_line(self):
        return (self.cleaned_data.get("address_line") or "").strip()

    def clean_address_place_label(self):
        return (self.cleaned_data.get("address_place_label") or "").strip()

    def _clean_coordinate(self, field_name: str, minimum: Decimal, maximum: Decimal):
        value = self.cleaned_data.get(field_name)
        if value in (None, ""):
            return None
        if value < minimum or value > maximum:
            label = "latitud" if field_name == "latitude" else "longitud"
            raise forms.ValidationError(f"La {label} está fuera de rango.")
        return value

    def clean_latitude(self):
        return self._clean_coordinate("latitude", Decimal("-90"), Decimal("90"))

    def clean_longitude(self):
        return self._clean_coordinate("longitude", Decimal("-180"), Decimal("180"))

    def clean(self):
        cleaned = super().clean()
        address = (cleaned.get("address_line") or "").strip()
        place = (cleaned.get("address_place_label") or "").strip()
        lat = cleaned.get("latitude")
        lng = cleaned.get("longitude")
        provider = (cleaned.get("geocoding_provider") or "").strip()
        place_id = (cleaned.get("geocoding_place_id") or "").strip()

        if address:
            cleaned["location_precision"] = PropertyListing.LocationPrecision.EXACT
        elif place:
            cleaned["location_precision"] = PropertyListing.LocationPrecision.APPROXIMATE
        else:
            cleaned["location_precision"] = PropertyListing.LocationPrecision.SECTOR

        if (lat is None) != (lng is None):
            self.add_error(
                "latitude" if lat is None else "longitude",
                "Completa latitud y longitud, o deja ambas vacías.",
            )

        if lat is not None and lng is not None and not coordinates_within_ecuador(lat, lng):
            self.add_error("latitude", "La ubicación debe estar dentro de Ecuador.")

        if provider and provider != MAPBOX_PROVIDER:
            cleaned["geocoding_provider"] = ""
            cleaned["geocoding_place_id"] = ""
        elif provider == MAPBOX_PROVIDER and (lat is None or lng is None):
            cleaned["geocoding_provider"] = ""
            cleaned["geocoding_place_id"] = ""
        elif provider == MAPBOX_PROVIDER:
            cleaned["geocoding_place_id"] = place_id

        if lat is None and provider:
            cleaned["geocoding_provider"] = ""
            cleaned["geocoding_place_id"] = ""

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        provider = (self.cleaned_data.get("geocoding_provider") or "").strip()
        place_id = (self.cleaned_data.get("geocoding_place_id") or "").strip()
        apply_mapbox_geocoding_metadata(
            obj,
            provider=provider,
            place_id=place_id,
        )
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class MotorcycleListingForm(forms.ModelForm):
    brand_fk = forms.ModelChoiceField(
        label="Marca",
        queryset=MarketBrand.objects.none(),
        required=False,
        empty_label="Selecciona marca",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "hx-get": "/api/motorcycle-models/",
                "hx-target": "#id_model_fk",
                "hx-swap": "innerHTML",
                "hx-trigger": "change",
                "hx-sync": "closest form:replace",
            }
        ),
    )
    model_fk = forms.ModelChoiceField(
        label="Modelo",
        queryset=MarketModel.objects.none(),
        required=False,
        empty_label="Selecciona modelo",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = MotorcycleListing
        fields = [
            "brand_fk",
            "model_fk",
            "year",
            "engine_cc",
            "mileage",
            "transmission",
            "fuel_type",
            "condition",
        ]
        labels = {
            "year": "Año",
            "engine_cc": "Cilindrada (cc)",
            "mileage": "Kilometraje",
            "transmission": "Transmisión",
            "fuel_type": "Combustible",
            "condition": "Condición",
        }
        help_texts = {name: "" for name in fields}
        error_messages = {
            "year": {
                "required": _MSG_REQUIRED,
                "invalid": "Introduce un año válido.",
            },
            "engine_cc": {"invalid": "Introduce una cilindrada válida."},
            "mileage": {"invalid": "Introduce un kilometraje válido."},
            "transmission": {
                "required": _MSG_REQUIRED,
                "invalid_choice": "Elegí una opción válida.",
            },
            "fuel_type": {
                "required": _MSG_REQUIRED,
                "invalid_choice": "Elegí una opción válida.",
            },
            "condition": {
                "required": _MSG_REQUIRED,
                "invalid_choice": "Elegí una opción válida.",
            },
        }
        widgets = {
            "year": forms.TextInput(
                attrs={
                    "class": "form-control motorcycle-input-year",
                    "min": "1980",
                    "max": "2100",
                    "step": "1",
                    "placeholder": "2018",
                    **_DIGITS_ONLY_ATTRS,
                }
            ),
            "engine_cc": forms.TextInput(
                attrs={
                    "class": "form-control motorcycle-input-compact",
                    "min": "50",
                    "max": "9999",
                    "step": "1",
                    "placeholder": "250",
                    **_DIGITS_ONLY_ATTRS,
                }
            ),
            "mileage": forms.TextInput(
                attrs={
                    "class": "form-control motorcycle-input-mileage",
                    "min": "0",
                    "max": "9999999",
                    "step": "1",
                    "placeholder": "12000",
                    **_DIGITS_ONLY_ATTRS,
                }
            ),
            "transmission": forms.Select(attrs={"class": "form-control"}),
            "fuel_type": forms.Select(attrs={"class": "form-control"}),
            "condition": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["brand_fk"].queryset = market_brand_queryset(MOTORCYCLE_SLUG)
        brand_id = None
        if self.is_bound:
            raw = self.data.get("brand_fk")
            if raw:
                try:
                    brand_id = int(raw)
                except (TypeError, ValueError):
                    brand_id = None
        elif getattr(self.instance, "brand_fk_id", None):
            brand_id = self.instance.brand_fk_id

        if brand_id:
            self.fields["model_fk"].queryset = market_model_queryset(
                MOTORCYCLE_SLUG,
                brand_id,
            )
            self.fields["model_fk"].widget.attrs.pop("disabled", None)
        else:
            self.fields["model_fk"].empty_label = "Primero selecciona una marca"
            self.fields["model_fk"].widget.attrs["disabled"] = "disabled"

        if not self.instance.pk and not self.is_bound:
            self.fields["transmission"].initial = (
                MotorcycleListing.Transmission.MANUAL
            )
            self.fields["fuel_type"].initial = MotorcycleListing.FuelType.GASOLINA
        self.fields["condition"].choices = _with_empty_choice(
            "Selecciona la condición",
            ItemCondition.choices,
        )
        self.fields["mileage"].required = False
        self.fields["engine_cc"].required = False

    def clean_year(self):
        if not _raw_digits_only(self, "year"):
            raise forms.ValidationError("Introduce un año usando solo números.")
        y = self.cleaned_data["year"]
        current = date.today().year
        if y < 1980 or y > current + 1:
            raise forms.ValidationError(
                f"Ingresa un año entre 1980 y {current + 1}."
            )
        return y

    def clean_engine_cc(self):
        if not _raw_digits_only(self, "engine_cc"):
            raise forms.ValidationError("Introduce cilindrada usando solo números.")
        v = self.cleaned_data.get("engine_cc")
        if v is not None and v < 50:
            raise forms.ValidationError(
                "Si indicás cilindrada, debe ser al menos 50 cc."
            )
        return v

    def clean_mileage(self):
        if not _raw_digits_only(self, "mileage"):
            raise forms.ValidationError("Introduce kilometraje usando solo números.")
        v = self.cleaned_data.get("mileage")
        if v is not None and v < 0:
            raise forms.ValidationError("El kilometraje no puede ser negativo.")
        return v

    def clean(self):
        cleaned = super().clean()
        brand = cleaned.get("brand_fk")
        model = cleaned.get("model_fk")
        if not brand:
            self.add_error("brand_fk", "Selecciona una marca.")
        elif not model:
            self.add_error("model_fk", "Selecciona un modelo.")
        elif not market_model_belongs_to_brand(MOTORCYCLE_SLUG, brand, model):
            self.add_error("model_fk", "El modelo seleccionado no pertenece a la marca.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class ElectronicsListingForm(forms.ModelForm):
    brand_fk = forms.ModelChoiceField(
        label="Marca",
        queryset=MarketBrand.objects.none(),
        required=False,
        empty_label="Selecciona marca",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "hx-get": "/api/electronics-models/",
                "hx-target": "#id_model_fk",
                "hx-include": "#id_item_type",
                "hx-swap": "innerHTML",
                "hx-trigger": "change",
                "hx-sync": "closest form:replace",
            }
        ),
    )
    model_fk = forms.ModelChoiceField(
        label="Modelo",
        queryset=MarketModel.objects.none(),
        required=False,
        empty_label="Selecciona modelo",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = ElectronicsListing
        fields = [
            "item_type",
            "brand_fk",
            "model_fk",
            "condition",
            "warranty",
            "warranty_months",
        ]
        labels = {
            "item_type": "Tipo de producto",
            "condition": "Condición",
            "warranty": "Tiene garantía vigente",
            "warranty_months": "Meses de garantía",
        }
        help_texts = {
            "item_type": "Ayuda a compradores a encontrar celulares, TVs, laptops y consolas.",
            "brand_fk": "Marcas comunes en Ecuador. Si no aparece, elige Otra marca.",
            "model_fk": "Modelos frecuentes por marca. Si no aparece, elige Otro.",
            "condition": "Nuevo, usado o reacondicionado.",
            "warranty": "Marcá solo si aplica garantía del fabricante o tienda.",
            "warranty_months": "Opcional. Si aplica, indicá la duración aproximada.",
        }
        error_messages = {
            "condition": {
                "required": _MSG_REQUIRED,
                "invalid_choice": "Elegí una opción válida.",
            },
            "warranty_months": {"invalid": "Introduce un número válido."},
        }
        widgets = {
            "item_type": forms.Select(attrs={"class": "form-control"}),
            "condition": forms.Select(attrs={"class": "form-control"}),
            "warranty": forms.CheckboxInput(attrs={"class": "checkbox-input"}),
            "warranty_months": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                    "max": 120,
                    "placeholder": "Ej. 12",
                    **_DIGITS_ONLY_ATTRS,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_item_type = ""
        brand_id = None
        if self.is_bound:
            current_item_type = (self.data.get("item_type") or "").strip()
            raw = self.data.get("brand_fk")
            if raw:
                try:
                    brand_id = int(raw)
                except (TypeError, ValueError):
                    brand_id = None
        elif self.instance.pk:
            current_item_type = (self.instance.item_type or "").strip()
            brand_id = self.instance.brand_fk_id

        self.fields["brand_fk"].queryset = (
            market_brand_queryset(
                ELECTRONICS_SLUG,
                item_type=current_item_type,
            )
            if current_item_type
            else MarketBrand.objects.none()
        )
        if not current_item_type:
            self.fields["brand_fk"].empty_label = (
                "Primero selecciona el tipo de producto"
            )
        if brand_id:
            self.fields["model_fk"].queryset = market_model_queryset(
                ELECTRONICS_SLUG,
                brand_id,
                item_type=current_item_type,
            )
            self.fields["model_fk"].widget.attrs.pop("disabled", None)
        else:
            self.fields["model_fk"].empty_label = "Primero selecciona una marca"
            self.fields["model_fk"].widget.attrs["disabled"] = "disabled"
        self.fields["item_type"].choices = _with_empty_choice(
            "Selecciona el tipo de producto",
            ElectronicsItemType.choices,
        )
        self.fields["item_type"].required = True
        self.fields["condition"].choices = _with_empty_choice(
            "Selecciona la condición",
            ItemCondition.choices,
        )
        self.fields["item_type"].widget.attrs.update(
            {
                "hx-get": "/api/electronics-brands/",
                "hx-target": "#id_brand_fk",
                "hx-swap": "innerHTML",
                "hx-trigger": "change",
                "hx-sync": "closest form:replace",
            }
        )

    def clean_warranty_months(self):
        if not _raw_digits_only(self, "warranty_months"):
            raise forms.ValidationError("Introduce meses usando solo números.")
        v = self.cleaned_data.get("warranty_months")
        if v is not None and (v < 1 or v > 120):
            raise forms.ValidationError("Indicá entre 1 y 120 meses, o dejá el campo vacío.")
        return v

    def clean(self):
        cleaned = super().clean()
        item_type = (cleaned.get("item_type") or "").strip()
        brand = cleaned.get("brand_fk")
        model = cleaned.get("model_fk")
        if not brand:
            self.add_error("brand_fk", "Selecciona una marca.")
        elif not model:
            self.add_error("model_fk", "Selecciona un modelo.")
        elif not market_model_belongs_to_brand(
            ELECTRONICS_SLUG,
            brand,
            model,
            item_type=item_type,
        ):
            self.add_error("model_fk", "El modelo seleccionado no pertenece a la marca.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class HomeGoodsListingForm(forms.ModelForm):
    brand_fk = forms.ModelChoiceField(
        label="Marca",
        queryset=MarketBrand.objects.none(),
        required=False,
        empty_label="Selecciona marca",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "hx-get": "/api/home-models/",
                "hx-target": "#id_model_fk",
                "hx-include": "#id_item_type",
                "hx-swap": "innerHTML",
                "hx-trigger": "change",
                "hx-sync": "closest form:replace",
            }
        ),
    )
    model_fk = forms.ModelChoiceField(
        label="Modelo",
        queryset=MarketModel.objects.none(),
        required=False,
        empty_label="Selecciona modelo",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = HomeGoodsListing
        fields = [
            "item_type",
            "brand_fk",
            "model_fk",
            "condition",
            "material",
            "dimensions",
        ]
        labels = {
            "item_type": "Tipo de artículo",
            "condition": "Condición",
            "material": "Material",
            "dimensions": "Dimensiones aprox.",
        }
        help_texts = {
            "item_type": "Muebles, electrodomésticos, decoración, cocina, colchones o jardín.",
            "brand_fk": "Opcional. Marcas comunes en Ecuador; si no aplica, elige Otra marca.",
            "model_fk": "Opcional. Modelo, línea o formato frecuente; si no aparece, elige Otro.",
            "condition": "Nuevo, usado o reacondicionado.",
            "material": "Opcional. Ej.: madera, melamina, metal.",
            "dimensions": "Opcional. Ej.: 180×90 cm.",
        }
        error_messages = {
            "item_type": {
                "required": _MSG_REQUIRED,
                "invalid_choice": "Elegí una opción válida.",
            },
            "condition": {
                "required": _MSG_REQUIRED,
                "invalid_choice": "Elegí una opción válida.",
            },
            "material": {
                "max_length": "El material no puede superar %(limit_value)d caracteres.",
            },
            "dimensions": {
                "max_length": "Las dimensiones no pueden superar %(limit_value)d caracteres.",
            },
        }
        widgets = {
            "item_type": forms.Select(attrs={"class": "form-control"}),
            "condition": forms.Select(attrs={"class": "form-control"}),
            "material": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "maxlength": 120,
                    "placeholder": "Ej.: melamina",
                    "autocomplete": "off",
                }
            ),
            "dimensions": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "maxlength": 120,
                    "placeholder": "Ej.: 200×100 cm",
                    "autocomplete": "off",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_item_type = ""
        brand_id = None
        if self.is_bound:
            current_item_type = (self.data.get("item_type") or "").strip()
            raw = self.data.get("brand_fk")
            if raw:
                try:
                    brand_id = int(raw)
                except (TypeError, ValueError):
                    brand_id = None
        elif self.instance.pk:
            current_item_type = (self.instance.item_type or "").strip()
            brand_id = self.instance.brand_fk_id

        self.fields["brand_fk"].queryset = (
            market_brand_queryset(
                HOMEGOODS_SLUG,
                item_type=current_item_type,
            )
            if current_item_type
            else MarketBrand.objects.none()
        )
        if not current_item_type:
            self.fields["brand_fk"].empty_label = (
                "Primero selecciona el tipo de artículo"
            )
        if brand_id:
            self.fields["model_fk"].queryset = market_model_queryset(
                HOMEGOODS_SLUG,
                brand_id,
                item_type=current_item_type,
            )
            self.fields["model_fk"].widget.attrs.pop("disabled", None)
        else:
            self.fields["model_fk"].empty_label = "Primero selecciona una marca"
            self.fields["model_fk"].widget.attrs["disabled"] = "disabled"
        self.fields["item_type"].choices = _with_empty_choice(
            "Selecciona el tipo de artículo",
            HomeItemType.choices,
        )
        self.fields["condition"].choices = _with_empty_choice(
            "Selecciona la condición",
            ItemCondition.choices,
        )
        self.fields["item_type"].widget.attrs.update(
            {
                "hx-get": "/api/home-brands/",
                "hx-target": "#id_brand_fk",
                "hx-swap": "innerHTML",
                "hx-trigger": "change",
                "hx-sync": "closest form:replace",
            }
        )

    def clean(self):
        cleaned = super().clean()
        item_type = (cleaned.get("item_type") or "").strip()
        brand = cleaned.get("brand_fk")
        model = cleaned.get("model_fk")
        if model and not brand:
            self.add_error("brand_fk", "Selecciona una marca.")
        elif brand and model and not market_model_belongs_to_brand(
            HOMEGOODS_SLUG,
            brand,
            model,
            item_type=item_type,
        ):
            self.add_error("model_fk", "El modelo seleccionado no pertenece a la marca.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class ListingReportForm(forms.ModelForm):
    class Meta:
        model = ListingReport
        fields = ["reason"]
        labels = {
            "reason": "Motivo del reporte",
        }
        widgets = {
            "reason": forms.Select(attrs={"class": "form-control"}),
        }
