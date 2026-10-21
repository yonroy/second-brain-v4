# ADR-008 — Đo từ transcript, một schema chung

**Ngày:** 2026-10-21 · **Trạng thái:** proposed

## Context
agent-ops v2 chỉ đọc được log omp, có hardcode miền, và harvest ghi đôi. Agent tự khai sai khoảng 1/3.

## Decision
- Adapter claude và omp đưa dữ liệu về `_metrics/runs.sqlite` (bảng runs và events), gắn brain_version.
- Khoá chống trùng là `(source, session_id, message_id)`.
- Vai trò agent lấy từ `brain.toml [roles]`.

## Consequences
- `brain stats` so được số liệu thực tế giữa các version, bổ sung cho benchmark.
- Pha 5 phải khớp `agent_ops.py runs` trong khoảng ±5% trên cùng log AFE.
