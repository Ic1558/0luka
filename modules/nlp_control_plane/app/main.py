"""
NLP Control Plane - FastAPI Application
=======================================
Slim app factory. Business logic lives in core/.

Entrypoint: uvicorn modules.nlp_control_plane.app.main:app --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import chat, gate, status

# ============================================================
# App Factory
# ============================================================

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="NLP Control Plane",
        description="Natural language interface for task submission (translate & forward only)",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routers
    app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
    app.include_router(gate.router, prefix="/api/v1/gate", tags=["gate"])
    app.include_router(status.router, prefix="/api/v1", tags=["status"])

    @app.get("/")
    async def root():
        return {"service": "nlp_control_plane", "version": "1.0.0"}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


# Module-level app instance for uvicorn
app = create_app()
