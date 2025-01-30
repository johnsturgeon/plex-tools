import os

import uvicorn
from fastapi import FastAPI, Request
from starlette.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("home.j2", {"request": request})


if __name__ == "__main__":
    reload: bool = os.getenv("ENVIRONMENT") != "production"
    uvicorn.run("main:app", host="0.0.0.0", port=6701, reload=reload, access_log=False)
