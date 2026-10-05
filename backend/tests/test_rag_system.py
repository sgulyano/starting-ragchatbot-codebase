"""Tests for how RAGSystem handles content queries (backend/rag_system.py).

Real VectorStore (temp ChromaDB) + scripted fake Ollama client. Set RUN_LIVE=1 to also run the
live smoke test against the real backend/chroma_db and the real Ollama Cloud model.
"""

import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace

import helpers
from helpers import ScriptedClient, chat_response, tool_call, make_store
from rag_system import RAGSystem


def make_config(chroma_path):
    return SimpleNamespace(
        CHUNK_SIZE=800,
        CHUNK_OVERLAP=100,
        MAX_RESULTS=5,
        MAX_HISTORY=2,
        CHROMA_PATH=chroma_path,
        EMBEDDING_MODEL="all-MiniLM-L6-v2",
        OLLAMA_API_KEY="key",
        OLLAMA_MODEL="model",
        OLLAMA_BASE_URL="https://example.invalid",
    )


class RagSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="rag_test_chroma_")
        make_store(cls.dir)  # seed the temp DB; RAGSystem reopens it below

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def setUp(self):
        self.rag = RAGSystem(make_config(self.dir))

    def script(self, *responses):
        self.rag.ai_generator.client = ScriptedClient(*responses)
        return self.rag.ai_generator.client

    def test_both_tools_registered(self):
        names = {
            d["function"]["name"] for d in self.rag.tool_manager.get_tool_definitions()
        }
        self.assertEqual(names, {"search_course_content", "get_course_outline"})

    def test_content_query_end_to_end(self):
        client = self.script(
            chat_response(
                "",
                [
                    tool_call(
                        "search_course_content",
                        {"query": "gizmo oil", "course_name": "Advanced Gizmos"},
                    )
                ],
            ),
            chat_response("Use synthetic oil."),
        )
        answer, sources = self.rag.query("How do I lubricate a gizmo?")
        self.assertEqual(answer, "Use synthetic oil.")
        self.assertEqual(
            {s["label"] for s in sources},
            {"Advanced Gizmos - Lesson 1", "Advanced Gizmos - Lesson 2"},
        )
        # the tool result reached the model on the follow-up call
        tool_msg = [
            m
            for m in client.calls[1]["messages"]
            if isinstance(m, dict) and m["role"] == "tool"
        ][0]
        self.assertIn("Gizmo lubrication", tool_msg["content"])

    def test_query_prompt_wraps_user_question(self):
        client = self.script(chat_response("hi"))
        self.rag.query("what is X?")
        self.assertIn("what is X?", client.calls[0]["messages"][1]["content"])

    def test_sources_reset_after_query(self):
        self.script(
            chat_response(
                "", [tool_call("search_course_content", {"query": "widgets"})]
            ),
            chat_response("ok"),
        )
        _, sources = self.rag.query("q")
        self.assertTrue(sources)
        self.assertEqual(self.rag.tool_manager.get_last_sources(), [])

    def test_no_sources_for_general_question(self):
        self.script(chat_response("4"))
        self.assertEqual(self.rag.query("2+2?"), ("4", []))

    def test_session_history_updated_and_fed_back(self):
        sid = self.rag.session_manager.create_session()
        self.script(chat_response("first answer"))
        self.rag.query("first q", sid)
        client = self.script(chat_response("second answer"))
        self.rag.query("second q", sid)
        self.assertIn("first answer", client.calls[0]["messages"][0]["content"])

    def test_no_match_result_still_yields_answer(self):
        self.script(
            chat_response(
                "",
                [
                    tool_call(
                        "search_course_content",
                        {"query": "x", "course_name": "Widgets", "lesson_number": 99},
                    )
                ],
            ),
            chat_response("No content found."),
        )
        answer, sources = self.rag.query("q")
        self.assertEqual(answer, "No content found.")
        self.assertEqual(sources, [])

    def test_string_lesson_number_from_model_does_not_break_query(self):
        self.script(
            chat_response(
                "",
                [
                    tool_call(
                        "search_course_content",
                        {"query": "x", "course_name": "Widgets", "lesson_number": "1"},
                    )
                ],
            ),
            chat_response("fine"),
        )
        answer, sources = self.rag.query("q")
        self.assertEqual(answer, "fine")
        self.assertTrue(sources, "string lesson_number silently matched nothing")

    def test_llm_failure_is_handled(self):
        self.script(ConnectionError("ollama unreachable"))
        try:
            answer, _ = self.rag.query("q")
        except Exception as e:  # noqa: BLE001
            self.fail(
                f"query() raised {e!r}; app.py would return HTTP 500 -> 'Query failed'"
            )
        self.assertTrue(answer)

    def test_outline_tool_flow(self):
        self.script(
            chat_response(
                "", [tool_call("get_course_outline", {"course_title": "Widgets"})]
            ),
            chat_response("outline"),
        )
        answer, _ = self.rag.query("outline of widgets")
        self.assertEqual(answer, "outline")

    def test_add_course_folder_skips_existing(self):
        # A missing folder must not raise.
        self.assertEqual(
            self.rag.add_course_folder(os.path.join(self.dir, "nope")), (0, 0)
        )


@unittest.skipUnless(
    os.environ.get("RUN_LIVE") == "1",
    "set RUN_LIVE=1 to hit the real model + real chroma_db",
)
class LiveSmokeTests(unittest.TestCase):
    """Runs from backend/ with the real config, like the server does."""

    @classmethod
    def setUpClass(cls):
        os.chdir(helpers.BACKEND_DIR)
        from config import config

        cls.rag = RAGSystem(config)

    def test_real_content_query(self):
        answer, sources = self.rag.query(
            "What does the MCP course say about why MCP is useful?"
        )
        self.assertTrue(answer.strip())
        self.assertTrue(sources, "model did not use the search tool")

    def test_real_api_endpoint(self):
        import asyncio
        import app as app_module

        resp = asyncio.run(
            app_module.query_documents(
                app_module.QueryRequest(query="Explain query expansion")
            )
        )
        self.assertTrue(resp.answer.strip())


if __name__ == "__main__":
    unittest.main()
