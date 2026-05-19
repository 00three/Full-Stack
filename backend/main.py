"""FastAPI 메인 서버"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.deps import get_rag_service
from backend.routers import articles, llm, press_releases

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
app.include_router(llm.router)


@app.on_event("startup")
def warm_related_search() -> None:
    # 관련기사 첫 클릭에서 RAG 검색 모듈 import 비용이 튀지 않도록 서버 시작 때 당겨둔다.
    get_rag_service()


@app.get("/")
def root():
    return {"message": "속보생성 보조시스템 API", "docs": "/docs"}
