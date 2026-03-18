from django.core.management.base import BaseCommand

from student.services.chat_memory import cleanup_expired_sessions


class Command(BaseCommand):
    help = "Deactivate or delete expired chat sessions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete expired sessions instead of marking them inactive.",
        )

    def handle(self, *args, **options):
        cleaned = cleanup_expired_sessions(delete=options["delete"])
        mode = "deleted" if options["delete"] else "deactivated"
        self.stdout.write(self.style.SUCCESS(f"{cleaned} expired chat sessions {mode}."))
