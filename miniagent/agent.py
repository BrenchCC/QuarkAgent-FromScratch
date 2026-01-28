import os
import re
import sys
import json
import time
import logging
from typing import Any, Dict, List, Union, Callable, Optional

from openai import OpenAI   
from tenacity import retry, stop_after_attempt, wait_random_exponential


sys.path.append(os.getcwd())

from miniagent.utils import parse_json, Reflector   
from miniagent.tools import get_registered_tools, get_tool, get_tool_description

logger = logging.getLogger("MiniAgent")

class MiniAgent():
    """
    MiniAgent main class for MiniAgent
    """
    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        top_p: float = 0.95,
        system_prompt: str = "You are a helpful assistant called MiniAgent created by brench that can use tools to get information and perform tasks.",
        use_reflector: bool = True,
        **kwargs
    ):
        """
        Initialize MiniAgent

        Args:
            model: LLM model name
            api_key: API key for LLM service
            base_url: Base URL for LLM service (optional)
            temperature: Temperature for LLM sampling (default: 0.7)
            system_prompt: System prompt for MiniAgent (default: "You are a helpful assistant called MiniAgent created by brench that can use tools to get information and perform tasks.")
            use_reflector: Whether to use reflector for response improvement (default: False)
            **kwargs: Additional keyword arguments for LLM client   
        """
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.top_p = top_p
        self.system_prompt = system_prompt
        self.tools = []
        self.client = None
        self.use_reflector = use_reflector
        
        # Initialize the LLM client
        self._init_llm_client()
        
        # Initialize reflector if enabled
        if use_reflector:
            self.reflector = Reflector(self.client, self.model)
        else:
            self.reflector = None
        
        logger.info(f"MiniAgent initialized with model {self.model}, temperature {self.temperature}, top_p {self.top_p}, system_prompt {self.system_prompt}, use_reflector {self.use_reflector}")

    def _init_llm_client(self):
        """
        Initialize the LLM client
        """
        logger.info(f"Default to use OpenAI client")
        try:
            self.client = OpenAI(
                    api_key = self.api_key,
                    base_url = self.base_url
                )
            logger.info(f"OpenAI client initialized with model: {self.model}")

        except ImportError:
            logger.error("OpenAI package not installed. Please install it with 'pip install openai'")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise
        
    def add_tool(self, tool: dict):
        """
        Add a tool to the agent
        
        Args:
            tool: Tool definition, containing name, description, and executor
        """
        if not isinstance(tool, dict):
            raise TypeError("Tool must be a dictionary type")
            
        required_keys = ["name", "description", "executor"]
        for key in required_keys:
            if key not in tool:
                raise ValueError(f"Tool is missing a required field: {key}")
                
        self.tools.append(tool)
        logger.debug(f"Added tool for MiniAgent: {tool['name']}")

    def load_builtin_tool(self, tool_name: str):
        """
        Load a built-in tool by name

        Args:
            tool_name: Name of the built-in tool to load
        """
        tool_item = get_tool(tool_name)
        if tool_item:
            tool_description = get_tool_description(tool_item)
            tool = {
                "name": tool_description["name"],
                "description": tool_description["description"],
                "parameters": tool_description.get("parameters", {}),
                "executor": tool_item
            }
            self.add_tool(tool)
            logger.info(f"Loaded built-in tool: {tool_name}")
            return True
        else:
            logger.warning(f"Built-in tool not found: {tool_name}")
            return False
        
    def get_available_tools(self) -> List[str]:
        """
        Get all available built-in tool names
        
        Returns:
            List of tool names
        """
        return list(get_registered_tools().keys())
    
    def _build_tools_prompt(self) -> str:
        """
        Build the tools prompt for the LLM
        
        Returns:
            Tools prompt string
        """
        tools_decription = []
        for tool in self.tools:
            params = tool.get("parameters", {})
            params_description = []

            for name, schema in params.get("properties", {}).items():
                required = name in params.get("required", [])
                params_description.append(
                    f"{name}: {schema.get('description', '')} {'(required)' if required else ''}"
                )
            
            description =f"""
            Tool: {tool['name']}
            Description: {tool['description']}
            Parameters:
            {chr(10).join(params_description)}
            """
            tools_decription.append(description)

        return '\n'.join(tools_decription)
    
    def _extract_string_value(self, text: str, quote_char: str) -> Optional[str]:
        """
        Extract a string value from text, handling escaped quotes
        
        Args:
            text: Text containing the string value
            quote_char: Quote character used to enclose the string value
            
        Returns:
            Extracted string value if found, None otherwise
        """
        # Strategy: Find all potential ending positions and pick the best one
        # A valid ending is: quote + optional whitespace + } or quote + optional whitespace + ,

        # First try: find the last occurrence of "} or "}
        # This works because JSON object ends with }
        best_end = -1
        i = 0
        while i < len(text):
            if text[i] == '\\' and i + 1 < len(text):
                i += 2
                continue

            if text[i] == quote_char:
                rest = text[i + 1:].strip()
                if rest.endswith('}') or rest.endswith(',}'):
                    best_end = i

                    # try to validate by checking if remaining text looks like end of JSON
                    if rest.startswith('}'):
                        # This looks like a good ending
                        return text[:i]
            i += 1
        
        # If we found a potential end, use it
        if best_end > 0:
            return text[:best_end]

        # Fallback: take everything up to the last quote before }
        last_quote = text.rfind(quote_char)
        if last_quote > 0:
            return text[:last_quote]

        return None
    
    def _extract_write_args(self, text: str) -> Optional[Dict]:
        """
        Extract arguments for write tool from text
        
        Args:
            text: Text containing write tool arguments
            
        Returns:
            Dictionary of extracted arguments if found, None otherwise
        """
        path_match = re.search(r'["\']path["\']\s*:\s*["\']([^"\']+)["\']', text)
        if not path_match:
            return None
        
        path = path_match.group(1)

        # Find content field - look for "content" or 'content' 
        content_match = re.search(r'["\']content["\']\s*:\s*["\']', text)
        if not content_match:
            return None
        
        content_start = content_match.end()
        quote_char = text[content_start - 1]

        # Find the end of content - look for closing pattern
        # The content ends with quote + } or quote + , + }
        # We need to find the LAST occurrence of "} or '}
        content = self._extract_string_value(text[content_start:], quote_char)

        if content is not None:
            return {"path": path, "content": content}

        return None

    def _extract_balanced_json(self, text: str) -> Optional[str]:
        """
        Extract balanced JSON string from text

        Args:
            text: Text containing JSON string

        Returns:
            Extracted JSON string if found, None otherwise
        """
        # Strategy: Count braces and find the last complete JSON object
        start = text.find('{')
        if start == -1:
            return None

        brace_count = 0
        in_string = False
        escape_next = False
        end = -1

        i = start
        while i < len(text):
            char = text[i]

            if escape_next:
                escape_next = False
                i += 1
                continue

            if char == '\\':
                escape_next = True
                i += 1
                continue

            if char in ('"', "'"):
                in_string = not in_string
                i += 1
                continue

            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = i
                        # Try to find the last complete JSON object
                        # Continue searching to see if there's another complete object
                        temp_end = end
                        temp_i = i + 1
                        temp_brace_count = 0
                        temp_in_string = False
                        temp_escape_next = False

                        while temp_i < len(text):
                            temp_char = text[temp_i]

                            if temp_escape_next:
                                temp_escape_next = False
                                temp_i += 1
                                continue

                            if temp_char == '\\':
                                temp_escape_next = True
                                temp_i += 1
                                continue

                            if temp_char in ('"', "'"):
                                temp_in_string = not temp_in_string
                                temp_i += 1
                                continue

                            if not temp_in_string:
                                if temp_char == '{':
                                    temp_brace_count += 1
                                elif temp_char == '}':
                                    temp_brace_count -= 1
                                    if temp_brace_count == 0:
                                        end = temp_i
                            temp_i += 1
                        break
            i += 1

        if end != -1:
            return text[start:end + 1]

        logger.error(f"Failed to extract balanced JSON from text: {text[:100]}...")
        return None

    def _parse_tool_call(self, content: str) -> Optional[dict]:
        """
        Parse a tool call from LLM content
        
        Args:
            content: LLM-generated content containing tool call
            
        Returns:
            Parsed tool call dictionary if found, None otherwise
        """
        logger.debug(f"Parsing tool call from content: {content[:100]}...")
        logger.debug(f"Query Content length: {len(content)}")

        #First, try to find TOOL: pattern and extract tool name
        tool_name_patterns = [
            r"TOOL:\s*(\w+)\s*ARGS:\s*",
            r"TOL:\s*(\w+)\s*ARGS:\s*",
            r"使用工具:\s*(\w+)\s*参数:\s*",
            r"USE TOOL:\s*(\w+)\s*WITH ARGS:\s*",
            r"工具名称:\s*(\w+)\s*工具参数:\s*",
            r"Tool:\s*(\w+)\s*Args:\s*",
            r"Tool:\s*(\w+)\s*Arguments:\s*"
        ]

        for pattern in tool_name_patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                name = match.group(1)
                # Find the start of JSON after the pattern
                json_start = match.end()
                remaining = content[json_start:]

                # For write tool with content, use special extraction
                if name == "write":
                    args = self._extract_write_args(remaining)
                    if args:
                        logger.info(f"Parsed write tool call with path: {args.get('path', 'unknown')}")
                        return {"name": name, "arguments": args}
                    
                # Extract balanced JSON using brace counting
                args_str = self._extract_balanced_json(remaining)

                if args_str:
                    logger.debug(f"Get Match Tools: {name} with Args: {args_str}")

                    # First try strict parsing
                    try:
                        return {
                            "name": name,
                            "arguments": json.loads(args_str)
                        }
                    except json.JSONDecodeError as e:
                        logger.debug(f"Strict JSON parse failed: {e}")

                    # Then try loose parsing via json_utils
                    args = parse_json(args_str)
                    if args:
                        logger.info(f"Parsed tool call: {name} with {len(args)} args")
                        return {
                            "name": name,
                            "arguments": args
                        }

                    logger.warning(f"Failed to parse tool arguments for {name}: {args_str[:100]}...")

        logger.debug("No tool call pattern matched")
        return None
    
    def _execute_tool(
        self,
        tool_call: Dict,
        tool_callback: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
    ) -> Any:
        """
        Execute a tool call

        Args:
            tool_call: Tool call information
            tool_callback: Callback for tool execution events

        Returns:
            Tool execution result
        """
        tool_name = tool_call["name"]
        tool_args = tool_call["arguments"]

        logger.info(f"Executing tool: {tool_name} with arguments: {tool_args}")

        # Find the tool in self.tools or use global registered tools
        tool = None
        for t in self.tools:
            if t["name"] == tool_name:
                tool = t
                break

        if tool:
            try:
                # Execute the tool using its executor
                result = tool["executor"](**tool_args)
                logger.info(f"Tool {tool_name} executed successfully")
            except Exception as e:
                error_msg = f"Error executing tool {tool_name}: {str(e)}"
                logger.error(error_msg)
                result = {"error": error_msg}
        else:
            # Fallback to global registered tools
            from miniagent.tools import execute_tool
            result = execute_tool(tool_name, **tool_args)

        # Call tool callback if provided
        if tool_callback:
            tool_callback(tool_name, "success" if "error" not in str(result) else "error", result)

        return result

    @retry(stop=stop_after_attempt(3), wait=wait_random_exponential(min=1, max=60))
    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """
        Call LLM with messages

        Args:
            messages: Conversation messages

        Returns:
            LLM response content
        """
        logger.debug(f"Calling LLM with {len(messages)} messages")

        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model = self.model,
                messages = messages,
                temperature = self.temperature,
                top_p = self.top_p
            )

            content = response.choices[0].message.content
            logger.debug(f"LLM response received: {content[:100]}...")
            return content

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def run_with_tools(
        self,
        query: str,
        max_iterations: int = 10,
        tool_callback: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Implement tool calling with formatted text

        This method uses specific text formats to represent tool calls, simulating native tools functionality.
        Suitable for scenarios requiring explicit tool calls, and can be used with models that don't support native tools.

        Args:
            query: User query text
            max_iterations: Maximum number of tool execution iterations
            tool_callback: Callback for tool execution events
            status_callback: Callback for status updates (e.g. "Thinking...", "Executing tool...")

        Returns:
            Final response text
        """
        logger.info(f"Starting run_with_tools with query: {query}")

        # Build initial messages
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": query}
        ]

        # If tools are available, add tools prompt
        if self.tools:
            tools_prompt = self._build_tools_prompt()
            messages[0]["content"] += "\n\nAvailable Tools:\n" + tools_prompt

        for iteration in range(max_iterations):
            logger.debug(f"Iteration {iteration + 1}/{max_iterations}")

            if status_callback:
                status_callback(f"Thinking... (Iteration {iteration + 1})")

            # Call LLM
            try:
                content = self._call_llm(messages)
            except Exception as e:
                error_msg = f"Failed to get LLM response: {str(e)}"
                logger.error(error_msg)
                return error_msg

            # Check if tool call is needed
            tool_call = self._parse_tool_call(content)

            if tool_call:
                tool_name = tool_call["name"]
                logger.info(f"Tool call detected: {tool_name}")

                if status_callback:
                    status_callback(f"Executing {tool_name}...")

                # Execute tool
                result = self._execute_tool(tool_call, tool_callback)

                # Format tool response
                tool_response = f"Tool {tool_name} returned: {result}"
                logger.debug(f"Tool response: {tool_response[:100]}...")

                # Add tool response to messages for next iteration
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": tool_response})
            else:
                # No tool call needed, return the response
                logger.info(f"Run completed without tool calls")

                # Use reflector if enabled
                if self.use_reflector and self.reflector:
                    if status_callback:
                        status_callback("Improving response...")
                    content = self.reflector.enhance_response(query, content)

                return content

        # Reached maximum iterations
        error_msg = "Reached maximum iterations without completing the task"
        logger.error(error_msg)
        return error_msg

    def run(self, query: str, max_iterations: int = 10) -> str:
        """
        Execute the default Agent tool calling method

        This is the main entry method for MiniAgent, using formatted text to implement tool calling.
        The method parses and executes tool call instructions from the model output.

        Args:
            query: User query text
            max_iterations: Maximum number of iterations

        Returns:
            Agent response text
        """
        logger.info(f"Starting run with query: {query}")
        return self.run_with_tools(query, max_iterations)
    
if __name__ == "__main__":
    from dotenv import load_dotenv

    # Load environment variables from .env file
    load_dotenv()

    # Configure logging
    logging.basicConfig(
        level = logging.INFO,
        format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers = [logging.StreamHandler()]
    )

    logger = logging.getLogger(__name__)

    def test_agent():
        """Test the MiniAgent functionality"""
        logger.info("Starting MiniAgent test...")

        # Test 1: Initialize MiniAgent
        logger.info("\nTest 1: Initializing MiniAgent")
        try:
            api_key = os.getenv("LLM_API_KEY")
            base_url = os.getenv("LLM_BASE_URL")
            model = os.getenv("LLM_MODEL")

            if not api_key:
                logger.warning("OPENAI_API_KEY not found in .env file, using dummy key")
                api_key = "dummy_key"

            agent = MiniAgent(
                model = model,
                api_key = api_key,
                base_url = base_url,
                temperature = 0.7,
                use_reflector = False
            )
            logger.info("✅ MiniAgent initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize MiniAgent: {e}")
            return False

        # Test 2: Check available tools
        logger.info("\nTest 2: Checking available built-in tools")
        try:
            available_tools = agent.get_available_tools()
            logger.info(f"✅ Available tools: {', '.join(available_tools)}")
            logger.info(f"✅ Number of available tools: {len(available_tools)}")
        except Exception as e:
            logger.error(f"❌ Failed to get available tools: {e}")
            return False

        # Test 3: Load built-in tools
        logger.info("\nTest 3: Loading built-in tools")
        try:
            # Load a few common tools
            tools_to_load = ["read", "write", "bash", "calculator"]
            loaded_count = 0

            for tool_name in tools_to_load:
                if agent.load_builtin_tool(tool_name):
                    logger.info(f"✅ Loaded tool: {tool_name}")
                    loaded_count += 1
                else:
                    logger.warning(f"⚠️ Failed to load tool: {tool_name}")

            logger.info(f"✅ Total tools loaded: {loaded_count}")
        except Exception as e:
            logger.error(f"❌ Failed to load built-in tools: {e}")
            return False

        # Test 4: Verify tools are loaded correctly
        logger.info("\nTest 4: Verifying tools are loaded")
        try:
            logger.info(f"✅ Number of tools in agent: {len(agent.tools)}")
            for tool in agent.tools:
                logger.info(f"  - Tool: {tool['name']}")
                logger.debug(f"    Description: {tool['description']}")

            if len(agent.tools) > 0:
                logger.info("✅ Tools loaded successfully")
            else:
                logger.warning("⚠️ No tools were loaded")
        except Exception as e:
            logger.error(f"❌ Failed to verify loaded tools: {e}")
            return False

        logger.info("\n🎉 All tests completed successfully!")
        return True

    # Run the test
    test_agent()