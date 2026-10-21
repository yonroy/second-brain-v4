# Playbook: Tạm dừng / Tiếp tục

## Tạm dừng (khi user nói dừng, sắp offline, hoặc context sắp đầy)

**Bạn chịu trách nhiệm về một điểm dừng sạch.** Nói "cứ chạy" thì không tạm dừng.

1. Dừng ở ranh giới an toàn: làm xong hoặc lùi lại bước hiện tại. Không bắt đầu việc mới.
2. Không làm hành động không đảo ngược được chỉ để dừng (không push, không mở PR mới).
3. Cất việc dở: một commit `wip:` trên nhánh hiện tại. Cây code đang hỏng thì ghi rõ một dòng trong commit.
4. Ghi điểm tiếp tục vào memory:
   - CONTEXT `Đang làm`: đang ở bước nào, cái gì đã kiểm, có `[ngày|nguồn]`.
   - CONTEXT `Việc tiếp theo`: hành động đầu tiên khi quay lại.
   - Bẫy vừa gặp thì ghi vào TRAPS.
   - Có `decision-log` thì trỏ tới, không chép lại.

**Trả lời:** đang ở đâu, cái gì đã lên đĩa và cái gì chỉ còn trong đầu, commit đã tạo, cây code sạch hay chưa, hành động đầu tiên khi tiếp tục.

## Tiếp tục (nhận lại việc dở)

**Bạn chịu trách nhiệm về điểm tiếp tục.** Đọc dấu vết phiên trước, đừng làm lại.

1. Đọc `brain start` (CONTEXT `Đang làm` / `Việc tiếp theo`), journal mới nhất, `decision-log` nếu có, `git log` và `git status`.
2. Dựng lại trạng thái: nhánh, cái đã xong, quyết định đã chốt. Dấu vết ghi lại là nguồn đáng tin; đừng "kiểm lại từ đầu".
3. So cái đã xong với cái còn lại, gọi tên điểm tiếp tục.
4. Chuyển phần còn lại sang playbook phù hợp.
5. Kiểm khẳng định được thừa kế trên thứ thật, ví dụ chạy lại test liên quan một lần. Lời tự khai "đã pass" không phải bằng chứng.

**Trả lời:** phiên trước dừng ở đâu, cái thừa kế và cái làm lại (tốt nhất là không làm lại gì), điểm tiếp tục, kết quả.
