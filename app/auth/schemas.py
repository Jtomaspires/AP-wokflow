"""Auth request/response bodies."""

from pydantic import BaseModel


class LoginBody(BaseModel):
    email: str
    password: str


class OperatorOut(BaseModel):
    id: str
    email: str
    display_name: str
