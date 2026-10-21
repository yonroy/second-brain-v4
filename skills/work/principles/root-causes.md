# Sửa tận gốc (Fix Root Causes)

Khi debug, sửa chỗ sai chứ không sửa chỗ lỗi lộ ra. Triệu chứng là nơi trạng thái sai trở nên nhìn thấy được. Gốc là chỗ đầu tiên hệ thống làm điều không nên làm.

- Tái hiện trước.
- Hỏi "vì sao" ở mỗi bước, cho tới khi câu trả lời là một quyết định sai trong code chứ không phải hệ quả của bước trước.
- Kẹt thì thêm log hoặc instrument. Đọc lỗi thật và trạng thái thật, không đoán.
- Hỏi xem trạng thái gây lỗi có hợp lệ không.
  - Hợp lệ: code bị vỡ khi gặp nó chính là gốc, xử lý ngay ở đó.
  - Không bao giờ nên tồn tại: thêm guard ở chỗ vỡ chỉ che bug; phải tìm thứ đã sinh ra trạng thái đó.
  - Guard, retry, nuốt lỗi, kẹp giá trị là những cách hay dùng để che bug.
- Lỗi chỉ xảy ra sau khi khởi động lại thì nghi state được lưu xuống đĩa trước (config, cache, lock).
- Tìm cả *mẫu lỗi*, không chỉ một chỗ. Sửa mọi chỗ cùng kiểu.
- Workaround cần một đoạn comment dài để biện minh thì code đang sai.
