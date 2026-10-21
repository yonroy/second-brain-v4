---
name: hieu
description: Giải thích một subsystem hoặc luồng code ("X hoạt động thế nào", "luồng Y đi qua đâu") ở mức một kỹ sư senior onboard, đủ để dựng mô hình trong đầu. Dùng khi user hỏi cách hoạt động, hoặc khi playbook của skill lam yêu cầu bước hieu trước khi sửa.
---

# hieu — giải thích cách một phần code hoạt động

Viết lại từ skill `how` của pstack (MIT).

## 1. Đánh giá độ phức tạp
Phạm vi mơ hồ thì nói cách bạn hiểu câu hỏi rồi bắt đầu đọc. User có thể chỉnh hướng.
- **Đơn giản** (một module, một hàm, một câu hỏi hẹp): tự đọc và giải thích trong một lượt. Phân vân thì chọn đường đơn giản.
- **Phức tạp** (một subsystem trải nhiều file hoặc service, một tính năng cắt ngang): chia câu hỏi thành 2–4 góc nhìn riêng. Muốn giao mỗi góc cho một subagent Explore chỉ-đọc chạy song song thì nêu kế hoạch và đợi user duyệt. Nếu user đã gõ `/hieu` cho câu hỏi phức tạp thì coi như đã duyệt. Không thì tự đọc lần lượt từng góc.

## 2. Đọc
- Đọc memory trước: CONTEXT `Kiến trúc`, `decisions/INDEX.md`, và trap có trigger trùng với vùng này.
- Lần theo đường chạy thật: điểm vào → các bước → nơi dữ liệu được ghi. Mỗi khẳng định ghi `file:dòng`.
- Chỗ nào không chắc thì chạy thử một lệnh nhỏ (in giá trị, chạy test hẹp) thay vì đoán.

## 3. Viết câu trả lời
Theo các mục dưới, bỏ mục không áp dụng:
- **Tổng quan:** 2–3 câu, phần này làm gì và cho ai.
- **Khái niệm chính:** các kiểu dữ liệu và thuật ngữ cần biết.
- **Luồng chạy:** đi qua từng bước, có `file:dòng`.
- **Ở đâu trong code:** bảng file → vai trò.
- **Bẫy:** những chỗ dễ hiểu nhầm hoặc dễ làm hỏng.

Mỗi khẳng định có nhãn [đo]/[suy]/[đoán]. Fact bền vững vừa xác nhận được thì ghi vào CONTEXT `Kiến trúc`, kèm `[ngày|file:…]`.
