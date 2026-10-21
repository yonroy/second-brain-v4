# ADR-007 — Benchmark trước khi build, so mọi version

**Ngày:** 2026-10-21 · **Trạng thái:** accepted

## Context
v2 chỉ có N=1 và không có nhóm đối chứng, nên không kết luận được luật harness có giúp không (research-overview-charts:41). User muốn so v1, v2 và v3.

## Decision
- `bench/` được xây ở pha 1, trước CLI v3, để đo baseline none, v1 và v2.
- Seed tri thức viết một lần ở dạng trung lập. Mỗi version có một brain adapter dựng seed thành định dạng của mình.
- Báo trung bình ± độ lệch; không kết luận khi chênh lệch nhỏ hơn độ lệch.

## Consequences
- Tốn token: bắt đầu với Claude Code, 8 task × 3 lần lặp.
- Thêm version mới chỉ cần viết thêm một adapter.
