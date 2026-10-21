from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=1, max_length=1024)


class RegistrationRequest(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=12, max_length=1024)


class PasswordSetupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=12, max_length=1024)
