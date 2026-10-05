import logging
from ollama import Client
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

LLM_ERROR_FALLBACK = "Sorry, I couldn't reach the language model. Please try again."
EMPTY_FALLBACK = "I wasn't able to produce an answer. Please try rephrasing your question."

class AIGenerator:
    """Handles interactions with Ollama Cloud chat API for generating responses"""

    # Maximum sequential rounds in which the model may call tools per query
    MAX_TOOL_ROUNDS = 2
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Tool Usage:
- `search_course_content`: use **only** for questions about specific course content or detailed educational materials
- `get_course_outline`: use for questions about a course's outline, structure, syllabus, or lesson list
- You may make up to **2 sequential tool calls** per query. Use a second call only when it depends on the first call's results
  (e.g. get a lesson's title from `get_course_outline`, then `search_course_content` for that topic in other courses)
- Prefer a single tool call when it is enough; do not repeat a call that already returned what you need
- Synthesize tool results into accurate, fact-based responses
- If a tool errors, or a search yields no results after at most one retry, state this clearly and stop calling tools

Outline Queries:
- Always return the course title, the course link, and the number and title of every lesson in the course
- Do not omit or summarize lessons; list them all

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course content questions**: Search first, then answer. If the question refers to another course's lesson or topic, get the outline first, then search
- **Course outline questions**: Use the outline tool first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str, host: str):
        self.client = Client(host=host, headers={"Authorization": f"Bearer {api_key}"})
        self.model = model

        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "options": {"temperature": 0, "num_predict": 800}
        }

    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Ollama takes the system prompt as the first message
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query}
        ]

        can_use_tools = bool(tools and tool_manager)
        rounds = 0

        # Each iteration is one API request with tools available, so the model
        # can reason over the results of earlier rounds before calling again.
        for _ in range(self.MAX_TOOL_ROUNDS if can_use_tools else 1):
            response = self._chat(messages, tools)
            if response is None:
                return LLM_ERROR_FALLBACK
            message = response.message

            if not (can_use_tools and message.tool_calls):
                return message.content or (EMPTY_FALLBACK if rounds else "")

            rounds += 1
            messages.append(message)
            tool_messages, failed = self._execute_tool_calls(message.tool_calls, tool_manager)
            messages.extend(tool_messages)
            if failed:
                break

        # Round cap reached or a tool failed: one last call without tools forces a text answer
        response = self._chat(messages, None)
        if response is None:
            return LLM_ERROR_FALLBACK
        return response.message.content or EMPTY_FALLBACK

    def _chat(self, messages: List, tools: Optional[List]):
        """Make one chat request; returns None if the LLM call fails."""
        params = {**self.base_params, "messages": list(messages)}
        if tools:
            params["tools"] = tools
        try:
            return self.client.chat(**params)
        except Exception:
            logger.exception("Ollama chat request failed")
            return None

    def _execute_tool_calls(self, tool_calls, tool_manager) -> Tuple[List[dict], bool]:
        """
        Execute one round of tool calls.

        Returns:
            (tool messages in call order, whether any call raised)
        """
        tool_messages = []
        failed = False
        for tool_call in tool_calls:
            name = tool_call.function.name
            try:
                result = tool_manager.execute_tool(name, **(tool_call.function.arguments or {}))
            except Exception as e:
                logger.exception("Tool %s failed", name)
                result, failed = f"Error executing {name}: {e}", True
            tool_messages.append({"role": "tool", "content": result, "tool_name": name})
        return tool_messages, failed
