"""Shared pytest fixtures. API tests use a standalone FastAPI app wired to a mocked RAGSystem,
so importing backend/app.py (static mount, real RAGSystem, startup loading) is never needed."""
from typing import List, Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class Source(BaseModel):
    label: str
    url: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]
    session_id: str


class CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


def create_test_app(rag_system) -> FastAPI:
    """Mirror of the endpoints in backend/app.py, minus static files and startup loading."""
    app = FastAPI(title="Course Materials RAG System (test)")

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id or rag_system.session_manager.create_session()
            answer, sources = rag_system.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = rag_system.get_course_analytics()
            return CourseStats(total_courses=analytics["total_courses"],
                               course_titles=analytics["course_titles"])
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/session/{session_id}")
    async def delete_session(session_id: str):
        rag_system.session_manager.delete_session(session_id)
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return "<html><body>RAG test index</body></html>"

    return app


@pytest.fixture
def sample_sources():
    return [{"label": "Intro to Widgets - Lesson 1", "url": "https://example.com/widgets/1"},
            {"label": "Advanced Gizmos - Lesson 2", "url": None}]


@pytest.fixture
def sample_analytics():
    return {"total_courses": 2, "course_titles": ["Intro to Widgets", "Advanced Gizmos"]}


@pytest.fixture
def mock_rag_system(sample_sources, sample_analytics):
    rag = MagicMock()
    rag.session_manager.create_session.return_value = "session_1"
    rag.query.return_value = ("Widgets are gadgets.", sample_sources)
    rag.get_course_analytics.return_value = sample_analytics
    return rag


@pytest.fixture
def client(mock_rag_system):
    return TestClient(create_test_app(mock_rag_system))
