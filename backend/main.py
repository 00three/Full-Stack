"""FastAPI 메인 서버"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import press_releases, articles

app = FastAPI(title="속보생성 보조시스템 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(press_releases.router)
app.include_router(articles.router)


@app.get("/")
def root():
    return {"message": "속보생성 보조시스템 API", "docs": "/docs"}
