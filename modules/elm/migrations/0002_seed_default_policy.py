"""Starting leave policy (problem statement section 3) and SLA thresholds.

Values are copied rather than imported: a migration must keep meaning what it
meant when it was written, however the code moves on.
"""
from django.db import migrations

POLICIES = [
    # category, annual days, applies_to, carry_forward, requires_substitute
    ("CL", "8", "all", False, False),
    ("RH", "2", "all", False, False),
    ("SCL", "15", "all", False, False),
    ("EL", "30", "non_faculty", True, True),
    ("COL", "20", "all", True, True),
    ("VL", "60", "faculty", False, True),
]


def seed(apps, schema_editor):
    Policy = apps.get_model("elm", "LeavePolicy")
    Sla = apps.get_model("elm", "SlaSetting")
    for category, days, applies_to, carry, substitute in POLICIES:
        Policy.objects.get_or_create(category=category, defaults={
            "annual_days": days, "applies_to": applies_to,
            "carry_forward": carry, "requires_substitute": substitute})
    if not Sla.objects.exists():
        Sla.objects.create()


def unseed(apps, schema_editor):
    apps.get_model("elm", "LeavePolicy").objects.all().delete()
    apps.get_model("elm", "SlaSetting").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("elm", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
