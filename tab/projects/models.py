from django.db import models

import log


class ProjectManager(models.Manager):

    @staticmethod
    def clean_repository(value: str):
        return value.lower().removesuffix(".git").strip("/")

    def from_repository(self, url: str):
        cleaned_url = url.lower().removesuffix(".git").strip("/")
        if "://" not in cleaned_url or cleaned_url.count("/") < 4:
            raise ValueError(f"Invalid repository URL: {cleaned_url}")
        project, created = self.get_or_create(repository=cleaned_url)
        if created:
            log.info(f"Created project: {project}")
        else:
            log.info(f"Found project: {project}")
        return project


class Project(models.Model):
    repository = models.URLField(unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects: ProjectManager = ProjectManager()

    def __str__(self):
        return self.path

    @property
    def path(self) -> str:
        self._update_repository()
        parts = self.repository.split("/")
        return " / ".join(parts[3:])

    def save(self, *args, **kwargs):
        self._update_repository()
        super().save(*args, **kwargs)

    def _update_repository(self):
        self.repository = ProjectManager.clean_repository(self.repository)


class Test(models.Model):
    name = models.CharField(max_length=1000)

    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    branch = models.CharField(max_length=100, default="")
    commit = models.CharField(max_length=100, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
