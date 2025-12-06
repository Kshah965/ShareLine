# routers/requests.py
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Response
from sqlmodel import select

from db import SessionDep
from models import Request as RequestModel, Item, User, Request
from schemas import RequestCreate, RequestStatusUpdate
from .auth import UserRoleDep

router = APIRouter(tags=["requests"])


@router.get("/{request_id}", response_model=RequestModel)
def get_request(request_id: int, session: SessionDep):
    """
    Get a single request by ID.
    """
    req = session.get(RequestModel, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return req


@router.post("/", response_model=RequestModel)
def create_request(request_data: RequestCreate, session: SessionDep):
    """
    Create a new request for an item.
    Also mark the item as 'Requested' so donors can see it has a pending request.
    """
    item = session.get(Item, request_data.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    if request_data.requested_quantity > item.quantity:
        raise HTTPException(
            status_code=400,
            detail="Requested quantity exceeds available quantity",
        )

    requester = session.get(User, request_data.requester_id)
    if requester is None:
        raise HTTPException(status_code=404, detail="Requester not found")

    new_request = RequestModel(
        requester_id=request_data.requester_id,
        item_id=request_data.item_id,
        requested_quantity=request_data.requested_quantity,
        status="Pending",
    )

    # 🔹 If the item was Available, mark it as Requested so UI can show that
    if item.status == "Available":
        item.status = "Requested"
        session.add(item)

    session.add(new_request)
    session.commit()
    session.refresh(new_request)
    return new_request


@router.get("/", response_model=List[RequestModel])
def list_requests(
    session: SessionDep,
    requester_id: Optional[int] = None,
    item_id: Optional[int] = None,
    status: Optional[str] = None,
):
    """
    List requests, optionally filtered by requester_id, item_id, and status.
    """
    query = select(RequestModel)

    if requester_id is not None:
        query = query.where(RequestModel.requester_id == requester_id)

    if item_id is not None:
        query = query.where(RequestModel.item_id == item_id)

    if status is not None:
        query = query.where(RequestModel.status == status)

    results = session.exec(query).all()
    return results


# routers/requests.py

@router.patch("/{request_id}", response_model=RequestModel)
def update_request_status(
    request_id: int,
    update: RequestStatusUpdate,
    session: SessionDep,
    current: UserRoleDep,
):
    """
    Approve or reject a request.

    - Only donors can change request status.
    - Only the donor who owns the item can approve/reject.
    - If approved, we reduce item.quantity.
      If quantity goes to 0, mark item as Completed so it disappears from "Available".
    """
    user = current["user"]
    role = current["role"]

    if role != "donor":
        raise HTTPException(status_code=403, detail="Only donors can update requests")

    db_request = session.get(RequestModel, request_id)
    if db_request is None:
        raise HTTPException(status_code=404, detail="Request not found")

    # Make sure this donor owns the item being requested
    item = session.get(Item, db_request.item_id)
    if item is None:
        raise HTTPException(
            status_code=400,
            detail="Associated item not found",
        )

    if item.donor_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only manage requests for your own items.",
        )

    # Only allow changing from Pending
    if db_request.status != "Pending":
        raise HTTPException(
            status_code=400,
            detail="Only pending requests can be updated",
        )

    if update.status == "Approved":
        # Make sure there is still enough quantity
        if db_request.requested_quantity > item.quantity:
            raise HTTPException(
                status_code=400,
                detail="Not enough quantity available",
            )

        # Decrease quantity
        item.quantity -= db_request.requested_quantity

        # If item is fully used, mark as Completed (will disappear from "Available")
        if item.quantity == 0:
            item.status = "Completed"

        db_request.status = "Approved"
        session.add(item)

    elif update.status == "Rejected":
        db_request.status = "Rejected"

    # If someone sent "Pending" again, we ignore it and keep it Pending.

    session.add(db_request)
    session.commit()
    session.refresh(db_request)
    return db_request


@router.delete("/{request_id}", status_code=204)
def delete_request(
    request_id: int,
    session: SessionDep,
    current: UserRoleDep,   # 👈 require auth
):
    user = current["user"]
    role = current["role"]

    req = session.get(Request, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")

    # If affected user: can only delete *their own* request
    if role == "affected":
        if req.requester_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You can only delete your own requests.",
            )

    # If donor: can delete requests on their own items
    elif role == "donor":
        item = session.get(Item, req.item_id)
        if item is None or item.donor_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Donors can only delete requests for their items.",
            )

    # (If you ever add 'admin', you could allow them to delete anything.)

    session.delete(req)
    session.commit()
    return Response(status_code=204)

