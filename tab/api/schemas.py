import log
from ninja import ModelSchema, Schema
from ninja.security import APIKeyHeader

from tab.projects.models import Result


class ApiKey(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        # TODO: Implement authentication
        log.info(f"Authenticating with API key: {key}")
        return True


class ResultRequest(ModelSchema):
    project: str
    test: str

    class Config:
        model = Result
        model_fields = ["branch", "commit", "status", "duration", "message"]

    @classmethod
    def get_metadata(cls, request_body: dict) -> dict:
        return {k: v for k, v in request_body.items() if k not in cls.model_fields}


class ResultResponse(Schema):
    project: str
    test: str
    result: str


class ErrorResponse(Schema):
    detail: str
