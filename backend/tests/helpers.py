"""Shared fakes and fixtures for the backend tests (stdlib unittest, no pytest needed)."""

import os
import sys
import tempfile
from types import SimpleNamespace

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from models import Course, Lesson, CourseChunk  # noqa: E402
from vector_store import VectorStore  # noqa: E402


def tool_call(name, arguments):
    """Mimic an ollama ToolCall: .function.name / .function.arguments"""
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))


def chat_response(content="", tool_calls=None):
    """Mimic an ollama ChatResponse: .message.content / .message.tool_calls"""
    return SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=tool_calls)
    )


class ScriptedClient:
    """Fake ollama Client: returns queued responses (or raises queued exceptions) and records calls."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class RecordingToolManager:
    """Fake ToolManager that records execute_tool calls.

    `result` is a string, or a {tool_name: string} map. `raises` is {tool_name: Exception}.
    """

    def __init__(self, result="TOOL RESULT", raises=None):
        self.result = result
        self.raises = raises or {}
        self.executed = []

    def execute_tool(self, name, **kwargs):
        self.executed.append((name, kwargs))
        if name in self.raises:
            raise self.raises[name]
        return self.result[name] if isinstance(self.result, dict) else self.result


def roles(messages):
    """Role of each message; non-dict messages (ollama Message objects) are the assistant."""
    return [m["role"] if isinstance(m, dict) else "assistant" for m in messages]


def make_store(path=None):
    """Real VectorStore (local embeddings) in a temp dir, seeded with two tiny courses."""
    path = path or tempfile.mkdtemp(prefix="rag_test_chroma_")
    store = VectorStore(path, "all-MiniLM-L6-v2", max_results=5)
    courses = [
        (
            "Intro to Widgets",
            "Widgets are small configurable gadgets used for testing.",
            "Widget calibration requires a steady hand and a tuning fork.",
        ),
        (
            "Advanced Gizmos",
            "Gizmos are complex mechanical devices with many gears.",
            "Gizmo lubrication should use synthetic oil every ten hours.",
        ),
    ]
    for title, l1, l2 in courses:
        store.add_course_metadata(
            Course(
                title=title,
                course_link=f"https://example.com/{title}",
                instructor="Tester",
                lessons=[
                    Lesson(
                        lesson_number=1,
                        title="Basics",
                        lesson_link=f"https://example.com/{title}/1",
                    ),
                    Lesson(
                        lesson_number=2,
                        title="Details",
                        lesson_link=f"https://example.com/{title}/2",
                    ),
                ],
            )
        )
        store.add_course_content(
            [
                CourseChunk(
                    content=l1, course_title=title, lesson_number=1, chunk_index=0
                ),
                CourseChunk(
                    content=l2, course_title=title, lesson_number=2, chunk_index=1
                ),
            ]
        )
    return store
