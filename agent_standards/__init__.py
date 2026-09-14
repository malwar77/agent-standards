"""agent-standards: discover, index, and inject your codebase's coding standards.

A lightweight, tool-agnostic system for turning the implicit conventions in an
existing codebase into documented, evidence-backed standards, and injecting only
the relevant ones into AI coding agents (Claude Code, Cursor, or any tool that
reads markdown).

Zero API keys. Deterministic discovery via AST mining. Local retrieval via
BM25-style lexical scoring. Advisory by default, enforced only for standards
you explicitly mark critical.
"""

__version__ = "0.1.0"
