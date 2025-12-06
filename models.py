from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str
    name: str
    is_donor: bool = False
    is_affected: bool = False
    password_hash: str


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    donor_id: int = Field(foreign_key="user.id")

    name: str
    category: str
    quantity: int
    description: str
    location: str
    status: str = "Available"


class Request(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    requester_id: int = Field(foreign_key="user.id")
    item_id: int = Field(foreign_key="item.id")

    requested_quantity: int
    status: str = "Pending"  # Pending | Approved | Rejected


