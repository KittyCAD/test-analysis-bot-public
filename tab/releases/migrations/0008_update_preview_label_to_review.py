# Generated manually to migrate data

from django.db import migrations, models


def update_preview_to_review(apps, schema_editor):
    """
    Update the enum constant from PREVIEW to REVIEW, value from "preview" to "review",
    and label from "Preview" to "Review".

    This updates all Environment records that have name="preview" to name="review".
    """
    Environment = apps.get_model("releases", "Environment")
    Environment.objects.filter(name="preview").update(name="review")


def reverse_update_preview_to_review(apps, schema_editor):
    """
    Reverse migration - change "review" back to "preview".
    """
    Environment = apps.get_model("releases", "Environment")
    Environment.objects.filter(name="review").update(name="preview")


class Migration(migrations.Migration):

    dependencies = [
        ("releases", "0007_release_dependencies"),
    ]

    operations = [
        migrations.RunPython(
            update_preview_to_review,
            reverse_update_preview_to_review,
        ),
        migrations.AlterModelOptions(
            name="environment",
            options={
                "ordering": [
                    models.Case(
                        models.When(name="local", then=models.Value(1)),
                        models.When(name="review", then=models.Value(2)),
                        models.When(name="staging", then=models.Value(3)),
                        models.When(name="production", then=models.Value(4)),
                        output_field=models.IntegerField(),
                    ),
                    "project__repository",
                ]
            },
        ),
        migrations.AlterField(
            model_name="environment",
            name="name",
            field=models.CharField(
                choices=[
                    ("local", "Local"),
                    ("review", "Review"),
                    ("staging", "Staging"),
                    ("production", "Production"),
                ],
                max_length=100,
            ),
        ),
    ]
