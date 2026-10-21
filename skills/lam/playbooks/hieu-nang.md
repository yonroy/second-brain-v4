# Playbook: Hiệu năng

**Bạn chịu trách nhiệm về câu chuyện đo đạc.** Mỗi lần sửa gắn với một số đo. Không đọc code thay cho việc đo.

1. **Đo baseline** bằng lệnh có thể chạy lại, lưu output thành artifact. Kiểm con số theo `nguyen-tac/giai-thich-con-so.md`: chạy nhiều lần, ghi độ lệch, nêu cái gì đang giới hạn nó.
2. **Đặt giả thuyết từ số đo** (profile, trace, counter), không từ cảm giác khi đọc code. Thử theo thứ tự, cái rẻ trước, đạt mục tiêu thì dừng:
   1. Không làm (bỏ việc mà kết quả không ai dùng).
   2. Làm nhưng đừng làm lại (cache, memo).
   3. Làm ít hơn.
   4. Làm sau.
   5. Làm lúc không ai chờ.
   6. Làm song song.
   7. Làm rẻ hơn.
3. **Mỗi lần thử là một đơn vị** (`nguyen-tac/don-vi-kiem-duoc.md`): sửa, đo lại, giữ nếu tốt hơn rõ (vượt độ lệch), revert nếu không.
4. **So artifact trước và sau.** "Không rõ" thì nói là không rõ, không làm tròn thành thắng.
5. **Ghi memory:** baseline và kết quả (số, ngày, lệnh) vào CONTEXT hoặc PROOF. Điều đã học về giới hạn hệ thống thì ghi vào CONTEXT `Kiến trúc`.

**Trả lời:** số baseline, số sau khi sửa, chênh lệch so với độ lệch, cái gì đang giới hạn, đường dẫn artifact.
