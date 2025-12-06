# routers/users.py
from typing import List

from fastapi import APIRouter, HTTPException, Response
from sqlmodel import select
from .auth import UserRoleDep
from db import SessionDep
from models import User, Item, Request
from schemas import UserRead

router = APIRouter(tags=["users"])


@router.get("/", response_model=List[UserRead])
def list_users(session: SessionDep):
    """
    List all users (debug/admin).
    """
    users = session.exec(select(User)).all()
    return users


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, session: SessionDep):
    """
    Get a single user by ID.
    """
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/me", status_code=204)
def delete_own_account(
    session: SessionDep,
    current: UserRoleDep,
):
    user = current["user"]

    if user.id is None:
        # Shouldn't happen in practice, but just in case
        raise HTTPException(status_code=400, detail="User has no id")

    # 1) Delete all requests *made by* this user
    my_requests = session.exec(
        select(Request).where(Request.requester_id == user.id)
    ).all()
    for req in my_requests:
        session.delete(req)

    # 2) Find all items *donated by* this user
    my_items = session.exec(
        select(Item).where(Item.donor_id == user.id)
    ).all()

    # 3) For each of those items, delete all requests for that item,
    #    then delete the item itself
    for item in my_items:
        item_reqs = session.exec(
            select(Request).where(Request.item_id == item.id)
        ).all()
        for req in item_reqs:
            session.delete(req)
        session.delete(item)

    # 4) Finally, delete the user record itself
    session.delete(user)
    session.commit()

    return Response(status_code=204)

