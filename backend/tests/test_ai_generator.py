"""Tests that AIGenerator calls the search tool correctly (backend/ai_generator.py). Ollama is mocked."""
import unittest

import helpers  # noqa: F401  (sets sys.path)
from helpers import ScriptedClient, RecordingToolManager, chat_response, tool_call, roles
from ai_generator import AIGenerator

TOOLS = [{"type": "function", "function": {"name": "search_course_content"}}]


def make_gen(*responses):
    gen = AIGenerator("key", "model", "https://example.invalid")
    gen.client = ScriptedClient(*responses)
    return gen


class ToolCallingTests(unittest.TestCase):
    def test_first_call_includes_tools_and_system_prompt(self):
        gen = make_gen(chat_response("direct"))
        gen.generate_response("q", tools=TOOLS, tool_manager=RecordingToolManager())
        first = gen.client.calls[0]
        self.assertEqual(first["tools"], TOOLS)
        self.assertEqual(first["messages"][0]["role"], "system")
        self.assertEqual(first["messages"][1], {"role": "user", "content": "q"})

    def test_no_tool_call_returns_direct_answer(self):
        gen = make_gen(chat_response("direct"))
        tm = RecordingToolManager()
        self.assertEqual(gen.generate_response("q", tools=TOOLS, tool_manager=tm), "direct")
        self.assertEqual(len(gen.client.calls), 1)
        self.assertEqual(tm.executed, [])

    def test_tool_call_is_executed_with_model_arguments(self):
        args = {"query": "embeddings", "course_name": "MCP", "lesson_number": 2}
        gen = make_gen(chat_response("", [tool_call("search_course_content", args)]),
                       chat_response("final"))
        tm = RecordingToolManager()
        out = gen.generate_response("q", tools=TOOLS, tool_manager=tm)
        self.assertEqual(out, "final")
        self.assertEqual(tm.executed, [("search_course_content", args)])

    def test_followup_keeps_tools_and_correct_message_order(self):
        gen = make_gen(chat_response("", [tool_call("search_course_content", {"query": "x"})]),
                       chat_response("final"))
        gen.generate_response("q", tools=TOOLS, tool_manager=RecordingToolManager("RESULT"))
        self.assertEqual(len(gen.client.calls), 2)
        second = gen.client.calls[1]
        self.assertEqual(second["tools"], TOOLS)
        msgs = second["messages"]
        self.assertEqual(roles(msgs), ["system", "user", "assistant", "tool"])
        self.assertEqual(msgs[3], {"role": "tool", "content": "RESULT", "tool_name": "search_course_content"})

    def test_multiple_tool_calls_all_executed(self):
        gen = make_gen(chat_response("", [tool_call("search_course_content", {"query": "a"}),
                                          tool_call("get_course_outline", {"course_title": "b"})]),
                       chat_response("final"))
        tm = RecordingToolManager()
        gen.generate_response("q", tools=TOOLS, tool_manager=tm)
        self.assertEqual([n for n, _ in tm.executed], ["search_course_content", "get_course_outline"])
        self.assertEqual(sum(1 for m in gen.client.calls[1]["messages"]
                             if isinstance(m, dict) and m["role"] == "tool"), 2)

    def test_tool_calls_ignored_without_tool_manager(self):
        gen = make_gen(chat_response("text", [tool_call("search_course_content", {"query": "x"})]))
        self.assertEqual(gen.generate_response("q", tools=TOOLS), "text")

    def test_no_tools_param_when_none_given(self):
        gen = make_gen(chat_response("hi"))
        gen.generate_response("q")
        self.assertNotIn("tools", gen.client.calls[0])

    def test_history_injected_into_system_prompt(self):
        gen = make_gen(chat_response("hi"))
        gen.generate_response("q", conversation_history="User: a\nAssistant: b")
        self.assertIn("Previous conversation:\nUser: a", gen.client.calls[0]["messages"][0]["content"])


OUTLINE = tool_call("get_course_outline", {"course_title": "X"})
SEARCH = tool_call("search_course_content", {"query": "topic"})


class SequentialToolCallingTests(unittest.TestCase):
    """Up to 2 tool rounds, each its own API request; a final tools-free call produces the answer."""

    def test_two_round_chain(self):
        gen = make_gen(chat_response("", [OUTLINE]), chat_response("", [SEARCH]), chat_response("final"))
        tm = RecordingToolManager({"get_course_outline": "LESSON 4: Topic",
                                   "search_course_content": "COURSE Y"})
        out = gen.generate_response("q", tools=TOOLS, tool_manager=tm)
        self.assertEqual(out, "final")
        self.assertEqual(tm.executed, [("get_course_outline", {"course_title": "X"}),
                                       ("search_course_content", {"query": "topic"})])
        calls = gen.client.calls
        self.assertEqual(len(calls), 3)
        self.assertIn("tools", calls[0])
        self.assertIn("tools", calls[1])
        self.assertNotIn("tools", calls[2])
        self.assertEqual(roles(calls[2]["messages"]),
                         ["system", "user", "assistant", "tool", "assistant", "tool"])

    def test_second_request_sees_first_round_result(self):
        gen = make_gen(chat_response("", [OUTLINE]), chat_response("", [SEARCH]), chat_response("final"))
        tm = RecordingToolManager({"get_course_outline": "LESSON 4: Topic",
                                   "search_course_content": "COURSE Y"})
        gen.generate_response("q", tools=TOOLS, tool_manager=tm)
        second_tool_msgs = [m for m in gen.client.calls[1]["messages"] if isinstance(m, dict) and m["role"] == "tool"]
        self.assertEqual([m["content"] for m in second_tool_msgs], ["LESSON 4: Topic"])
        third_tool_msgs = [m for m in gen.client.calls[2]["messages"] if isinstance(m, dict) and m["role"] == "tool"]
        self.assertEqual([m["content"] for m in third_tool_msgs], ["LESSON 4: Topic", "COURSE Y"])

    def test_stops_after_one_round_when_no_more_tool_calls(self):
        gen = make_gen(chat_response("", [SEARCH]), chat_response("final"))
        tm = RecordingToolManager()
        self.assertEqual(gen.generate_response("q", tools=TOOLS, tool_manager=tm), "final")
        self.assertEqual(len(gen.client.calls), 2)
        self.assertEqual(len(tm.executed), 1)

    def test_round_cap_forces_tools_free_final_answer(self):
        gen = make_gen(chat_response("", [OUTLINE]), chat_response("", [SEARCH]),
                       chat_response("answer after cap"))
        tm = RecordingToolManager()
        self.assertEqual(gen.generate_response("q", tools=TOOLS, tool_manager=tm), "answer after cap")
        self.assertEqual(len(tm.executed), 2)
        self.assertNotIn("tools", gen.client.calls[2])

    def test_model_still_wanting_tools_after_cap_gets_non_empty_text(self):
        gen = make_gen(chat_response("", [OUTLINE]), chat_response("", [SEARCH]),
                       chat_response("", [SEARCH]))
        tm = RecordingToolManager()
        out = gen.generate_response("q", tools=TOOLS, tool_manager=tm)
        self.assertTrue(out)
        self.assertEqual(len(gen.client.calls), 3)
        self.assertEqual(len(tm.executed), 2)

    def test_multiple_tool_calls_in_one_response_count_as_one_round(self):
        gen = make_gen(chat_response("", [OUTLINE, SEARCH]), chat_response("", [SEARCH]),
                       chat_response("final"))
        tm = RecordingToolManager()
        self.assertEqual(gen.generate_response("q", tools=TOOLS, tool_manager=tm), "final")
        self.assertEqual(len(tm.executed), 3)
        self.assertEqual(len(gen.client.calls), 3)

    def test_tool_exception_stops_further_tool_use_and_reports_error(self):
        gen = make_gen(chat_response("", [OUTLINE]), chat_response("sorry, that failed"))
        tm = RecordingToolManager(raises={"get_course_outline": RuntimeError("chroma exploded")})
        out = gen.generate_response("q", tools=TOOLS, tool_manager=tm)
        self.assertEqual(out, "sorry, that failed")
        self.assertEqual(len(gen.client.calls), 2)
        self.assertNotIn("tools", gen.client.calls[1])
        tool_msg = gen.client.calls[1]["messages"][-1]
        self.assertEqual(tool_msg["role"], "tool")
        self.assertIn("chroma exploded", tool_msg["content"])

    def test_tool_exception_in_second_round_still_answers(self):
        gen = make_gen(chat_response("", [OUTLINE]), chat_response("", [SEARCH]), chat_response("partial"))
        tm = RecordingToolManager(raises={"search_course_content": RuntimeError("boom")})
        self.assertEqual(gen.generate_response("q", tools=TOOLS, tool_manager=tm), "partial")
        self.assertEqual(len(gen.client.calls), 3)
        self.assertNotIn("tools", gen.client.calls[2])

    def test_error_string_result_does_not_stop_the_chain(self):
        gen = make_gen(chat_response("", [SEARCH]), chat_response("", [SEARCH]), chat_response("final"))
        tm = RecordingToolManager("No relevant content found.")
        self.assertEqual(gen.generate_response("q", tools=TOOLS, tool_manager=tm), "final")
        self.assertIn("tools", gen.client.calls[1])
        self.assertEqual(len(tm.executed), 2)

    def test_llm_error_in_second_round_returns_text_not_exception(self):
        gen = make_gen(chat_response("", [OUTLINE]), ConnectionError("down"))
        out = gen.generate_response("q", tools=TOOLS, tool_manager=RecordingToolManager())
        self.assertTrue(out)

    def test_empty_final_content_after_tools_returns_fallback(self):
        gen = make_gen(chat_response("", [SEARCH]), chat_response(None))
        self.assertTrue(gen.generate_response("q", tools=TOOLS, tool_manager=RecordingToolManager()))


class FailureModeTests(unittest.TestCase):
    """What happens when the model/tool misbehaves. Anything that raises here becomes HTTP 500 -> 'Query failed'."""

    def test_unknown_argument_from_model_does_not_raise(self):
        from search_tools import ToolManager, CourseSearchTool
        from unittest.mock import MagicMock
        from vector_store import SearchResults
        store = MagicMock()
        store.search.return_value = SearchResults([], [], [])
        tm = ToolManager()
        tm.register_tool(CourseSearchTool(store))
        gen = make_gen(chat_response("", [tool_call("search_course_content", {"query": "x", "topic": "y"})]),
                       chat_response("final"))
        self.assertEqual(gen.generate_response("q", tools=TOOLS, tool_manager=tm), "final")

    def test_tool_exception_does_not_raise(self):
        class Boom(RecordingToolManager):
            def execute_tool(self, name, **kw):
                raise RuntimeError("chroma exploded")
        gen = make_gen(chat_response("", [tool_call("search_course_content", {"query": "x"})]),
                       chat_response("sorry"))
        try:
            out = gen.generate_response("q", tools=TOOLS, tool_manager=Boom())
        except Exception as e:  # noqa: BLE001
            self.fail(f"tool failure escaped generate_response: {e!r}")
        self.assertIsInstance(out, str)

    def test_llm_exception_does_not_raise(self):
        gen = make_gen(ConnectionError("ollama unreachable"))
        try:
            out = gen.generate_response("q", tools=TOOLS, tool_manager=RecordingToolManager())
        except Exception as e:  # noqa: BLE001
            self.fail(f"LLM failure escaped generate_response: {e!r}")
        self.assertTrue(out)

    def test_followup_that_requests_another_tool_returns_non_empty_text(self):
        gen = make_gen(chat_response("", [tool_call("search_course_content", {"query": "x"})]),
                       chat_response("", [tool_call("search_course_content", {"query": "y"})]))
        out = gen.generate_response("q", tools=TOOLS, tool_manager=RecordingToolManager())
        self.assertTrue(out, "empty answer returned when the follow-up asks for another tool")

    def test_none_content_becomes_empty_string_not_error(self):
        gen = make_gen(chat_response(None))
        self.assertEqual(gen.generate_response("q"), "")


if __name__ == "__main__":
    unittest.main()
