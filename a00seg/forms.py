"""
Formularios personalizados para SercaProp.

- CustomSignupForm: agrega first_name, last_name, dni, cel_phone al registro de allauth.
"""
from django import forms
from allauth.account.forms import SignupForm


class CustomSignupForm(SignupForm):
    """Formulario de registro con campos extra para SercaProp."""

    first_name = forms.CharField(
        label='Nombres',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Juan', 'class': 'form-control'}),
    )
    last_name = forms.CharField(
        label='Apellidos',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Pérez', 'class': 'form-control'}),
    )
    dni = forms.CharField(
        label='RUT / DNI',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': '12.345.678-9', 'class': 'form-control'}),
    )
    cel_phone = forms.CharField(
        label='Teléfono',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': '+56 9 1234 5678', 'class': 'form-control'}),
    )

    def clean_dni(self):
        dni = self.cleaned_data.get('dni', '').strip()
        if dni:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if User.objects.filter(dni=dni).exists():
                raise forms.ValidationError("Este RUT/DNI ya está registrado.")
        return dni or None

    def clean_email(self):
        email = super().clean_email()
        if email:
            email = email.strip().lower()
        return email

    def save(self, request):
        # Delegar todo al adapter (allauth_adapters.py) que ya maneja
        # los campos extra correctamente. No hacemos doble save.
        user = super().save(request)
        return user
