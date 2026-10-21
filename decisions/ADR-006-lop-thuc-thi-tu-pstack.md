# ADR-006 — Lớp thực thi viết lại từ pstack

**Ngày:** 2026-10-21 · **Trạng thái:** accepted

## Context
Harness v2 không quy định cách làm bên trong một task. pstack (cursor/plugins, MIT, v0.15.29) có router, playbook và principle, nhưng thiên về Cursor, mặc định dùng model grok, không chặn chờ người duyệt, và nhiều playbook xoay quanh PR.

## Decision
- Viết lại bằng tiếng Việt: router `work`, 8 playbook, 12 principle, 5 skill phụ. Ghi nguồn trong LICENSE-THIRD-PARTY.md.
- Autonomy theo Harness: spawn phải qua Cổng 2 và được user duyệt. Override bằng overnight contract.
- Review đa model dùng `opus`/`sonnet`/`haiku`.

## Consequences
- Không phụ thuộc plugin pstack.
- Benchmark đo được lớp này có giúp hay không.
