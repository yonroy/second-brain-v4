---
name: tdd
description: Sửa bug theo kiểu test đỏ trước - viết test nhỏ nhất bắt được lỗi, chạy thấy fail đúng lý do, rồi mới sửa và chạy thấy pass. Dùng khi sửa bug có đường test rẻ, khi user gõ /tdd, hoặc khi playbook sua-bug của skill lam gọi tới.
---

# tdd — test đỏ trước, sửa sau

Viết lại từ skill `tdd` của pstack (MIT). Mục tiêu là một test hồi quy tập trung, fail trước khi sửa và pass sau khi sửa.

## Quy trình
1. **Hiểu lỗi:** behavior mong muốn, behavior hiện tại, đường code bị ảnh hưởng, cách tái hiện nhỏ nhất.
2. **Chọn chỗ kiểm hẹp nhất** mà dự án đã dùng cho đường code này (unit, component, integration). Không thấy đường test thực tế nào thì đừng tạo hạ tầng test mới chỉ để làm cho đủ quy trình.
3. **Viết test fail trước.** Test mô tả behavior mong muốn, không chép lại implementation hiện tại.
4. **Chạy test trước khi sửa.** Thấy nó fail đúng lý do. Nếu nó pass, hoặc fail vì lý do khác, thì sửa test trước.
5. **Sửa nhỏ nhất** để đạt behavior mong muốn, giữ các contract xung quanh.
6. **Chạy lại:** test mới pass, các test liên quan vẫn pass.
7. **Thêm dòng vào `PROOF.md`** (`B-NNN`, behavior, `cmd` chạy test này), rồi chạy `brain verify B-NNN`.

## Khi test fail-trước không thực tế
Ví dụ: cần hạ tầng lớn, mock mong manh, phụ thuộc state production. Khi đó dùng cách kiểm hồi quy gần nhất: script nhắm thẳng vào lỗi, lệnh tái hiện, so snapshot, assert trên log. Không có test còn hơn test tồi. Test tồi là test chủ yếu kiểm mock, chép lại chi tiết implementation, hoặc phụ thuộc thời gian và state toàn cục.

## Không được
- Sửa test cho khớp với implementation sai.
- Nới lỏng assertion có sẵn, trừ khi behavior mong muốn thật sự đã đổi và lý do rõ ràng.

## Báo cáo
- Tên test (hoặc lệnh kiểm), cùng output fail trước khi sửa.
- Output pass sau khi sửa, và các kiểm khác đã chạy.
- Không chứng minh được fail-trước thì nói vì sao, và nói đã dùng cách kiểm nào thay.
