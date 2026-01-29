#!/usr/bin/env python3
"""
Test script to verify the functionality of QuarkAgent memory system.
"""
import os
import sys
import tempfile
import shutil
import logging
sys.path.append(os.getcwd())

from quarkagent.memory import Memory

# Configure logging
logging.basicConfig(
    level = logging.INFO,
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers = [logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


def test_memory_initialization():
    """Test Memory initialization"""
    logger.info("=" * 80)
    logger.info("Testing Memory Initialization")
    logger.info("=" * 80)

    try:
        # Test default initialization
        memory = Memory()
        logger.info(f"✓ Memory initialized with path: {memory.path}")
        assert memory.path.exists(), "Memory file not created"

        # Test preferences and facts are empty by default
        assert len(memory.preferences) == 0, "Preferences should be empty"
        assert len(memory.facts) == 0, "Facts should be empty"
        assert len(memory.messages) == 0, "Messages should be empty"

        logger.info("✓ Memory initialization tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Memory initialization test failed: {e}")
        return False


def test_memory_operations():
    """Test memory operations (set/get preferences, facts, messages)"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Memory Operations")
    logger.info("-" * 60)

    try:
        memory = Memory()

        # Test set and get preferences
        memory.set_preference("temperature", 0.1)
        memory.set_preference("model", "gpt-3.5-turbo")
        assert memory.preferences["temperature"] == 0.1, "Failed to set temperature preference"
        assert memory.preferences["model"] == "gpt-3.5-turbo", "Failed to set model preference"
        logger.info("✓ Preferences set and retrieved successfully")

        # Test set and get facts
        memory.set_fact("username", "testuser")
        memory.set_fact("project", "QuarkAgent")
        assert memory.facts["username"] == "testuser", "Failed to set username fact"
        assert memory.facts["project"] == "QuarkAgent", "Failed to set project fact"
        logger.info("✓ Facts set and retrieved successfully")

        # Test push messages
        memory.push("user", "Hello, how are you?")
        memory.push("assistant", "I'm doing well, thank you!")
        assert len(memory.messages) == 2, "Failed to push messages"
        assert memory.messages[0]["role"] == "user", "First message role incorrect"
        assert memory.messages[1]["role"] == "assistant", "Second message role incorrect"
        logger.info("✓ Messages pushed successfully")

        # Test context generation
        context = memory.context()
        logger.info(f"✓ Context generated successfully (length: {len(context)} characters)")
        assert "testuser" in context, "Username not in context"
        assert "QuarkAgent" in context, "Project not in context"
        assert "Hello" in context, "Message not in context"

        logger.info("✓ All memory operations tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Memory operations test failed: {e}")
        return False


def test_memory_persistence():
    """Test memory persistence (save and load)"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Memory Persistence")
    logger.info("-" * 60)

    try:
        # Create a temporary directory for memory testing
        temp_dir = tempfile.mkdtemp()
        original_home = os.environ.get("QUARKAGENT_HOME")
        os.environ["QUARKAGENT_HOME"] = temp_dir

        # Create and populate memory
        memory1 = Memory()
        memory1.set_preference("test_pref", "test_value")
        memory1.set_fact("test_fact", "fact_value")
        memory1.push("user", "Test message 1")
        memory1.push("assistant", "Test response 1")

        # Save and reload from same path
        memory_path = memory1.path
        memory2 = Memory(path = memory_path)
        memory2.load()

        assert memory2.preferences["test_pref"] == "test_value", "Failed to load preferences"
        assert memory2.facts["test_fact"] == "fact_value", "Failed to load facts"
        assert len(memory2.messages) == 2, "Failed to load messages"

        logger.info("✓ Memory persisted and loaded successfully")

        # Clean up
        os.environ["QUARKAGENT_HOME"] = original_home or ""
        shutil.rmtree(temp_dir)

        logger.info("✓ All memory persistence tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Memory persistence test failed: {e}")
        try:
            if 'temp_dir' in locals():
                shutil.rmtree(temp_dir)
            if 'original_home' in locals():
                os.environ["QUARKAGENT_HOME"] = original_home or ""
        except:
            pass
        return False


def test_memory_from_index():
    """Test Memory.from_index method"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Memory.from_index")
    logger.info("-" * 60)

    try:
        # Create a temporary directory for memory testing
        temp_dir = tempfile.mkdtemp()
        original_home = os.environ.get("QUARKAGENT_HOME")
        os.environ["QUARKAGENT_HOME"] = temp_dir

        # Create multiple memory instances
        memories = []
        for i in range(3):
            mem = Memory()
            mem.set_preference("index", i)
            mem.push("user", f"Message {i}")
            memories.append(mem)

        # Test loading by index (1-based)
        for i in range(1, 4):
            loaded_mem = Memory.from_index(i)
            expected_index = 3 - i  # Most recent is index 1
            assert loaded_mem.preferences.get("index") == expected_index, \
                f"Expected index {expected_index} for index {i}"
            logger.info(f"✓ Loaded memory index {i} (expected index {expected_index})")

        # Test loading non-existent index
        non_existent_mem = Memory.from_index(10)
        logger.info("✓ Non-existent index handled gracefully")

        # Clean up
        os.environ["QUARKAGENT_HOME"] = original_home or ""
        shutil.rmtree(temp_dir)

        logger.info("✓ All Memory.from_index tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Memory.from_index test failed: {e}")
        try:
            if 'temp_dir' in locals():
                shutil.rmtree(temp_dir)
            if 'original_home' in locals():
                os.environ["QUARKAGENT_HOME"] = original_home or ""
        except:
            pass
        return False


def test_message_limit():
    """Test message limit functionality"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Message Limit")
    logger.info("-" * 60)

    try:
        memory = Memory(max_messages = 5)

        # Push more messages than limit
        for i in range(10):
            memory.push("user", f"Message {i}")
            memory.push("assistant", f"Response {i}")

        # Should only keep last 5 messages
        assert len(memory.messages) == 5, f"Expected 5 messages, got {len(memory.messages)}"
        logger.info(f"✓ Message limit enforced: {len(memory.messages)} messages kept")

        logger.info("✓ All message limit tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Message limit test failed: {e}")
        return False


def main():
    """Run all memory tests"""
    logger.info("Running QuarkAgent memory system tests...")

    tests = [
        test_memory_initialization,
        test_memory_operations,
        test_memory_persistence,
        test_memory_from_index,
        test_message_limit
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
