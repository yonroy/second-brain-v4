# Playbook: Refactor

**Bạn giữ contract. Cấu trúc đổi, behavior không đổi.** Phát hiện bug hoặc thiếu tính năng thì tách ra việc riêng. Ship thay đổi cấu trúc trước, dựa trên contract đã ghim.

1. **Đọc quyết định liên quan.** Ví dụ, quy định đổi tên API là phải migrate hết caller rồi xoá tên cũ.
2. **Ghim behavior** trước khi dời bất cứ thứ gì: test đặc tả, snapshot hoặc script so output cũ và mới. Vùng chưa có test thì viết pin trước. Type check và lint không tính là pin.
3. **Gọi tên cấu trúc còn thiếu và hình dạng đích** (`nguyen-tac/mo-hinh-hoa-mien.md`, `nguyen-tac/nen-mong.md`). Cấu trúc mới phải xoá được nhánh hoặc trạng thái sai, không chỉ thêm một lớp gián tiếp.
4. **Bớt trước, thêm sau** (`nguyen-tac/bot-truoc-them-sau.md`): xoá code chết, gộp wrapper chỉ có một caller, bỏ validate thừa.
5. **Dời từng bước nhỏ**, pin luôn xanh.
   - Đổi API: migrate **mọi** caller và xoá API cũ trong cùng một đợt. Không để alias, shim hay hai đường chạy song song.
   - Đổi tên: grep lại toàn repo, cả chuỗi, tài liệu và test, rồi kiểm từng chỗ.
6. **Chứng minh không đổi behavior** trên thứ thật (`nguyen-tac/chung-minh.md`). Chạy toàn bộ test, cộng script so sánh nếu thay đổi lớn.
7. **Đáng giữ không?** Thước đo là người đọc sau dễ hiểu hơn. Diff không làm code dễ đọc hơn ở chỗ nào thì revert.
8. **Ghi memory:** quyết định cấu trúc vào `decisions/INDEX.md`. Fact về module mới vào CONTEXT `Kiến trúc`.

**Trả lời:** cấu trúc đã đổi, pin đã dùng, bằng chứng tương đương, phần dễ đọc hơn, cái gì giữ và cái gì đã revert. Không có behavior mới.
