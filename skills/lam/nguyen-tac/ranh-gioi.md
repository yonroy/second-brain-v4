# Kỷ luật ranh giới (Boundary Discipline)

Validate, thu hẹp kiểu và xử lý lỗi ở **biên hệ thống** (tham số CLI, file config, API ngoài, mạng, dữ liệu user). Bên trong thì tin kiểu dữ liệu, không kiểm lại.

- Parse dữ liệu thô thành kiểu của miền ngay tại biên.
- Logic nghiệp vụ là hàm thuần. Lớp vỏ bên ngoài mỏng và máy móc.
- Không để kiểu của transport, storage hay framework lộ ra bề mặt công khai.

Hai câu hỏi để kiểm:
- "Dữ liệu này có đang đi qua biên không?" Không thì validate là thừa.
- "Đoạn này có thể là hàm thuần để lớp vỏ gọi không?" Có thì tách ra.

Lưu ý: luật của dự án (`decisions/`) về kiểu dữ liệu ở biên được ưu tiên hơn sở thích cá nhân.
