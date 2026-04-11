from django import forms


class WaitlistForm(forms.Form):
    """Captura mínima para pre-lanzamiento; persistencia se puede añadir después."""

    company_url = forms.CharField(
        required=False,
        label="",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "tabindex": "-1",
                "class": "visually-hidden",
                "aria-hidden": "true",
            }
        ),
    )

    email = forms.EmailField(
        label="Correo electrónico",
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "autocomplete": "email",
                "inputmode": "email",
                "placeholder": "tu@email.com",
            }
        ),
    )
    whatsapp = forms.CharField(
        label="WhatsApp (opcional)",
        required=False,
        max_length=40,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "tel",
                "placeholder": "Ej: +593 9 XXXX XXXX",
            }
        ),
    )

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()
