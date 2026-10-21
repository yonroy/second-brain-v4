---
name: soi
description: Review đối kháng một diff bằng nhiều model (opus, sonnet) chạy song song, rồi tổng hợp thành phán quyết Làm / Cân nhắc / Ghi nhận / Bỏ. Chỉ chạy khi user gõ /soi hoặc playbook của skill lam gọi tới cho thiết kế đang tranh cãi. Không tự sửa code.
---

# soi — review đa model

Viết lại từ skill `interrogate` của pstack (MIT). Tín hiệu đến từ việc dùng **nhiều model khác nhau**, không phải từ việc gán persona. Kết quả là một phán quyết đã tổng hợp. **Không tự áp thay đổi.**

User gõ `/soi` thì coi như đã duyệt việc spawn reviewer của skill này. Khi skill được playbook gọi tới thì phải báo trước và đợi user duyệt (Cổng 2).

## 1. Phạm vi
Lấy diff cần soi. Ưu tiên theo thứ tự:
1. File hoặc diff user chỉ định;
2. `git diff <nhánh gốc>...HEAD`;
3. `git diff` của các thay đổi chưa commit.

Gom thêm các file ngữ cảnh mà reviewer cần, cùng các quyết định liên quan trong `decisions/INDEX.md`.

## 2. Ý định
Viết một đoạn nêu ý định của thay đổi, rút từ yêu cầu của user, commit message và chính code. Không chắc ý định thì hỏi user trước.

## 3. Reviewer
Spawn các subagent sau **trong cùng một message**, cùng một prompt, chỉ khác model:

| Reviewer | `subagent_type` | `model` |
|---|---|---|
| A | `Explore` | `opus` |
| B | `Explore` | `sonnet` |

Prompt gồm:
- ý định;
- diff;
- các quyết định liên quan;
- tiêu chí: đúng hay sai, bảo mật, idempotent khi retry, xử lý lỗi ở biên, contract bị đổi ngầm, test có kiểm behavior thật không, code thừa;
- yêu cầu mỗi finding có `file:dòng`, mức độ (P1/P2/P3), lý do và kịch bản gây lỗi cụ thể;
- dòng "Chỉ đọc, không sửa file."

## 4. Tổng hợp và phán quyết
Gộp các finding nói cùng một vấn đề và ghi model nào đã nêu. Finding được từ 2 model trở lên nêu độc lập là tín hiệu mạnh nhất. Bạn là reviewer chính, không phải người tổng hợp trung lập. Xếp mỗi finding vào một nhóm:
- **Làm:** vấn đề thật về độ đúng, bảo mật hoặc khả năng bảo trì. Đủ để chặn một PR.
- **Cân nhắc:** hợp lý, nhưng chưa chắc đáng làm ngay. Nêu đánh đổi.
- **Ghi nhận:** đúng về kỹ thuật nhưng chưa cần hành động.
- **Bỏ:** sai, bắt bẻ vụn, hoặc thiếu ngữ cảnh. Kèm lý do ngắn.

## Định dạng trả lời
`### Ý định` · `### Reviewer` (model, số finding) · `### Làm` · `### Cân nhắc` · `### Ghi nhận` · `### Bỏ` · `### Đồng thuận` (chỗ các model khớp nhau và chỗ lệch nhau).
