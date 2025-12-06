
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import  Literal


class ItemCreate(BaseModel):
    donor_id: int
    name: str
    category: str
    quantity: int
    description: str
    location: str

class RequestCreate(BaseModel):
    requester_id: int
    item_id: int
    requested_quantity: int = Field(gt=0)

class RequestStatusUpdate(BaseModel):
    status: str = Field(pattern="^(Pending|Approved|Rejected)$")


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    is_donor: bool = False
    is_affected: bool = False


class UserRead(BaseModel):
    id: int
    email: EmailStr
    name: str
    is_donor: bool
    is_affected: bool

    model_config = ConfigDict(from_attributes=True)

class LoginData(BaseModel):
    email: EmailStr
    password: str
    
    role: Literal["donor", "affected"]
