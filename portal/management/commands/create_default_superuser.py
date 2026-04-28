from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update default superuser admin"

    def handle(self, *args, **options):
        username = "admin"
        password = "adminBauRzHan_N77011"
        email = "admin@example.com"

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "full_name": "System Admin",
                "role": "admin",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
            self.stdout.write(
                self.style.SUCCESS("Superuser 'admin' created successfully.")
            )
            return

        changed = False
        if not user.is_staff:
            user.is_staff = True
            changed = True
        if not user.is_superuser:
            user.is_superuser = True
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if hasattr(user, "role") and user.role != "admin":
            user.role = "admin"
            changed = True
        if user.email != email:
            user.email = email
            changed = True
        if hasattr(user, "full_name") and not user.full_name:
            user.full_name = "System Admin"
            changed = True

        user.set_password(password)
        changed = True

        if changed:
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    "Superuser 'admin' already existed; credentials were updated."
                )
            )
        else:
            self.stdout.write(self.style.WARNING("Superuser 'admin' already exists."))
