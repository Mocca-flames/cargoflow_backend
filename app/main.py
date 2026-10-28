from fastapi import FastAPI

from app.core.config import settings
from app.features.auth.router import router as auth_router
from app.features.users.router import router as users_router
from app.features.documents.router import router as documents_router


app = FastAPI(title=settings.PROJECT_NAME)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(documents_router)


@app.get("/")
def root():
    return {"Cargo Flow": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}
