# Nền móng trước (Foundational Thinking)

**Dữ liệu trước, logic sau.** Chốt kiểu dữ liệu cốt lõi trước khi viết logic. Liệt kê mọi cách dữ liệu được đọc và ghi, rồi chọn cấu trúc hợp với đường chạy chính.

- Gom trùng lặp ở cấp cấu trúc, không ở từng dòng. Ba câu lệnh giống nhau vẫn tốt hơn một abstraction làm quá sớm. Rõ ràng tốt hơn khéo léo.
- **Concurrency:** trước khi chia sẻ state giữa nhiều tác nhân, hỏi "nếu tác nhân khác sửa cái này cùng lúc thì sao?". Câu trả lời không phải "không sao" thì tách ra.
- **Scaffold trước:** thứ giúp được mọi bước sau (test, kiểu dùng chung, công cụ kiểm) thì làm trước. Setup trước feature, test trước fix.
- Mỗi bước thêm vào phải tạo ra hoặc làm sâu thêm một abstraction mạch lạc. Không rải năng lực mới ra các caller thành từng trường hợp đặc biệt.
