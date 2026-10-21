# ADR-003 — Bỏ thang L0–L4, dùng 3 module

**Ngày:** 2026-10-21 · **Trạng thái:** proposed

## Context
Không project nào có artifact của L2–L4 (contract, BOARD, MATURITY). Init v2 không có lệnh lên cấp. Có 17 file / 5 level phải nhớ.

## Decision
- Module `core` luôn bật. `team` (Cổng 2 đầy đủ) và `ops` (control-room) là tuỳ chọn.
- Bỏ BOARD, MATURITY, AUDIT, IMPROVEMENT, TOOL_REGISTRY, story.contract, UPGRADES.

## Consequences
- Project chỉ có 7 file/thư mục.
- Bật module bằng `brain init --modules` (idempotent).
