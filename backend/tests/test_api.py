"""API endpoint tests against the test app from conftest.py (mocked RAGSystem)."""
import pytest

pytestmark = pytest.mark.api


class TestQueryEndpoint:
    def test_query_without_session_creates_one(self, client, mock_rag_system, sample_sources):
        r = client.post("/api/query", json={"query": "What are widgets?"})
        assert r.status_code == 200
        body = r.json()
        assert body["answer"] == "Widgets are gadgets."
        assert body["session_id"] == "session_1"
        assert body["sources"] == sample_sources
        mock_rag_system.session_manager.create_session.assert_called_once()
        mock_rag_system.query.assert_called_once_with("What are widgets?", "session_1")

    def test_query_with_session_reuses_it(self, client, mock_rag_system):
        r = client.post("/api/query", json={"query": "hi", "session_id": "abc"})
        assert r.status_code == 200
        assert r.json()["session_id"] == "abc"
        mock_rag_system.session_manager.create_session.assert_not_called()
        mock_rag_system.query.assert_called_once_with("hi", "abc")

    def test_missing_query_is_422(self, client):
        assert client.post("/api/query", json={"session_id": "abc"}).status_code == 422

    def test_invalid_json_body_is_422(self, client):
        assert client.post("/api/query", content="nope",
                           headers={"Content-Type": "application/json"}).status_code == 422

    def test_rag_failure_is_500(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("llm down")
        r = client.post("/api/query", json={"query": "x"})
        assert r.status_code == 500
        assert "llm down" in r.json()["detail"]

    def test_wrong_method_is_405(self, client):
        assert client.get("/api/query").status_code == 405


class TestCoursesEndpoint:
    def test_returns_stats(self, client, sample_analytics):
        r = client.get("/api/courses")
        assert r.status_code == 200
        assert r.json() == sample_analytics

    def test_empty_catalog(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {"total_courses": 0, "course_titles": []}
        assert client.get("/api/courses").json() == {"total_courses": 0, "course_titles": []}

    def test_failure_is_500(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("chroma broke")
        r = client.get("/api/courses")
        assert r.status_code == 500
        assert "chroma broke" in r.json()["detail"]


class TestSessionEndpoint:
    def test_delete_is_idempotent(self, client, mock_rag_system):
        for _ in range(2):
            r = client.delete("/api/session/abc")
            assert r.status_code == 200 and r.json() == {"status": "ok"}
        assert mock_rag_system.session_manager.delete_session.call_count == 2


class TestRoot:
    def test_root_serves_html(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
