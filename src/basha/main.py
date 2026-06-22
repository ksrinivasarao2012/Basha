import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from basha.api.routes import router as api_router
from basha.core.logging import setup_logging, RequestLoggingMiddleware

# Path to the static web UI (client/web/index.html), relative to the repo root.
_WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "client", "web")

# 1. Setup structured logging
setup_logging()

# 2. Initialize the FastAPI app
app = FastAPI(
    title="Basha API",
    description="Multilingual Text-to-Speech & Localization Service",
    version="1.0.0"
)

# 3. Add Request Logging Middleware
app.add_middleware(RequestLoggingMiddleware)

# 4. Include our synthesis and health check endpoints
app.include_router(api_router)

# 5. Serve the web UI at the root URL (/). API docs remain at /docs.
@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse(os.path.join(_WEB_DIR, "index.html"))