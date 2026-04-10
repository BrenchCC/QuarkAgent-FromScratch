import os
import sys
import json
import queue
import logging
import threading

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.append(os.getcwd())

from quarkagent.agent import QuarkAgent
from quarkagent.subagent import build_subagent_tool
from quarkagent.skills import SkillManager, build_skill_command_response
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
        self._active_stop_events: Dict[str, threading.Event] = {}
        self._lock = threading.RLock()

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

        skill_manager = self._build_skill_manager()
        agent = QuarkAgent(
            model = self.settings.llm_model,
            api_key = self.settings.llm_api_key,
            base_url = self.settings.llm_api_base,
            temperature = self.settings.llm_temperature,
            top_p = self.settings.llm_top_p,
            system_skills = skill_manager.get_enabled_system_skills(),
            skill_manager = skill_manager,
            model_identifier = self.settings.llm_identifier or None,
            use_reflector = self.settings.use_reflector,
        )
        agent.agent_scope = "main"

        tool_names = self.settings.default_tools or sorted(get_registered_tools().keys())
        agent.tools = []
        for tool_name in tool_names:
            if tool_name == "skills":
                continue
            agent.load_builtin_tool(tool_name)

        if self.settings.enable_custom_skill_tool:
            agent.add_tool(skill_manager.build_skills_tool())

        if self.settings.enable_subagent_tool:
            agent.add_tool(
                build_subagent_tool(
                    agent,
                    default_max_iterations = self.settings.subagent_max_iterations,
                )
            )

        return agent

    def _build_skill_manager(self) -> SkillManager:
        """
        Build the shared skill manager for the current settings.

        Args:
            None.

        Returns:
            Configured skill manager instance.
        """
        return SkillManager(
            system_skills_dir = self.settings.system_skills_dir,
            custom_skills_dir = self.settings.custom_skills_dir,
            default_system_skills = self.settings.default_system_skills,
            enable_system_skills = self.settings.enable_system_skills,
            enable_custom_skill_tool = self.settings.enable_custom_skill_tool,
        )

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

    def _start_session_run(self, session_id: Optional[str]) -> Optional[threading.Event]:
        """
        Register a stop event for an active session run.

        Args:
            session_id: Session identifier for the active run.

        Returns:
            Stop event for the run, or `None`.
        """
        if not session_id:
            return None

        stop_event = threading.Event()
        with self._lock:
            self._active_stop_events[session_id] = stop_event
        return stop_event

    def _finish_session_run(
        self,
        session_id: Optional[str],
        stop_event: Optional[threading.Event]
    ) -> None:
        """
        Remove the stop event for a completed session run.

        Args:
            session_id: Session identifier for the completed run.
            stop_event: Stop event created for the run.

        Returns:
            None.
        """
        if not session_id or not stop_event:
            return

        with self._lock:
            current_event = self._active_stop_events.get(session_id)
            if current_event is stop_event:
                self._active_stop_events.pop(session_id, None)

    def request_stop(self, session_id: str) -> bool:
        """
        Request that an active session stops at the next safe boundary.

        Args:
            session_id: Session identifier to stop.

        Returns:
            Whether an active session run was found.
        """
        with self._lock:
            stop_event = self._active_stop_events.get(session_id)

        if not stop_event:
            return False

        stop_event.set()
        return True

    def _build_local_skill_response(self, message: str) -> Optional[str]:
        """
        Resolve a local `/skills` command without invoking the LLM.

        Args:
            message: Raw user message.

        Returns:
            Rendered response text or `None`.
        """
        skill_result = build_skill_command_response(self._build_skill_manager(), message)
        if not skill_result:
            return None
        return skill_result.body

    def get_available_tools(self) -> List[str]:
        """
        Get available tool names.

        Args:
            None.

        Returns:
            Sorted tool name list.
        """
        available_tools = sorted(get_registered_tools().keys())
        if self.settings.enable_custom_skill_tool:
            available_tools.append("skills")
        if self.settings.enable_subagent_tool:
            available_tools.append("subagent")
        return sorted(set(available_tools))

    def get_available_skills(self) -> List[Dict[str, Any]]:
        """
        Get available skills across all namespaces.

        Args:
            None.

        Returns:
            Serialized skill metadata list.
        """
        skill_manager = self._build_skill_manager()
        return skill_manager.list_skill_payloads()

    def run_sync(
        self,
        history: List[Dict[str, str]],
        message: str,
        max_iterations: int = 10,
        session_id: Optional[str] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Execute synchronous chat request and collect lifecycle events.

        Args:
            history: Existing session history.
            message: Current user message.
            max_iterations: Maximum tool-call iterations.
            session_id: Optional session identifier for stop control.

        Returns:
            Tuple of final answer and collected events.
        """
        events: List[Dict[str, Any]] = []

        def push_event(event_type: str, data: Dict[str, Any]) -> None:
            events.append(self._build_event(event_type, data))

        local_skill_response = self._build_local_skill_response(message)
        if local_skill_response is not None:
            push_event("status", {"message": "Rendering skills..."})
            push_event("final", {"answer": local_skill_response})
            push_event("done", {"message": "stream closed"})
            return local_skill_response, events

        agent = self._build_agent()
        query = self._format_history(history) + message
        stop_event = self._start_session_run(session_id)

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

        try:
            answer = agent.run_with_tools(
                query,
                max_iterations = max_iterations,
                tool_callback = tool_callback,
                status_callback = status_callback,
                stop_callback = stop_event.is_set if stop_event else None,
            )
        finally:
            self._finish_session_run(session_id, stop_event)

        push_event("final", {"answer": answer})
        push_event("done", {"message": "stream closed"})
        return answer, events

    def run_stream(
        self,
        history: List[Dict[str, str]],
        message: str,
        emit_event: Callable[[Dict[str, Any]], None],
        max_iterations: int = 10,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Execute chat request and emit streaming lifecycle events.

        Args:
            history: Existing session history.
            message: Current user message.
            emit_event: Event callback invoked on each event.
            max_iterations: Maximum tool-call iterations.
            session_id: Optional session identifier for stop control.

        Returns:
            Final answer string.
        """
        local_skill_response = self._build_local_skill_response(message)
        if local_skill_response is not None:
            emit_event(self._build_event("status", {"message": "Rendering skills..."}))
            emit_event(self._build_event("final", {"answer": local_skill_response}))
            return local_skill_response

        agent = self._build_agent()
        query = self._format_history(history) + message
        stop_event = self._start_session_run(session_id)

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
                    stop_callback = stop_event.is_set if stop_event else None,
                )
            except Exception as exc:
                error_holder["value"] = str(exc)
            finally:
                self._finish_session_run(session_id, stop_event)
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
