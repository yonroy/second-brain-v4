---
name: lam
description: Cách làm một task code cho kỹ trong dự án Second Brain v3. Chọn playbook theo loại việc (điều tra, sửa bug, tính năng, refactor, hiệu năng, prototype, chạy qua đêm, tạm dừng/tiếp tục), chép các bước vào todo, áp nguyên tắc, chứng minh bằng chạy thật và ghi memory đúng chỗ. Dùng cho mọi việc không tầm thường, khi user gõ /lam, hoặc khi CLAUDE.md của dự án trỏ tới skill này.
---

# lam — làm cho kỹ trước, nhanh sau

Viết lại từ `poteto-mode` của pstack (MIT, xem `LICENSE-THIRD-PARTY.md` của package). Đã chỉnh lại cho Second Brain v3:
- memory nằm ở hub;
- bằng chứng ghi bằng `brain verify`;
- spawn subagent phải được user duyệt.

Các file đi kèm nằm cạnh file này: `playbooks/<tên>.md` và `nguyen-tac/<tên>.md`.

## Bắt buộc

1. **Chọn playbook trước khi làm.** Xem bảng Playbook bên dưới, mở `playbooks/<tên>.md` và chép nguyên các bước vào todo list, đặt ở đầu danh sách. Bước nào không làm thì vẫn giữ trong list, ghi `skip: <lý do>`. Việc tiny (dưới 30 phút, không đổi contract) thì vẫn chọn playbook nhưng làm gọn.
   - Phiên không có tool todo (TodoWrite / TaskCreate), ví dụ chạy headless: in checklist `- [ ] <bước>` ngay trước tool call đầu tiên sau khi chọn playbook.
   - Câu trả lời cuối lặp lại checklist đó, mỗi bước ghi `✓` hoặc `skip: <lý do>`.
2. **Memory trước, code sau.** Đọc các quyết định và trap mà `brain start` đã in ra. Việc chạm đúng chủ đề của một quyết định thì làm theo, không làm ngược. Muốn làm khác thì nói rõ và ghi quyết định mới vào `decisions/INDEX.md`.
3. **Gọi tên dữ liệu trước khi viết logic.** Nói rõ kiểu dữ liệu, bảng hay state machine nào sẽ mang logic này (`nguyen-tac/mo-hinh-hoa-mien.md`).
4. **Chứng minh trên thứ thật.** Chạy test, chạy lệnh, đọc giá trị thật. "Đã compile" hay "agent con báo xong" chưa phải bằng chứng (`nguyen-tac/chung-minh.md`). Behavior có dòng trong `PROOF.md` thì chạy `brain verify <B-ID>`.
5. **Mỗi khẳng định gắn nhãn** ngay trong câu đó:
   - **[đo]**: đã chạy và thấy kết quả;
   - **[suy]**: suy ra từ code hoặc tài liệu đã đọc;
   - **[đoán]**: chưa kiểm.
   Đừng giao cho user một việc kiểm tra mà bạn tự chạy được.
6. **Ghi memory trước khi dừng.** Gồm: CONTEXT (Đang làm / Việc tiếp theo, mỗi fact có `[ngày|nguồn]`), trap mới vào TRAPS, quyết định vào `decisions/INDEX.md`. Stop hook sẽ nhắc nếu quên.

## Autonomy

- Việc đảo ngược được (sửa file, chạy test, thử nghiệm trong thư mục tạm): cứ làm, xong thì báo.
- **Luôn dừng và hỏi trước khi** force-push, deploy, xoá dữ liệu, gửi tin ra ngoài.
- **Spawn subagent hoặc agent team:** chấm Cổng 2 (`agent-team-playbook`: veto rồi tính điểm), báo đội hình và đợi user duyệt. Có 2 ngoại lệ:
  - user đã gõ lệnh skill có spawn sẵn trong quy trình (`/soi`, `/hieu` phức tạp);
  - user đã cho phép chạy tự động (xem `playbooks/chay-qua-dem.md`).
- **Câu hỏi "nên làm A hay B" mà trả lời được bằng cách chạy thử** (behavior, thời gian, output) thì không phải câu hỏi cho user. Làm prototype nhỏ rồi để kết quả quyết định (`playbooks/prototype.md`). Chỉ hỏi user về sở thích hoặc quyết định sản phẩm.
- **"Không" là câu trả lời hợp lệ.** Ý tưởng không đáng làm thì nói thẳng và nêu lý do.

## Playbook

| Playbook | Khi nào |
|---|---|
| `dieu-tra` | Câu hỏi chỉ-đọc: X hoạt động thế nào, vì sao Y như vậy, nên A hay B. Không sửa code. |
| `sua-bug` | Có lỗi cần tái hiện, tìm gốc, sửa, chứng minh. |
| `tinh-nang` | Behavior mới hoặc đổi behavior. |
| `refactor` | Đổi cấu trúc, giữ nguyên behavior (đổi tên, tách, gộp, dời). |
| `hieu-nang` | Có độ chậm đo được, cần cải thiện so với baseline. |
| `prototype` | Bản nháp vứt đi, để quyết một lựa chọn thiết kế hoặc trả lời một câu hỏi bằng thực nghiệm. |
| `chay-qua-dem` | Việc dài, user rời đi ("cứ chạy", "đi ngủ", "/loop đến khi xong"). |
| `tam-dung-tiep-tuc` | Dừng an toàn để làm tiếp sau, hoặc nhận lại việc dở của phiên trước. |

Không playbook nào khớp: tự viết 4–8 bước theo khung *hiểu → thiết kế dữ liệu → làm từng đơn vị kiểm được → chứng minh → ghi memory*, chép vào todo, và nói rõ là playbook tự soạn.

## Nguyên tắc

Mỗi nguyên tắc nằm ở `nguyen-tac/<tên>.md`. Đọc file trước khi viện dẫn. Trong câu trả lời, nêu nguyên tắc nào đã làm đổi quyết định nào, và chỉ nêu nguyên tắc đã đọc trong phiên này.

| Nguyên tắc | Khi nào |
|---|---|
| `lam-it` | Định cỡ diff, muốn thêm lớp hay abstraction: thay đổi nhỏ nhất giải quyết được vấn đề. |
| `nen-mong` | Trước khi viết logic: kiểu dữ liệu, thứ tự scaffold rồi mới feature, state dùng chung. |
| `bot-truoc-them-sau` | Trước khi thêm hoặc refactor: xoá phần chết trước, rồi xây trên nền gọn hơn. |
| `mo-hinh-hoa-mien` | Logic có state, nhiều nhánh, lặp giả định: chuyển thành cấu trúc dữ liệu thay vì if/else rải rác. |
| `ranh-gioi` | Validate và xử lý lỗi ở biên (CLI, config, API ngoài). Bên trong tin kiểu dữ liệu. |
| `idempotent` | Lệnh, job, vòng lặp chạy lại khi crash hoặc retry: chạy N lần vẫn ra cùng một trạng thái. |
| `sua-tan-goc` | Debug: lần ngược tới chỗ đầu tiên hệ thống sai và sửa ở đó, không vá chỗ triệu chứng. |
| `chung-minh` | Trước khi nói "xong": kiểm trên thứ thật, không qua proxy hay lời tự khai. |
| `don-vi-kiem-duoc` | Việc nhiều bước: chia thành đơn vị nhỏ, mỗi đơn vị kết thúc bằng một lần kiểm xanh. |
| `giai-thich-con-so` | Trước khi tin hoặc báo một con số đo: biết cái gì giới hạn nó và loại trừ cách đo sai. |
| `giu-context` | Output lớn, file dài: tóm tắt trong luồng chính, việc nặng giao subagent (khi đã được duyệt). |
| `ma-hoa-bai-hoc` | Thấy mình nhắc cùng một điều lần thứ hai: biến nó thành lint, test hoặc script (skill `sua-goc`). |

## Skill phụ

- `hieu`: giải thích một subsystem.
- `tdd`: viết test đỏ trước, rồi mới sửa.
- `soi`: review đa model một diff.
- `sua-goc`: biến lỗi lặp lại thành enforcer.
- `nhat-ky`: log quyết định TSV cho việc dài.

## Câu trả lời cuối

- Câu ngắn, mỗi câu một ý. Mở đầu bằng điều đổi với người dùng hoặc người bảo trì, sau đó mới đến chi tiết kỹ thuật.
- Mỗi khẳng định có nhãn [đo]/[suy]/[đoán]. Có lệnh đã chạy thì dán output then chốt.
- Nêu playbook đã dùng kèm checklist các bước (`✓` / `skip: <lý do>`), và nguyên tắc đã đổi quyết định nào.
- Liệt kê memory đã ghi: file và mục. Không bịa link hay tham chiếu tới thứ chưa đọc.
- Phần mỗi playbook yêu cầu riêng nằm ở dòng **Trả lời:** cuối file playbook đó.
