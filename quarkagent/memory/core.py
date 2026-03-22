import json
import re
import time

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import os
import sys

sys.path.append(os.getcwd())

from .constants import (
    DEFAULT_AGENT_SCOPE,
    DEFAULT_MAX_CONTEXT_CHARS,
    DEFAULT_MAX_DECISIONS,
    DEFAULT_MAX_EPISODES,
    DEFAULT_PRESERVE_RECENT_MESSAGES,
    DEFAULT_RECENT_CONTEXT_MESSAGES,
    DEFAULT_SUMMARY_CHAR_LIMIT,
    STOP_WORDS,
    logger,
)
from .storage import (
    default_memory_path,
    get_memory_path_by_index,
    normalize_agent_scope,
)


@dataclass
class Memory:
    """
    Hierarchical memory store for QuarkAgent.
    """

    path: Optional[Path] = None
    agent_scope: str = DEFAULT_AGENT_SCOPE
    preferences: Dict[str, Any] = field(default_factory = dict)
    facts: Dict[str, Any] = field(default_factory = dict)
    messages: List[Dict[str, str]] = field(default_factory = list)
    rolling_summary: str = ""
    task_state: Dict[str, Any] = field(default_factory = dict)
    episodes: List[Dict[str, Any]] = field(default_factory = list)
    decision_log: List[Dict[str, Any]] = field(default_factory = list)
    system_prompt: Optional[str] = None
    tools: List[str] = field(default_factory = list)
    skills: List[Dict[str, Any]] = field(default_factory = list)
    task_id: Optional[str] = None
    max_messages: int = 12
    preserve_recent_messages: int = DEFAULT_PRESERVE_RECENT_MESSAGES
    max_episodes: int = DEFAULT_MAX_EPISODES
    max_decisions: int = DEFAULT_MAX_DECISIONS
    max_summary_chars: int = DEFAULT_SUMMARY_CHAR_LIMIT
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS

    def __post_init__(self) -> None:
        """
        Finalize runtime defaults after dataclass initialization.

        Args:
            None.

        Returns:
            None.
        """
        self.agent_scope = normalize_agent_scope(self.agent_scope)
        self.max_messages = max(1, self.max_messages)
        self.preserve_recent_messages = max(1, min(self.preserve_recent_messages, self.max_messages))
        self.max_episodes = max(1, self.max_episodes)
        self.max_decisions = max(1, self.max_decisions)
        self.max_summary_chars = max(200, self.max_summary_chars)
        self.max_context_chars = max(400, self.max_context_chars)

        if self.path is None:
            self.path = default_memory_path(self.agent_scope)
        else:
            self.path = Path(self.path)

    @classmethod
    def from_index(
        cls,
        index: int,
        agent_scope: str = DEFAULT_AGENT_SCOPE
    ) -> "Memory":
        """
        Create a Memory instance from a conversation index (1-based).

        Args:
            index: Reverse-chronological memory index.
            agent_scope: Logical agent scope such as `main` or `subagent`.

        Returns:
            Loaded memory instance when the index exists, otherwise a fresh memory.
        """
        normalized_scope = normalize_agent_scope(agent_scope)
        path = get_memory_path_by_index(index, agent_scope = normalized_scope)
        if path:
            logger.info("Loading memory from: %s", path)
            memory = cls(path = path, agent_scope = normalized_scope)
            memory.load()
            return memory

        logger.warning("Memory index %s not found, creating new memory", index)
        return cls(agent_scope = normalized_scope)

    def load(self) -> None:
        """
        Load memory payload from disk when it exists.

        Args:
            None.

        Returns:
            None.
        """
        if not self.path.exists():
            return

        try:
            data = json.loads(self.path.read_text(encoding = "utf-8"))
            self.agent_scope = normalize_agent_scope(data.get("agent_scope", self.agent_scope))
            self.preferences = data.get("preferences", {}) or {}
            self.facts = data.get("facts", {}) or {}
            self.messages = data.get("messages", []) or []
            self.rolling_summary = data.get("rolling_summary", "") or data.get("summary", "") or ""
            self.task_state = data.get("task_state", {}) or {}
            self.episodes = data.get("episodes", []) or []
            self.decision_log = data.get("decision_log", []) or []
            self.system_prompt = data.get("system_prompt")
            self.tools = data.get("tools", []) or []
            self.skills = data.get("skills", []) or []
            self.task_id = data.get("task_id") or self.facts.get("task_id")
            self._compress_overflow_messages()
        except Exception:
            logger.exception("Failed to load memory")

    def save(self) -> None:
        """
        Persist the current memory payload to disk.

        Args:
            None.

        Returns:
            None.
        """
        try:
            self.path.parent.mkdir(parents = True, exist_ok = True)
            payload = {
                "updated_at": int(time.time()),
                "agent_scope": self.agent_scope,
                "preferences": self.preferences,
                "facts": self.facts,
                "messages": self.messages[-self.max_messages :],
                "rolling_summary": self.rolling_summary,
                "task_state": self.task_state,
                "episodes": self.episodes[-self.max_episodes :],
                "decision_log": self.decision_log[-self.max_decisions :],
                "system_prompt": self.system_prompt,
                "tools": self.tools,
                "skills": self.skills,
                "task_id": self.task_id,
            }
            self.path.write_text(
                json.dumps(payload, ensure_ascii = False, indent = 2),
                encoding = "utf-8"
            )
        except Exception:
            logger.exception("Failed to save memory")

    def set_runtime_state(
        self,
        system_prompt: Optional[str],
        tools: Optional[List[str]] = None,
        skills: Optional[List[Dict[str, Any]]] = None,
        task_id: Optional[str] = None
    ) -> None:
        """
        Persist runtime prompt, tool list, and skill list for the current session.

        Args:
            system_prompt: Final system prompt assigned to the current agent session.
            tools: Runtime tool names exposed to the current session.
            skills: Runtime skill payloads exposed to the current session.
            task_id: Optional stable task identifier for the current session.

        Returns:
            None.
        """
        self.system_prompt = system_prompt or None
        self.tools = list(tools or [])
        self.skills = list(skills or [])
        self.task_id = task_id or self.task_id
        self.save()

    def set_system_prompt(self, system_prompt: Optional[str]) -> None:
        """
        Persist only the resolved system prompt used for the current session.

        Args:
            system_prompt: Final system prompt assigned to the current agent session.

        Returns:
            None.
        """
        self.system_prompt = system_prompt or None
        self.save()

    def set_preference(self, key: str, value: Any) -> None:
        """
        Persist one stable user preference.

        Args:
            key: Preference key.
            value: Preference value.

        Returns:
            None.
        """
        self.preferences[key] = value
        self.save()

    def set_fact(self, key: str, value: Any) -> None:
        """
        Persist one stable user fact.

        Args:
            key: Fact key.
            value: Fact value.

        Returns:
            None.
        """
        self.facts[key] = value
        self.save()

    def set_task_state(
        self,
        goal: Optional[str] = None,
        topic: Optional[str] = None,
        latest_user_request: Optional[str] = None,
        plan: Optional[List[str]] = None,
        todo: Optional[List[str]] = None,
        done: Optional[List[str]] = None,
        blockers: Optional[List[str]] = None
    ) -> None:
        """
        Update structured task-state fields.

        Args:
            goal: Current task goal summary.
            topic: Current task topic.
            latest_user_request: Latest user-facing request summary.
            plan: High-level plan items.
            todo: Pending work items.
            done: Completed work items.
            blockers: Known blockers or risks.

        Returns:
            None.
        """
        updates = {
            "goal": goal,
            "topic": topic,
            "latest_user_request": latest_user_request,
        }

        for key, value in updates.items():
            if value:
                self.task_state[key] = str(value).strip()

        list_updates = {
            "plan": plan,
            "todo": todo,
            "done": done,
            "blockers": blockers,
        }

        for key, value in list_updates.items():
            normalized_list = self._normalize_text_list(value)
            if normalized_list is not None:
                self.task_state[key] = normalized_list

        self.save()

    def record_decision(
        self,
        decision: str,
        rationale: Optional[str] = None
    ) -> None:
        """
        Record one high-value decision into the decision log.

        Args:
            decision: Decision statement.
            rationale: Optional reason or tradeoff summary.

        Returns:
            None.
        """
        if not decision or not decision.strip():
            return

        self.decision_log.append(
            {
                "decision": decision.strip(),
                "rationale": (rationale or "").strip(),
                "updated_at": int(time.time()),
            }
        )
        self.decision_log = self.decision_log[-self.max_decisions :]
        self.save()

    def remember_episode(
        self,
        topic: str,
        summary: str,
        keywords: Optional[List[str]] = None,
        source: str = "manual"
    ) -> None:
        """
        Persist one episodic memory entry.

        Args:
            topic: Episode topic label.
            summary: Episode summary text.
            keywords: Optional retrieval keywords.
            source: Creation source such as `manual` or `compression`.

        Returns:
            None.
        """
        topic_text = (topic or "").strip() or "general"
        summary_text = (summary or "").strip()
        if not summary_text:
            return

        episode = {
            "topic": topic_text,
            "summary": summary_text,
            "keywords": keywords or self._derive_keywords(topic_text + " " + summary_text),
            "source": source,
            "updated_at": int(time.time()),
        }
        self.episodes.append(episode)
        self.episodes = self.episodes[-self.max_episodes :]
        self.save()

    def push(self, role: str, content: str) -> None:
        """
        Append one conversational turn into short-term memory.

        Args:
            role: Message role such as `user` or `assistant`.
            content: Message text.

        Returns:
            None.
        """
        if not content:
            return

        clean_content = str(content).strip()
        if not clean_content:
            return

        self.messages.append({"role": role, "content": clean_content})

        if role == "user":
            inferred_topic = self._infer_topic_from_text(clean_content)
            if inferred_topic:
                self.task_state["topic"] = inferred_topic
            self.task_state["latest_user_request"] = self._clip_text(clean_content, 220)

        self._compress_overflow_messages()
        self.save()

    def context(
        self,
        query: Optional[str] = None,
        max_chars: Optional[int] = None
    ) -> str:
        """
        Generate a compact layered memory context string for the LLM.

        Args:
            query: Optional current query used for relevance scoring.
            max_chars: Optional maximum character budget for the rendered context.

        Returns:
            Rendered context string.
        """
        budget = max_chars or self.max_context_chars
        sections: List[str] = []

        preferences_section = self._render_preferences_section()
        facts_section = self._render_facts_section()
        task_state_section = self._render_task_state_section()
        decisions_section = self._render_decision_section(query)
        episodes_section = self._render_episode_section(query)
        summary_section = self._render_summary_section()
        recent_section = self._render_recent_messages_section(query)

        for section in [
            preferences_section,
            facts_section,
            task_state_section,
            decisions_section,
            episodes_section,
            summary_section,
            recent_section,
        ]:
            if section:
                sections.append(section)

        return self._fit_sections_to_budget(sections, budget).strip()

    def _normalize_text_list(self, items: Optional[List[str]]) -> Optional[List[str]]:
        """
        Normalize an optional list of text items.

        Args:
            items: Raw list-like value.

        Returns:
            Cleaned list when provided, otherwise `None`.
        """
        if items is None:
            return None

        normalized_items = []
        for item in items:
            text = str(item).strip()
            if text:
                normalized_items.append(text)
        return normalized_items

    def _compress_overflow_messages(self) -> None:
        """
        Compress overflowed short-term messages into episodic and summary memory.

        Args:
            None.

        Returns:
            None.
        """
        if len(self.messages) <= self.max_messages:
            return

        preserve_count = min(self.preserve_recent_messages, self.max_messages)
        overflow_messages = self.messages[:-preserve_count]
        self.messages = self.messages[-preserve_count :]

        if not overflow_messages:
            return

        episode = self._create_episode_from_messages(overflow_messages)
        if episode:
            self.episodes.append(episode)
            self.episodes = self.episodes[-self.max_episodes :]
            self._append_rolling_summary(episode["summary"])

    def _create_episode_from_messages(
        self,
        messages: List[Dict[str, str]]
    ) -> Optional[Dict[str, Any]]:
        """
        Build one episodic memory item from a batch of older messages.

        Args:
            messages: Overflowed short-term messages.

        Returns:
            Episodic memory dictionary when the batch is non-empty.
        """
        if not messages:
            return None

        summary = self._build_chunk_summary(messages)
        topic = self._infer_topic_from_messages(messages)

        return {
            "topic": topic,
            "summary": summary,
            "keywords": self._derive_keywords(topic + " " + summary),
            "message_count": len(messages),
            "source": "compression",
            "updated_at": int(time.time()),
        }

    def _build_chunk_summary(
        self,
        messages: List[Dict[str, str]]
    ) -> str:
        """
        Build a compact textual summary for a chunk of messages.

        Args:
            messages: Messages to summarize.

        Returns:
            Compact chunk summary.
        """
        lines = []
        for message in messages[-6:]:
            role = message.get("role", "unknown").strip().title()
            content = self._clip_text(message.get("content", ""), 140)
            if content:
                lines.append(f"{role}: {content}")

        if not lines:
            return ""

        return " | ".join(lines)

    def _append_rolling_summary(self, new_summary: str) -> None:
        """
        Append one chunk summary into the bounded rolling summary.

        Args:
            new_summary: New summary text to append.

        Returns:
            None.
        """
        summary_text = (new_summary or "").strip()
        if not summary_text:
            return

        if self.rolling_summary:
            combined = self.rolling_summary.rstrip() + "\n" + summary_text
        else:
            combined = summary_text

        if len(combined) > self.max_summary_chars:
            combined = "..." + combined[-(self.max_summary_chars - 3) :]

        self.rolling_summary = combined

    def _fit_sections_to_budget(
        self,
        sections: List[str],
        max_chars: int
    ) -> str:
        """
        Fit ordered context sections into a fixed character budget.

        Args:
            sections: Ordered context sections.
            max_chars: Character budget.

        Returns:
            Concatenated section string within the budget.
        """
        rendered_sections: List[str] = []
        used_chars = 0

        for section in sections:
            clean_section = section.strip()
            if not clean_section:
                continue

            separator_cost = 2 if rendered_sections else 0
            remaining_chars = max_chars - used_chars - separator_cost

            if remaining_chars <= 40:
                break

            if len(clean_section) > remaining_chars:
                clean_section = self._clip_text(clean_section, remaining_chars)

            rendered_sections.append(clean_section)
            used_chars += len(clean_section) + separator_cost

        return "\n\n".join(rendered_sections)

    def _render_preferences_section(self) -> str:
        """
        Render the stable preference section.

        Args:
            None.

        Returns:
            Rendered preference section.
        """
        if not self.preferences:
            return ""

        preference_pairs = ", ".join(
            f"{key}={value}" for key, value in sorted(self.preferences.items())
        )
        return f"User preferences: {preference_pairs}"

    def _render_facts_section(self) -> str:
        """
        Render the stable fact section.

        Args:
            None.

        Returns:
            Rendered fact section.
        """
        if not self.facts:
            return ""

        fact_pairs = ", ".join(f"{key}={value}" for key, value in sorted(self.facts.items()))
        return f"User facts: {fact_pairs}"

    def _render_task_state_section(self) -> str:
        """
        Render the structured task-state section.

        Args:
            None.

        Returns:
            Rendered task-state section.
        """
        if not self.task_state:
            return ""

        lines: List[str] = []
        scalar_keys = ["goal", "topic", "latest_user_request"]
        list_keys = ["plan", "todo", "done", "blockers"]

        for key in scalar_keys:
            value = self.task_state.get(key)
            if value:
                lines.append(f"{key}={value}")

        for key in list_keys:
            values = self.task_state.get(key) or []
            if values:
                lines.append(f"{key}=" + "; ".join(values))

        if not lines:
            return ""

        return "Task state:\n" + "\n".join(lines)

    def _render_summary_section(self) -> str:
        """
        Render the rolling long-term summary section.

        Args:
            None.

        Returns:
            Rendered summary section.
        """
        if not self.rolling_summary:
            return ""
        return "Long-term summary:\n" + self.rolling_summary.strip()

    def _render_recent_messages_section(self, query: Optional[str]) -> str:
        """
        Render the short-term recent conversation section.

        Args:
            query: Optional live query string.

        Returns:
            Rendered recent-message section.
        """
        if not self.messages:
            return ""

        recent_limit = DEFAULT_RECENT_CONTEXT_MESSAGES if query is None else min(6, DEFAULT_RECENT_CONTEXT_MESSAGES)
        recent_messages = self.messages[-recent_limit :]
        conversation = "\n".join(
            f"{message['role']}: {message['content']}"
            for message in recent_messages
        )
        return "Recent conversation:\n" + conversation

    def _render_episode_section(self, query: Optional[str]) -> str:
        """
        Render the most relevant episodic memories for the current query.

        Args:
            query: Optional live query string.

        Returns:
            Rendered episodic-memory section.
        """
        selected_episodes = self._select_relevant_episodes(query)
        if not selected_episodes:
            return ""

        lines = []
        for episode in selected_episodes:
            topic = episode.get("topic", "general")
            summary = episode.get("summary", "")
            lines.append(f"- [{topic}] {summary}")

        return "Relevant episodes:\n" + "\n".join(lines)

    def _render_decision_section(self, query: Optional[str]) -> str:
        """
        Render the most relevant high-value decisions for the current query.

        Args:
            query: Optional live query string.

        Returns:
            Rendered decision section.
        """
        selected_decisions = self._select_relevant_decisions(query)
        if not selected_decisions:
            return ""

        lines = []
        for item in selected_decisions:
            decision = item.get("decision", "")
            rationale = item.get("rationale", "")
            if rationale:
                lines.append(f"- {decision} (reason: {rationale})")
            else:
                lines.append(f"- {decision}")

        return "Key decisions:\n" + "\n".join(lines)

    def _select_relevant_episodes(
        self,
        query: Optional[str],
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Select relevant episodic memories for one query.

        Args:
            query: Optional query string used for scoring.
            limit: Maximum number of episodes to return.

        Returns:
            Selected episode dictionaries.
        """
        if not self.episodes:
            return []

        if not query or not query.strip():
            return self.episodes[-limit :]

        scored_episodes = []
        for episode in self.episodes:
            score = self._score_relevance(
                query,
                " ".join(
                    [
                        str(episode.get("topic", "")),
                        str(episode.get("summary", "")),
                        " ".join(episode.get("keywords", []) or []),
                    ]
                )
            )
            if score > 0:
                scored_episodes.append((score, episode.get("updated_at", 0), episode))

        if not scored_episodes:
            return self.episodes[-1:]

        scored_episodes.sort(key = lambda item: (item[0], item[1]), reverse = True)
        return [item[2] for item in scored_episodes[:limit]]

    def _select_relevant_decisions(
        self,
        query: Optional[str],
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Select relevant decision-log entries for one query.

        Args:
            query: Optional query string used for scoring.
            limit: Maximum number of decisions to return.

        Returns:
            Selected decision dictionaries.
        """
        if not self.decision_log:
            return []

        if not query or not query.strip():
            return self.decision_log[-limit :]

        scored_decisions = []
        for item in self.decision_log:
            score = self._score_relevance(
                query,
                str(item.get("decision", "")) + " " + str(item.get("rationale", ""))
            )
            if score > 0:
                scored_decisions.append((score, item.get("updated_at", 0), item))

        if not scored_decisions:
            return self.decision_log[-1:]

        scored_decisions.sort(key = lambda value: (value[0], value[1]), reverse = True)
        return [value[2] for value in scored_decisions[:limit]]

    def _score_relevance(
        self,
        query: str,
        text: str
    ) -> int:
        """
        Compute a simple lexical overlap score between a query and memory text.

        Args:
            query: Query string.
            text: Candidate memory text.

        Returns:
            Integer overlap score.
        """
        query_tokens = set(self._tokenize(query))
        text_tokens = set(self._tokenize(text))
        if not query_tokens or not text_tokens:
            return 0
        return len(query_tokens.intersection(text_tokens))

    def _infer_topic_from_messages(
        self,
        messages: List[Dict[str, str]]
    ) -> str:
        """
        Infer a coarse topic label from a batch of messages.

        Args:
            messages: Message batch.

        Returns:
            Topic string.
        """
        user_messages = [
            message.get("content", "")
            for message in messages
            if message.get("role") == "user"
        ]
        if user_messages:
            return self._infer_topic_from_text(user_messages[-1])

        all_text = " ".join(message.get("content", "") for message in messages)
        return self._infer_topic_from_text(all_text)

    def _infer_topic_from_text(self, text: str) -> str:
        """
        Infer a lightweight topic label from free text.

        Args:
            text: Source text.

        Returns:
            Topic string.
        """
        keywords = self._derive_keywords(text, limit = 4)
        if keywords:
            return "/".join(keywords)
        return "general"

    def _derive_keywords(
        self,
        text: str,
        limit: int = 6
    ) -> List[str]:
        """
        Derive normalized keywords from text for retrieval.

        Args:
            text: Source text.
            limit: Maximum number of keywords to return.

        Returns:
            Keyword list.
        """
        keywords = []
        for token in self._tokenize(text):
            if token in STOP_WORDS:
                continue
            if token not in keywords:
                keywords.append(token)
            if len(keywords) >= limit:
                break
        return keywords

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into lowercase retrieval tokens.

        Args:
            text: Source text.

        Returns:
            Token list.
        """
        normalized_text = str(text or "").lower()
        tokens = re.findall(r"[a-z0-9_\-\u4e00-\u9fff]+", normalized_text)
        return [token for token in tokens if len(token) > 1]

    def _clip_text(
        self,
        text: str,
        limit: int
    ) -> str:
        """
        Clip text to a safe length while preserving readability.

        Args:
            text: Source text.
            limit: Maximum returned length.

        Returns:
            Clipped text string.
        """
        clean_text = " ".join(str(text or "").split())
        if len(clean_text) <= limit:
            return clean_text
        if limit <= 3:
            return clean_text[:limit]
        return clean_text[:limit - 3].rstrip() + "..."
