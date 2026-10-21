---
name: decision-log
description: Giữ decision log TSV cho việc dài hoặc chạy không giám sát - mỗi quyết định một dòng (thời điểm, pha, quyết định, lý do, bằng chứng, kết quả), để user audit sau. Dùng khi user gõ /decision-log, khi chạy playbook overnight của skill work, hoặc việc nhiều pha user sẽ xem lại sau.
---

# decision-log — dấu vết quyết định có thể audit

Viết lại từ skill `show-me-your-work` của pstack (MIT). Mỗi lần chạy một file log.

## Định dạng
Một file TSV, mỗi quyết định một dòng, mỗi ô nằm trên một dòng. Bằng chứng là con trỏ, không phải đoạn văn.

Vị trí: `<project>/journal/<YYYY-MM-DD>-<slug>.tsv` trong hub. `brain start` in đường dẫn project.

```
ts	phase	decision	why	evidence	result
2026-10-21T09:02:00	frame	đếm khối lượng trước: 40 caller	muốn biết cỡ việc trước khi chạy dài	grep -c get_usr	40 caller, 3 module
2026-10-21T09:40:00	pin	chụp output cũ trước khi đổi	để so cũ/mới	scripts/snap.sh, baseline/	12 snapshot
2026-10-21T11:15:00	module-a	đổi caller module a	giữ thay đổi nhỏ	commit 7c21e0a	test xanh
2026-10-21T12:30:00	module-b	bỏ kết quả của subagent vì test không chạy thật	tự kiểm thay vì tin báo cáo	git reset	đã revert
```

Các cột:
- `ts`: ISO 8601.
- `phase`: pha hoặc luồng việc.
- `decision`: đã chọn hoặc đã làm gì, một dòng.
- `why`: lý do bằng lời thường.
- `evidence`: commit, `file:dòng`, lệnh hoặc đường dẫn artifact.
- `result`: `test xanh`, `đã revert`, `KHÔNG RÕ`, `mở`…

## Ghi gì
- Ghi điểm quyết định và checkpoint, không ghi mọi hành động:
  - chọn một nhánh;
  - xong một đơn vị kèm kết quả kiểm;
  - đổi hướng hoặc revert kèm lý do;
  - gặp chỗ chặn.
- Chạy theo vòng lặp thì mỗi vòng một dòng.
- **Chỉ thêm dòng.** Quyết định sai thì thêm dòng mới thay thế, không sửa hay xoá dòng cũ.
- Ô không được có tab hay xuống dòng. Ô bắt đầu bằng `=`, `+`, `-`, `@` thì thêm `'` ở đầu.

## Trước khi bàn giao
1. **Đối chiếu log với transcript.** Mỗi dòng phải ứng với một việc có thật, và bằng chứng phải mở ra được. Ngã rẽ hay đổi hướng quan trọng mà chưa ghi thì thêm vào. Sửa log bằng cách thêm dòng thay thế, không viết lại.
2. **Review chéo.** Báo user và xin duyệt spawn một subagent `Explore` dùng model khác với model đã làm việc (ví dụ làm bằng opus thì review bằng sonnet). Subagent đọc log và chỉ ra:
   - quyết định có bằng chứng yếu;
   - bước kiểm bị bỏ hoặc khẳng định không có lệnh chứng minh;
   - lựa chọn rủi ro.
   Không được duyệt thì tự rà theo đúng danh sách này và nói rõ là tự rà.
3. Câu trả lời kết thúc bằng mục **Cần xem**: dòng đầu là `rà bởi <model>`, sau đó là từng điểm, trỏ tới dòng log cụ thể. "Không có điểm nào" là câu trả lời hợp lệ.
