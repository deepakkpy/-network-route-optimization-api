from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from app.database import Base, engine
import app.models  # noqa: F401
from app.routers import nodes, edges, routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Network Route Optimization API",
    description="REST API for network graph management and shortest path queries",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid request", "details": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


app.include_router(nodes.router, prefix="/nodes", tags=["nodes"])
app.include_router(edges.router, prefix="/edges", tags=["edges"])
app.include_router(routes.router, prefix="/routes", tags=["routes"])


@app.get("/")
def root():
    return {"message": "Network Route Optimization API", "docs": "/docs"}
