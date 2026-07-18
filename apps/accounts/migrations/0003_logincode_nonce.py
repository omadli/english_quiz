import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _clear_login_codes(apps, schema_editor):
    # LoginCode rows are short-lived (10-min) login attempts; the flow changed to
    # nonce-keyed, so any in-flight rows are meaningless. Drop them rather than
    # backfill a unique nonce.
    apps.get_model("accounts", "LoginCode").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_logincode"),
    ]

    operations = [
        migrations.RunPython(_clear_login_codes, migrations.RunPython.noop),
        migrations.AddField(
            model_name="logincode",
            name="nonce",
            field=models.CharField(default="", max_length=48),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="logincode",
            name="nonce",
            field=models.CharField(max_length=48, unique=True),
        ),
        migrations.AlterField(
            model_name="logincode",
            name="code",
            field=models.CharField(blank=True, max_length=6),
        ),
        migrations.AlterField(
            model_name="logincode",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="login_codes",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
