# Chứng minh nó chạy (Prove It Works)

Kiểm mọi kết quả bằng cách nhìn thẳng vào thứ thật, không suy ra từ proxy, lời tự khai hay "đã compile".

- Đọc giá trị thật, không đọc bản cache hay bản suy ra.
- Kiểm process có sống hay không trực tiếp, không qua trạng thái gián tiếp.
- Subagent báo "xong, test pass" thì tự chạy lại lệnh đó.
- Kiểm thất bại thì nghi cách quan sát trước, rồi mới nghi hệ thống.

**Viết script kiểm khi có thể.** Bằng chứng mạnh nhất là một script tất định mà người khác chạy lại được. Trong Second Brain v3, đó là dòng `PROOF.md` có `cmd`, chạy bằng `brain verify`. Chỉ tool được ghi ✅.
