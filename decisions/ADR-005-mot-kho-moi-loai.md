# ADR-005 — Mỗi loại tri thức một kho

**Ngày:** 2026-10-21 · **Trạng thái:** proposed

## Context
v2 có nhiều kho trùng nhau: DECISIONS.md và ADR; sessions, MONITOR, runs.tsv và harvested.tsv; CONTEXT §Bẫy, MISTAKES và _global/mistakes; TEST_MATRIX, story Proof và contract. Kết quả là DECISIONS 152 KB bị cũ và mâu thuẫn với code (M-033, M-090).

## Decision
- TRAPS.md thay MISTAKES, có `trigger` và `enforce`.
- decisions/ (INDEX + ADR) thay DECISIONS + ADR.
- PROOF.md thay TEST_MATRIX: bắt buộc có `cmd`, chỉ tool được ghi ✅.
- Story gộp intake.
- journal tự sinh thay sessions viết tay.
- runs.sqlite thay MONITOR, runs.tsv và harvested.tsv.

## Consequences
- Agent luôn biết phải ghi vào đâu.
- Bench adapter v3 dựng seed vào đúng các kho này.
