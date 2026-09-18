# ADR 0003 — Financial and occupancy figures are never model outputs

Status: accepted · 2026-09-19

## Context
LLMs produce fluent, plausible numbers. A wrong hostel fee balance shown to a
student — or a wrong occupancy count used for planning — is worse than no answer.

## Decision
1. There is no writable `balance` column. A student's balance is derived in SQL
   as `SUM(DEBIT) - SUM(CREDIT)` over the append-only `student_ledger_entries`.
2. Occupancy is a `COUNT` over `bed_assignments`, guarded by partial unique
   indexes that make double-allocation a constraint violation.
3. The assistant obtains every figure through a tool; the system prompt forbids
   stating a number from memory, and instructs it to report failure rather than
   estimate.
4. Analytics narration receives ALREADY-COMPUTED metrics and may only explain
   them.

## Consequences
- No AI code path can corrupt a financial figure, because none can write one.
- A tool failure degrades to "I could not retrieve that", never to a guess.
- Python/SQL do arithmetic; Gemini does language. That split is deliberate and
  should not be relaxed for convenience.
