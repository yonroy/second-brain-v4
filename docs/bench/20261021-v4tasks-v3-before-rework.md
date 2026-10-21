# Bench report

- Lượt chạy: 24 · model: sonnet · task: 8

## Tổng hợp theo brain

| Brain | n | Pass | Tránh trap | Đọc memory | Cập nhật memory | Chạy test | Claim không bằng chứng | Lỗi chạy | $ / lượt | Giây / lượt | Token vào / lượt |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v3 | 24 | 14/24 (58%) | 10/15 (67%) | 24/24 (100%) | 23/24 (96%) | 24/24 (100%) | 0/24 (0%) | 0 | 0.492 ± 0.126 | 140 ± 50 | 1236878 ± 355515 |

## Pass theo task

| Task | Loại | v3 |
|---|---|---|
| T17 | history | 3/3 |
| T18 | efficiency | 3/3 |
| T19 | history | 0/3 |
| T20 | graph | 1/3 |
| T21 | graph | 0/3 |
| T22 | history | 3/3 |
| T23 | history | 1/3 |
| T24 | efficiency | 3/3 |

## Ghi chú đọc số

- `±` là độ lệch chuẩn giữa các lượt. Chênh lệch giữa hai brain nhỏ hơn độ lệch thì **chưa kết luận được**.
- `Đọc memory` / `Cập nhật memory` không áp cho `none`.
- `Claim không bằng chứng`: câu trả lời cuối nói test pass/xanh nhưng transcript không có lệnh chạy test.
