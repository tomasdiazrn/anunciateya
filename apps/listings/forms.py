from datetime import date

from django import forms

from apps.trust.models import ListingReport

from .models import (
    ElectronicsListing,
    HomeGoodsListing,
    Listing,
    MotorcycleListing,
    PropertyListing,
    VehicleBrand,
    VehicleListing,
    VehicleModel,
)


class ListingInterestForm(forms.Form):
    """Mensaje validado en servidor cuando un comprador contacta (parcial HTMX)."""

    message = forms.CharField(
        label="Mensaje al vendedor",
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
        max_length=2000,
    )


class BaseListingForm(forms.ModelForm):
    """Campos comunes del anuncio (sin categoría; la fija la URL o la vista)."""

    publish_state = forms.ChoiceField(
        label="Publicación",
        choices=[
            (Listing.Status.PUBLISHED, "Publicar"),
            (Listing.Status.DRAFT, "Guardar como borrador"),
        ],
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Listing
        fields = [
            "title",
            "description",
            "price_amount",
            "currency",
            "location",
        ]
        labels = {
            "title": "Título",
            "description": "Descripción",
            "price_amount": "Precio",
            "currency": "Moneda",
            "location": "Ubicación",
        }
        help_texts = {
            "title": "",
            "description": "Describe el artículo, defectos, entrega o retiro.",
            "price_amount": "",
            "location": "Ciudad, sector o punto de encuentro (obligatorio).",
        }
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "maxlength": 200,
                    "autocomplete": "off",
                    "placeholder": (
                        "Toyota Corolla 2018 automático, excelente estado"
                    ),
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": (
                        "Estado, accesorios, motivo de venta, forma de pago…"
                    ),
                }
            ),
            "price_amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0.01",
                    "placeholder": "18500",
                    "inputmode": "decimal",
                }
            ),
            "location": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Urdesa, Guayaquil",
                    "maxlength": 200,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["currency"].widget = forms.HiddenInput()
        self.fields["currency"].required = False
        if not self.instance.pk:
            self.fields["currency"].initial = "USD"
            self.fields["publish_state"].initial = Listing.Status.PUBLISHED
        else:
            self.fields["publish_state"].initial = (
                self.instance.status or Listing.Status.DRAFT
            )

    def clean_price_amount(self):
        value = self.cleaned_data["price_amount"]
        if value is not None and value <= 0:
            raise forms.ValidationError("Ingresa un precio mayor que cero.")
        return value

    def clean_location(self):
        loc = (self.cleaned_data.get("location") or "").strip()
        if not loc:
            raise forms.ValidationError("La ubicación es obligatoria.")
        return loc


class ListingForm(BaseListingForm):
    """Crear o editar anuncio con selector de categoría (flujo genérico / edición mixta)."""

    class Meta(BaseListingForm.Meta):
        fields = [
            "title",
            "description",
            "price_amount",
            "currency",
            "category",
            "location",
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
            "category": {"required": "Elige una categoría."},
        }
        widgets = {
            **BaseListingForm.Meta.widgets,
            "category": forms.Select(attrs={"class": "form-control"}),
        }


class VehicleListingForm(forms.ModelForm):
    brand_fk = forms.ModelChoiceField(
        label="Marca",
        queryset=VehicleBrand.objects.all().order_by("name"),
        required=False,
        empty_label="Selecciona marca",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "hx-get": "/api/vehicle-models/",
                "hx-target": "#id_model_fk",
                "hx-swap": "innerHTML",
                "hx-trigger": "change",
            }
        ),
    )
    model_fk = forms.ModelChoiceField(
        label="Modelo",
        queryset=VehicleModel.objects.none(),
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
        widgets = {
            "year": forms.NumberInput(
                attrs={
                    "class": "form-control vehicle-input-year",
                    "min": "1980",
                    "max": "2100",
                    "step": "1",
                    "placeholder": "2018",
                }
            ),
            "mileage": forms.NumberInput(
                attrs={
                    "class": "form-control vehicle-input-mileage",
                    "min": "0",
                    "max": "9999999",
                    "step": "1",
                    "inputmode": "numeric",
                    "placeholder": "85000",
                }
            ),
            "doors": forms.NumberInput(
                attrs={
                    "class": "form-control vehicle-input-doors",
                    "min": "2",
                    "max": "9",
                    "step": "1",
                    "placeholder": "4",
                }
            ),
            "transmission": forms.Select(attrs={"class": "form-control"}),
            "fuel_type": forms.Select(
                attrs={"class": "form-control vehicle-select-fuel"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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
                VehicleModel.objects.filter(brand_id=brand_id)
                .order_by("name")
            )
            self.fields["model_fk"].widget.attrs.pop("disabled", None)
        else:
            self.fields["model_fk"].queryset = VehicleModel.objects.none()
            # UX: no se puede escoger modelo sin marca.
            self.fields["model_fk"].widget.attrs["disabled"] = "disabled"

    def clean_year(self):
        y = self.cleaned_data["year"]
        current = date.today().year
        if y < 1980 or y > current + 1:
            raise forms.ValidationError(
                f"Ingresa un año entre 1980 y {current + 1}."
            )
        return y

    def clean_mileage(self):
        v = self.cleaned_data.get("mileage")
        if v is not None and v < 0:
            raise forms.ValidationError("El kilometraje debe ser 0 o mayor.")
        return v

    def clean_doors(self):
        d = self.cleaned_data["doors"]
        if d < 2 or d > 9:
            raise forms.ValidationError("Indica un número de puertas entre 2 y 9.")
        return d

    def clean(self):
        cleaned = super().clean()
        b = cleaned.get("brand_fk")
        m = cleaned.get("model_fk")
        if b and m and m.brand_id != b.id:
            self.add_error("model_fk", "El modelo seleccionado no pertenece a la marca.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        if obj.brand_fk_id:
            obj.brand = obj.brand_fk.name
        if obj.model_fk_id:
            obj.model = obj.model_fk.name
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
        }
        help_texts = {name: "" for name in fields}
        widgets = {
            "property_type": forms.Select(attrs={"class": "form-control"}),
            "operation_type": forms.Select(attrs={"class": "form-control"}),
            "rooms": forms.NumberInput(
                attrs={
                    "class": "form-control property-input-compact",
                    "min": "1",
                    "max": "99",
                    "step": "1",
                    "placeholder": "3",
                    "inputmode": "numeric",
                }
            ),
            "bathrooms": forms.NumberInput(
                attrs={
                    "class": "form-control property-input-compact",
                    "min": "1",
                    "max": "99",
                    "step": "1",
                    "placeholder": "2",
                    "inputmode": "numeric",
                }
            ),
            "area_m2": forms.NumberInput(
                attrs={
                    "class": "form-control property-input-compact",
                    "min": "1",
                    "max": "999999",
                    "step": "1",
                    "placeholder": "120",
                    "inputmode": "numeric",
                }
            ),
            "parking_spaces": forms.NumberInput(
                attrs={
                    "class": "form-control property-input-compact",
                    "min": "0",
                    "max": "99",
                    "step": "1",
                    "placeholder": "1",
                    "inputmode": "numeric",
                }
            ),
            "furnished": forms.CheckboxInput(
                attrs={"class": "checkbox-input"}
            ),
            "property_condition": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        op = self.fields["operation_type"]
        op.required = False
        op.choices = [("", "—")] + list(PropertyListing.OperationType.choices)
        cond = self.fields["property_condition"]
        cond.required = False
        cond.choices = [("", "—")] + list(
            PropertyListing.PropertyConditionChoice.choices
        )
        self.fields["parking_spaces"].required = False

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
        v = self.cleaned_data.get("parking_spaces")
        if v in (None, ""):
            return None
        return v

    def clean_rooms(self):
        v = self.cleaned_data["rooms"]
        if v < 1:
            raise forms.ValidationError("Indica al menos 1 habitación.")
        return v

    def clean_bathrooms(self):
        v = self.cleaned_data["bathrooms"]
        if v < 1:
            raise forms.ValidationError("Indica al menos 1 baño.")
        return v

    def clean_area_m2(self):
        v = self.cleaned_data["area_m2"]
        if v < 1:
            raise forms.ValidationError("La superficie debe ser mayor que cero.")
        return v


class MotorcycleListingForm(forms.ModelForm):
    class Meta:
        model = MotorcycleListing
        fields = [
            "brand",
            "model",
            "year",
            "engine_cc",
            "mileage",
            "transmission",
            "fuel_type",
            "condition",
        ]
        labels = {
            "brand": "Marca",
            "model": "Modelo",
            "year": "Año",
            "engine_cc": "Cilindrada (cc)",
            "mileage": "Kilometraje",
            "transmission": "Transmisión",
            "fuel_type": "Combustible",
            "condition": "Condición",
        }
        help_texts = {name: "" for name in fields}
        widgets = {
            "brand": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "maxlength": 80,
                    "placeholder": "Honda",
                    "autocomplete": "off",
                }
            ),
            "model": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "maxlength": 80,
                    "placeholder": "CBR 250",
                    "autocomplete": "off",
                }
            ),
            "year": forms.NumberInput(
                attrs={
                    "class": "form-control motorcycle-input-year",
                    "min": "1980",
                    "max": "2100",
                    "step": "1",
                    "placeholder": "2018",
                    "inputmode": "numeric",
                }
            ),
            "engine_cc": forms.NumberInput(
                attrs={
                    "class": "form-control motorcycle-input-compact",
                    "min": "50",
                    "max": "9999",
                    "step": "1",
                    "placeholder": "250",
                    "inputmode": "numeric",
                }
            ),
            "mileage": forms.NumberInput(
                attrs={
                    "class": "form-control motorcycle-input-mileage",
                    "min": "0",
                    "max": "9999999",
                    "step": "1",
                    "placeholder": "12000",
                    "inputmode": "numeric",
                }
            ),
            "transmission": forms.Select(attrs={"class": "form-control"}),
            "fuel_type": forms.Select(attrs={"class": "form-control"}),
            "condition": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and not self.is_bound:
            self.fields["transmission"].initial = (
                MotorcycleListing.Transmission.MANUAL
            )
            self.fields["fuel_type"].initial = MotorcycleListing.FuelType.GASOLINA
        self.fields["mileage"].required = False
        self.fields["engine_cc"].required = False

    def clean_year(self):
        y = self.cleaned_data["year"]
        current = date.today().year
        if y < 1980 or y > current + 1:
            raise forms.ValidationError(
                f"Ingresa un año entre 1980 y {current + 1}."
            )
        return y

    def clean_engine_cc(self):
        v = self.cleaned_data.get("engine_cc")
        if v is not None and v < 50:
            raise forms.ValidationError(
                "Si indicás cilindrada, debe ser al menos 50 cc."
            )
        return v

    def clean_mileage(self):
        v = self.cleaned_data.get("mileage")
        if v is not None and v < 0:
            raise forms.ValidationError("El kilometraje no puede ser negativo.")
        return v


class ElectronicsListingForm(forms.ModelForm):
    class Meta:
        model = ElectronicsListing
        fields = ["brand", "model", "condition", "warranty", "warranty_months"]
        labels = {
            "brand": "Marca",
            "model": "Modelo",
            "condition": "Condición",
            "warranty": "Tiene garantía vigente",
            "warranty_months": "Meses de garantía",
        }
        help_texts = {
            "brand": "Ej.: Samsung, Apple, Dell.",
            "model": "Referencia o nombre comercial.",
            "condition": "Nuevo, usado o reacondicionado.",
            "warranty": "Marcá solo si aplica garantía del fabricante o tienda.",
            "warranty_months": "Opcional. Si aplica, indicá la duración aproximada.",
        }
        widgets = {
            "brand": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "maxlength": 80,
                    "placeholder": "Ej.: Samsung",
                    "autocomplete": "off",
                }
            ),
            "model": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "maxlength": 120,
                    "placeholder": "Ej.: Galaxy A54",
                    "autocomplete": "off",
                }
            ),
            "condition": forms.Select(attrs={"class": "form-control"}),
            "warranty": forms.CheckboxInput(attrs={"class": "checkbox-input"}),
            "warranty_months": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                    "max": 120,
                    "placeholder": "Ej. 12",
                }
            ),
        }

    def clean_warranty_months(self):
        v = self.cleaned_data.get("warranty_months")
        if v is not None and (v < 1 or v > 120):
            raise forms.ValidationError("Indicá entre 1 y 120 meses, o dejá el campo vacío.")
        return v


class HomeGoodsListingForm(forms.ModelForm):
    class Meta:
        model = HomeGoodsListing
        fields = ["item_type", "brand", "condition", "material", "dimensions"]
        labels = {
            "item_type": "Tipo de artículo",
            "brand": "Marca",
            "condition": "Condición",
            "material": "Material",
            "dimensions": "Dimensiones aprox.",
        }
        help_texts = {
            "item_type": "Muebles, cocina o decoración.",
            "brand": "Opcional. Ej.: IKEA, local.",
            "condition": "Nuevo, usado o reacondicionado.",
            "material": "Opcional. Ej.: madera, melamina, metal.",
            "dimensions": "Opcional. Ej.: 180×90 cm.",
        }
        widgets = {
            "item_type": forms.Select(attrs={"class": "form-control"}),
            "brand": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "maxlength": 80,
                    "placeholder": "Ej.: IKEA",
                    "autocomplete": "off",
                }
            ),
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
