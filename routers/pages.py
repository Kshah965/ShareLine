# routers/pages.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# Import the correct dependencies from your auth.py
from .auth import CurrentUserRoleDep

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="templates")


@router.get("/affected/requests", response_class=HTMLResponse)
async def affected_requests_page(
    request: Request,
    current: CurrentUserRoleDep  # Uses your existing auth dependency
):
    """
    Display the affected user's request tracking page.
    Shows all requests made by the current user with their statuses.
    """
    user = current["user"]
    role = current["role"]

    # Check if user is an affected user
    if role != "affected":
        # Redirect to home or appropriate dashboard
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        "affected_requests.html",
        {
            "request": request,
            "current_user": user,
            "current_role": role
        }
    )


# You can move your existing dashboard routes here from auth.py
# to keep all page routes in one place (optional but recommended)

@router.get("/donor", response_class=HTMLResponse)
async def donor_dashboard(
    request: Request,
    current: CurrentUserRoleDep
):
    """Donor dashboard page"""
    user = current["user"]
    role = current["role"]

    if role != "donor":
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        "donor_dashboard.html",
        {
            "request": request,
            "current_user": user,
            "current_role": role
        }
    )


@router.get("/affected", response_class=HTMLResponse)
async def affected_dashboard(
    request: Request,
    current: CurrentUserRoleDep
):
    """Affected user dashboard page"""
    user = current["user"]
    role = current["role"]

    if role != "affected":
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        "affected_dashboard.html",
        {
            "request": request,
            "current_user": user,
            "current_role": role
        }
    )

