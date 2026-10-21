# Thao tác idempotent (Make Operations Idempotent)

Thiết kế sao cho chạy bao nhiêu lần, hay lần trước dừng ở đâu, cũng hội tụ về cùng một trạng thái đúng. Mọi thao tác thay đổi state phải trả lời được: "chạy 2 lần thì sao? lần trước crash giữa chừng thì sao?"

**Cách làm:** suy ra mỗi bước từ trạng thái đang tồn tại, không từ ý định của lần chạy trước. Đọc trạng thái hiện tại, so với mục tiêu, chỉ áp phần chênh lệch.

- Ghi dữ liệu: dùng upsert theo khoá tự nhiên, không INSERT thuần, khi job có thể bị retry.
- File: ghi ra file tạm rồi rename, không ghi đè dở dang.
- Lock, file tạm hay bản ghi dở mà lần chạy trước để lại: lần sau phải nhận ra được là đồ cũ.

**Phép thử:** (1) chạy 2 lần liền; (2) giả sử crash ở từng điểm có thể; (3) chạy lại có hội tụ không. Câu trả lời nào là "tuỳ trạng thái còn lại" thì thao tác đó cần một bước đối soát.
