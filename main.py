import os
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
import urllib.parse

from starlette.responses import RedirectResponse, JSONResponse
import uvicorn
from fastapi import FastAPI, Request, Depends
from starlette.templating import Jinja2Templates
from sqlmodel import Session, SQLModel, create_engine, Field

PLEX_CLIENT_ID = "dc0537e0-6755-44de-97ee-6edd7a51c9b4"  # Generate a UUID for this
PLEX_REDIRECT_URI = "http://localhost:6701/auth/callback"
PLEX_PRODUCT_NAME = "Gosh Darned Plex Tools"
PLEX_PIN_URL = "https://plex.tv/api/v2/pins"
PLEX_AUTH_URL = "https://app.plex.tv/auth#"
PLEX_FORWARD_URL = "http://localhost:6701/"


class AuthUser(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: int | None = Field(default=None, primary_key=True)
    pin: str = Field(index=True)
    auth_key: str | None = Field(default=None, nullable=True)


templates = Jinja2Templates(directory="templates")

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=True, connect_args=connect_args)


@asynccontextmanager
async def lifespan(the_app: FastAPI):
    # All startup logig goes here
    create_db_and_tables()
    yield
    # Any shutdown / cleanup code goes here


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
app = FastAPI()


@app.get("/")
async def root(request: Request, session: SessionDep):
    # Check for authentication and retrieve token
    return templates.TemplateResponse("home.j2", {"request": request, "token": token})


@app.get("/auth/login")
async def login(session: SessionDep):
    """
    Step 1: Generate a PIN and redirect the user to Plex for authentication.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            PLEX_PIN_URL,
            json={"strong": True},
            headers={
                "accept": "application/json",
                "X-Plex-Product": PLEX_PRODUCT_NAME,
                "X-Plex-Client-Identifier": PLEX_CLIENT_ID,
            },
        )

    if response.status_code != 201:
        return JSONResponse(
            status_code=500, content={"error": "Failed to generate PIN"}
        )

    pin_data = response.json()
    pin_code = pin_data.get("code")
    pin_id = pin_data.get("id")

    if not pin_code or not pin_id:
        return JSONResponse(status_code=500, content={"error": "Invalid PIN response"})

    auth_url = (
        f"{PLEX_AUTH_URL}?clientID={PLEX_CLIENT_ID}&code={pin_code}"
        f"&context%5Bdevice%5D%5Bproduct%5D="
        + urllib.parse.quote(PLEX_PRODUCT_NAME)
        + "&forwardUrl="
        + urllib.parse.quote(PLEX_FORWARD_URL)
    )
    # Store the pin_id temporarily
    auth_user = AuthUser(pin=pin_id)
    session.add(auth_user)
    session.commit()
    session.refresh(auth_user)

    return RedirectResponse(auth_url)


if __name__ == "__main__":
    reload: bool = os.getenv("ENVIRONMENT") != "production"
    uvicorn.run("main:app", host="0.0.0.0", port=6701, reload=reload, access_log=False)
