"""Tests for CourseSearchTool.execute (backend/search_tools.py)."""

import unittest
from unittest.mock import MagicMock

import helpers  # noqa: F401  (sets sys.path)
from helpers import make_store
from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from vector_store import SearchResults


def results(docs, metas):
    return SearchResults(documents=docs, metadata=metas, distances=[0.1] * len(docs))


class SearchToolUnitTests(unittest.TestCase):
    """execute() against a mocked VectorStore."""

    def setUp(self):
        self.store = MagicMock()
        self.store.get_lesson_link.return_value = "https://example.com/l1"
        self.tool = CourseSearchTool(self.store)

    def test_passes_arguments_to_store(self):
        self.store.search.return_value = results(
            ["x"], [{"course_title": "C", "lesson_number": 1}]
        )
        self.tool.execute("q", course_name="C", lesson_number=1)
        self.store.search.assert_called_once_with(
            query="q", course_name="C", lesson_number=1
        )

    def test_formats_results_with_header(self):
        self.store.search.return_value = results(
            ["alpha", "beta"],
            [
                {"course_title": "C", "lesson_number": 1},
                {"course_title": "C", "lesson_number": 2},
            ],
        )
        out = self.tool.execute("q")
        self.assertIn("[C - Lesson 1]\nalpha", out)
        self.assertIn("[C - Lesson 2]\nbeta", out)

    def test_error_is_returned_verbatim(self):
        self.store.search.return_value = SearchResults.empty("Search error: boom")
        self.assertEqual(self.tool.execute("q"), "Search error: boom")

    def test_empty_results_message_includes_filters(self):
        self.store.search.return_value = results([], [])
        out = self.tool.execute("q", course_name="C", lesson_number=3)
        self.assertEqual(out, "No relevant content found in course 'C' in lesson 3.")

    def test_empty_results_without_filters(self):
        self.store.search.return_value = results([], [])
        self.assertEqual(self.tool.execute("q"), "No relevant content found.")

    def test_last_sources_tracked_and_deduplicated(self):
        meta = {"course_title": "C", "lesson_number": 1}
        self.store.search.return_value = results(["a", "b"], [meta, meta])
        self.tool.execute("q")
        self.assertEqual(
            self.tool.last_sources,
            [{"label": "C - Lesson 1", "url": "https://example.com/l1"}],
        )
        self.store.get_lesson_link.assert_called_once()  # cached per (course, lesson)

    def test_chunk_without_lesson_number(self):
        self.store.search.return_value = results(
            ["a"], [{"course_title": "C", "lesson_number": None}]
        )
        out = self.tool.execute("q")
        self.assertTrue(out.startswith("[C]\n"))
        self.assertEqual(self.tool.last_sources, [{"label": "C", "url": None}])

    def test_lesson_number_zero_is_reported_in_empty_message(self):
        # Lesson 0 is a valid lesson in the docs format ("Lesson 0: ...").
        self.store.search.return_value = results([], [])
        out = self.tool.execute("q", lesson_number=0)
        self.assertIn("lesson 0", out)

    def test_definition_shape(self):
        d = self.tool.get_tool_definition()
        self.assertEqual(d["type"], "function")
        self.assertEqual(d["function"]["name"], "search_course_content")
        self.assertEqual(d["function"]["parameters"]["required"], ["query"])

    def test_tool_manager_registers_and_executes(self):
        self.store.search.return_value = results(
            ["a"], [{"course_title": "C", "lesson_number": 1}]
        )
        tm = ToolManager()
        tm.register_tool(self.tool)
        tm.register_tool(CourseOutlineTool(self.store))
        self.assertEqual(
            {d["function"]["name"] for d in tm.get_tool_definitions()},
            {"search_course_content", "get_course_outline"},
        )
        self.assertIn(
            "[C - Lesson 1]", tm.execute_tool("search_course_content", query="q")
        )
        self.assertTrue(tm.get_last_sources())
        tm.reset_sources()
        self.assertEqual(tm.get_last_sources(), [])

    def test_unknown_kwarg_raises(self):
        # AIGenerator splats model-provided arguments straight into execute();
        # documents the current behaviour when the model invents a parameter.
        with self.assertRaises(TypeError):
            self.tool.execute(query="q", bogus=1)


class SearchToolIntegrationTests(unittest.TestCase):
    """execute() against a real (temp) ChromaDB store."""

    @classmethod
    def setUpClass(cls):
        cls.tool = CourseSearchTool(make_store())

    def test_unfiltered_search_finds_relevant_chunk(self):
        out = self.tool.execute("how to lubricate gizmo gears")
        self.assertIn("Gizmo lubrication", out)

    def test_fuzzy_course_name_resolves(self):
        out = self.tool.execute("anything", course_name="Widgets")
        self.assertIn("[Intro to Widgets", out)
        self.assertNotIn("Advanced Gizmos", out)

    def test_lesson_filter(self):
        out = self.tool.execute(
            "anything", course_name="Intro to Widgets", lesson_number=2
        )
        self.assertIn("Lesson 2", out)
        self.assertNotIn("Lesson 1", out)

    def test_lesson_filter_alone(self):
        out = self.tool.execute("anything", lesson_number=1)
        self.assertNotIn("Lesson 2", out)

    def test_sources_have_links(self):
        self.tool.execute(
            "widget calibration", course_name="Intro to Widgets", lesson_number=2
        )
        self.assertEqual(
            self.tool.last_sources,
            [
                {
                    "label": "Intro to Widgets - Lesson 2",
                    "url": "https://example.com/Intro to Widgets/2",
                }
            ],
        )

    def test_missing_lesson_gives_no_content_message(self):
        out = self.tool.execute(
            "anything", course_name="Intro to Widgets", lesson_number=99
        )
        self.assertIn("No relevant content found", out)

    def test_string_lesson_number_still_finds_content(self):
        # LLMs sometimes send "2" instead of 2. Chroma's where-filter is type-strict.
        out = self.tool.execute(
            "anything", course_name="Intro to Widgets", lesson_number="2"
        )
        self.assertNotIn("No relevant content found", out)
        self.assertNotIn("error", out.lower())


if __name__ == "__main__":
    unittest.main()
