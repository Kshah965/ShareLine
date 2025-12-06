

from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select

from db import SessionDep
from models import Item, User, Request
from schemas import ItemCreate
from .auth import UserRoleDep

router = APIRouter(tags=["items"])

templates = Jinja2Templates(directory="templates")



@router.get("/{item_id}", response_model=Item)
def get_item(item_id: int, session: SessionDep):
    """
    Get a single item by ID.
    """
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/", response_model=Item)
def create_item(item_in: ItemCreate, session: SessionDep):
    """
    Create a new item batch for a donor.
    If an identical batch already exists, increase its quantity instead.
    """

    # 1) Check donor exists and is flagged as donor
    donor = session.get(User, item_in.donor_id)
    if donor is None or not donor.is_donor:
        raise HTTPException(
            status_code=400,
            detail="Invalid donor_id or user is not a donor",
        )

    # 2) Check if a similar item already exists (same donor, name, category, location, description)
    query = select(Item).where(
        Item.donor_id == item_in.donor_id,
        Item.name == item_in.name,
        Item.category == item_in.category,
        Item.location == item_in.location,
        Item.description == item_in.description,
    )
    existing = session.exec(query).first()

    # 3) If found, just bump quantity
    if existing:
        existing.quantity += item_in.quantity

        # If it was "Completed" and now has stock, make it "Available"
        if existing.quantity > 0 and existing.status == "Completed":
            existing.status = "Available"

        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    # 4) Otherwise create a brand new item
    item = Item(
        donor_id=item_in.donor_id,
        name=item_in.name,
        category=item_in.category,
        quantity=item_in.quantity,
        description=item_in.description,
        location=item_in.location,
        status="Available",
    )

    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("/", response_model=List[Item])
def list_items(
    session: SessionDep,
    category: Optional[str] = None,
    location: Optional[str] = None,
    status: Optional[str] = None,
    min_quantity: Optional[int] = None,
):
    """
    List items, optionally filtered by category, location, status, and min_quantity.
    """
    query = select(Item)

    if category is not None:
        query = query.where(Item.category == category)

    if location is not None:
        query = query.where(Item.location == location)

    if status is not None:
        query = query.where(Item.status == status)

    if min_quantity is not None:
        query = query.where(Item.quantity >= min_quantity)

    results = session.exec(query).all()
    return results


@router.delete("/{item_id}", status_code=204)
def delete_item(
    item_id: int,
    session: SessionDep,
    current: UserRoleDep,
):
    user = current["user"]
    role = current["role"]

    # Only donors can delete items
    if role != "donor":
        raise HTTPException(
            status_code=403,
            detail="Only donors can delete items.",
        )

    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    # Donor can only delete their *own* items
    if item.donor_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only delete items you donated.",
        )

    # Block delete if there are pending requests
    pending = session.exec(
        select(Request).where(
            Request.item_id == item_id,
            Request.status == "Pending",
        )
    ).first()

    if pending:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete item with pending requests.",
        )

    # If you also want to clean up old non-pending requests, you *can* do:
    old_requests = session.exec(select(Request).where(Request.item_id == item_id)).all()
    for r in old_requests:
        session.delete(r)

    session.delete(item)
    session.commit()
    return Response(status_code=204)

@router.get("/fragments/list", response_class=HTMLResponse)
def items_list_fragment(request: Request, session: SessionDep):
    items = session.exec(select(Item)).all()
    return templates.TemplateResponse(
        "fragments/items_list.html",
        {"request": request, "items": items},
    )

@router.get("/fragments/my-items", response_class=HTMLResponse)
def my_items_fragment(request: Request, session: SessionDep, current: UserRoleDep):
    user = current["user"]
    role = current["role"]

    if role != "donor":
        raise HTTPException(status_code=403, detail="Only donors can view this page.")

    items = session.exec(
        select(Item).where(Item.donor_id == user.id)
    ).all()

    return templates.TemplateResponse(
        "fragments/items_list.html",
        {"request": request, "items": items},
    )

@router.get("/my", response_class=HTMLResponse)
def my_items_page(request: Request, session: SessionDep, current: UserRoleDep):
    user = current["user"]
    role = current["role"]

    if role != "donor":
        raise HTTPException(status_code=403, detail="Only donors can view this page.")

    items = session.exec(
        select(Item).where(Item.donor_id == user.id)
    ).all()

    return templates.TemplateResponse(
        "items_my.html",
        {"request": request, "current_user": user, "current_role": role, "items": items},
    )

@router.post("/new")
async def create_item_from_form(request: Request, session: SessionDep, current: UserRoleDep):
    user = current["user"]
    role = current["role"]

    if role != "donor":
        raise HTTPException(status_code=403, detail="Only donors can create items.")

    form = await request.form() # type: ignore

    name = form.get("name")
    category = form.get("category")
    quantity_raw = form.get("quantity")
    description = form.get("description")
    location = form.get("location")

    if not all([name, category, quantity_raw, description, location]):
        raise HTTPException(status_code=400, detail="All fields required")

    quantity = int(quantity_raw)

    item_in = ItemCreate(
        donor_id=user.id,
        name=name,
        category=category,
        quantity=quantity,
        description=description,
        location=location,
    )

    create_item(item_in=item_in, session=session)

    return RedirectResponse(url="/items/my", status_code=303)

@router.get("/new", response_class=HTMLResponse)
def new_item_page(request: Request, current: UserRoleDep):
    user = current["user"]
    role = current["role"]

    if role != "donor":
        raise HTTPException(
            status_code=403,
            detail="Only donors can create items.",
        )

    return templates.TemplateResponse(
        "items_new.html",
        {
            "request": request,
            "current_user": user,
            "current_role": role,
        },
    )
