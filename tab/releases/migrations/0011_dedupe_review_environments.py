from django.db import migrations, models
from django.db.models import Count


def _merge_releases(Release, keeper, duplicate):
    for release in Release.objects.filter(environment=duplicate):
        existing = Release.objects.filter(
            environment=keeper, commit=release.commit
        ).first()
        if existing:
            existing.results = max(existing.results, release.results)
            if release.tested_at and (
                not existing.tested_at or release.tested_at > existing.tested_at
            ):
                existing.tested_at = release.tested_at
            if release.finalized_at and (
                not existing.finalized_at
                or release.finalized_at > existing.finalized_at
            ):
                existing.finalized_at = release.finalized_at
            if not existing.branch and release.branch:
                existing.branch = release.branch
            existing.save()
            existing.dependencies.add(*release.dependencies.all())
            release.delete()
        else:
            release.environment = keeper
            release.save(update_fields=["environment"])


def _merge_environment(Environment, Release, keeper, duplicate):
    _merge_releases(Release, keeper, duplicate)

    keeper.dependencies.add(*duplicate.dependencies.all())

    for dependent in Environment.objects.filter(dependencies=duplicate):
        dependent.dependencies.remove(duplicate)
        dependent.dependencies.add(keeper)

    duplicate.dependencies.clear()


def dedupe_review_environments(apps, schema_editor):
    Environment = apps.get_model("releases", "Environment")
    Release = apps.get_model("releases", "Release")

    duplicates = (
        Environment.objects.filter(url__isnull=False)
        .values("project", "url", "name")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
    )

    deleted_count = 0
    for dup in duplicates:
        environments = Environment.objects.filter(
            project=dup["project"],
            url=dup["url"],
            name=dup["name"],
        ).order_by("created_at", "id")

        keeper = environments.first()
        for duplicate in environments.exclude(id=keeper.id):
            _merge_environment(Environment, Release, keeper, duplicate)
            duplicate.delete()
            deleted_count += 1

    if deleted_count:
        print(f"Removed {deleted_count} duplicate environments")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("releases", "0010_alter_environment_options"),
    ]

    operations = [
        migrations.RunPython(dedupe_review_environments, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="environment",
            constraint=models.UniqueConstraint(
                condition=models.Q(("url__isnull", False)),
                fields=("project", "url", "name"),
                name="unique_environment_project_url_name",
            ),
        ),
    ]
