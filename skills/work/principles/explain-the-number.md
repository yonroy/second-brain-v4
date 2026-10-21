# Giải thích con số (Explain the Number)

Trước khi tin, báo hoặc hành động theo một con số đã đo (tốc độ, độ trễ, tỉ lệ pass, kết quả bench):

- **Hỏi "sao không gấp đôi?"** Nêu tài nguyên hoặc đường code đang giới hạn kết quả (CPU, lock, đĩa, mạng, chính bộ sinh tải), lấy từ profile hoặc counter chứ không đoán khi đọc code.
- **Liệt kê những thứ khác con số có thể đang đo**, rồi loại từng cái bằng bằng chứng: lỗi bị nuốt, việc bị bỏ qua hoặc cache, code không chạy tới, nhiễu, phần quá nhỏ để có ý nghĩa.
- **Giữ bằng chứng đi kèm con số:** số lần chạy, độ lệch, yếu tố giới hạn. Chênh lệch nhỏ hơn độ lệch thì nói "chưa kết luận".
