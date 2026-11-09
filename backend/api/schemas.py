import re
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=8, max_length=1024)
    target_score: int | None = Field(default=None, ge=0, le=99, strict=True)
    full_knowledge: bool = False
    mode: Literal["all", "knowledge", "tasks"] = "all"
    login_method: Literal["easyplu", "easy-plu", "sso"] = "easyplu"

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        if not value.strip():
            raise ValueError("Empty username")
        return value.strip()

    @model_validator(mode="after")
    def validate_login_identity(self):
        pattern = r"[0-9]{8}" if self.login_method == "sso" else r"[^\s@]+@[^\s@]+\.[^\s@]+"
        if not re.fullmatch(pattern, self.email):
            raise ValueError("Invalid login identity")
        return self


class OtpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    otp: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")


class ScheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = Field(strict=True)
    consent: bool = Field(default=False, strict=True)


