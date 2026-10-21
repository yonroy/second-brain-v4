# ADR-004 — Enforce bằng hook, không bằng nghi lễ

**Ngày:** 2026-10-21 · **Trạng thái:** accepted

## Context
Nghi lễ 3 bị bỏ ở hầu hết các phiên. Lời dặn "grep MISTAKES" không được làm theo (1/37 phiên).

## Decision
- Claude Code: SessionStart → `brain start`; PreToolUse Edit/Write/Bash → `brain trap-check`; PreToolUse Agent → `brain brief-lint` (chỉ cảnh báo); Stop → `brain end --check` (chặn tối đa 1 lần); SessionEnd → `brain ingest`.
- omp: kiểm cơ chế hook ở pha 3; nếu không có thì dùng wrapper `brain run-omp` trong herdr.

## Consequences
- Hook phải nhanh (dưới 300 ms) và không bao giờ làm hỏng phiên: lỗi nội bộ thì in cảnh báo rồi exit 0.
- Có bảng luật ↔ enforcer trong AGENTS.md.
