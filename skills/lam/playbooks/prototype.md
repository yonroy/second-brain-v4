# Playbook: Prototype

**Bạn chịu trách nhiệm về quyết định, không phải về code.** Prototype là dụng cụ dùng xong vứt. Bản thật làm theo `tinh-nang`.

Đây là playbook duy nhất đảo ngược thứ tự ưu tiên: nhanh hơn đẹp, không test, không abstraction. Cái kỹ nằm ở chỗ chọn đúng phương án với chi phí thấp.

1. **Nêu quyết định mà prototype phải trả lời**: bố cục nào, cách tương tác nào, hay behavior hoặc thời gian nào. Không có quyết định cần trả lời thì không làm prototype, chuyển sang `tinh-nang`.
2. **Làm trong thư mục tạm**, tách khỏi code thật. Câu hỏi về behavior hay thời gian: viết script nhỏ nhất trả lời được. Câu hỏi về giao diện: HTML/JS đơn giản nhất hiển thị được ý tưởng.
3. **So 2–3 phương án** cạnh nhau, đặt nhãn rõ (`nguyen-tac/lam-it.md` không áp ở đây, cứ thử thêm phương án user chưa nghĩ tới).
4. **Quan sát chính thứ đang cần quyết**: in output, đo thời gian, chụp màn hình. Ở đây quan sát là test.
5. **Ghi kết luận:** quyết định chọn ghi vào `decisions/INDEX.md`, kèm đường dẫn prototype làm bằng chứng.

**Trả lời:** các phương án đã thử, bằng chứng (output, thời gian, ảnh), đánh đổi, khuyến nghị, đường dẫn thư mục tạm. Nói rõ prototype là đồ vứt đi.
