"""FastAPI 应用入口。"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import history, prediction, training, parlay

app = FastAPI(
    title="MyMoltbot API",
    description="足彩赔率分析与智能预测系统",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(history.router)
app.include_router(prediction.router)
app.include_router(training.router)
app.include_router(parlay.router)


@app.get("/api/health")
def health():
    return {"ok": True, "version": "2.0.0"}


def main():
    import uvicorn
    port = int(os.environ.get("API_PORT", "8000"))
    host = os.environ.get("API_HOST", "0.0.0.0")
    uvicorn.run("api.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
