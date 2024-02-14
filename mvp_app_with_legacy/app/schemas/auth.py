from pydantic import BaseModel


class ResponseTokens(BaseModel):
    refresh_token: str
    access_token: str


class ResponseTokensGoogle(BaseModel):
    refresh_token: str
    access_token: str
    verify_phone: bool
    user_id: int


class ResponseCheckPhoneCode(BaseModel):
    phone_token: str


class ResponseSuccess(BaseModel):
    msg: str = "success"


class RequestDeviceData(BaseModel):
    token: str
    device: str
    system: str


class GoogleTokenData(BaseModel):
    sub: str
    email: str | None = None
    email_verified: bool = False
    given_name: str | None = None
    family_name: str | None = None
    picture: str | None = None


class AppleTokenData(BaseModel):
    sub: str
    email: str | None = None


class ResponseSuccessWithPostId(BaseModel):
    msg: str = "success"
    postId: int
