from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from accounts.roles import ensure_default_groups


class Command(BaseCommand):
    help = "Idempotently create and sync the default Admin and Analyst groups."

    def handle(self, *args, **options):
        try:
            results = ensure_default_groups()
        except (DatabaseError, LookupError) as error:
            raise CommandError(f"Group initialization failed: {error}") from error

        for item in results:
            state = "created" if item.created else "updated"
            self.stdout.write(
                f"group={item.name} state={state} permissions={item.permission_count}"
            )
