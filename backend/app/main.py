from fastapi import FastAPI

from app.modules.auth.router import router as auth_router
from app.modules.audit.router import router as audit_router
from app.modules.property.router import router as property_router
from app.modules.residents.router import router as resident_router
from app.modules.rbac.router import router as rbac_router
from app.modules.society.router import router as society_router

app = FastAPI(
    title="Society Management Platform API",
    description="API for Society Management, Property Master Data, and Residents Master Data",
    version="1.0.0",
)

app.include_router(society_router)
app.include_router(property_router)
app.include_router(resident_router)
app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(rbac_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}