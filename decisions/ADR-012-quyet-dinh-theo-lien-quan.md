# ADR-012 — Quyết định theo liên quan thay cho in tất cả

**Ngày:** 2026-10-21 · **Trạng thái:** accepted

## Context
`brain start` của v3 in mọi quyết định đang hiệu lực. Dự án thật có thể có hàng chục quyết định (AFE có 54 ADR).

## Decision
- SessionStart chỉ in ≤ 8 quyết định liên quan: nhắc tới file đổi gần đây, story đang làm, hoặc ghi ngày ≤ 14 ngày. Các quyết định còn lại chỉ ghi số lượng kèm gợi ý `brain recall`.
- Quyết định liên quan tới file đang chạm được tiêm qua file context (PreToolUse).

## Consequences
- Rủi ro: bỏ sót quyết định không gắn với file nào. T18 (25 quyết định nhiễu) đo đúng rủi ro này. Nếu fail thì nới tiêu chí hoặc in tiêu đề của tất cả quyết định.
