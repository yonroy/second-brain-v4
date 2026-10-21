# Giữ context window (Guard the Context Window)

Context tràn làm giảm chất lượng suy luận và cản tiến độ.

- Chia pha và giới hạn phạm vi: số file mỗi pha, số lượt mỗi pha.
- Output lớn (log dài, file lớn, kết quả grep rộng): lọc trước khi đọc (`head`, `grep`, đọc theo đoạn). Giữ bản tóm tắt trong luồng chính, không giữ payload thô.
- Việc nặng và tách được (đọc rộng, rà nhiều file) có thể giao subagent, nhưng phải theo Cổng 2 và được user duyệt.
- Memory đã có câu trả lời thì đừng đọc lại tài liệu gốc.
