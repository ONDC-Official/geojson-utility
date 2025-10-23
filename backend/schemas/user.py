from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    password: str

class UserRead(BaseModel):
    id: int
    username: str
    class Config:
        from_attributes = True
# UNUSED - UserLogin class is imported but never used in the codebase
# class UserLogin(BaseModel):
#     username: str
#     password: str 