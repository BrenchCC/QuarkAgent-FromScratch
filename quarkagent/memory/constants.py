import logging

logger = logging.getLogger("QuarkAgent Memory")

DEFAULT_AGENT_SCOPE = "main"
LEGACY_MEMORY_FILENAME = "memory.json"
DEFAULT_MAX_CONTEXT_CHARS = 4000
DEFAULT_RECENT_CONTEXT_MESSAGES = 8
DEFAULT_SUMMARY_CHAR_LIMIT = 1600
DEFAULT_PRESERVE_RECENT_MESSAGES = 5
DEFAULT_MAX_EPISODES = 12
DEFAULT_MAX_DECISIONS = 12
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "we",
    "what",
    "when",
    "where",
    "which",
    "with",
    "you",
    "your",
}
