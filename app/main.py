import urllib.parse
from typing import Optional, Final, Annotated

import httpx
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends
from sqlalchemy import Engine
from sqlmodel import Session, select
from starlette import status
from starlette.responses import JSONResponse, RedirectResponse
from starlette.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.db import get_engine, PlexUser
from config import Config

# Constants used for Plex API configuration and cookie settings.

config = Config.get_config()

SECONDS_IN_A_DAY: Final[int] = 60 * 60 * 24
COOKIE_TIME_OUT = config.COOKIE_RETENTION_DAYS * SECONDS_IN_A_DAY

# Initialize the FastAPI app and add session middleware.
app = FastAPI()
# noinspection PyTypeChecker
app.add_middleware(SessionMiddleware, secret_key="some-random-string")

engine: Engine = get_engine()


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@app.middleware("http")
async def some_middleware(request: Request, call_next):
    """
    Middleware to preserve the session cookie across HTTP responses.

    This middleware intercepts incoming HTTP requests and ensures that if the session cookie is present,
    it is set as an HTTP-only cookie in the outgoing response.

    Args:
        request (Request): The incoming HTTP request.
        call_next (Callable): The next middleware or route handler in the chain.

    Returns:
        Response: The HTTP response with the session cookie set (if present).
    """
    response = await call_next(request)
    session = request.cookies.get("session")
    if session:
        response.set_cookie(
            key="session", value=request.cookies.get("session"), httponly=True
        )
    return response


# Initialize the Jinja2 templates directory.
templates = Jinja2Templates(directory="templates")

# A simple in-memory store for user tokens (if needed in the future).
user_tokens = {}


async def get_user_from_request(request: Request) -> Optional[PlexUser]:
    plex_user = None
    plex_uuid = request.cookies.get("plex_uuid")
    if plex_uuid:
        with Session(engine) as session:
            statement = select(PlexUser).where(PlexUser.plex_uuid == plex_uuid)
            # noinspection PyTypeChecker
            result = session.exec(statement)
            plex_user = result.first()
    return plex_user


async def verify_plex_user(request: Request) -> PlexUser:
    """
    Verify the Plex user from the current session or redirect to the login if not authenticated.

    This function attempts to retrieve the Plex user information using the 'auth_token' stored in the cookies.
    If the token is valid, it returns a PlexUser object. Otherwise, it raises an HTTPException to trigger a
    redirection to the login route.

    Args:
        request (Request): The incoming HTTP request.

    Returns:
        PlexUser: The authenticated Plex user.

    Raises:
        HTTPException: If the user is not authenticated, with a temporary redirect header to the login page.
    """
    plex_user: PlexUser = await get_user_from_request(request)
    if plex_user:
        return plex_user
    if request.cookies.get("plex_uuid"):
        request.cookies.pop("plex_uuid")
    raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        headers={"Location": "/auth/login"},
    )


async def get_auth_token_from_pin(pin_id: str, pin_code: str) -> Optional[str]:
    """
    Retrieve the authentication token from a previously generated PIN stored in session.

    This function checks if the session contains PIN information. If present, it uses that information
    to fetch the authentication token from the Plex API. Once the token is retrieved, it removes the
    PIN information from the session.

    Args:
        pin_id (str): The PIN ID of the PLEX user.
        pin_code (str): The PIN code of the PLEX user.

    Returns:
        Optional[str]: The retrieved authentication token if available; otherwise, None.
    """
    auth_token: Optional[str] = None
    pin_data = await fetch_auth_token(pin_id, pin_code)
    if isinstance(pin_data, dict):
        auth_token = pin_data.get("authToken")
    return auth_token


async def generate_pin():
    """
    Generate a PIN for Plex authentication.

    This function calls the Plex PIN API to generate a new PIN for user authentication. It sends a POST request
    with the required headers and returns the JSON response containing the PIN details.

    Returns:
        dict or JSONResponse: The JSON response with PIN information if successful,
                              or a JSONResponse with an error message if PIN generation fails.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            config.PLEX_PIN_URL,
            json={"strong": True},
            headers={
                "accept": "application/json",
                "X-Plex-Product": config.APP_PRODUCT_NAME,
                "X-Plex-Client-Identifier": config.APP_CLIENT_ID,
            },
        )

    if response.status_code != 201:
        return JSONResponse(
            status_code=500, content={"error": "Failed to generate PIN"}
        )
    response_json = response.json()
    return response_json


async def fetch_auth_token(pin_id, pin_code):
    """
    Fetch the authentication token using a given PIN ID and code.

    This function queries the Plex PIN API with the provided PIN ID and PIN code to retrieve
    the associated authentication token.

    Args:
        pin_id (str): The ID of the generated PIN.
        pin_code (str): The code corresponding to the PIN.

    Returns:
        dict or JSONResponse: The JSON response containing the authentication token if successful,
                              or a JSONResponse with an error message if the token cannot be fetched.
    """
    url = f"{config.PLEX_PIN_URL}/{pin_id}"
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            params={"code": pin_code},
            headers={
                "accept": "application/json",
                "X-Plex-Client-Identifier": config.APP_CLIENT_ID,
            },
        )

    if response.status_code != 200:
        return JSONResponse(status_code=500, content={"error": "Failed to fetch token"})
    response_json = response.json()
    return response_json


async def get_plex_user_from_auth_token(auth_token) -> Optional[PlexUser]:
    """
    Retrieve Plex user information using an authentication token.

    This function sends a GET request to the Plex user API endpoint with the provided authentication token.
    If the response is successful, it returns a PlexUser object containing the user's details; otherwise, it returns None.

    Args:
        auth_token (str): The authentication token for the Plex user.

    Returns:
        Optional[PlexUser]: A PlexUser object if successful; otherwise, None.
    """
    url = f"{config.PLEX_USER_URL}"
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers={
                "accept": "application/json",
                "X-Plex-Product": config.APP_PRODUCT_NAME,
                "X-Plex-Client-Identifier": config.APP_CLIENT_ID,
                "X-Plex-Token": auth_token,
            },
        )

    if response.status_code != 200:
        return None
    response_json = response.json()
    user = PlexUser(
        name=response_json["username"],
        auth_token=auth_token,
        plex_uuid=response_json["uuid"],
    )
    return user


@app.get("/")
async def root(request: Request):
    """
    Render the home page for authenticated Plex users.

    This route handler renders the home page template with the authenticated user's information.

    Args:
        request (Request): The incoming HTTP request.
        plex_user (PlexUser): The authenticated Plex user, obtained via dependency injection.

    Returns:
        TemplateResponse: The rendered home page.
    """
    user_name: Optional[str] = None
    plex_user: PlexUser = await get_user_from_request(request)
    if plex_user:
        user_name: str = plex_user.name
    return templates.TemplateResponse(
        "home.j2",
        {"request": request, "user_name": user_name},
    )


@app.get("/duplicates")
async def duplicates(request: Request, plex_user: PlexUser = Depends(verify_plex_user)):
    """
    Render the home page for authenticated Plex users.

    This route handler renders the home page template with the authenticated user's information.

    Args:
        request (Request): The incoming HTTP request.
        plex_user (PlexUser): The authenticated Plex user, obtained via dependency injection.

    Returns:
        TemplateResponse: The rendered home page.
    """
    return templates.TemplateResponse(
        "duplicates.j2",
        {"request": request, "plex_user": plex_user},
    )


@app.get("/fetch_duplicates")
async def fetch_duplicates(
    request: Request, plex_user: PlexUser = Depends(verify_plex_user)
):
    """
    Render the home page for authenticated Plex users.

    This route handler renders the home page template with the authenticated user's information.

    Args:
        request (Request): The incoming HTTP request.
        plex_user (PlexUser): The authenticated Plex user, obtained via dependency injection.

    Returns:
        TemplateResponse: The rendered home page.
    """
    return templates.TemplateResponse(
        "duplicates.j2",
        {"request": request, "plex_user": plex_user, "duplicates": ["one", "two"]},
    )


@app.get("/callback")
async def callback(request: Request, pin_id: str, pin_code: str):
    """
    Handle the callback from Plex authentication.

    After Plex authentication, this route is called to retrieve the authentication token using the PIN
    information stored in the session. Depending on whether the token retrieval is successful, the user is
    redirected either to the home page or to the login page.

    Args:
        request (Request): The incoming HTTP request containing session data.
        pin_id (str): The ID of the generated PIN.
        pin_code (str): The code corresponding to the PIN.

    Returns:
        RedirectResponse: A redirection to the home page if authentication is successful,
                          or to the login page if not.
    """
    auth_token = await get_auth_token_from_pin(pin_id, pin_code)
    if auth_token:
        plex_user: PlexUser = await get_plex_user_from_auth_token(auth_token)
        plex_uuid: str = plex_user.plex_uuid
        with Session(engine) as session:
            # Check if the user already exists
            statement = select(PlexUser).where(PlexUser.plex_uuid == plex_uuid)
            # noinspection PyTypeChecker
            existing_user = session.exec(statement).first()

            if existing_user:
                # Update existing user
                existing_user.auth_token = plex_user.auth_token
                existing_user.name = plex_user.name
            else:
                # Insert new user
                session.add(plex_user)

            session.commit()  # Commit changes
        redirect_url = request.url_for("root")
        response = RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key="plex_uuid",
            value=plex_uuid,
            max_age=COOKIE_TIME_OUT,
        )
    else:
        redirect_url = request.url_for("login")
        response = RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)
    return response


@app.get("/auth/login")
async def login(request: Request):
    """
    Initiate the Plex login process by generating a PIN and redirecting to Plex's authentication page.

    This route handler calls the Plex PIN API to generate a new PIN, builds the authentication URL using the
    generated PIN, and stores the PIN information in the session. The user is then redirected to Plex to complete
    the authentication process.

    Args:
        request (Request): The incoming HTTP request.

    Returns:
        RedirectResponse: A redirection to the Plex authentication URL, or a JSONResponse with an error message
                          if the PIN generation fails.
    """
    request_pin_info = await generate_pin()
    pin_code = request_pin_info.get("code")
    pin_id = request_pin_info.get("id")

    if not pin_code or not pin_id:
        return JSONResponse(status_code=500, content={"error": "Invalid PIN response"})

    forward_url = f"{config.APP_FORWARD_URL}?pin_id={pin_id}&pin_code={pin_code}"
    auth_url = (
        f"{config.PLEX_AUTH_URL}?clientID={config.APP_CLIENT_ID}&code={pin_code}"
        f"&context%5Bdevice%5D%5Bproduct%5D="
        + urllib.parse.quote(config.APP_PRODUCT_NAME)
        + "&forwardUrl="
        + urllib.parse.quote(forward_url)
    )
    return RedirectResponse(auth_url)


if __name__ == "__main__":
    """
    Entry point for running the application.

    This block checks the 'ENVIRONMENT' variable to determine whether to enable auto-reloading.
    It then runs the FastAPI application using uvicorn on host '0.0.0.0' and port 6701.
    """
    reload: bool = config.ENVIRONMENT != "production"
    uvicorn.run(
        "main:app", host="0.0.0.0", port=config.PORT, reload=reload, access_log=False
    )
