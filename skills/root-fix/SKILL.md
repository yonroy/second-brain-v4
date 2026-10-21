---
name: root-fix
description: Tìm các lỗi agent cứ lặp lại trong dự án và làm cho chúng không thể xảy ra - sửa ở mức cao nhất có thể (kiến trúc, kiểu, lint, test; tài liệu là cuối cùng), chứng minh check fail trên lỗi cũ, ghi bảng luật ↔ enforcer. Dùng khi user gõ /root-fix, trong review hằng tuần, hoặc khi một trap có seen từ 2 ngày trở lên.
---

# root-fix — biến lỗi lặp thành thứ không thể xảy ra

Viết lại từ skill `correct` của pstack (MIT). Đây là bậc 3 trong thang thăng cấp bài học (trap → luật → enforcer).

Hãy giả sử mọi người đóng góp đều là agent chỉ thấy những file nó mở, chép theo ví dụ gần nhất và chọn đường ngắn nhất miễn là chạy được. Thiết kế repo sao cho một thay đổi trông đúng từ một file thì cũng đúng với cả repo.

## 1. Tìm lớp lỗi
- `brain promote`, nếu đã có lệnh này, hoặc đọc `TRAPS.md`: trap có `seen` từ 2 ngày trở lên mà `enforce: none`.
- Đọc thêm: commit revert gần đây, review comment, journal, comment giải thích workaround.
- Gom thành lớp lỗi. Một lớp chỉ được tính khi đã xảy ra từ 2 lần.

## 2. Sửa mỗi lớp ở mức cao nhất làm được
1. **Kiến trúc loại bỏ nó.**
   - Mỗi mẩu state một chủ sở hữu; mỗi việc một cách làm được hỗ trợ.
   - Giấu phần nội bộ để import sai sẽ fail.
   - Thay danh sách đồng bộ tay bằng một nguồn sự thật.
   - Xoá cách cũ, code chết mà agent có thể chép theo.
2. **Kiểu dữ liệu chặn nó**, để trạng thái sai không viết ra được. Code sai vẫn compile được thì thêm lint hoặc check, với thông báo lỗi nêu đúng file, kiểu hoặc hàm nên dùng thay. Mẫu sai đã phổ biến thì chỉ fail khi thay đổi thêm mẫu đó mới.
3. **Test behavior.** Sửa hoặc xoá test vẫn pass khi behavior hỏng, hoặc fail khi chỉ phần nội bộ đổi.
4. **Tài liệu hoặc luật cho agent là cuối cùng**, chỉ dành cho những việc cần phán đoán. Không có gì fail khi agent bỏ qua chúng.

## 3. Sửa và chứng minh
- Sửa các lớp lỗi thường gặp nhất trước, mỗi lớp một commit.
- **Chứng minh check mới fail trên một lỗi thật đã xảy ra** (checkout commit lỗi cũ hoặc tái tạo nó) và pass trên code đúng.
- Lệnh chạy local và chạy trong CI phải là một.
- Ngoại lệ đặt ngay tại dòng vi phạm, kèm lý do, ngày hết hạn và người duyệt.

## 4. Ghi lại
- Trong `TRAPS.md`: đặt `enforce: lint:<tên>`, `test:<path>` hoặc `hook:<tên>` cho trap đã có enforcer.
- Trong bảng **luật ↔ enforcer** của `AGENTS.md`: mỗi luật một dòng kèm thứ enforce nó. Luật đã có mà không gì enforce thì đó là lỗi lặp, sửa ở mức cao nhất ngay trong thay đổi này. Lỗi không thể xảy ra nữa thì bỏ luật đi.
- Ghi quyết định vào `decisions/INDEX.md` nếu thay đổi kiến trúc.

**Trả lời:** từng lớp lỗi kèm bằng chứng (trap, commit, journal), mức đã chọn, vì sao mức cao hơn không làm được, bằng chứng check fail trên lỗi cũ.
