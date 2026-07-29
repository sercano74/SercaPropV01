"""
Adapter personalizado de django-allauth para SercaProp.

Maneja la creación de usuarios con campos extra (dni, cel_phone, first_name, last_name)
y asigna rol='base' por defecto. También sincroniza email_confirmado con el modelo
allauth EmailAddress.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.utils import user_email
from allauth.core.exceptions import ImmediateHttpResponse
from django.shortcuts import redirect
from django.contrib import messages

User = get_user_model()


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Adapter para el registro por formulario (email + password).
    Puebla first_name, last_name, dni, cel_phone del POST.
    """

    def save_user(self, request, user, form, commit=True):
        """
        Guarda el usuario con campos extra del formulario de signup.
        """
        user = super().save_user(request, user, form, commit=False)

        # Asignar rol base por defecto
        if not user.rol or user.rol == '':
            user.rol = 'base'

        # Campos extra del formulario
        data = form.cleaned_data
        user.first_name = data.get('first_name', '')
        user.last_name = data.get('last_name', '')
        user.dni = data.get('dni', '') or None
        user.cel_phone = data.get('cel_phone', '') or ''

        if commit:
            user.save()
        return user

    def respond_user_inactive(self, request, user):
        """
        Si el usuario está inactivo (is_active=False), redirige al login con mensaje.
        """
        messages.error(
            request,
            "Tu cuenta está desactivada. Contacta al administrador."
        )
        return redirect('account_login')

    def get_email_confirmation_url(self, request, emailconfirmation):
        """
        Retorna la URL de confirmación de email.
        """
        url = super().get_email_confirmation_url(request, emailconfirmation)
        return url

    def pre_login(self, request, user, *, email_verification, signal_kwargs, email):
        """
        Antes del login, asegura que exista un EmailAddress para usuarios existentes
        que no tienen registro en allauth (migración desde sistema anterior).
        Si el usuario tiene email_confirmado=True, lo marca como verificado.
        """
        from allauth.account.models import EmailAddress
        if user.email:
            email_obj, created = EmailAddress.objects.get_or_create(
                user=user,
                email=user.email,
                defaults={
                    'verified': user.email_confirmado,
                    'primary': True,
                }
            )
            if not created and not email_obj.verified and user.email_confirmado:
                email_obj.verified = True
                email_obj.save()
        return super().pre_login(
            request, user,
            email_verification=email_verification,
            signal_kwargs=signal_kwargs,
            email=email
        )


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Adapter para registro/login via redes sociales.

    - Si el usuario ya existe con ese email, vincula la cuenta social.
    - Si es nuevo, crea el usuario con rol='base' y datos del provider.
    """

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        user.rol = 'base'
        return user

    def pre_social_login(self, request, sociallogin):
        """
        Antes del login social. Si ya existe un usuario con ese email,
        conectamos la cuenta social automáticamente.
        """
        email = user_email(sociallogin.user)
        if email:
            try:
                existing_user = User.objects.get(email=email)
                # Conectar la cuenta social al usuario existente
                sociallogin.connect(request, existing_user)
                # Mensaje de feedback
                messages.info(
                    request,
                    f"Se ha vinculado tu cuenta de {sociallogin.account.provider} "
                    f"con tu usuario existente ({email})."
                )
                raise ImmediateHttpResponse(redirect(settings.LOGIN_REDIRECT_URL))
            except User.DoesNotExist:
                pass
        return super().pre_social_login(request, sociallogin)

    def save_user(self, request, sociallogin, form=None):
        """
        Después de crear el usuario vía social, aseguramos rol='base'.
        """
        user = super().save_user(request, sociallogin, form=form)
        if not user.rol or user.rol == '':
            user.rol = 'base'
            user.save(update_fields=['rol'])
        return user
