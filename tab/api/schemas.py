from django.conf import settings

import log
from ninja import ModelSchema, Schema
from ninja.security import APIKeyHeader

from tab.core.models import Organization
from tab.projects.constants import DEFAULT_SUITE
from tab.projects.models import Result


class ApiKey(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        if hasattr(settings, "TEST"):
            log.warning("Bypassing authentication for tests")
            return True
        return Organization.objects.filter(key=key).exists()


class ResultRequest(ModelSchema):
    project: str
    test: str
    suite: str = DEFAULT_SUITE

    class Config:
        model = Result
        model_fields = [
            "branch",
            "commit",
            "status",
            "duration",
            "message",
            "target",
            "platform",
        ]

    @classmethod
    def get_metadata(cls, request_body: dict) -> dict:
        return {k: v for k, v in request_body.items() if k not in cls.model_fields}

    def get_model_fields(self) -> dict:
        return {
            field: getattr(self, field)
            for field in self.__class__.model_fields
            if field not in ["project", "suite", "test"]
        }


class BulkResultRequest(Schema):
    project: str
    suite: str = DEFAULT_SUITE
    branch: str
    commit: str

    class Config:
        model_fields = [
            "project",
            "branch",
            "commit",
            "tests",
        ]

    @classmethod
    def get_metadata(cls, request_body: dict) -> dict:
        return {
            k: v for k, v in request_body.items() if k not in cls.Config.model_fields
        }

    def get_model_fields(self) -> dict:
        return {
            field: getattr(self, field)
            for field in self.__class__.Config.model_fields
            if field not in ["project", "suite", "tests"]
        }


class BulkResultResponse(Schema):
    project: str
    branch: str
    commit: str
    tests: int


class ResultResponse(Schema):
    project: str
    test: str
    status: str
    block: bool


class ShareRequest(Schema):
    project: str
    branch: str
    commit: str


class ShareResponse(Schema):
    project: str
    branch: str
    commit: str
    tests: int


class ErrorResponse(Schema):
    detail: str
