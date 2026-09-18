# ADR 0002 — Self-scoped AI tools take no identity argument

Status: accepted · 2026-09-19

## Context
The assistant answers "what is my outstanding fee?" by calling backend tools.
The obvious design gives the model a `get_fee_balance(student_id)` tool. That
makes the model's output part of the authorization decision: a prompt injection
in an uploaded document, or a jailbroken conversation, could name another
resident's id. This system holds data about young women at a known residential
address, so cross-tenant leakage is the highest-severity failure available.

## Decision
Self-scoped tools declare **no** identity parameter. `ToolContext` carries a
`Principal` built from the authenticated request, and the executor injects it.
Role filtering happens in `specs_for()` before the model runs, and is re-checked
in `execute()`.

## Consequences
- The model is structurally incapable of requesting another student's data: the
  parameter does not exist in the schema it is given.
- Authorization never consults model output, so prompt injection cannot
  escalate privilege — it can at most cause a refusal.
- Staff tools operating on other people (future work) must be separate,
  explicitly role-gated tools with their own audit trail, never a widened
  version of a self-scoped tool.
- Enforced by `tests/unit/test_tool_security.py`, which fails if any self-scoped
  tool grows an identity parameter.
