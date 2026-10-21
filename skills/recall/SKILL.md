---
name: recall
description: Tra lịch sử dài và code graph của dự án Second Brain v4 trước khi đoán - dùng `brain recall` khi gặp triệu chứng, quy ước khách hàng, quyết định hoặc "vì sao code thế này", và `brain graph uses` trước khi đổi tên, đổi chữ ký hay xoá một hàm/cột/handler. Dùng khi skill work hoặc playbook gọi tới, hoặc khi user hỏi về chuyện đã làm trước đây.
---

# recall — nhớ trước khi đoán

Lớp Recall của v4 index **journal cũ, mọi quyết định (kể cả đã thay), fact đã dời khỏi CONTEXT (archive), trap và git log**, cùng một code graph của repo. Hook đã tự tiêm một phần, có ngân sách. Skill này dùng khi bạn cần tra **chủ động**.

## Khi nào tra lịch sử: `brain recall "<từ khoá>"`
- Trước khi chọn một quy ước mà dự án có thể đã chốt: TTL, định dạng ngày/tuần, header API, làm tròn, cách gửi email…
- Khi gặp lỗi hoặc triệu chứng: tra theo thông báo lỗi và tên hàm.
- Khi được bảo xoá hoặc "dọn" code trông thừa: chạy `brain recall` theo tên hàm, và `git log -p -- <file>` nếu cần. Code tồn tại thường có lý do.
- Có thể lọc: `--kind decision|journal|archive|commit|trap`, hoặc ưu tiên mục nhắc tới một file: `--file src/x.py`.

## Khi nào tra code graph: `brain graph uses <tên>`
- Trước khi đổi tên, đổi chữ ký hay xoá hàm, class, cột hoặc handler. Kết quả gồm chỗ gọi qua alias (`import x as y`), `functools.partial`, và **tham chiếu bằng chuỗi** trong JSON/TOML/SQL/YAML mà grep `*.py` hay bỏ sót.
- `brain graph dependents <file>`: những file import file này.
- `brain context <file>`: xem trước những gì hook sẽ báo khi mở file.

## Luật
- Kết quả recall là **bằng chứng có ngày**. Mới thì dùng; cũ thì đối chiếu với code hoặc config hiện tại (thứ bậc sự thật của AGENTS.md).
- Dùng điều tìm được thì nêu trong câu trả lời, kèm nhãn và nguồn, ví dụ: "[suy] theo journal 2026-07-12".
- Không tìm thấy thì nói "không có trong lịch sử", rồi mới chọn mặc định hợp lý và ghi quyết định vào `decisions/INDEX.md`.
