#!/usr/bin/env python3
"""
Test script to verify the QuarkAgent skills system.
"""
import os
import sys
import shutil
import logging
import tempfile

sys.path.append(os.getcwd())

from quarkagent.agent import QuarkAgent
from quarkagent.skills import SkillManager, build_skill_command_response

logging.basicConfig(
    level = logging.INFO,
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers = [logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


def clear_proxy_environment() -> dict:
    """
    Temporarily remove proxy variables from the current process environment.

    Args:
        None.

    Returns:
        Dictionary of removed environment variables and their original values.
    """
    removed_values = {}
    proxy_keys = [
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
    ]

    for key in proxy_keys:
        if key in os.environ:
            removed_values[key] = os.environ.pop(key)

    return removed_values


def restore_environment(saved_values: dict) -> None:
    """
    Restore environment variables from a saved dictionary.

    Args:
        saved_values: Environment variable values keyed by variable name.

    Returns:
        None.
    """
    for key, value in saved_values.items():
        os.environ[key] = value


def write_skill_file(
    root_dir: str,
    namespace: str,
    directory_name: str,
    display_name: str,
    description: str,
    body: str
) -> None:
    """
    Create one test skill file on disk.

    Args:
        root_dir: Temporary root directory.
        namespace: Skill namespace directory name.
        directory_name: Directory name used on disk.
        display_name: Skill name written to frontmatter.
        description: Short description written to frontmatter.
        body: Markdown body content.

    Returns:
        None.
    """
    skill_dir = os.path.join(root_dir, namespace, directory_name)
    os.makedirs(skill_dir, exist_ok = True)

    skill_text = "\n".join(
        [
            "---",
            f"name: {display_name}",
            f"description: {description}",
            "---",
            "",
            body.strip(),
            "",
        ]
    )

    with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding = "utf-8") as file_obj:
        file_obj.write(skill_text)


def build_skill_manager() -> SkillManager:
    """
    Build a temporary skill manager for tests.

    Args:
        None.

    Returns:
        Configured temporary skill manager.
    """
    temp_root = tempfile.mkdtemp(prefix = "quarkagent-skills-")

    write_skill_file(
        temp_root,
        "system",
        "docx",
        "docx",
        "Default docx skill",
        "# DOCX\nAlways loaded.",
    )
    write_skill_file(
        temp_root,
        "system",
        "pdf",
        "pdf",
        "Default pdf skill",
        "# PDF\nAlways loaded.",
    )
    write_skill_file(
        temp_root,
        "custom",
        "demo-skill",
        "demo-skill",
        "Custom demo skill",
        "# Demo\nLoaded on demand.",
    )

    skill_manager = SkillManager(
        system_skills_dir = os.path.join(temp_root, "system"),
        custom_skills_dir = os.path.join(temp_root, "custom"),
        enable_system_skills = True,
        enable_custom_skill_tool = True,
    )
    skill_manager._temp_root = temp_root  # type: ignore[attr-defined]
    return skill_manager


def cleanup_skill_manager(skill_manager: SkillManager) -> None:
    """
    Remove the temporary directory backing a test skill manager.

    Args:
        skill_manager: Temporary skill manager instance.

    Returns:
        None.
    """
    temp_root = getattr(skill_manager, "_temp_root", None)
    if temp_root and os.path.exists(temp_root):
        shutil.rmtree(temp_root)


def test_namespace_discovery() -> bool:
    """
    Test skill discovery across `system` and `custom` namespaces.

    Args:
        None.

    Returns:
        Whether the test passed.
    """
    logger.info("=" * 80)
    logger.info("Testing Skill Namespace Discovery")
    logger.info("=" * 80)

    skill_manager = build_skill_manager()

    try:
        assert sorted(skill_manager.system_skills.keys()) == ["docx", "pdf"], "Unexpected system skill set"
        assert sorted(skill_manager.custom_skills.keys()) == ["demo-skill"], "Unexpected custom skill set"
        logger.info("✓ Namespace discovery passed")
        return True
    finally:
        cleanup_skill_manager(skill_manager)


def test_default_system_skill_loading() -> bool:
    """
    Test default loading behavior for system skills.

    Args:
        None.

    Returns:
        Whether the test passed.
    """
    logger.info("\n" + "-" * 60)
    logger.info("Testing Default System Skill Loading")
    logger.info("-" * 60)

    skill_manager = build_skill_manager()

    try:
        enabled_skills = skill_manager.get_enabled_system_skills()
        enabled_names = [skill.name for skill in enabled_skills]
        assert enabled_names == ["docx", "pdf"], f"Unexpected enabled skills: {enabled_names}"

        skill_manager.default_system_skills = ["pdf"]
        enabled_skills = skill_manager.get_enabled_system_skills()
        enabled_names = [skill.name for skill in enabled_skills]
        assert enabled_names == ["pdf"], f"Unexpected filtered skills: {enabled_names}"

        logger.info("✓ Default system skill loading passed")
        return True
    finally:
        cleanup_skill_manager(skill_manager)


def test_custom_skill_lookup() -> bool:
    """
    Test `${skill_name}` parsing and custom skill lookup behavior.

    Args:
        None.

    Returns:
        Whether the test passed.
    """
    logger.info("\n" + "-" * 60)
    logger.info("Testing Custom Skill Lookup")
    logger.info("-" * 60)

    skill_manager = build_skill_manager()

    try:
        requested_names = skill_manager.extract_custom_skill_names("Please load ${demo-skill} and ${demo-skill}")
        assert requested_names == ["demo-skill"], f"Unexpected parsed names: {requested_names}"

        found_result = skill_manager.lookup_custom_skill("${demo-skill}")
        assert found_result["status"] == "ok", f"Expected ok result, got {found_result}"
        assert found_result["name"] == "demo-skill", "Custom skill name mismatch"

        missing_result = skill_manager.lookup_custom_skill("${missing-skill}")
        assert missing_result["status"] == "not_found", f"Expected not_found result, got {missing_result}"

        invalid_result = skill_manager.lookup_custom_skill("../bad-skill")
        assert invalid_result["status"] == "error", f"Expected error result, got {invalid_result}"

        logger.info("✓ Custom skill lookup passed")
        return True
    finally:
        cleanup_skill_manager(skill_manager)


def test_local_skill_commands() -> bool:
    """
    Test shared local `/skills` command rendering.

    Args:
        None.

    Returns:
        Whether the test passed.
    """
    logger.info("\n" + "-" * 60)
    logger.info("Testing Local Skill Commands")
    logger.info("-" * 60)

    skill_manager = build_skill_manager()

    try:
        overview_result = build_skill_command_response(skill_manager, "/skills")
        assert overview_result is not None, "Expected overview command result"
        assert overview_result.status == "overview", f"Unexpected overview status: {overview_result}"
        assert "System Skills" in overview_result.body, "Overview is missing system skill section"
        assert "${skill_name}" in overview_result.body, "Overview is missing custom skill usage"

        detail_result = build_skill_command_response(skill_manager, "$skills demo-skill")
        assert detail_result is not None, "Expected detail command result"
        assert detail_result.status == "detail", f"Unexpected detail status: {detail_result}"
        assert "Load on demand" in detail_result.body, "Detail is missing custom load policy"

        missing_result = build_skill_command_response(skill_manager, "/skills missing-skill")
        assert missing_result is not None, "Expected missing skill result"
        assert missing_result.status == "not_found", f"Unexpected missing status: {missing_result}"

        logger.info("✓ Local skill commands passed")
        return True
    finally:
        cleanup_skill_manager(skill_manager)


def test_agent_runtime_prompt_with_skills() -> bool:
    """
    Test runtime prompt rendering with system and custom skill hints.

    Args:
        None.

    Returns:
        Whether the test passed.
    """
    logger.info("\n" + "-" * 60)
    logger.info("Testing Agent Runtime Prompt With Skills")
    logger.info("-" * 60)

    skill_manager = build_skill_manager()

    try:
        removed_proxy_values = clear_proxy_environment()
        agent = QuarkAgent(
            model = "gpt-3.5-turbo",
            api_key = "dummy_key",
            system_prompt = (
                "Base prompt\n\n"
                "{system_skills_prompt}\n\n"
                "{custom_skills_hint}\n\n"
                "{tools_prompt}"
            ),
            system_skills = skill_manager.get_enabled_system_skills(),
            skill_manager = skill_manager,
            use_reflector = False,
        )
        agent.add_tool(skill_manager.build_skills_tool())

        runtime_prompt = agent._build_runtime_system_prompt("Use ${demo-skill} for this task")
        assert "System Skill: docx" in runtime_prompt, "System skill content missing from runtime prompt"
        assert "skills/custom" in runtime_prompt, "Custom skill hint missing from runtime prompt"
        assert "Tool: skills" in runtime_prompt, "Dynamic skills tool missing from runtime prompt"

        logger.info("✓ Agent runtime prompt rendering passed")
        return True
    finally:
        restore_environment(locals().get("removed_proxy_values", {}))
        cleanup_skill_manager(skill_manager)


def main() -> int:
    """
    Run all skills tests.

    Args:
        None.

    Returns:
        Process exit code.
    """
    tests = [
        test_namespace_discovery,
        test_default_system_skill_loading,
        test_custom_skill_lookup,
        test_local_skill_commands,
        test_agent_runtime_prompt_with_skills,
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
            logger.error("✗ %s failed: %s", test.__name__, exc)
            failed += 1

    logger.info("\n" + "=" * 80)
    logger.info("Skills Test Results: %s passed, %s failed", passed, failed)
    logger.info("=" * 80)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
