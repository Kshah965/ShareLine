import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select

from db import SessionDep
from models import Item, Request as RequestModel, User
from schemas import ItemCreate
from .auth import UserRoleDep
from .items import create_item as api_create_item
from .requests import _refresh_item_status

router = APIRouter(prefix="/ui", tags=["ui"])
templates = Jinja2Templates(directory="templates")


FLASH_SUCCESS = "success"
FLASH_ERROR = "error"


def _ensure_donor(role: str) -> None:
    if role != "donor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only donors can access this section.")


def _load_donor_items(session: SessionDep, donor_id: int) -> List[Item]:
    stmt = select(Item).where(Item.donor_id == donor_id).order_by(Item.id.desc())
    return session.exec(stmt).all()


def _render_items_fragment(
    request: Request,
    items: List[Item],
    flash_message: Optional[dict] = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        "fragments/donor_items_list.html",
        {"request": request, "items": items, "flash_message": flash_message},
    )


def _load_request_rows(session: SessionDep, item_id: int) -> List[dict]:
    stmt = (
        select(RequestModel, User.name)
        .join(User, User.id == RequestModel.requester_id)
        .where(RequestModel.item_id == item_id)
        .order_by(RequestModel.id.desc())
    )
    rows = session.exec(stmt).all()
    formatted = []
    for req, requester_name in rows:
        formatted.append({"model": req, "requester_name": requester_name})
    return formatted


def _render_requests_fragment(
    request: Request,
    item: Optional[Item],
    requests_data: List[dict],
    modal_message: Optional[dict] = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    response = templates.TemplateResponse(
        "fragments/donor_requests_list.html",
        {
            "request": request,
            "item": item,
            "requests": requests_data,
            "modal_message": modal_message,
        },
    )
    response.status_code = status_code
    return response


@router.get("/donor/items", response_class=HTMLResponse)
def donor_items_fragment(
    request: Request,
    session: SessionDep,
    current: UserRoleDep,
):
    user = current["user"]
    role = current["role"]
    _ensure_donor(role)
    items = _load_donor_items(session, user.id)
    return _render_items_fragment(request, items)


@router.get("/donor/donate-form", response_class=HTMLResponse)
def donor_donate_form(
    request: Request,
    current: UserRoleDep,
):
    _ensure_donor(current["role"])
    return templates.TemplateResponse(
        "fragments/donor_donate_form.html",
        {
            "request": request,
            "form_data": {},
            "errors": [],
            "flash_message": None,
        },
    )


@router.post("/donor/items", response_class=HTMLResponse)
async def donor_create_item(
    request: Request,
    session: SessionDep,
    current: UserRoleDep,
):
    user = current["user"]
    role = current["role"]
    _ensure_donor(role)

    form = await request.form()
    form_data = {
        "name": (form.get("name") or "").strip(),
        "category": (form.get("category") or "").strip(),
        "quantity": (form.get("quantity") or "").strip(),
        "location": (form.get("location") or "").strip(),
        "description": (form.get("description") or "").strip(),
    }

    errors: List[str] = []

    for field, label in (
        ("name", "Item name"),
        ("category", "Category"),
        ("quantity", "Quantity"),
        ("location", "Location"),
        ("description", "Description"),
    ):
        if not form_data[field]:
            errors.append(f"{label} is required.")

    quantity_value: Optional[int] = None
    if form_data["quantity"]:
        try:
            quantity_value = int(form_data["quantity"])
            if quantity_value < 1:
                errors.append("Quantity must be at least 1.")
        except ValueError:
            errors.append("Quantity must be an integer.")

    if errors:
        response = templates.TemplateResponse(
            "fragments/donor_donate_form.html",
            {
                "request": request,
                "form_data": form_data,
                "errors": errors,
                "flash_message": None,
            },
        )
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response

    item_in = ItemCreate(
        donor_id=user.id,
        name=form_data["name"],
        category=form_data["category"],
        quantity=quantity_value or 1,
        description=form_data["description"],
        location=form_data["location"],
    )

    try:
        api_create_item(item_in=item_in, session=session)
    except HTTPException as exc:
        errors.append(exc.detail)
        response = templates.TemplateResponse(
            "fragments/donor_donate_form.html",
            {
                "request": request,
                "form_data": form_data,
                "errors": errors,
                "flash_message": None,
            },
        )
        response.status_code = exc.status_code
        return response

    context = {
        "request": request,
        "form_data": {},
        "errors": [],
        "flash_message": {"kind": FLASH_SUCCESS, "text": "Item donated successfully."},
    }
    response = templates.TemplateResponse("fragments/donor_donate_form.html", context)
    response.headers["HX-Trigger"] = json.dumps(
        {"donor-items-refresh": True, "close-donate-modal": True}
    )
    return response


@router.post("/donor/items/{item_id}/delete", response_class=HTMLResponse)
def donor_delete_item(
    item_id: int,
    request: Request,
    session: SessionDep,
    current: UserRoleDep,
):
    user = current["user"]
    role = current["role"]
    _ensure_donor(role)

    try:
        item = session.get(Item, item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found.")
        if item.donor_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own items.")
        if item.status == "Completed":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Completed items cannot be deleted.")

        old_requests = session.exec(select(RequestModel).where(RequestModel.item_id == item_id)).all()
        for req in old_requests:
            session.delete(req)

        session.delete(item)
        session.commit()
        flash_message = {"kind": FLASH_SUCCESS, "text": "Item deleted successfully."}
    except HTTPException as exc:
        session.rollback()
        items = _load_donor_items(session, user.id)
        response = _render_items_fragment(
            request,
            items,
            {"kind": FLASH_ERROR, "text": exc.detail},
        )
        response.status_code = exc.status_code
        return response

    items = _load_donor_items(session, user.id)
    return _render_items_fragment(request, items, flash_message)


@router.get("/donor/items/{item_id}/requests", response_class=HTMLResponse)
def donor_item_requests(
    item_id: int,
    request: Request,
    session: SessionDep,
    current: UserRoleDep,
):
    user = current["user"]
    role = current["role"]
    _ensure_donor(role)

    item = session.get(Item, item_id)
    if item is None or item.donor_id != user.id:
        return _render_requests_fragment(
            request,
            None,
            [],
            {"kind": FLASH_ERROR, "text": "Item not found or no longer accessible."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    requests_data = _load_request_rows(session, item_id)
    return _render_requests_fragment(request, item, requests_data)


@router.post("/donor/requests/{request_id}/status", response_class=HTMLResponse)
async def donor_update_request_status(
    request_id: int,
    http_request: Request,
    session: SessionDep,
    current: UserRoleDep,
):
    user = current["user"]
    role = current["role"]
    _ensure_donor(role)

    form = await http_request.form()
    new_status = (form.get("status") or "").strip()

    item: Optional[Item] = None

    try:
        if new_status not in {"Approved", "Rejected"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status value.")

        db_request = session.get(RequestModel, request_id)
        if db_request is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")

        item = session.get(Item, db_request.item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Associated item not found.")
        if item.donor_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only manage requests for your own items.")
        if db_request.status != "Pending":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending requests can be updated.")

        if new_status == "Approved":
            if db_request.requested_quantity > item.quantity:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough quantity available.")
            item.quantity -= db_request.requested_quantity
            db_request.status = "Approved"
        else:
            db_request.status = "Rejected"

        _refresh_item_status(session, item)
        session.add(item)
        session.add(db_request)
        session.commit()
        session.refresh(db_request)
        modal_message = {
            "kind": FLASH_SUCCESS,
            "text": f"Request {new_status.lower()} successfully.",
        }
    except HTTPException as exc:
        session.rollback()
        requests_data = _load_request_rows(session, item.id) if item else []
        response = _render_requests_fragment(
            http_request,
            item,
            requests_data,
            {"kind": FLASH_ERROR, "text": exc.detail},
            status_code=exc.status_code,
        )
        return response

    requests_data = _load_request_rows(session, item.id)
    response = _render_requests_fragment(http_request, item, requests_data, modal_message)
    response.headers["HX-Trigger"] = json.dumps({"donor-items-refresh": True})
    return response
