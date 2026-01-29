from __future__ import annotations

import os
import sys
import logging
import argparse
from typing import Dict, List, Union, Any, Optional

from rich import box

from rich.text import Text
from rich.emoji import Emoji
from rich.style import Style
from rich.panel import Panel
from rich.align import Align
from rich.table import Table
from rich.status import Status
from rich.prompt import Prompt
from rich.console import Console
from rich.columns import Columns
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn


sys.path.append(os.getcwd())

from quarkagent.memory import Memory
from quarkagent.agent import QuarkAgent
from quarkagent.config import load_config,save_config

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

def _build_agent(args: argparse.Namespace) -> tuple[QuarkAgent, Memory]:
    """
    Build the QuarkAgent instance with the given arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        Tuple of (QuarkAgent instance, Memory instance)
    """
    cfg = load_config(args.config)

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
        memory = Memory.from_index(args.load)
    else:
        memory = Memory()
    memory.load()

    system_prompt = cfg.system_prompt
    mem_ctx = memory.context()
    if mem_ctx:
        system_prompt = system_prompt.rstrip() + "\n\n" + mem_ctx

    # Determine whether to use reflector
    use_reflector = cfg.enable_reflection
    if args.reflect:
        use_reflector = True
    if args.no_reflect:
        use_reflector = False

    agent = QuarkAgent(
        model = model,
        api_key = api_key,
        base_url = base_url,
        temperature = temperature,
        top_p = top_p,
        system_prompt = system_prompt,
        use_reflector = use_reflector,
    )
    logger.info(f"Using model: {model}, temperature: {temperature}, top_p: {top_p}")
    # Load some default tools if configured, else fall back to all currently registered.
    agent.tools = []
    tools = cfg.default_tools or agent.get_available_tools()
    for tool_name in tools:
        agent.load_builtin_tool(tool_name)
    
    if args.config:
        save_config(cfg, args.config)
    else:
        save_config(cfg, ".quarkagent/configs/config.json")
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
            f"[dim {STYLES['text']}]commands:[/dim {STYLES['text']}] /help /c /q"
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
            help_table.add_row("/c", "Clear conversation history")
            help_table.add_row("/q", "Quit the application")
            console.print(help_table)
            console.print()
            continue

        history.append({"role": "user", "content": user_text})
        memory.push("user", user_text)

        query = _format_history(history) + user_text

        try:
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
                        status_callback = _status_callback
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