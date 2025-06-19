from fastapi import FastAPI
from db.session import engine, Base
from routers import users, catchment
from models import user, csvfile
from core.auth import admin_router, cleanup_expired_blacklist_entries


app = FastAPI(docs_url="/swagger-docs")

# Create tables for all models
Base.metadata.create_all(bind=engine)
# Include routers
app.include_router(users.router)
app.include_router(catchment.router)
app.include_router(admin_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"message": "Welcome to the GeoJSON backend API"}

@app.on_event("startup")
def run_blacklist_cleanup():
    cleanup_expired_blacklist_entries() 