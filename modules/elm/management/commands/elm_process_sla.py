from django.core.management.base import BaseCommand

from modules.elm.services import sla


class Command(BaseCommand):
    help = "Send reminders and escalations for overdue ELM tasks"

    def handle(self, *args, **options):
        report = sla.process()
        self.stdout.write(f"{report.reminded} reminder(s), "
                          f"{report.escalated} escalation(s)")
