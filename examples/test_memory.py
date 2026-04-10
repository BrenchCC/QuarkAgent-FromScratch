#!/usr/bin/env python3
"""
Test script to verify the functionality of the QuarkAgent memory system.
"""
import json
import logging
import os
import shutil
import sys
import tempfile

from contextlib import contextmanager

sys.path.append(os.getcwd())

from quarkagent.memory import Memory

logger = logging.getLogger(__name__)


@contextmanager
def temporary_memory_home():
    """
    Run one memory test with an isolated QUARKAGENT_HOME directory.

    Args:
        None.

    Yields:
        Temporary directory path used as QUARKAGENT_HOME.
    """
    original_home = os.environ.get("QUARKAGENT_HOME")
    temp_dir = tempfile.mkdtemp(prefix = "quarkagent-memory-")
    os.environ["QUARKAGENT_HOME"] = temp_dir

    try:
        yield temp_dir
    finally:
        if original_home is None:
            os.environ.pop("QUARKAGENT_HOME", None)
        else:
            os.environ["QUARKAGENT_HOME"] = original_home
        shutil.rmtree(temp_dir, ignore_errors = True)


def test_memory_initialization():
    """Test Memory initialization."""
    logger.info("=" * 80)
    logger.info("Testing Memory Initialization")
    logger.info("=" * 80)

    try:
        with temporary_memory_home():
            memory = Memory(agent_scope = "main")
            logger.info("✓ Memory initialized with path: %s", memory.path)
            assert memory.path.parent.exists(), "Memory directory not created"
            assert memory.path.parent.name == "main", "Main memory should live under the main scope directory"
            assert len(memory.preferences) == 0, "Preferences should be empty"
            assert len(memory.facts) == 0, "Facts should be empty"
            assert len(memory.messages) == 0, "Messages should be empty"
            assert memory.rolling_summary == "", "Rolling summary should be empty"
            assert memory.task_state == {}, "Task state should be empty"
            assert memory.episodes == [], "Episodes should be empty"
            assert memory.decision_log == [], "Decision log should be empty"

        logger.info("✓ Memory initialization tests passed")
        return True

    except Exception as exc:
        logger.error("✗ Memory initialization test failed: %s", exc)
        return False


def test_memory_operations():
    """Test memory operations for structured fields and rendered context."""
    logger.info("-" * 60)
    logger.info("Testing Memory Operations")
    logger.info("-" * 60)

    try:
        with temporary_memory_home():
            memory = Memory(agent_scope = "main")
            memory.set_preference("temperature", 0.1)
            memory.set_preference("model", "gpt-3.5-turbo")
            memory.set_fact("username", "testuser")
            memory.set_fact("project", "QuarkAgent")
            memory.set_task_state(
                goal = "Implement memory module",
                topic = "context-memory",
                todo = ["design", "implement", "test"],
                blockers = ["none"],
            )
            memory.record_decision(
                decision = "Use heuristic compression",
                rationale = "Avoid extra LLM dependency",
            )
            memory.remember_episode(
                topic = "semantic-search",
                summary = "Semantic retrieval is useful for selecting relevant history.",
                keywords = ["semantic", "retrieval", "history"],
            )
            memory.push("user", "Hello, how are you?")
            memory.push("assistant", "I'm doing well, thank you!")

            context = memory.context(query = "How should I implement semantic retrieval?")
            logger.info("✓ Context generated successfully (length: %s characters)", len(context))
            assert "User preferences: model=gpt-3.5-turbo, temperature=0.1" in context, "Preferences missing"
            assert "User facts: project=QuarkAgent, username=testuser" in context, "Facts missing"
            assert "Task state:" in context, "Task state missing"
            assert "Key decisions:" in context, "Decision log missing"
            assert "Relevant episodes:" in context, "Relevant episodes missing"
            assert "Recent conversation:" in context, "Recent conversation missing"
            assert "semantic-search" in context, "Relevant episode not selected"

        logger.info("✓ All memory operations tests passed")
        return True

    except Exception as exc:
        logger.error("✗ Memory operations test failed: %s", exc)
        return False


def test_memory_persistence():
    """Test memory persistence for structured memory fields."""
    logger.info("-" * 60)
    logger.info("Testing Memory Persistence")
    logger.info("-" * 60)

    try:
        with temporary_memory_home():
            memory1 = Memory(agent_scope = "main")
            memory1.set_preference("test_pref", "test_value")
            memory1.set_fact("test_fact", "fact_value")
            memory1.set_task_state(
                goal = "Persist layered memory",
                todo = ["save", "load"],
            )
            memory1.record_decision(
                decision = "Keep backward compatibility",
                rationale = "Old memory payloads should still load",
            )
            memory1.remember_episode(
                topic = "compatibility",
                summary = "Old payloads still load because new fields are optional.",
            )
            memory1.set_runtime_state(
                system_prompt = "Resolved system prompt for persistence testing",
                tools = ["read", "write", "skills"],
                skills = [
                    {
                        "name": "docx",
                        "namespace": "system",
                        "enabled": True,
                        "path": "skills/system/docx",
                    }
                ],
                task_id = "task_memory123",
            )
            memory1.push("user", "Test message 1")
            memory1.push("assistant", "Test response 1")

            memory_path = memory1.path
            memory2 = Memory(path = memory_path, agent_scope = "main")
            memory2.load()

            assert memory2.agent_scope == "main", "Failed to persist memory scope"
            assert memory2.preferences["test_pref"] == "test_value", "Failed to load preferences"
            assert memory2.facts["test_fact"] == "fact_value", "Failed to load facts"
            assert len(memory2.messages) == 2, "Failed to load messages"
            assert memory2.task_state["goal"] == "Persist layered memory", "Failed to load task state"
            assert memory2.decision_log[0]["decision"] == "Keep backward compatibility", "Decision log missing"
            assert memory2.episodes[0]["topic"] == "compatibility", "Episodes missing"
            assert memory2.system_prompt == "Resolved system prompt for persistence testing", "Prompt missing"
            assert memory2.tools == ["read", "write", "skills"], "Failed to load persisted tools"
            assert memory2.skills[0]["name"] == "docx", "Failed to load persisted skills"
            assert memory2.task_id == "task_memory123", "Failed to load persisted task_id"

        logger.info("✓ All memory persistence tests passed")
        return True

    except Exception as exc:
        logger.error("✗ Memory persistence test failed: %s", exc)
        return False


def test_memory_from_index():
    """Test Memory.from_index method."""
    logger.info("-" * 60)
    logger.info("Testing Memory.from_index")
    logger.info("-" * 60)

    try:
        with temporary_memory_home():
            for index in range(3):
                memory = Memory(agent_scope = "main")
                memory.set_preference("index", index)
                memory.push("user", f"Message {index}")

            for index in range(1, 4):
                loaded_memory = Memory.from_index(index, agent_scope = "main")
                expected_index = 3 - index
                assert loaded_memory.preferences.get("index") == expected_index, \
                    f"Expected index {expected_index} for index {index}"
                logger.info("✓ Loaded memory index %s (expected index %s)", index, expected_index)

            Memory.from_index(10, agent_scope = "main")
            logger.info("✓ Non-existent index handled gracefully")

        logger.info("✓ All Memory.from_index tests passed")
        return True

    except Exception as exc:
        logger.error("✗ Memory.from_index test failed: %s", exc)
        return False


def test_automatic_compression():
    """Test that message overflow is compressed into long-term memory layers."""
    logger.info("-" * 60)
    logger.info("Testing Automatic Compression")
    logger.info("-" * 60)

    try:
        with temporary_memory_home():
            memory = Memory(
                agent_scope = "main",
                max_messages = 5,
                preserve_recent_messages = 2,
            )

            for index in range(4):
                memory.push("user", f"Research memory strategy {index}")
                memory.push("assistant", f"Response about strategy {index}")

            assert len(memory.messages) <= 5, "Recent message window should stay within max_messages"
            assert memory.rolling_summary, "Rolling summary should be populated after compression"
            assert memory.episodes, "Episodes should be created after compression"
            assert memory.messages[-1]["content"] == "Response about strategy 3", "Recent tail incorrect"

        logger.info("✓ Automatic compression passed")
        return True

    except Exception as exc:
        logger.error("✗ Automatic compression test failed: %s", exc)
        return False


def test_relevant_episode_selection():
    """Test query-aware episodic retrieval."""
    logger.info("-" * 60)
    logger.info("Testing Relevant Episode Selection")
    logger.info("-" * 60)

    try:
        with temporary_memory_home():
            memory = Memory(agent_scope = "main")
            memory.remember_episode(
                topic = "vector-retrieval",
                summary = "Use semantic search to retrieve relevant historical context chunks.",
                keywords = ["semantic", "search", "retrieval"],
            )
            memory.remember_episode(
                topic = "ui-theme",
                summary = "Choose stronger typography and color contrast for the dashboard.",
                keywords = ["ui", "design", "theme"],
            )
            memory.record_decision(
                decision = "Prefer query-aware retrieval",
                rationale = "Avoid injecting unrelated historical context",
            )

            retrieval_context = memory.context(query = "How should semantic retrieval work for memory?")
            assert "vector-retrieval" in retrieval_context, "Relevant episode should be retrieved"
            assert "Prefer query-aware retrieval" in retrieval_context, "Relevant decision should be retrieved"

        logger.info("✓ Relevant episode selection passed")
        return True

    except Exception as exc:
        logger.error("✗ Relevant episode selection test failed: %s", exc)
        return False


def test_memory_scope_separation():
    """Test that main and subagent memory logs are stored separately."""
    logger.info("-" * 60)
    logger.info("Testing Memory Scope Separation")
    logger.info("-" * 60)

    try:
        with temporary_memory_home() as temp_home:
            main_memory = Memory(agent_scope = "main")
            main_memory.push("user", "Main session message")

            subagent_memory = Memory(agent_scope = "subagent")
            subagent_memory.push("user", "Subagent session message")

            assert main_memory.path.parent.name == "main", "Main memory path is not scoped to main"
            assert subagent_memory.path.parent.name == "subagent", "Subagent memory path is not scoped to subagent"
            assert main_memory.path != subagent_memory.path, "Main and subagent memory files should differ"

            loaded_subagent = Memory.from_index(1, agent_scope = "subagent")
            assert loaded_subagent.messages[-1]["content"] == "Subagent session message", \
                "Subagent load should only inspect subagent logs"

            main_payload = json.loads(main_memory.path.read_text(encoding = "utf-8"))
            subagent_payload = json.loads(subagent_memory.path.read_text(encoding = "utf-8"))
            assert main_payload["agent_scope"] == "main", "Main payload missing main scope marker"
            assert subagent_payload["agent_scope"] == "subagent", "Subagent payload missing subagent scope marker"
            assert (os.path.join(temp_home, "memory", "main")) in str(main_memory.path.parent), \
                "Main memory should live in the main scope directory"
            assert (os.path.join(temp_home, "memory", "subagent")) in str(subagent_memory.path.parent), \
                "Subagent memory should live in the subagent scope directory"

        logger.info("✓ Memory scope separation passed")
        return True

    except Exception as exc:
        logger.error("✗ Memory scope separation test failed: %s", exc)
        return False


def main():
    """Run all memory tests."""
    logger.info("Running QuarkAgent memory system tests...")

    tests = [
        test_memory_initialization,
        test_memory_operations,
        test_memory_persistence,
        test_memory_from_index,
        test_automatic_compression,
        test_relevant_episode_selection,
        test_memory_scope_separation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as exc:
            logger.error("✗ Test failed with exception: %s", exc)
            failed += 1

    logger.info("=" * 80)
    logger.info("Test Results: %s passed, %s failed", passed, failed)
    logger.info("=" * 80)
    return failed == 0


if __name__ == "__main__":
    logging.basicConfig(
        level = logging.INFO,
        format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers = [logging.StreamHandler()]
    )

    success = main()
    sys.exit(0 if success else 1)
