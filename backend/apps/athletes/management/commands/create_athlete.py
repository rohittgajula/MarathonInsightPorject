from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from apps.athletes.models import Athlete


class Command(BaseCommand):
    help = "Create a user + athlete profile and print an API token."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--password", required=True)
        parser.add_argument("--display-name", default=None)
        parser.add_argument("--timezone", default="UTC")
        parser.add_argument("--superuser", action="store_true")

    def handle(self, *args, **opts):
        from rest_framework.authtoken.models import Token

        username = opts["username"]
        user, created = User.objects.get_or_create(username=username)
        if created or opts["password"]:
            user.set_password(opts["password"])
        if opts["superuser"]:
            user.is_staff = user.is_superuser = True
        user.save()

        athlete, _ = Athlete.objects.get_or_create(
            user=user,
            defaults={
                "display_name": opts["display_name"] or username,
                "timezone": opts["timezone"],
            },
        )
        token, _ = Token.objects.get_or_create(user=user)

        self.stdout.write(self.style.SUCCESS(f"athlete id={athlete.pk} user={username}"))
        self.stdout.write(f"token={token.key}")
