# ADR-009 — Hub riêng D:\SecondBrainV4, package clone từ V3

**Ngày:** 2026-10-21 · **Trạng thái:** accepted

## Context
User chọn tách v4 khỏi v3 để so sánh được, giống lần tách v2 → v3. Bench cần chạy được v3 thật song song với v4.

## Decision
- `D:\SecondBrainV4\Brain` là git clone của `D:\SecondBrainV3\Brain` (remote `v3`), version 4.0.0-dev.
- Env `SECOND_BRAIN_V4_ROOT`, marker CLAUDE.md `SECOND-BRAIN-V4`, hook trỏ tới package V4. Hằng số gom về `brain/__init__.py`.
- Adapter bench `v3` gọi CLI của package V3 bằng subprocess, không import code V4.

## Consequences
- Một codebase không nên cài cả hook v3 lẫn v4. Gate của v4 báo 🔴 nếu thấy block `SECOND-BRAIN-V3` trong CLAUDE.md.
- Sửa lỗi ở v3 phải cherry-pick sang v4 bằng tay.
