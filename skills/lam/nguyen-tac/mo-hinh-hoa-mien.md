# Mô hình hoá miền (Model the Domain)

Đưa miền nghiệp vụ vào một cấu trúc dữ liệu, thay vì rải nó vào các câu if. Cấu trúc khớp với miền thì trạng thái sai không biểu diễn được, và nhiều nhánh tự biến mất. Chọn cấu trúc lúc viết thì rẻ; để sau mới gỡ ra thì thành refactor và hay bị hoãn.

Nên dùng:
- state machine thay cho nhiều boolean hay phase rời rạc;
- kiểu dữ liệu có tên thay cho tham số lỏng hoặc giả định lặp về shape;
- bảng tra, registry hoặc union có phân biệt thay cho chuỗi if/else rải nhiều file;
- module xoay quanh một mảng tri thức, không xoay quanh thứ tự chạy (load → validate → save).

Đừng ép abstraction. Code nhàm chán mà rõ ràng, cục bộ và ít khả năng lớn thêm thì giữ nguyên. Dấu hiệu đã bỏ qua nguyên tắc này: feature mới làm chuỗi if/else dài thêm một nhánh, hoặc có boolean thứ hai phải giữ đồng bộ với boolean thứ nhất.
