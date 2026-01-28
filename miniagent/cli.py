from __future__ import annotations

import os
import sys
import logging
import argparse
from typing import Dict, List, Union, Any, Optional


from rich.text import Text
from rich.style import Style
from rich.panel import Panel
from rich.status import Status
from rich.prompt import Prompt
from rich.console import Console
from rich.markdown import Markdown

sys.path.append(os.getcwd())

from miniagent.memory import Memory
from miniagent.agent import MiniAgent  
from miniagent.config import load_config 

logger = logging.getLogger("MiniAgent")

# Console instance for rich output
console = Console()

# Global status for thinking indicator
CURRENT_STATUS : Optional[Status] = None

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
        
        # Print tool invocation line (dim, compact)
        icon = "●" 
        console.print(f"  [dim]{icon}[/dim] [cyan]{name}[/cyan] [dim]{args_str}[/dim]")

    elif event == "end":
        result = payload.get("result", payload.get("error"))
        result_str = _format_tool_result(name, result)
        
        # Only print result if it's meaningful and short
        if result_str and result_str != "✓" and len(result_str) < 100:
            # Indent result under the tool call
            for line in result_str.split("\n")[:3]:  # Max 3 lines
                console.print(f"    [dim]→ {line}[/dim]")
        
        # Restore status
        if CURRENT_STATUS:
           CURRENT_STATUS.start()

def _build_agent(args: argparse.Namespace) -> tuple[MiniAgent, Memory]:
    """
    Build the MiniAgent instance with the given arguments.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Tuple of (MiniAgent instance, Memory instance)
    """
    cfg = load_config(args.config)

    model = args.model or cfg.llm.model_name
    api_key = args.api_key or cfg.llm.api_key
    base_url = args.base_url or cfg.llm.api_base
    temperature = args.temperature if args.temperature is not None else cfg.llm.temperature

    if not api_key:
        raise SystemExit("Missing API key. Set LLM_API_KEY or pass --api-key.")

    memory = Memory()
    memory.load()

    system_prompt = cfg.system_prompt
    mem_ctx = memory.context()
    if mem_ctx:
        system_prompt = system_prompt.rstrip() + "\n\n" + mem_ctx

    agent = MiniAgent(
        model = model,
        api_key = api_key,
        base_url = base_url,
        temperature = temperature,
        system_prompt = system_prompt,
        use_reflector = cfg.enable_reflection,
    )

    # Load some default tools if configured, else fall back to all currently registered.
    agent.tools = []
    tools = cfg.default_tools or agent.get_available_tools()
    for tool_name in tools:
        agent.load_builtin_tool(tool_name)

    return agent, memory

def args_parse():
    parser = argparse.ArgumentParser(prog = "miniagent", description = "MiniAgent interactive CLI")
    parser.add_argument("--config", help = "Path to config JSON")
    parser.add_argument("--model", help = "Override model name")
    parser.add_argument("--api-key", help = "Override API key")
    parser.add_argument("--base-url", help = "Override base URL")
    parser.add_argument("--temperature", type = float, help = "Override temperature")
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

    console.print(f"[dim]cwd:[/dim] {os.getcwd()}")
    console.print(f"[dim]commands:[/dim] /help /c /q")

    history: List[Dict[str, str]] = []

    while True:
        try:
            user_text = Prompt.ask("[cyan]you[/cyan]")
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
            console.print(f"[dim]cleared[/dim]")
            continue
        if user_text in ("/help", "help"):
            console.print("/help  show help")
            console.print("/c     clear conversation")
            console.print("/q     quit")
            continue

        history.append({"role": "user", "content": user_text})
        memory.push("user", user_text)

        query = _format_history(history) + user_text

        try:
            # Show thinking indicator
            with console.status("[dim]Thinking...[/dim]", spinner="dots") as status:
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
            console.print(f"[red]error:[/red] {e}")
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
        
        console.print(Panel(Markdown(display_response), title="assistant", style="green", border_style="green"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())