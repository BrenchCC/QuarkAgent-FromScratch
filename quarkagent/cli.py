from __future__ import annotations

import os
import sys
import logging
import argparse
import threading

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich import box

from rich.panel import Panel
from rich.align import Align
from rich.table import Table
from rich.status import Status
from rich.prompt import Prompt
from rich.console import Console
from rich.markdown import Markdown


sys.path.append(os.getcwd())

from quarkagent.memory import Memory, MemorySummary, list_memory_summaries
from quarkagent.agent import QuarkAgent
from quarkagent.config import load_config, save_config
from quarkagent.subagent import build_subagent_tool
from quarkagent.skills import SkillCommandResult, SkillManager, build_skill_command_response

logger = logging.getLogger("QuarkAgent")

# Console instance for rich output
console = Console()

# Global status for thinking indicator
CURRENT_STATUS : Optional[Status] = None

# Style configurations
STYLES = {
    "primary": "cyan",
    "secondary": "blue",
    "success": "green",
    "error": "red",
    "warning": "yellow",
    "info": "dim white",
    "accent": "magenta",
    "border": "bright_blue",
    "header": "bold cyan",
    "subheader": "cyan",
    "text": "white",
    "dim": "dim white"
}


class EscapeStopMonitor:
    """
    Listen for the `Esc` key while the agent is generating.

    Args:
        None.
    """

    def __init__(self):
        """
        Initialize the stop monitor state.

        Args:
            None.
        """
        self._stop_event = threading.Event()
        self._shutdown_event = threading.Event()
        self._listener_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """
        Start the keyboard listener when stdin is interactive.

        Args:
            None.

        Returns:
            None.
        """
        if not sys.stdin.isatty() or self._listener_thread:
            return

        self._stop_event.clear()
        self._shutdown_event.clear()
        self._listener_thread = threading.Thread(target = self._listen_for_escape, daemon = True)
        self._listener_thread.start()

    def stop(self) -> None:
        """
        Stop the keyboard listener and restore stdin state.

        Args:
            None.

        Returns:
            None.
        """
        self._shutdown_event.set()
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout = 0.5)
        self._listener_thread = None

    def is_stop_requested(self) -> bool:
        """
        Check whether the user requested a stop.

        Args:
            None.

        Returns:
            Whether stop has been requested.
        """
        return self._stop_event.is_set()

    def _listen_for_escape(self) -> None:
        """
        Dispatch to the platform-specific keyboard listener.

        Args:
            None.

        Returns:
            None.
        """
        if os.name == "nt":
            self._listen_windows()
            return

        self._listen_posix()

    def _listen_windows(self) -> None:
        """
        Listen for `Esc` on Windows terminals.

        Args:
            None.

        Returns:
            None.
        """
        try:
            import msvcrt
        except ImportError:
            return

        while not self._shutdown_event.is_set():
            if not msvcrt.kbhit():
                self._shutdown_event.wait(timeout = 0.1)
                continue

            char = msvcrt.getwch()
            if char == "\x1b":
                self._stop_event.set()
                return

    def _listen_posix(self) -> None:
        """
        Listen for `Esc` on POSIX terminals.

        Args:
            None.

        Returns:
            None.
        """
        try:
            import select
            import termios
            import tty
        except ImportError:
            return

        fd = sys.stdin.fileno()

        try:
            original_settings = termios.tcgetattr(fd)
        except termios.error:
            return

        try:
            tty.setcbreak(fd)
            while not self._shutdown_event.is_set():
                readable, _, _ = select.select([fd], [], [], 0.1)
                if not readable:
                    continue

                char = os.read(fd, 1).decode("utf-8", errors = "ignore")
                if char == "\x1b":
                    self._stop_event.set()
                    return
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, original_settings)
            except termios.error:
                return

def _format_history(history: List[Dict[str, str]], limit_turns: int = 10) -> str:
    """
    Format the conversation history for display.
    
    Args:
        history: List of conversation history entries
        limit_turns: Number of recent turns to display
        
    Returns:
        Formatted string of the conversation history
    """
    if not history:
        return None
    
    # Format the recent history
    recent_text = history[-(limit_turns * 2) :]
    formatted_history = ["Conversation history (most recent last):"]
    for entry in recent_text:
        role = entry.get('role', '')
        content = entry.get('content', '')
        formatted_history.append(f"{role}: {content}")

    return '\n'.join(formatted_history) + "\n\n"

def _truncate_str(s: str, limit: int = 60) -> str:
    """Truncate a string for display."""
    if len(s) > limit:
        return s[:limit] + "…"
    return s


def _format_tool_args(name: str, args: Dict[str, Any]) -> str:
    """Format tool arguments for display."""
    # Tool-specific formatting functions
    def format_bash(a):
        cmd = a.get("cmd", a.get("command", ""))
        return _truncate_str(cmd, 80)

    def format_read(a):
        path = a.get("path", "")
        offset = a.get("offset", 1)
        limit = a.get("limit", 50)
        return f"{path} (lines {offset}-{offset + limit - 1})"

    def format_write(a):
        path = a.get("path", "")
        content = a.get("content", "")
        lines = content.count("\n") + 1
        return f"{path} ({lines} lines)"

    def format_edit(a):
        return a.get("path", "")

    def format_glob_grep(a):
        pattern = a.get("pattern", "")
        path = a.get("path", a.get("root", "."))
        return f"{pattern} in {path}"

    def format_calculator(a):
        return a.get("expression", str(a))

    formatters = {
        "bash": format_bash,
        "read": format_read,
        "write": format_write,
        "edit": format_edit,
        "glob": format_glob_grep,
        "grep": format_glob_grep,
        "calculator": format_calculator,
    }

    # Use tool-specific formatter if available
    if name in formatters:
        return formatters[name](args)

    # Generic formatting for unknown tools
    if args:
        first_key = next(iter(args))
        return f"{first_key}={_truncate_str(str(args[first_key]), 50)}"
    return ""

def _format_tool_result(name: str, result: Any) -> str:
    """
    Format tool result for display.
    """
    if not result:
        return "✅"
    
    if isinstance(result, dict):
        if "exit_code" in result:
            code = result.get("exit_code", "0")
            if code == 0:
                stdout = result.get("stdout", "")
                lines = stdout.strip().split("\n") if stdout else []
                if len(lines) <= 3:
                    return "\n".join(lines) if lines else "✓"
                return f"{len(lines)} lines"
            else:
                return f"exit {code}"
        elif "error" in result:
            return f"✗ {_truncate_str(str(result['error']), 50)}"
    if isinstance(result, str):
        if len(result) > 100:
            lines = result.count("\n") + 1
            return f"{lines} lines" if lines > 3 else _truncate_str(result, 60)
        return _truncate_str(result, 60)
    return _truncate_str(str(result), 60)

def _status_callback(status_text: str) -> None:
    """
    Update the global status indicator.
    
    Args:
        status_text: Text to display in the status indicator
    """
    global CURRENT_STATUS

    if CURRENT_STATUS:
        CURRENT_STATUS.update(f"[dim]{status_text}[/dim]")

def _tool_callback(event: str, name: str, payload: Dict[str, Any]) -> None:
    """
    Handle tool callback events.

    Args:
        event: Event type ('start' or 'end')
        name: Tool name
        payload: Event payload containing arguments and results
    """
    global CURRENT_STATUS

    if event == "status":
        # Stop any existing status
        if CURRENT_STATUS:
            CURRENT_STATUS.stop()
            CURRENT_STATUS = None

        args = payload.get("arguments", {})
        args_str = _format_tool_args(name, args)

        # Enhanced tool invocation display
        tool_table = Table(show_header = False, box = box.ROUNDED, style = STYLES["border"], width = None)
        tool_table.add_row(
            f"[bold {STYLES['accent']}]🛠️[/bold {STYLES['accent']}]",
            f"[bold {STYLES['primary']}]{name}[/bold {STYLES['primary']}]",
            f"[dim {STYLES['text']}]{args_str}[/dim {STYLES['text']}]"
        )
        console.print(tool_table)

    elif event == "end":
        result = payload.get("result", payload.get("error"))
        result_str = _format_tool_result(name, result)

        # Enhanced result display
        if result_str and result_str != "✓" and len(result_str) < 100:
            result_panel = Panel(
                Markdown(result_str),
                title = "Result",
                style = STYLES["success"],
                border_style = STYLES["success"],
                box = box.ROUNDED,
                padding = (0, 1)
            )
            console.print(Align.left(result_panel, pad = 2))

        # Restore status
        if CURRENT_STATUS:
           CURRENT_STATUS.start()


def _render_skill_command_result(result: SkillCommandResult) -> None:
    """
    Render a shared local skill command result in the CLI.

    Args:
        result: Shared skill command response payload.

    Returns:
        None.
    """
    style = STYLES["primary"]
    if result.status in {"not_found", "unavailable"}:
        style = STYLES["error"] if result.status == "not_found" else STYLES["warning"]

    console.print(
        Panel(
            Markdown(result.body),
            title = result.title,
            style = style,
            border_style = style,
            box = box.ROUNDED,
            padding = (1, 2),
        )
    )


def _format_memory_timestamp(updated_at: Optional[int]) -> str:
    """
    Format a memory summary timestamp for CLI display.

    Args:
        updated_at: Unix timestamp in seconds.

    Returns:
        Human-readable timestamp.
    """
    if not updated_at:
        return "-"

    try:
        return datetime.fromtimestamp(updated_at).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "-"


def _build_memory_table(
    title: str,
    summaries: List[MemorySummary],
    current_memory: Optional[Memory] = None,
    include_load_hint: bool = False,
    include_task_id: bool = False
) -> Table:
    """
    Build a Rich table for one memory scope.

    Args:
        title: Table title.
        summaries: Memory summary items.
        current_memory: Optional current active memory instance.
        include_load_hint: Whether to show CLI load hints.
        include_task_id: Whether to show task IDs for tracked subagent sessions.

    Returns:
        Rendered table instance.
    """
    table = Table(title = title, box = box.ROUNDED, style = STYLES["border"])
    table.add_column("Index", style = STYLES["primary"], justify = "right")
    table.add_column("Updated", style = STYLES["text"])
    table.add_column("Msgs", style = STYLES["text"], justify = "right")

    if include_load_hint:
        table.add_column("Load", style = STYLES["accent"])
    if include_task_id:
        table.add_column("Task ID", style = STYLES["accent"])

    table.add_column("Note", style = STYLES["text"])
    table.add_column("File", style = STYLES["dim"])

    current_path = str(current_memory.path) if current_memory else ""

    if not summaries:
        empty_row = ["-", "-", "-"]
        if include_load_hint:
            empty_row.append("-")
        if include_task_id:
            empty_row.append("-")
        empty_row.extend(["No saved sessions yet", "-"])
        table.add_row(*empty_row)
        return table

    for summary in summaries:
        note = "Legacy main log" if summary.is_legacy else ""
        if summary.delegated_task:
            note = _truncate_str(summary.delegated_task, 48)
        elif summary.last_message:
            note = _truncate_str(summary.last_message.replace("\n", " "), 48)

        if current_path and str(summary.path) == current_path:
            note = (note + " | current").strip(" |")

        row = [
            str(summary.index),
            _format_memory_timestamp(summary.updated_at),
            str(summary.message_count),
        ]

        if include_load_hint:
            row.append(f"--load {summary.index}")
        if include_task_id:
            row.append(summary.task_id or "-")

        row.extend(
            [
                note or "-",
                summary.path.name,
            ]
        )
        table.add_row(*row)

    return table


def _render_memory_command(
    current_memory: Memory,
    command_text: str
) -> bool:
    """
    Render local `/memory` command output without invoking the LLM.

    Args:
        current_memory: Current main-session memory instance.
        command_text: Raw user command text.

    Returns:
        Whether the command was handled.
    """
    normalized_command = command_text.strip()
    if not normalized_command:
        return False

    command_name = normalized_command.split(maxsplit = 1)[0]
    if command_name != "/memory":
        return False

    parts = normalized_command.split(maxsplit = 1)
    requested_scope = "all"
    if len(parts) == 2:
        requested_scope = parts[1].strip().lower()

    valid_scopes = {"all", "main", "subagent"}
    if requested_scope not in valid_scopes:
        console.print(
            Panel(
                Markdown("Usage: `/memory`, `/memory main`, `/memory subagent`"),
                title = "Memory",
                style = STYLES["error"],
                border_style = STYLES["error"],
                box = box.ROUNDED,
                padding = (1, 2),
            )
        )
        console.print()
        return True

    header_lines = [
        f"Current main session path: `{current_memory.path}`",
        "Use `--load N` to resume one saved main session.",
        "Subagent sessions are persisted separately under the `subagent` scope.",
    ]
    console.print(
        Panel(
            Markdown("\n".join(header_lines)),
            title = "Memory Overview",
            style = STYLES["primary"],
            border_style = STYLES["primary"],
            box = box.ROUNDED,
            padding = (1, 2),
        )
    )

    if requested_scope in {"all", "main"}:
        console.print(
            _build_memory_table(
                "Saved Main Sessions",
                list_memory_summaries(agent_scope = "main"),
                current_memory = current_memory,
                include_load_hint = True,
            )
        )
        console.print()

    if requested_scope in {"all", "subagent"}:
        subagent_summaries = list_memory_summaries(agent_scope = "subagent")
        console.print(
            _build_memory_table(
                "Saved Subagent Sessions",
                subagent_summaries,
                include_task_id = True,
            )
        )
        console.print()

        delegated_lines = [
            f"{summary.index}. {summary.task_id or '-'} | {summary.delegated_task}"
            for summary in subagent_summaries
            if summary.delegated_task
        ]
        if delegated_lines:
            console.print(
                Panel(
                    Markdown("\n".join(delegated_lines)),
                    title = "Recent Delegated Tasks",
                    style = STYLES["secondary"],
                    border_style = STYLES["secondary"],
                    box = box.ROUNDED,
                    padding = (1, 2),
                )
            )
            console.print()

    return True

def _build_agent(args: argparse.Namespace) -> tuple[QuarkAgent, Memory]:
    """
    Build the QuarkAgent instance with the given arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        Tuple of (QuarkAgent instance, Memory instance)
    """
    cfg = load_config(args.config)
    runtime_config_path = Path(".quarkagent/configs/config.json")

    model = args.model or cfg.llm.model_name
    api_key = args.api_key or cfg.llm.api_key
    base_url = args.base_url or cfg.llm.api_base
    temperature = args.temperature if args.temperature is not None else cfg.llm.temperature
    top_p = args.top_p if args.top_p is not None else cfg.llm.top_p

    # Update config with command-line values
    if args.model:
        cfg.llm.model_name = model
    if args.api_key:
        cfg.llm.api_key = api_key
    if args.base_url:
        cfg.llm.api_base = base_url
    if args.temperature is not None:
        cfg.llm.temperature = temperature
    if args.top_p is not None:
        cfg.llm.top_p = top_p

    if not api_key:
        raise SystemExit("Missing API key. Set LLM_API_KEY or pass --api-key.")

    if args.load:
        memory = Memory.from_index(args.load, agent_scope = "main")
    else:
        memory = Memory(agent_scope = "main")
    memory.load()

    system_prompt = cfg.system_prompt

    def build_memory_context(query: Optional[str] = None) -> str:
        """
        Render contextual memory for the current user turn.

        Args:
            query: Optional current user query string.

        Returns:
            Rendered memory context text.
        """
        return memory.context(query = query)

    # Determine whether to use reflector
    use_reflector = cfg.enable_reflection
    if args.reflect:
        use_reflector = True
    if args.no_reflect:
        use_reflector = False

    skill_manager = SkillManager(
        system_skills_dir = cfg.system_skills_dir,
        custom_skills_dir = cfg.custom_skills_dir,
        default_system_skills = cfg.default_system_skills,
        enable_system_skills = cfg.enable_system_skills,
        enable_custom_skill_tool = cfg.enable_custom_skill_tool,
    )

    agent = QuarkAgent(
        model = model,
        api_key = api_key,
        base_url = base_url,
        temperature = temperature,
        top_p = top_p,
        system_prompt = system_prompt,
        system_skills = skill_manager.get_enabled_system_skills(),
        skill_manager = skill_manager,
        model_identifier = cfg.llm.model_identifier,
        use_reflector = use_reflector,
        memory_context_provider = build_memory_context,
    )
    agent.agent_scope = memory.agent_scope
    agent.memory_path = str(memory.path)
    logger.info(
        f"Using request model: {model}, "
        f"model identifier: {cfg.llm.model_identifier}, "
        f"temperature: {temperature}, top_p: {top_p}"
    )
    # Load some default tools if configured, else fall back to all currently registered.
    agent.tools = []
    tools = cfg.default_tools or agent.get_available_tools()
    for tool_name in tools:
        if tool_name == "skills":
            continue
        agent.load_builtin_tool(tool_name)

    if cfg.enable_custom_skill_tool:
        agent.add_tool(skill_manager.build_skills_tool())

    if cfg.enable_subagent_tool:
        agent.add_tool(
            build_subagent_tool(
                agent,
                default_max_iterations = cfg.subagent_max_iterations,
            )
        )

    runtime_tool_names = [tool["name"] for tool in agent.tools]
    runtime_skill_payloads = skill_manager.list_skill_payloads()
    runtime_prompt_snapshot = agent.build_runtime_snapshot_prompt()
    memory.set_runtime_state(
        system_prompt = runtime_prompt_snapshot,
        tools = runtime_tool_names,
        skills = runtime_skill_payloads,
    )
    
    if args.config:
        save_config(cfg, args.config)
    else:
        save_config(
            cfg,
            str(runtime_config_path),
            system_prompt_override = runtime_prompt_snapshot,
            tools_override = runtime_tool_names,
            skills_override = runtime_skill_payloads,
        )
    return agent, memory

def args_parse():
    parser = argparse.ArgumentParser(prog = "quarkagent", description = "QuarkAgent interactive CLI")
    parser.add_argument("--config", help = "Path to config JSON for loading")
    parser.add_argument("--model", help = "Choose model to use")
    parser.add_argument("--api-key", help = "API key for LLM service")
    parser.add_argument("--base-url", help = "Base URL for LLM service")
    parser.add_argument("--temperature", type = float, default = 0.3, help = "Temperature for LLM model")
    parser.add_argument("--top-p", type = float, default = 0.9, help = "Top-p (nucleus sampling) for LLM model")
    parser.add_argument("--load", type = int, choices = range(1, 9), metavar = "N",
                        help = "Load memory from previous conversation N (1-8), where 1 is the most recent")
    parser.add_argument("--reflect", action = "store_true", help = "Enable reflector for response improvement")
    parser.add_argument("--no-reflect", action = "store_true", help = "Disable reflector for response improvement")
    args = parser.parse_args()
    return args

def main():
    args = args_parse()

    try:
        agent, memory = _build_agent(args)
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"[red]error:[/red] {e}")
        return 1

    # Enhanced welcome message
    welcome_panel = Panel(
        Align.center(
            f"[bold {STYLES['header']}]🚀 QuarkAgent[/bold {STYLES['header']}]\n"
            f"[dim {STYLES['text']}]Interactive AI Assistant[/dim {STYLES['text']}]\n\n"
            f"[dim {STYLES['text']}]cwd:[/dim {STYLES['text']}] {os.getcwd()}\n"
            f"[dim {STYLES['text']}]commands:[/dim {STYLES['text']}] /help /skills /memory /c /q\n"
            f"[dim {STYLES['text']}]runtime:[/dim {STYLES['text']}] press Esc to stop the current response"
        ),
        style = STYLES["border"],
        border_style = STYLES["border"],
        box = box.DOUBLE_EDGE,
        padding = (1, 2)
    )
    console.print(welcome_panel)
    console.print()

    history: List[Dict[str, str]] = []

    while True:
        try:
            user_text = Prompt.ask(f"[bold {STYLES['primary']}]👤 You[/bold {STYLES['primary']}]")
            user_text = user_text.strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break

        if not user_text:
            continue

        if user_text in ("/q", "/quit", "/exit"):
            break
        if user_text in ("/c", "/clear"):
            history.clear()
            console.print(f"[bold {STYLES['success']}]✅ Conversation history cleared[/bold {STYLES['success']}]")
            console.print()
            continue
        if user_text in ("/help", "help"):
            help_table = Table(title = "Available Commands", box = box.ROUNDED, style = STYLES["border"])
            help_table.add_column("Command", style = STYLES["primary"], justify = "left")
            help_table.add_column("Description", style = STYLES["text"], justify = "left")
            help_table.add_row("/help", "Show this help message")
            help_table.add_row("/skills", "Show the current system/custom skills and usage")
            help_table.add_row("/skills <name>", "Show the full detail for one skill")
            help_table.add_row("$skills <name>", "Alias for `/skills <name>`")
            help_table.add_row("/memory", "Show saved main/subagent sessions")
            help_table.add_row("/memory <scope>", "Show one scope: `main` or `subagent`")
            help_table.add_row("/c", "Clear conversation history")
            help_table.add_row("/q", "Quit the application")
            help_table.add_row("Esc", "Stop the current response after the active step completes")
            console.print(help_table)
            console.print()
            continue

        skill_command_result = build_skill_command_response(agent.skill_manager, user_text)
        if skill_command_result:
            _render_skill_command_result(skill_command_result)
            console.print()
            continue

        if _render_memory_command(memory, user_text):
            continue

        history.append({"role": "user", "content": user_text})
        memory.push("user", user_text)

        query = (_format_history(history[:-1]) or "") + user_text

        stop_monitor = EscapeStopMonitor()
        try:
            stop_monitor.start()

            # Enhanced thinking indicator
            with console.status(
                f"[bold {STYLES['primary']}]🤔 Thinking...[/bold {STYLES['primary']}]",
                spinner = "arc",
                spinner_style = STYLES["accent"]
            ) as status:
                global CURRENT_STATUS
                CURRENT_STATUS = status
                try:
                    response = agent.run_with_tools(
                        query,
                        tool_callback = _tool_callback,
                        status_callback = _status_callback,
                        stop_callback = stop_monitor.is_stop_requested,
                    )
                finally:
                    CURRENT_STATUS = None
        except TypeError:
            # Backward compatibility if tool_callback not available.
            response = agent.run(query)
        except Exception as e:
            error_panel = Panel(
                f"[bold {STYLES['error']}]❌ Error:[/bold {STYLES['error']}] {e}",
                style = STYLES["error"],
                border_style = STYLES["error"],
                box = box.ROUNDED,
                padding = (1, 2)
            )
            console.print(error_panel)
            console.print()
            continue
        finally:
            stop_monitor.stop()

        history.append({"role": "assistant", "content": response})
        memory.push("assistant", response)

        # Truncate overly long responses for display (keep full in history)
        display_response = response
        if len(response) > 2000:
            # Count lines and truncate if too long
            lines = response.split('\n')
            if len(lines) > 50:
                display_response = '\n'.join(lines[:20]) + f'\n\n... ({len(lines) - 40} lines omitted) ...\n\n' + '\n'.join(lines[-20:])
            else:
                display_response = response[:1000] + f'\n\n... ({len(response) - 2000} chars omitted) ...\n\n' + response[-1000:]
        
        # Enhanced assistant response display
        response_panel = Panel(
            Markdown(display_response),
            title = f"[bold {STYLES['primary']}]🤖 Assistant[/bold {STYLES['primary']}]",
            style = STYLES["success"],
            border_style = STYLES["success"],
            box = box.ROUNDED,
            padding = (1, 2)
        )
        console.print(response_panel)
        console.print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
