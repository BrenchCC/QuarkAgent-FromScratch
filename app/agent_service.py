import os
import sys
import json
import queue
import logging
import threading

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Callable

sys.path.append(os.getcwd())

from quarkagent.agent import QuarkAgent
from quarkagent.tools import get_registered_tools

from app.settings import AppSettings

logger = logging.getLogger(__name__)


class AgentService:
    """Bridge web routes with the existing QuarkAgent runtime."""

    def __init__(self, settings: AppSettings):
        """
        Initialize the agent service.

        Args:
            settings: Web application settings.
        """
        self.settings = settings

    @staticmethod
    def _utc_iso() -> str:
        """
        Build UTC ISO timestamp string.

        Args:
            None.

        Returns:
            ISO 8601 timestamp.
        """
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _format_history(history: List[Dict[str, str]], limit_turns: int = 10) -> str:
        """
        Format history in the same style as CLI path.

        Args:
            history: Session history entries.
            limit_turns: Number of recent turns to include.

        Returns:
            Formatted history string.
        """
        if not history:
            return ""

        recent_items = history[-(limit_turns * 2):]
        lines = ["Conversation history (most recent last):"]
        for item in recent_items:
            role = item.get("role", "")
            content = item.get("content", "")
            lines.append(f"{role}: {content}")

        return "\n".join(lines) + "\n\n"

    def _build_agent(self) -> QuarkAgent:
        """
        Build a configured QuarkAgent instance.

        Args:
            None.

        Returns:
            Ready-to-run QuarkAgent.
        """
        if not self.settings.llm_api_key:
            raise RuntimeError("Missing LLM_API_KEY for web service.")

        agent = QuarkAgent(
            model = self.settings.llm_model,
            api_key = self.settings.llm_api_key,
            base_url = self.settings.llm_api_base,
            temperature = self.settings.llm_temperature,
            top_p = self.settings.llm_top_p,
            use_reflector = self.settings.use_reflector,
        )

        tool_names = self.settings.default_tools or sorted(get_registered_tools().keys())
        agent.tools = []
        for tool_name in tool_names:
            agent.load_builtin_tool(tool_name)

        return agent

    @staticmethod
    def _build_event(event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a unified event dictionary.

        Args:
            event_type: Event type string.
            data: Event payload.

        Returns:
            Event dictionary.
        """
        return {
            "type": event_type,
            "timestamp": AgentService._utc_iso(),
            "data": data,
        }

    def get_available_tools(self) -> List[str]:
        """
        Get available tool names.

        Args:
            None.

        Returns:
            Sorted tool name list.
        """
        return sorted(get_registered_tools().keys())

    def run_sync(self, history: List[Dict[str, str]], message: str, max_iterations: int = 10) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Execute synchronous chat request and collect lifecycle events.

        Args:
            history: Existing session history.
            message: Current user message.
            max_iterations: Maximum tool-call iterations.

        Returns:
            Tuple of final answer and collected events.
        """
        agent = self._build_agent()
        query = self._format_history(history) + message
        events: List[Dict[str, Any]] = []

        def push_event(event_type: str, data: Dict[str, Any]) -> None:
            events.append(self._build_event(event_type, data))

        def status_callback(status_text: str) -> None:
            push_event("status", {"message": status_text})

        def tool_callback(event: str, name: str, payload: Dict[str, Any]) -> None:
            if event == "status":
                push_event(
                    "tool_start",
                    {
                        "tool": name,
                        "arguments": payload.get("arguments", {}),
                    },
                )
                return

            if event == "end":
                push_event(
                    "tool_end",
                    {
                        "tool": name,
                        "result": payload.get("result", payload.get("error")),
                    },
                )

        answer = agent.run_with_tools(
            query,
            max_iterations = max_iterations,
            tool_callback = tool_callback,
            status_callback = status_callback,
        )

        push_event("final", {"answer": answer})
        push_event("done", {"message": "stream closed"})
        return answer, events

    def run_stream(
        self,
        history: List[Dict[str, str]],
        message: str,
        emit_event: Callable[[Dict[str, Any]], None],
        max_iterations: int = 10,
    ) -> str:
        """
        Execute chat request and emit streaming lifecycle events.

        Args:
            history: Existing session history.
            message: Current user message.
            emit_event: Event callback invoked on each event.
            max_iterations: Maximum tool-call iterations.

        Returns:
            Final answer string.
        """
        agent = self._build_agent()
        query = self._format_history(history) + message

        event_queue: "queue.Queue[Dict[str, Any] | None]" = queue.Queue()

        def status_callback(status_text: str) -> None:
            event_queue.put(self._build_event("status", {"message": status_text}))

        def tool_callback(event: str, name: str, payload: Dict[str, Any]) -> None:
            if event == "status":
                event_queue.put(
                    self._build_event(
                        "tool_start",
                        {
                            "tool": name,
                            "arguments": payload.get("arguments", {}),
                        },
                    )
                )
                return

            if event == "end":
                event_queue.put(
                    self._build_event(
                        "tool_end",
                        {
                            "tool": name,
                            "result": payload.get("result", payload.get("error")),
                        },
                    )
                )

        answer_holder = {"value": ""}
        error_holder = {"value": ""}

        def run_agent() -> None:
            try:
                answer_holder["value"] = agent.run_with_tools(
                    query,
                    max_iterations = max_iterations,
                    tool_callback = tool_callback,
                    status_callback = status_callback,
                )
            except Exception as exc:
                error_holder["value"] = str(exc)
            finally:
                event_queue.put(None)

        worker = threading.Thread(target = run_agent, daemon = True)
        worker.start()

        while True:
            next_item = event_queue.get()
            if next_item is None:
                break
            emit_event(next_item)

        if error_holder["value"]:
            emit_event(self._build_event("error", {"message": error_holder["value"]}))
            return ""

        final_answer = answer_holder["value"]
        emit_event(self._build_event("final", {"answer": final_answer}))
        return final_answer

    @staticmethod
    def event_to_sse(event: Dict[str, Any]) -> str:
        """
        Convert event dictionary to SSE frame text.

        Args:
            event: Event dictionary to serialize.

        Returns:
            Formatted SSE frame.
        """
        event_name = event.get("type", "status")
        payload = json.dumps(event, ensure_ascii = False)
        return f"event: {event_name}\ndata: {payload}\n\n"
