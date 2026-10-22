---
name: wiki
description: Tra wiki kiến thức chung (AI agent, harness, memory, công cụ, quy trình) theo NGHĨA của câu hỏi - đọc danh mục `brain wiki map` (mỗi trang một dòng, luôn khớp file thật) rồi chọn trang theo nghĩa; dùng `brain wiki search` nhiều cách hỏi khi cần tìm chi tiết sâu trong trang. Dùng khi user hỏi "wiki nói gì về…", "tra tài liệu…", hoặc khi cần kiến thức nền không riêng dự án. Không dùng cho lịch sử của dự án (đó là skill recall).
---

# wiki — bạn hiểu nghĩa, brain đưa danh mục

Lệnh `brain` = `python "D:/SecondBrainV4/Brain/bin/brain.py"` nếu CLAUDE.md chưa định nghĩa.

## Quy trình (thường 3 bước: map → Read → trả lời)
1. **`brain wiki map`**: mỗi trang một dòng gồm đường dẫn, tiêu đề, `[tag]` và tóm tắt, tự sinh từ file thật nên không bị cũ như `index.md` viết tay. Đọc rồi **chọn 1–2 trang theo nghĩa** của câu hỏi, không theo chữ trùng.
   - Lọc nếu cần: `brain wiki map concepts` (thư mục con) hoặc `brain wiki map --tag memory`.
2. **`Read` đúng trang đã chọn.** Đọc phần Tóm tắt và mục liên quan; không đọc cả wiki.
3. **Chỉ khi danh mục không đủ** (câu hỏi về một chi tiết nằm sâu trong trang, hoặc không trang nào khớp rõ), mới dùng search. Viết 3–6 cách hỏi (Việt/Anh, đồng nghĩa, thuật ngữ, tên cụ thể) rồi chạy một lệnh:
   ```
   brain wiki search "agent nhớ lâu giữa các phiên" "long-term memory" "persistent memory" "memory system"
   ```
   Trang khớp nhiều cách hỏi (`khớp 4/4`) và có tóm tắt đúng ý thì đáng tin. Trang chỉ khớp 1 cách hỏi thường là nhiễu.
4. Mở rộng: `brain wiki related <trang>` cho các trang trỏ tới, được trỏ từ, và cùng tag.

## Trả lời
- Chọn trang **chuyên về chủ đề** (concepts/, entities/, sources/) trước template hoặc prompt, trừ khi câu hỏi hỏi đúng về template.
- Ghi nguồn bằng đường dẫn trang, ví dụ "(wiki: concepts/memory-system.md)".
- Wiki không có thì nói "wiki chưa có", không bịa.
- Kiến thức wiki là **chung**. Nếu nó mâu thuẫn với quyết định hay CONTEXT của dự án đang làm, thì dự án thắng.
