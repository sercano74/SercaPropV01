"""
Management command to migrate existing users to allauth EmailAddress table.
Run: python manage.py migrate_allauth_emails

Creates EmailAddress records for all existing users based on their
email_confirmado field.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress

User = get_user_model()


class Command(BaseCommand):
    help = 'Migra usuarios existentes a la tabla EmailAddress de django-allauth'

    def handle(self, *args, **options):
        users = User.objects.all()
        count = 0
        created_count = 0
        updated_count = 0

        for user in users:
            email = user.email
            if not email:
                self.stdout.write(self.style.WARNING(
                    f"  Saltando {user.username}: sin email"
                ))
                continue

            email_obj, created = EmailAddress.objects.get_or_create(
                user=user,
                email=email,
                defaults={
                    'verified': user.email_confirmado,
                    'primary': True,
                }
            )

            if created:
                created_count += 1
            else:
                if email_obj.verified != user.email_confirmado:
                    email_obj.verified = user.email_confirmado
                    email_obj.save()
                    updated_count += 1

            status = '✅ verificado' if user.email_confirmado else '⏳ pendiente'
            self.stdout.write(f"  {status}: {user.username} <{email}>")
            count += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ {count} usuarios procesados "
            f"({created_count} creados, {updated_count} actualizados)"
        ))
