"""Data models for AI Providers and Coding Actions."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ProviderType(str, Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"
    OLLAMA = "ollama"


@dataclass
class AIProviderConfig:
    """Configuration settings for an AI Provider."""
    provider_type: ProviderType = ProviderType.GEMINI
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout: int = 20
    is_encrypted: bool = False

    def get_effective_base_url(self) -> str:
        if self.base_url and self.base_url.strip():
            return self.base_url.strip().rstrip("/")
        if self.provider_type == ProviderType.OLLAMA:
            return "http://localhost:11434/v1"
        if self.provider_type == ProviderType.OPENAI:
            return "https://api.openai.com/v1"
        if self.provider_type == ProviderType.GEMINI:
            return "https://generativelanguage.googleapis.com"
        return ""


class CodingActionType(str, Enum):
    EXPLAIN_CODE = "explain_code"
    FIND_BUGS = "find_bugs"
    REFACTOR = "refactor"
    OPTIMIZE = "optimize"
    GENERATE_TESTS = "generate_tests"
    GENERATE_DOCSTRINGS = "generate_docstrings"
    ADD_TYPE_HINTS = "add_type_hints"
    EXPLAIN_ERROR = "explain_error"
    GENERATE_REGEX = "generate_regex"
    EXPLAIN_REGEX = "explain_regex"
    GENERATE_SQL = "generate_sql"
    EXPLAIN_SQL = "explain_sql"
    CONVERT_CODE = "convert_code"


@dataclass
class CodingActionMeta:
    action_type: CodingActionType
    label: str
    description: str
    system_prompt: str
    user_prompt_template: str


CODING_ACTIONS: Dict[CodingActionType, CodingActionMeta] = {
    CodingActionType.EXPLAIN_CODE: CodingActionMeta(
        action_type=CodingActionType.EXPLAIN_CODE,
        label="📖 Explain Code",
        description="Explain how this code works step-by-step with complexity analysis.",
        system_prompt="You are an expert senior software engineer. Explain the code clearly, concisely, and highlight time/space complexity.",
        user_prompt_template="Explain the following code step-by-step:\n\n```\n{code}\n```",
    ),
    CodingActionType.FIND_BUGS: CodingActionMeta(
        action_type=CodingActionType.FIND_BUGS,
        label="🐛 Find Bugs & Security Flaws",
        description="Detect bugs, edge-case failures, resource leaks, and security risks.",
        system_prompt="You are a security auditor and senior QA architect. Identify all bugs, security issues, and edge cases in the code with concrete fixes.",
        user_prompt_template="Analyze this code for bugs, edge cases, and security vulnerabilities:\n\n```\n{code}\n```",
    ),
    CodingActionType.REFACTOR: CodingActionMeta(
        action_type=CodingActionType.REFACTOR,
        label="🔨 Refactor Code (Clean Architecture)",
        description="Refactor code following Clean Code, SOLID principles, and idiomatic style.",
        system_prompt="You are an expert in Clean Architecture and refactoring. Produce clean, idiomatic, and maintainable code without changing external behavior.",
        user_prompt_template="Refactor the following code for better readability and maintainability:\n\n```\n{code}\n```",
    ),
    CodingActionType.OPTIMIZE: CodingActionMeta(
        action_type=CodingActionType.OPTIMIZE,
        label="⚡ Optimize Performance",
        description="Optimize algorithms and memory consumption for maximum efficiency.",
        system_prompt="You are a high-performance computing specialist. Optimize the given code for execution speed, algorithmic efficiency, and memory footprint.",
        user_prompt_template="Optimize this code for execution speed and memory efficiency:\n\n```\n{code}\n```",
    ),
    CodingActionType.GENERATE_TESTS: CodingActionMeta(
        action_type=CodingActionType.GENERATE_TESTS,
        label="🧪 Generate Unit Tests",
        description="Create comprehensive unit tests covering edge cases and boundary conditions.",
        system_prompt="You are a test-driven development engineer. Generate robust unit tests with full coverage, edge cases, and clear assertions.",
        user_prompt_template="Generate comprehensive unit tests for this code:\n\n```\n{code}\n```",
    ),
    CodingActionType.GENERATE_DOCSTRINGS: CodingActionMeta(
        action_type=CodingActionType.GENERATE_DOCSTRINGS,
        label="📝 Generate Docstrings & Comments",
        description="Add standard docstrings, parameter types, and return descriptions.",
        system_prompt="You are a technical documentation engineer. Add standard, accurate docstrings (Google or Sphinx format) and explanatory comments.",
        user_prompt_template="Add complete docstrings and comments to the following code:\n\n```\n{code}\n```",
    ),
    CodingActionType.ADD_TYPE_HINTS: CodingActionMeta(
        action_type=CodingActionType.ADD_TYPE_HINTS,
        label="🏷️ Add Strict Type Hints",
        description="Annotate variables, function parameters, and return types strictly.",
        system_prompt="You are a static typing specialist. Add strict, precise type annotations compatible with modern type checkers.",
        user_prompt_template="Add strict type annotations to the following code:\n\n```\n{code}\n```",
    ),
    CodingActionType.EXPLAIN_ERROR: CodingActionMeta(
        action_type=CodingActionType.EXPLAIN_ERROR,
        label="🚨 Explain Error / Traceback",
        description="Analyze error stacktrace, pinpoint root cause, and provide solutions.",
        system_prompt="You are a diagnostic debugging specialist. Pinpoint the root cause of the error traceback and provide the exact fix.",
        user_prompt_template="Explain the root cause and provide a fix for this error:\n\n```\n{code}\n```",
    ),
    CodingActionType.GENERATE_REGEX: CodingActionMeta(
        action_type=CodingActionType.GENERATE_REGEX,
        label="🔍 Generate Regular Expression",
        description="Generate a regex pattern matching specified requirements safely.",
        system_prompt="You are a regex specialist. Write safe, efficient regular expressions that avoid ReDoS / catastrophic backtracking.",
        user_prompt_template="Generate a regular expression for the following requirement with an explanation:\n\n{code}",
    ),
    CodingActionType.EXPLAIN_REGEX: CodingActionMeta(
        action_type=CodingActionType.EXPLAIN_REGEX,
        label="🔎 Explain Regular Expression",
        description="Break down regex tokens, capture groups, and flags clearly.",
        system_prompt="You are a regex specialist. Deconstruct the given regular expression token-by-token.",
        user_prompt_template="Deconstruct and explain this regular expression:\n\n`{code}`",
    ),
    CodingActionType.GENERATE_SQL: CodingActionMeta(
        action_type=CodingActionType.GENERATE_SQL,
        label="💾 Generate SQL Query",
        description="Write standard or dialect-specific SQL queries with index tips.",
        system_prompt="You are a database architect. Write correct, optimized SQL queries and suggest indexing strategies.",
        user_prompt_template="Generate an optimized SQL query for the following requirement:\n\n{code}",
    ),
    CodingActionType.EXPLAIN_SQL: CodingActionMeta(
        action_type=CodingActionType.EXPLAIN_SQL,
        label="📊 Explain SQL Query Plan",
        description="Explain SQL logic, joins, filtering order, and potential bottlenecks.",
        system_prompt="You are a database tuning specialist. Explain the logic and performance implications of the query.",
        user_prompt_template="Explain this SQL query and point out any potential performance bottlenecks:\n\n```sql\n{code}\n```",
    ),
    CodingActionType.CONVERT_CODE: CodingActionMeta(
        action_type=CodingActionType.CONVERT_CODE,
        label="🔄 Convert Code Language",
        description="Translate code from one programming language to another with semantic disclaimer.",
        system_prompt="You are a polyglot programmer. Translate code preserving logic, error handling, and idiomatic target conventions. Always include a disclaimer regarding semantic equivalence.",
        user_prompt_template=(
            "Convert the following code from {source_lang} to {target_lang}.\n"
            "Note: Please review the output as subtle runtime or semantic differences may exist across languages.\n\n"
            "```{source_lang}\n{code}\n```"
        ),
    ),
}
