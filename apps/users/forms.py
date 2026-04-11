import re

from django import forms
from django.utils.safestring import mark_safe
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth.forms import UserChangeForm as DjangoUserChangeForm
from django.contrib.auth.forms import UserCreationForm as DjangoUserCreationForm
from django.contrib.auth import get_user_model
from django.contrib.auth import password_validation

from .models import User


class EmailAuthenticationForm(AuthenticationForm):
    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].label = "Correo electrónico"
        self.fields["username"].widget = forms.EmailInput(
            attrs={"class": "form-control", "autocomplete": "email", "autofocus": True}
        )
        self.fields["password"].widget.attrs.setdefault("class", "form-control")
        self.fields["password"].widget.attrs.setdefault(
            "autocomplete", "current-password"
        )


class UserCreationForm(DjangoUserCreationForm):
    phone_country_code = forms.CharField(
        label="Teléfono",
        max_length=8,
        required=True,
        initial="+593",
        widget=forms.HiddenInput(),
    )
    phone_number = forms.CharField(
        label="",
        max_length=32,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "tel-national",
                "inputmode": "numeric",
                "placeholder": "987654321",
            }
        ),
    )

    accept_terms = forms.BooleanField(
        required=True,
        label=mark_safe(
            'He leído y acepto los <a href="/terminos/" target="_blank" rel="noopener">Términos &amp; Condiciones</a>.'
        ),
        error_messages={
            "required": "Debes aceptar los Términos & Condiciones para continuar.",
        },
    )

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")
        labels = {
            "email": "Correo electrónico",
            "first_name": "Nombre",
            "last_name": "Apellido",
        }
        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "email",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "given-name",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "family-name",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("password1", "password2"):
            self.fields[name].widget.attrs.setdefault("class", "form-control")
            self.fields[name].widget.attrs.setdefault("autocomplete", "new-password")

        # Spanish labels + compact, friendly help text (avoid long default bullet list).
        self.fields["password1"].label = "Contraseña"
        self.fields["password2"].label = "Confirmar contraseña"
        self.fields["password1"].help_text = "Mínimo 8 caracteres."
        self.fields["password2"].help_text = "Repite tu contraseña para confirmar."

        # Put phone right before password, checkbox at the end.
        self.order_fields(
            [
                "email",
                "first_name",
                "last_name",
                "phone_country_code",
                "phone_number",
                "password1",
                "password2",
                "accept_terms",
            ]
        )

    def clean_phone_country_code(self):
        raw = (self.cleaned_data.get("phone_country_code") or "").strip()
        if not raw.startswith("+"):
            raise forms.ValidationError("Selecciona un código de país válido.")
        digits = re.sub(r"\D", "", raw)
        if not digits:
            raise forms.ValidationError("Selecciona un código de país válido.")
        code = f"+{digits}"
        if len(code) > 8:
            raise forms.ValidationError("Selecciona un código de país válido.")
        return code

    def clean_phone_number(self):
        raw = (self.cleaned_data.get("phone_number") or "").strip()
        digits = re.sub(r"\D", "", raw)
        if not digits.isdigit():
            raise forms.ValidationError("Introduce solo números en el teléfono.")
        if not (7 <= len(digits) <= 15):
            raise forms.ValidationError("Introduce un teléfono válido (7 a 15 dígitos).")
        return digits


class RegisterStepOneForm(forms.Form):
    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(
            attrs={"class": "form-control", "autocomplete": "email", "autofocus": True}
        ),
    )
    first_name = forms.CharField(
        label="Nombre",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        label="Apellido",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "family-name"}),
    )

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        UserModel = get_user_model()
        if UserModel.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con ese correo electrónico.")
        return email


class RegisterStepTwoForm(forms.Form):
    phone_country_code = forms.CharField(
        label="Teléfono",
        max_length=8,
        required=True,
        initial="+593",
        widget=forms.HiddenInput(),
    )
    phone_number = forms.CharField(
        label="",
        max_length=32,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "tel-national",
                "inputmode": "numeric",
                "placeholder": "987654321",
            }
        ),
    )
    password1 = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "autocomplete": "new-password"},
            render_value=False,
        ),
        help_text="Mínimo 8 caracteres.",
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "autocomplete": "new-password"},
            render_value=False,
        ),
        help_text="Repite tu contraseña para confirmar.",
    )
    accept_terms = forms.BooleanField(
        required=True,
        label=mark_safe(
            'He leído y acepto los <a href="/terminos/" target="_blank" rel="noopener">Términos &amp; Condiciones</a>.'
        ),
        error_messages={
            "required": "Debes aceptar los Términos & Condiciones para continuar.",
        },
    )

    def clean_phone_country_code(self):
        raw = (self.cleaned_data.get("phone_country_code") or "").strip()
        if not raw.startswith("+"):
            raise forms.ValidationError("Selecciona un código de país válido.")
        digits = re.sub(r"\D", "", raw)
        if not digits:
            raise forms.ValidationError("Selecciona un código de país válido.")
        code = f"+{digits}"
        if len(code) > 8:
            raise forms.ValidationError("Selecciona un código de país válido.")
        return code

    def clean_phone_number(self):
        raw = (self.cleaned_data.get("phone_number") or "").strip()
        digits = re.sub(r"\D", "", raw)
        if not digits.isdigit():
            raise forms.ValidationError("Introduce solo números en el teléfono.")
        if not (7 <= len(digits) <= 15):
            raise forms.ValidationError("Introduce un teléfono válido (7 a 15 dígitos).")
        return digits

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1") or ""
        p2 = cleaned.get("password2") or ""
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
            return cleaned
        if p1:
            password_validation.validate_password(p1)
        return cleaned


class AccountPasswordChangeForm(DjangoPasswordChangeForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        for name in ("old_password", "new_password1", "new_password2"):
            self.fields[name].widget.attrs.setdefault("class", "form-control")
        self.fields["old_password"].label = "Contraseña actual"
        self.fields["old_password"].widget.attrs.setdefault("autocomplete", "current-password")
        self.fields["new_password1"].label = "Nueva contraseña"
        self.fields["new_password2"].label = "Confirmar nueva contraseña"
        self.fields["new_password1"].help_text = "Mínimo 8 caracteres."
        self.fields["new_password2"].help_text = ""
        self.fields["new_password1"].widget.attrs.setdefault("autocomplete", "new-password")
        self.fields["new_password2"].widget.attrs.setdefault("autocomplete", "new-password")


class UserChangeForm(DjangoUserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


class PhoneVerificationForm(forms.Form):
    """SMS simulado: teléfono y confirmación en un paso."""

    phone_number = forms.CharField(
        label="Número de móvil",
        max_length=32,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "+593 98 000 0000",
                "autocomplete": "tel",
            }
        ),
    )
    confirm_demo = forms.BooleanField(
        label="Recibí el código de verificación (simulado en la demo)",
        required=True,
        error_messages={
            "required": "Marca la casilla para simular una verificación SMS correcta.",
        },
    )

    def clean_phone_number(self):
        raw = (self.cleaned_data.get("phone_number") or "").strip()
        digits = re.sub(r"\D", "", raw)
        if len(digits) < 10:
            raise forms.ValidationError(
                "Introduce un teléfono válido (al menos 10 dígitos)."
            )
        return raw
