"""Expose shared conversation DTOs before BM-03/BM-09 add storage and HTTP routes."""

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.openapi.models import Schema
from fastapi.openapi.utils import get_openapi
from pydantic.json_schema import models_json_schema

from bizmate.domain.models import ConversationThread, LanguageContext


def install_domain_schemas(app: FastAPI) -> None:
    def domain_openapi():
        if app.openapi_schema is not None:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        _, shared = models_json_schema(
            [(ConversationThread, "serialization"), (LanguageContext, "serialization")],
            ref_template="#/components/schemas/{model}",
        )
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        for name, definition in shared.get("$defs", {}).items():
            # Match FastAPI's OpenAPI serialization (notably omitted null defaults).
            definition = jsonable_encoder(Schema.model_validate(definition), exclude_none=True)
            if name in components and components[name] != definition:
                raise ValueError(f"Conflicting shared OpenAPI schema: {name}")
            components[name] = definition
        app.openapi_schema = schema
        return schema

    app.openapi = domain_openapi
