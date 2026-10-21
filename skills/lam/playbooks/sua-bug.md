# Playbook: Sửa bug

**Bạn chịu trách nhiệm cho việc này.** Mỗi dòng code được giữ lại phải truy được về một bằng chứng lúc chạy. Kiểu sửa "thêm cho chắc" chỉ là giả thuyết, không ship. Bằng chứng bác bỏ giả thuyết nào thì revert phần sửa xuất phát từ giả thuyết đó.

1. **Đọc trap, quyết định và lịch sử liên quan.** Chạy `brain recall "<triệu chứng / tên hàm>"` (skill `nho`). Bug này có thể đã được ghi lại, kể cả trong journal cũ hoặc commit.
2. **Tự tái hiện** bằng test, lệnh hoặc script, trên đúng bề mặt lỗi xảy ra. Không tái hiện được thì tạo điều kiện kích hoạt hoặc thêm log cho tới khi nó xảy ra. Chỉ nhờ user khi có lý do cụ thể, sau khi đã thử hết cách.
3. **Tìm nguyên nhân kiểu chia đôi.** Liệt kê các giả thuyết, mỗi lượt chọn phép thử loại được nhiều khả năng nhất, lấy bằng chứng, loại bỏ. Trạng thái không rõ thì thêm log, không đoán. Xác nhận *cơ chế* gây lỗi trước khi sửa (`nguyen-tac/sua-tan-goc.md`).
4. **Test đỏ trước** nếu có đường test rẻ (skill `tdd`): chạy, thấy fail đúng lý do.
5. **Sửa nhỏ nhất** mà bằng chứng biện minh được. Sửa ở chỗ gốc, không chặn ở chỗ triệu chứng. Tìm cùng lỗi ở chỗ khác và sửa hết.
6. **Chứng minh:** repro ban đầu giờ pass, cộng bộ test liên quan. "Không rõ" hoặc kiểm sai bề mặt thì không tính là pass, phải nói rõ. Behavior có dòng PROOF thì chạy `brain verify`. Chưa có dòng thì thêm `B-NNN` kèm `cmd` rồi verify.
7. **Ghi memory:**
   - **Trap** vào TRAPS, có `trigger`. Gặp lại trap cũ thì thêm ngày vào `seen`; `seen` đủ 2 ngày thì xem skill `sua-goc`.
   - **Fact** về hệ thống vào CONTEXT.

**Trả lời:** cái gì hỏng, nguyên nhân gốc, cách sửa, cách đã kiểm. Dán nguyên văn output fail lúc trước và pass lúc sau.
