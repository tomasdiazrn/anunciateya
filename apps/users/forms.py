import re

from django import forms
from django.utils.safestring import mark_safe
from django.contrib.auth.forms import UserChangeForm as DjangoUserChangeForm
from django.contrib.auth import get_user_model

from .models import USER_EMAIL_MAX_LENGTH, USER_NAME_MAX_LENGTH, User


class UserCreationForm(forms.ModelForm):
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
                    "maxlength": USER_EMAIL_MAX_LENGTH,
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "given-name",
                    "maxlength": USER_NAME_MAX_LENGTH,
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "family-name",
                    "maxlength": USER_NAME_MAX_LENGTH,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(
            [
                "email",
                "first_name",
                "last_name",
                "phone_country_code",
                "phone_number",
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

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        UserModel = get_user_model()
        if UserModel.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con ese correo electrónico.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = (user.email or "").strip().lower()
        user.set_unusable_password()
        if commit:
            user.save()
        return user


class RegisterStepOneForm(forms.Form):
    email = forms.EmailField(
        label="Correo electrónico",
        max_length=USER_EMAIL_MAX_LENGTH,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "autocomplete": "email",
                "autofocus": True,
                "maxlength": USER_EMAIL_MAX_LENGTH,
            }
        ),
    )
    first_name = forms.CharField(
        label="Nombre",
        max_length=USER_NAME_MAX_LENGTH,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "given-name",
                "maxlength": USER_NAME_MAX_LENGTH,
            }
        ),
    )
    last_name = forms.CharField(
        label="Apellido",
        max_length=USER_NAME_MAX_LENGTH,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "family-name",
                "maxlength": USER_NAME_MAX_LENGTH,
            }
        ),
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
    accept_terms = forms.BooleanField(
        required=True,
        label=mark_safe(
            'He leído y acepto los <a href="/terminos/" target="_blank" rel="noopener">Términos &amp; Condiciones</a>.'
        ),
        error_messages={
            "required": "Debes aceptar los Términos & Condiciones para continuar.",
        },
    )

    def __init__(self, *args, profile=None, **kwargs):
        self._profile = profile or {}
        super().__init__(*args, **kwargs)

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
