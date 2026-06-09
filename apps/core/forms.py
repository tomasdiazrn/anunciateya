from django import forms


class NewsletterSignupForm(forms.Form):
    email = forms.EmailField(
        label="Correo electrónico",
        max_length=254,
        error_messages={
            "required": "Ingresá tu email para suscribirte.",
            "invalid": "Ingresá un email válido.",
        },
        widget=forms.EmailInput(
            attrs={
                "class": "newsletter-bar__input",
                "autocomplete": "email",
                "placeholder": "Ingresá tu email...",
            }
        ),
    )

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()
