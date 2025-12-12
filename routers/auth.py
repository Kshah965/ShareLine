import secrets
from typing import Annotated, Optional

from db import SessionDep
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer
from models import User
from passlib.context import CryptContext
from schemas import LoginData, UserCreate, UserRead
from sqlmodel import select

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="templates")

SECRET_KEY = secrets.token_hex(32)
serializer = URLSafeTimedSerializer(SECRET_KEY)


pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_session_token(user_id: int, role: str) -> str:
    """
    Store user_id + role in the signed token.
    Example data:
        {"user_id": 3, "role": "donor"}
    """
    return serializer.dumps({"user_id": user_id, "role": role})


def verify_session_token(token: str, max_age_seconds: int = 60 * 60 * 8):
    """
    Returns dict {'user_id': ..., 'role': ...} if valid,
    or None if token is invalid/expired.
    """
    try:
        data = serializer.loads(token, max_age=max_age_seconds)
        return data
    except Exception:
        return None


def get_current_user_and_role(
    session: SessionDep,
    session_token: Optional[str] = Cookie(default=None, alias="session"),
) -> dict:
    """
    Reads the 'session' cookie, verifies the token,
    looks up the user, and returns {"user": User, "role": str}.
    Raises 401 if not logged in / invalid.
    """
    if session_token is None:
        raise HTTPException(status_code=401, detail="Not logged in")

    data = verify_session_token(session_token)
    if not data:
        raise HTTPException(
            status_code=401, detail="Invalid or expired session")

    user = session.get(User, data["user_id"])
    if user is None:
        raise HTTPException(
            status_code=401, detail="User not found for this session")

    return {"user": user, "role": data["role"]}


CurrentUserRoleDep = Annotated[dict, Depends(get_current_user_and_role)]


def get_optional_user_and_role(
    session: SessionDep,
    session_token: Optional[str] = Cookie(default=None, alias="session"),
) -> Optional[dict]:
    """
    Like get_current_user_and_role, but:
    - returns None if not logged in / invalid instead of raising HTTP 401.
    Perfect for templates/navbar.
    """
    if session_token is None:
        return None

    data = verify_session_token(session_token)
    if not data:
        return None

    user = session.get(User, data["user_id"])
    if user is None:
        return None

    return {"user": user, "role": data["role"]}


OptionalUserRoleDep = Annotated[Optional[dict],
                                Depends(get_optional_user_and_role)]


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    current: OptionalUserRoleDep,
):
    user = current["user"] if current else None
    role = current["role"] if current else None
    if user is not None:
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "current_user": user,
            "current_role": role,
        },
    )


@router.get("/register", response_class=HTMLResponse)
def register_page(
    request: Request,
    current: OptionalUserRoleDep,
):
    user = current["user"] if current else None
    role = current["role"] if current else None

    if user is not None:
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "current_user": user,
            "current_role": role,
        },
    )


@router.post("/register")
async def register(request: Request, session: SessionDep):
    """
    Register a new user with a hashed password.
    Accepts either JSON (API/Swagger) or form-data (from HTML form).
    """
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("application/json"):
        data = await request.json()
        user_in = UserCreate(**data)

        if user_in.is_donor:
            role = "donor"
        elif user_in.is_affected:
            role = "affected"
        else:
            raise HTTPException(
                status_code=400,
                detail="User must be registered as donor or affected",
            )

    else:
        form = await request.form()

        raw_email = form.get("email")
        raw_name = form.get("name")
        raw_password = form.get("password")
        raw_role = form.get("role")

        email = raw_email if isinstance(raw_email, str) else None
        name = raw_name if isinstance(raw_name, str) else None
        password = raw_password if isinstance(raw_password, str) else None
        role = raw_role if isinstance(raw_role, str) else None

        if not email or not name or not password or not role:
            raise HTTPException(
                status_code=400, detail="All fields are required"
            )

        is_donor = role == "donor"
        is_affected = role == "affected"

        user_in = UserCreate(
            email=email,
            name=name,
            password=password,
            is_donor=is_donor,
            is_affected=is_affected,
        )

    existing = session.exec(
        select(User).where(User.email == user_in.email)
    ).first()

    if existing:
        if content_type.startswith("application/json"):
            raise HTTPException(status_code=400, detail="Email already registered")

        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "current_user": None,
                "current_role": None,
                "error": "Email already registered",
            },
            status_code=400,
        )

    password_hash = hash_password(user_in.password)

    user = User(
        email=user_in.email,
        name=user_in.name,
        password_hash=password_hash,
        is_donor=user_in.is_donor,
        is_affected=user_in.is_affected,
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    if user.id is None:
        raise HTTPException(
            status_code=500, detail="User was not created successfully"
        )

    token = create_session_token(user.id, role)

    if content_type.startswith("application/json"):
        resp = JSONResponse({"message": "Registration successful", "role": role})
    else:
        resp = RedirectResponse(url="/", status_code=303)

    resp.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 8,
    )
    return resp





@router.post("/login")
async def login(request: Request, session: SessionDep, response: Response):
    """
    Log in with email + password + chosen role ("donor" / "affected"),
    set a signed cookie.

    Accepts either JSON (API/Swagger) or form-data (from HTML form).
    """
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("application/json"):
        data = await request.json()
        payload = LoginData(**data)
    else:
        form = await request.form()

        raw_email = form.get("email")
        raw_password = form.get("password")
        raw_role = form.get("role")

        email = raw_email if isinstance(raw_email, str) else None
        password = raw_password if isinstance(raw_password, str) else None
        role = raw_role if isinstance(raw_role, str) else None

        if not email or not password or not role:
            raise HTTPException(
                status_code=400, detail="All fields are required")

        payload = LoginData(email=email, password=password,
                            role=role)  # type: ignore

    try:
        user = session.exec(
            select(User).where(User.email == payload.email)
        ).first()

        if user is None:
            raise HTTPException(
                status_code=400, detail="Invalid email or password"
            )

        if not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=400, detail="Invalid email or password"
            )

        if payload.role == "donor" and not user.is_donor:
            raise HTTPException(
                status_code=400, detail="User is not registered as donor"
            )

        if payload.role == "affected" and not user.is_affected:
            raise HTTPException(
                status_code=400, detail="User is not registered as affected"
            )

        if user.id is None:
            raise HTTPException(
                status_code=500, detail="User has no ID in database"
            )

        token = create_session_token(user.id, payload.role)

        if request.headers.get("content-type", "").startswith("application/json"):
            response.set_cookie(
                key="session",
                value=token,
                httponly=True,
                secure=False,
                samesite="lax",
                max_age=60 * 60 * 8,
            )
            return {"message": "Login successful", "role": payload.role}

        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(
            key="session",
            value=token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=60 * 60 * 8,
        )
        return resp

    except HTTPException as exc:
        if request.headers.get("content-type", "").startswith("application/json"):
            raise

        user = None
        role = None
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "current_user": user,
                "current_role": role,
                "error": exc.detail,
            },
            status_code=exc.status_code,
        )


@router.post("/logout")
def logout():
    """
    Clear the session cookie and redirect to home.
    """
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session")
    return response


@router.get("/me")
def read_me(current: CurrentUserRoleDep):
    """
    Get info about the currently logged-in user + active role.
    """
    user = current["user"]
    role = current["role"]
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": role,
        "is_donor": user.is_donor,
        "is_affected": user.is_affected,
    }


def require_auth(
    user_and_role: Optional[dict] = Depends(get_current_user_and_role),
) -> dict:
    if user_and_role is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    return user_and_role


UserRoleDep = Annotated[dict, Depends(require_auth)]

@router.get("/donor", include_in_schema=False)
def donor_dashboard(
    request: Request,
    current: CurrentUserRoleDep,
):
    user = current["user"]
    role = current["role"]

    if role != "donor":
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        "donor_dashboard.html",
        {
            "request": request,
            "current_user": user,
            "current_role": role,
        },
    )


@router.get("/affected", include_in_schema=False)
def affected_dashboard(
    request: Request,
    current: CurrentUserRoleDep,
):
    user = current["user"]
    role = current["role"]

    if role != "affected":
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        "affected_dashboard.html",
        {
            "request": request,
            "current_user": user,
            "current_role": role,
        },
    )
