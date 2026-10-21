# {{NAME}} — Second Brain v3

> Đầu phiên, hook đã chạy `brain start` để nạp CONTEXT, trap và quyết định. Không thấy khối đó thì tự chạy:
> `{{BRAIN}} start`

## Ghi vào đâu (mỗi loại tri thức một chỗ)

| Loại | File | Luật |
|---|---|---|
| Trạng thái hiện tại | `CONTEXT.md` | Sửa tại chỗ, ≤ 120 dòng, mỗi fact có `[YYYY-MM-DD\|nguồn]` |
| Bẫy / lỗi đã gặp | `TRAPS.md` | `## M-NNN`, có `trigger:`; gặp lại thì thêm ngày vào `seen:` |
| Quyết định | `decisions/INDEX.md` | Một dòng mỗi quyết định; quyết định bền thì thêm `ADR-NNN-<slug>.md` |
| Việc normal / high-risk | `work/S-NNN-<slug>.md` | Frontmatter `status` bắt buộc; mẫu ở `work/_template.md` |
| Bằng chứng | `PROOF.md` | Mỗi dòng có `cmd`; chỉ `brain verify` được ghi ✅ |
| Nhật ký phiên | `journal/` | Tự sinh, không viết tay |

## Thứ bậc sự thật
1. Output chạy thật: lệnh, file trong repo, log.
2. Fact có ngày + nguồn, chưa quá 30 ngày: dùng luôn.
3. Fact quá hạn hoặc không có tag: kiểm trên repo trước khi dùng. Nếu sai thì sửa CONTEXT.
4. Kiến thức của model: không dùng làm số hay cấu hình.

## Trước khi code
- Đọc các quyết định và trap mà `brain start` in ra. Việc chạm đúng chủ đề đó thì làm theo, không làm ngược.
- tiny (dưới 30 phút, không đổi contract): làm luôn.
- normal / high-risk: tạo `work/S-NNN`, ghi proof `B-NNN`. high-risk thêm ADR.
- Spawn subagent hoặc team: báo user và **đợi duyệt** trước.

## Trước khi dừng
- Cập nhật CONTEXT (`Đang làm`, `Việc tiếp theo`).
- Gặp lỗi hoặc bẫy mới thì thêm vào TRAPS; có quyết định thì thêm vào `decisions/INDEX.md`.
- Behavior đổi thì chạy `{{BRAIN}} verify <B-ID>`.

## Luật ↔ enforcer

| Luật | Enforcer |
|---|---|
| CONTEXT ≤ 120 dòng, fact có tag, không quá hạn | `brain gate` |
| ✅ chỉ do tool ghi | `brain gate` (đối chiếu verify log) |
| Story có `status` hợp lệ; `done` thì proof đã ✅ | `brain gate` |
| Không có MEMORY/HARNESS trùng trong codebase | `brain gate` |
| Cập nhật memory cuối phiên | Stop hook `brain end --check` |
| Trap được nạp đúng lúc | PreToolUse + UserPromptSubmit `brain trap-check` |
