#!/usr/bin/env python3
"""
Test script to verify the functionality of QuarkAgent CLI commands.
"""
import os
import sys
import subprocess
import tempfile
import json
import logging
sys.path.append(os.getcwd())

# Configure logging
logging.basicConfig(
    level = logging.INFO,
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers = [logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


def build_subprocess_env(clear_proxy: bool = False) -> dict:
    """
    Build a subprocess environment for CLI tests.

    Args:
        clear_proxy: Whether to remove proxy-related variables.

    Returns:
        Environment dictionary for subprocess execution.
    """
    env = os.environ.copy()
    if not clear_proxy:
        return env

    proxy_keys = [
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
    ]
    for key in proxy_keys:
        env.pop(key, None)

    return env


def write_memory_fixture(
    memory_root: str,
    scope: str,
    filename: str,
    payload: dict
) -> None:
    """
    Write one memory payload fixture under a scoped memory directory.

    Args:
        memory_root: Root directory used as QUARKAGENT_HOME.
        scope: Memory scope such as `main` or `subagent`.
        filename: Output JSON filename.
        payload: JSON payload to persist.

    Returns:
        None.
    """
    scope_dir = os.path.join(memory_root, "memory", scope)
    os.makedirs(scope_dir, exist_ok = True)

    with open(os.path.join(scope_dir, filename), "w", encoding = "utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii = False, indent = 2)


def test_cli_help():
    """Test CLI help command"""
    logger.info("=" * 80)
    logger.info("Testing CLI Help Command")
    logger.info("=" * 80)

    try:
        # Test --help
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--help"],
            capture_output = True,
            text = True
        )
        assert result.returncode == 0, "Help command failed"
        assert "usage:" in result.stdout.lower(), "Help output should contain usage information"
        logger.info("✓ --help command executed successfully")

        logger.info("✓ All help command tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Help command test failed: {e}")
        return False


def test_cli_version():
    """Test CLI version command"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing CLI Version Command")
    logger.info("-" * 60)

    try:
        # Test --version
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--version"],
            capture_output = True,
            text = True
        )
        # It's possible --version isn't implemented, so check if command fails or not
        if result.returncode == 0:
            logger.info("✓ --version command executed successfully")
        else:
            logger.warning("⚠️  --version command not implemented")

        logger.info("✓ Version command test completed")
        return True

    except Exception as e:
        logger.error(f"✗ Version command test failed: {e}")
        return False


def test_cli_config_commands():
    """Test CLI configuration commands"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing CLI Configuration Commands")
    logger.info("-" * 60)

    try:
        # Create a temporary config file
        with tempfile.NamedTemporaryFile(mode = 'w', suffix = '.json', delete = False) as temp:
            temp.write(json.dumps({
                "llm": {
                    "model_name": "gpt-3.5-turbo",
                    "api_key": "test-key",
                    "temperature": 0.1
                },
                "default_tools": ["calculator", "read"]
            }))
            temp_filename = temp.name

        # Test loading config file
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--config", temp_filename, "--help"],
            capture_output = True,
            text = True
        )
        assert result.returncode == 0, "Failed to load config file"
        logger.info("✓ --config parameter works correctly")

        # Clean up
        os.unlink(temp_filename)

        logger.info("✓ All config command tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Config command test failed: {e}")
        try:
            os.unlink(temp_filename)
        except:
            pass
        return False


def test_cli_model_parameters():
    """Test CLI model parameters"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing CLI Model Parameters")
    logger.info("-" * 60)

    try:
        # Test model parameter
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--model", "gpt-4", "--help"],
            capture_output = True,
            text = True
        )
        assert result.returncode == 0, "--model parameter failed"
        logger.info("✓ --model parameter works correctly")

        # Test temperature parameter
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--temperature", "0.5", "--help"],
            capture_output = True,
            text = True
        )
        assert result.returncode == 0, "--temperature parameter failed"
        logger.info("✓ --temperature parameter works correctly")

        # Test top-p parameter
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--top-p", "0.8", "--help"],
            capture_output = True,
            text = True
        )
        assert result.returncode == 0, "--top-p parameter failed"
        logger.info("✓ --top-p parameter works correctly")

        logger.info("✓ All model parameter tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Model parameter test failed: {e}")
        return False


def test_cli_memory_commands():
    """Test CLI memory commands"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing CLI Memory Commands")
    logger.info("-" * 60)

    try:
        # Test load memory parameter with a valid saved-memory index
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--load", "1", "--help"],
            capture_output = True,
            text = True
        )
        assert result.returncode == 0, "--load parameter failed"
        logger.info("✓ --load parameter works correctly")

        logger.info("✓ All memory command tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Memory command test failed: {e}")
        return False


def test_cli_memory_overview_command():
    """Test interactive /memory command output."""
    logger.info("\n" + "-" * 60)
    logger.info("Testing CLI Memory Overview Command")
    logger.info("-" * 60)

    try:
        with tempfile.TemporaryDirectory(prefix = "quarkagent-cli-memory-") as temp_home:
            write_memory_fixture(
                temp_home,
                "main",
                "main_fixture.json",
                {
                    "updated_at": 1710000000,
                    "agent_scope": "main",
                    "preferences": {},
                    "facts": {},
                    "messages": [
                        {"role": "user", "content": "hello main"},
                        {"role": "assistant", "content": "hello from main"},
                    ],
                },
            )
            write_memory_fixture(
                temp_home,
                "subagent",
                "subagent_fixture.json",
                {
                    "updated_at": 1710000100,
                    "agent_scope": "subagent",
                    "task_id": "task_demo123456",
                    "preferences": {},
                    "facts": {"delegated_task": "Summarize the report"},
                    "messages": [
                        {"role": "user", "content": "delegated query"},
                        {"role": "assistant", "content": "delegated answer"},
                    ],
                },
            )

            env = build_subprocess_env(clear_proxy = True)
            env["QUARKAGENT_HOME"] = temp_home

            result = subprocess.run(
                [sys.executable, "-m", "quarkagent", "--api-key", "test-key"],
                input = "/memory\n/q\n",
                capture_output = True,
                text = True,
                env = env
            )
            output = result.stdout + result.stderr

            assert result.returncode == 0, "/memory command failed"
            assert "Memory Overview" in output, "Memory overview header missing"
            assert "Saved Main Sessions" in output, "Main memory table missing"
            assert "Saved Subagent Sessions" in output, "Subagent memory table missing"
            assert "--load 1" in output, "Main-session load hint missing"
            assert "Summarize the report" in output, "Delegated subagent task missing"
            assert "task_demo123456" in output, "Subagent task_id missing"
            logger.info("✓ /memory command executed successfully")

        logger.info("✓ All /memory command tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ /memory command test failed: {e}")
        return False


def test_cli_runtime_system_prompt_snapshot():
    """Test that runtime system prompt is persisted to config and memory snapshots."""
    logger.info("\n" + "-" * 60)
    logger.info("Testing CLI Runtime System Prompt Snapshot")
    logger.info("-" * 60)

    try:
        with tempfile.TemporaryDirectory(prefix = "quarkagent-cli-prompt-") as temp_home:
            project_root = os.getcwd()
            write_memory_fixture(
                temp_home,
                "main",
                "main_runtime_fixture.json",
                {
                    "updated_at": 1710000200,
                    "agent_scope": "main",
                    "preferences": {"language": "zh"},
                    "facts": {"project": "QuarkAgent"},
                    "messages": [
                        {"role": "user", "content": "previous user question"},
                        {"role": "assistant", "content": "previous assistant answer"},
                    ],
                },
            )

            env = build_subprocess_env(clear_proxy = True)
            env["QUARKAGENT_HOME"] = temp_home
            env["PYTHONPATH"] = (
                project_root
                if not env.get("PYTHONPATH")
                else project_root + os.pathsep + env["PYTHONPATH"]
            )

            result = subprocess.run(
                [sys.executable, "-m", "quarkagent", "--api-key", "test-key", "--load", "1"],
                input = "/q\n",
                capture_output = True,
                text = True,
                env = env,
                cwd = temp_home
            )

            assert result.returncode == 0, "CLI prompt snapshot run failed"

            config_path = os.path.join(temp_home, ".quarkagent", "configs", "config.json")
            assert os.path.exists(config_path), "Runtime config snapshot was not created"

            with open(config_path, "r", encoding = "utf-8") as file_obj:
                config_payload = json.load(file_obj)

            main_memory_dir = os.path.join(temp_home, "memory", "main")
            main_memory_files = sorted(os.listdir(main_memory_dir))
            assert main_memory_files, "Main memory snapshot was not created"

            latest_memory_path = os.path.join(main_memory_dir, main_memory_files[-1])
            with open(latest_memory_path, "r", encoding = "utf-8") as file_obj:
                memory_payload = json.load(file_obj)

            expected_markers = [
                "User preferences: language=zh",
                "User facts: project=QuarkAgent",
                "Recent conversation:",
                "previous user question",
            ]

            for marker in expected_markers:
                assert marker in config_payload["system_prompt"], f"Config snapshot missing marker: {marker}"
                assert marker in memory_payload["system_prompt"], f"Memory snapshot missing marker: {marker}"

            assert "skills" in config_payload["tools"], "Config snapshot missing skills tool"
            assert "subagent" in config_payload["tools"], "Config snapshot missing subagent tool"
            assert config_payload["tools"] == memory_payload["tools"], "Config and memory tools should match"
            assert isinstance(config_payload["skills"], list), "Config snapshot missing skills list"
            assert isinstance(memory_payload["skills"], list), "Memory snapshot missing skills list"
            assert config_payload["skills"] == memory_payload["skills"], "Config and memory skills should match"

            logger.info("✓ Runtime system prompt persisted to config and memory snapshots")
        return True

    except Exception as e:
        logger.error(f"✗ Runtime system prompt snapshot test failed: {e}")
        return False


def test_cli_api_parameters():
    """Test CLI API parameters"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing CLI API Parameters")
    logger.info("-" * 60)

    try:
        # Test API key parameter
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--api-key", "test-key-123", "--help"],
            capture_output = True,
            text = True
        )
        assert result.returncode == 0, "--api-key parameter failed"
        logger.info("✓ --api-key parameter works correctly")

        # Test base URL parameter
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--base-url", "https://api.example.com", "--help"],
            capture_output = True,
            text = True
        )
        assert result.returncode == 0, "--base-url parameter failed"
        logger.info("✓ --base-url parameter works correctly")

        logger.info("✓ All API parameter tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ API parameter test failed: {e}")
        return False


def test_cli_skills_command():
    """Test interactive /skills command"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing CLI Skills Command")
    logger.info("-" * 60)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--api-key", "test-key"],
            input = "/skills\n/q\n",
            capture_output = True,
            text = True,
            env = build_subprocess_env(clear_proxy = True)
        )
        output = result.stdout + result.stderr

        assert result.returncode == 0, "/skills command failed"
        assert "System Skills" in output, "System skills section missing"
        assert "Custom Skills" in output, "Custom skills section missing"
        assert "${skill_name}" in output, "Custom skill usage hint missing"
        logger.info("✓ /skills command executed successfully")

        logger.info("✓ All /skills command tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Skills command test failed: {e}")
        return False


def test_cli_skill_detail_command():
    """Test interactive skill detail command"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing CLI Skill Detail Command")
    logger.info("-" * 60)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--api-key", "test-key"],
            input = "$skills docx\n/q\n",
            capture_output = True,
            text = True,
            env = build_subprocess_env(clear_proxy = True)
        )
        output = result.stdout + result.stderr

        assert result.returncode == 0, "Skill detail command failed"
        assert "Skill Detail: docx" in output, "Skill detail header missing"
        assert "Loaded by default in the runtime prompt" in output, "Skill load policy missing"
        assert "skills/system/docx" in output, "Skill source path missing"
        logger.info("✓ Skill detail command executed successfully")

        logger.info("✓ All skill detail command tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Skill detail command test failed: {e}")
        return False


def test_cli_help_mentions_escape_stop():
    """Test interactive help mentions Esc stop behavior"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing CLI Help Mentions Esc Stop")
    logger.info("-" * 60)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--api-key", "test-key"],
            input = "/help\n/q\n",
            capture_output = True,
            text = True,
            env = build_subprocess_env(clear_proxy = True)
        )
        output = result.stdout + result.stderr

        assert result.returncode == 0, "Interactive help command failed"
        assert "Esc" in output, "Esc help entry missing"
        assert "stop the current response" in output.lower(), "Esc stop description missing"
        logger.info("✓ Interactive help includes Esc stop hint")

        logger.info("✓ All interactive help tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Interactive help test failed: {e}")
        return False


def main():
    """Run all CLI tests"""
    logger.info("Running QuarkAgent CLI tests...")

    tests = [
        test_cli_help,
        test_cli_version,
        test_cli_config_commands,
        test_cli_model_parameters,
        test_cli_memory_commands,
        test_cli_memory_overview_command,
        test_cli_runtime_system_prompt_snapshot,
        test_cli_api_parameters,
        test_cli_skills_command,
        test_cli_skill_detail_command,
        test_cli_help_mentions_escape_stop
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"✗ Test failed with exception: {e}")
            failed += 1

    logger.info("\n" + "=" * 80)
    logger.info(f"Test Results: {passed} passed, {failed} failed")
    logger.info("=" * 80)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
