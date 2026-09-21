import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0071_alter_test_maintainer_help"),
    ]

    operations = [
        migrations.CreateModel(
            name="CommitStatusOwner",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("commit", models.CharField(max_length=100)),
                ("branch", models.CharField(max_length=500)),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commit_status_owners",
                        to="projects.project",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="commitstatusowner",
            constraint=models.UniqueConstraint(
                fields=("project", "commit"), name="unique_commit_status_owner"
            ),
        ),
    ]
