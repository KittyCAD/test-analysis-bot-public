import django.db.models.deletion
from django.db import migrations, models


def backfill_result_project(apps, schema_editor):
    Result = apps.get_model("projects", "Result")
    # Copy project from the related test in one statement (Postgres).
    schema_editor.execute(f"""
        UPDATE {Result._meta.db_table} AS result
        SET project_id = test.project_id
        FROM {apps.get_model("projects", "Test")._meta.db_table} AS test
        WHERE result.test_id = test.id
          AND result.project_id IS NULL
        """)


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0073_longer_test_names_again"),
    ]

    operations = [
        migrations.AddField(
            model_name="result",
            name="project",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="results",
                to="projects.project",
            ),
        ),
        migrations.RunPython(backfill_result_project, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="result",
            name="project",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="results",
                to="projects.project",
            ),
        ),
        migrations.AddIndex(
            model_name="result",
            index=models.Index(
                fields=["project", "branch", "-created_at"],
                name="projects_re_project_c44002_idx",
            ),
        ),
    ]
