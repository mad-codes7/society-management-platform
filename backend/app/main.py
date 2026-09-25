from fastapi import FastAPI

from app.modules.society.router import router as society_router


app = FastAPI(
    title="Society Management Platform API",
    version="1.0.0",
)


app.include_router(society_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}