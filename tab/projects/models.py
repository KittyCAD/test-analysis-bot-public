from django.db import models


class Project(models.Model):
    repository = models.URLField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
        self.repository = self.repository.lower().removesuffix(".git")
