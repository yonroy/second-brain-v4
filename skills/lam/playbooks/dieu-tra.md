# Playbook: Điều tra (chỉ đọc)

**Bạn chịu trách nhiệm về câu trả lời có dẫn chứng.** Không sửa code.

1. Đọc memory liên quan: CONTEXT, các quyết định trong `decisions/INDEX.md`, và grep TRAPS theo từ khoá của câu hỏi.
2. Dùng skill `hieu` cho phần "X hoạt động thế nào". Câu hỏi "vì sao" thì chạy `brain recall` (journal, commit, archive), đọc thêm `git log -p` / `git blame` của đoạn liên quan và ADR tương ứng.
3. Câu hỏi "nên A hay B" mà trả lời được bằng cách chạy thử: chạy một thí nghiệm nhỏ trong thư mục tạm (theo `prototype`, nhưng chỉ đo, không giao code).
4. Viết câu trả lời theo khung *Tổng quan · Khái niệm chính · Luồng chạy · Ở đâu trong code · Bẫy*. Nếu là bài toán chọn A hay B thì dùng bảng đánh đổi kèm khuyến nghị.
5. Ghi memory: fact mới đã kiểm chứng vào CONTEXT (`Kiến trúc` / `Môi trường`, có `[ngày|nguồn]`). Bẫy phát hiện được thì ghi vào TRAPS.

Điều tra dẫn tới việc sửa code thì dừng ở đây, chuyển sang `sua-bug` hoặc `tinh-nang`.

**Trả lời:** kết quả điều tra, mỗi khẳng định có `file:dòng` hoặc lệnh làm bằng chứng và nhãn [đo]/[suy]/[đoán]. Hỏi "chắc chưa?" thì đưa phán đoán thật kèm lý do. Tiền đề sai thì nói thẳng.
