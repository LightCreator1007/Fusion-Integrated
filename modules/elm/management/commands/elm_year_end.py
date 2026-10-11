from django.core.management.base import BaseCommand, CommandError

from modules.elm.services import yearend


class Command(BaseCommand):
    help = "Run ELM year-end processing for a leave year (idempotent)"

    def add_arguments(self, parser):
        parser.add_argument("year", type=int)

    def handle(self, *args, year, **options):
        report = yearend.run(year)
        self.stdout.write(f"{report.year}: {report.processed} account(s), "
                          f"{report.entries} entr(ies) posted")
        for line in report.exceptions:
            self.stderr.write(self.style.WARNING(f"  exception: {line}"))
        if report.exceptions:
            raise CommandError(f"{len(report.exceptions)} exception(s)")
