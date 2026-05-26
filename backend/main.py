# smart-stock/backend/main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from backend.api import signals, backtest, monitor, data
from backend.engine.data.schema import init_db

app = FastAPI(title="SmartStock API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signals.router)
app.include_router(backtest.router)
app.include_router(monitor.router)
app.include_router(data.router)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---- 生产环境：托管前端静态文件 ----
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
FRONTEND_DIR = os.path.abspath(FRONTEND_DIR)

if os.path.isdir(FRONTEND_DIR):
    # 托管 assets 等静态资源
    assets_dir = os.path.join(FRONTEND_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str = ""):
        """SPA fallback: 所有非 /api/ 请求返回 index.html"""
        file_path = os.path.join(FRONTEND_DIR, full_path) if full_path else ""
        if file_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
