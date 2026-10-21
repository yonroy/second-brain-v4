# ADR-010 — Lớp Recall bằng stdlib, tất định

**Ngày:** 2026-10-21 · **Trạng thái:** accepted

## Context
Đã xem xét cognee (graph + vector, server, LLM). Rủi ro: không tất định, phụ thuộc nặng, tốn quota Claude ở local mode. Bench của v3 cho thấy đưa ra tất định thắng (T06: v2 0/3, v3 3/3). FTS5 có sẵn trên Windows (SQLite 3.50) và WSL (3.46).

## Decision
- Index lịch sử bằng SQLite FTS5 trên văn bản đã chuẩn hoá tiếng Việt (đ→d, bỏ dấu). Code graph bằng `ast` cho Python, regex cho ngôn ngữ khác, cộng index identifier cho mọi file text.
- Không embedding, không LLM. `.index/` là dữ liệu dẫn xuất, dựng lại được.

## Consequences
- Truy hồi theo từ khoá nên có thể trượt khi diễn đạt khác. Bù bằng cách khớp theo file (`files`) và bằng skill `recall`.
- Có thể thêm adapter cognee sau để so, nhưng chỉ khi bench cho thấy recall theo từ khoá là chỗ nghẽn.
