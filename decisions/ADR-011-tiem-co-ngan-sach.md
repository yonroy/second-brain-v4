# ADR-011 — Tiêm context có ngân sách và sổ ghi

**Ngày:** 2026-10-21 · **Trạng thái:** accepted

## Context
v3 là brain đắt nhất. Thêm recall sẽ làm tăng token nếu không có trần. Cognee dùng injection budget và ledger.

## Decision
- Mỗi phiên có trần `budget_chars` (mặc định 4000), file context ≤ 800 ký tự, tối đa 3 kết quả cho prompt.
- Sổ ghi `.state/<sid>.ledger.json`: mỗi key (trap, file, mục lịch sử) tiêm một lần mỗi phiên.

## Consequences
- `brain stats` đo được `budget_used`. Bench T24 đo chi phí so với v3.
