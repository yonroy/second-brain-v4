# Playbook: Chạy qua đêm (tự chạy đến khi xong)

**Bạn chịu trách nhiệm về điều kiện kết thúc.** Định nghĩa "xong" trước, rồi chạy tới đó không dừng.

Chỉ dùng khi user cho phép rõ ràng, ví dụ "cứ chạy", "đi ngủ", "/loop đến khi xong". Khi đó, những lần spawn đã nêu trong hợp đồng được coi là đã duyệt.

1. **Viết hợp đồng** vào đầu `decision-log` (decision log). Thiếu mục nào thì tự chọn mặc định hợp lý và ghi rõ.
   - Mục tiêu.
   - Điều kiện xong, viết thành một câu kiểm được (test xanh, 0 caller cũ, repro pass). "Làm 4 tiếng" không phải điều kiện xong.
   - Quyền: được commit, được spawn tối đa N subagent đọc hoặc ghi vùng file nào. Không bao giờ được force-push, deploy hay xoá dữ liệu.
   - Lối thoát: kẹt thật sau X giờ thì dừng và viết lý do.
2. **Làm trong worktree hoặc nhánh riêng** để không đụng việc khác.
3. **Mỗi vòng lặp:**
   - kiểm điều kiện xong;
   - làm thay đổi nhỏ nhất mà bằng chứng biện minh được;
   - kiểm trên thứ thật;
   - tiến lên thì commit, không thì bỏ thay đổi;
   - ghi một dòng `decision-log`.
4. **Gặp sự cố giữa chừng** (test chập chờn, công cụ hỏng, bug liên quan): tự xử lý nếu đảo ngược được, rồi quay lại mục tiêu. Chỉ dừng khi gặp hành động không đảo ngược được, quyết định sản phẩm mà thực nghiệm không trả lời được, hoặc ngõ cụt thật.
5. **Chững lại không phải lý do dừng.** Đổi cách tiếp cận. Không bao giờ nới lỏng điều kiện xong để tuyên bố thắng.
6. **Kết thúc:** ghi memory như các playbook khác, và `brain verify` các proof liên quan.

**Trả lời:** hợp đồng, số vòng đã chạy, cái đã giữ, cái đã bỏ, trạng thái cuối của điều kiện xong, đường dẫn `decision-log`, mục **Cần xem** (điểm rủi ro hoặc bằng chứng yếu).
