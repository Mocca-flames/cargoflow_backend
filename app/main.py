from fastapi import FastAPI

from app.core.config import settings
from app.features.auth.router import router as auth_router
from app.features.users.router import router as users_router
from app.features.documents.router import router as documents_router
from app.features.onboarding.router import router as onboarding_router
from app.features.companies.router import router as companies_router
from app.features.document_types.router import router as document_types_router
from app.features.trucks.router import router as trucks_router
from app.features.availability.router import router as availability_router
from app.features.loads.router import router as loads_router, public_router as public_loads_router


app = FastAPI(title=settings.PROJECT_NAME)

if settings.SKIP_OTP and settings.ENVIRONMENT.lower() != "development":
    raise RuntimeError("SKIP_OTP is only allowed when ENVIRONMENT=development")

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(documents_router)
app.include_router(onboarding_router)
app.include_router(companies_router)
app.include_router(document_types_router)
app.include_router(trucks_router)
app.include_router(availability_router)
app.include_router(loads_router)
app.include_router(public_loads_router)


@app.get("/")
def root():
    return {"Cargo Flow": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}
