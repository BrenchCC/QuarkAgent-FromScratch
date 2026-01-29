#!/usr/bin/env python3
"""
Run all QuarkAgent tests.
"""
import os
import sys
import subprocess
import logging
from typing import List, Tuple

# Configure logging
logging.basicConfig(
    level = logging.INFO,
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers = [logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


def run_test_script(script_name: str) -> Tuple[bool, str]:
    """
    Run a test script and return the result.

    Args:
        script_name: Name of the test script to run

    Returns:
        Tuple of (success, output)
    """
    script_path = os.path.join(os.path.dirname(__file__), script_name)

    if not os.path.exists(script_path):
        return False, f"Script not found: {script_path}"

    logger.info(f"\n{'='*80}")
    logger.info(f"Running test script: {script_name}")
    logger.info(f"{'='*80}")

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output = True,
            text = True
        )

        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file = sys.stderr)

        return result.returncode == 0, f"Return code: {result.returncode}"

    except Exception as e:
        logger.error(f"Error running {script_name}: {e}")
        return False, f"Exception: {e}"


def main():
    """Run all test scripts in examples directory"""
    logger.info("Running all QuarkAgent tests...")

    # List of test scripts to run
    test_scripts = [
        "test_json_llm_utils.py",
        "test_agent_basic.py",
        "test_tools.py",
        "test_memory.py",
        "test_config.py",
        "test_cli.py",
        "test_reflector.py"
    ]

    results = []

    # Run each test script
    for script in test_scripts:
        success, details = run_test_script(script)
        results.append((script, success, details))

    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("Test Results Summary")
    logger.info("=" * 80)

    passed = 0
    failed = 0

    for script, success, details in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        logger.info(f"{status} - {script} ({details})")
        if success:
            passed += 1
        else:
            failed += 1

    logger.info(f"\nTotal: {passed} passed, {failed} failed")

    # Return appropriate exit code
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
