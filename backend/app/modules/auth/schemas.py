from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    login_name: str
    password: str


class PasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=256)


class ContactsRequest(BaseModel):
    current_password: str
    email: EmailStr
    phone_number: str = Field(min_length=5, max_length=32)


class ResetPasswordRequest(BaseModel):
    temporary_password: str = Field(min_length=10, max_length=256)


class CsrfResponse(BaseModel):
    csrf_token: str
