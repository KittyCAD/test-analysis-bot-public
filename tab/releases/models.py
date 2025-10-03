from django.db import models

from tab.projects.models import Project

from .enums import Type


class Environment(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="environments"
    )
    url = models.URLField()
    name = models.CharField(max_length=100, choices=Type.choices)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = [["project", "url"]]

    def __str__(self):
        return f"{self.get_name_display()}: {self.url}"
