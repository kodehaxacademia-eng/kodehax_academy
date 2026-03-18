from django.core.management.base import BaseCommand

from daily_challenges.services import assign_daily_challenges


class Command(BaseCommand):
    help = "Generate today's daily coding challenges for all active students."

    def handle(self, *args, **options):
        generated_sets = assign_daily_challenges()
        self.stdout.write(
            self.style.SUCCESS(
                f"Daily challenge generation completed for {len(generated_sets)} students."
            )
        )
