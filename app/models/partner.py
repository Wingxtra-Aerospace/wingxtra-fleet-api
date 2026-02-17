from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl, model_validator


class PartnerTarget(BaseModel):
    name: str = Field(min_length=1)
    url: HttpUrl
    auth_type: str
    api_key: str = Field(min_length=1)
    header_name: str | None = None

    @model_validator(mode="after")
    def validate_auth(self) -> "PartnerTarget":
        if self.auth_type not in {"bearer", "header"}:
            raise ValueError("auth_type must be 'bearer' or 'header'")
        if self.auth_type == "header" and not self.header_name:
            raise ValueError("header_name is required for auth_type='header'")
        return self

    def redacted(self) -> dict[str, str | None]:
        return {
            "name": self.name,
            "url": str(self.url),
            "auth_type": self.auth_type,
            "header_name": self.header_name,
            "api_key": "***REDACTED***",
        }
