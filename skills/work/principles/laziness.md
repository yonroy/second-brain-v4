# Làm ít (Laziness Protocol)

- **Gom quyết định về một chỗ.** Cùng một lựa chọn đừng lặp ở nhiều nơi. Đặt nó sau một nguồn sự thật duy nhất, rồi truyền kết quả đi như một cờ đơn giản.
- **Diff nhỏ nhất.** Thay đổi nhỏ nhất giải quyết được vấn đề. Ít dòng tốt hơn boilerplate "đẹp".
- **Nghiêng về xoá.** Trước khi thêm abstraction, layer hay tham số truyền xuyên nhiều tầng, hỏi xem xoá bớt có giải được không.

Dấu hiệu đã bỏ qua nguyên tắc này: diff có helper chỉ một chỗ gọi, có tham số "phòng khi cần", hoặc có lớp bọc không xoá được nhánh nào.
