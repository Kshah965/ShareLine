from fastapi import  FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from routers.auth import OptionalUserRoleDep


from db import create_db_and_tables
from routers import users, items, auth, requests, pages, ui

app = FastAPI(title="ShareLine")


templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


@app.get("/", response_class=HTMLResponse)
def read_root(
    request: Request,
    current: OptionalUserRoleDep,
):
    user = current["user"] if current else None
    role = current["role"] if current else None

    # ⭐ If logged in, redirect to correct dashboard
    if user:
        if role == "donor":
            return RedirectResponse(url="/donor", status_code=303)
        if role == "affected":
            return RedirectResponse(url="/affected", status_code=303)

    # ⭐ If not logged in, show landing page
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "current_user": user,
            "current_role": role,
        },
    )

app.include_router(auth.router)
app.include_router(users.router, prefix="/users")
app.include_router(items.router, prefix="/items")
app.include_router(requests.router, prefix="/requests")

app.include_router(pages.router)
app.include_router(ui.router)
