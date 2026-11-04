# ADR-014 — Memory dự án thành vault lat.md dẫn xuất

**Ngày:** 2026-11-04 · **Trạng thái:** accepted

## Context
User muốn dùng [lat.md](https://github.com/vercel-labs/lat.md) để dựng graph cho memory dự án (`_projects/<p>/`). lat là CLI Node.js:
- Vault là thư mục `lat.md/`; mỗi section liên kết nhau bằng `[[file#Section]]` và liên kết vào code bằng `[[src/x.py#func]]`.
- `lat check` kiểm link còn đúng; `lat section`, `lat refs`, `lat search` và `lat ui` dùng để đi trong graph.

Đã chạy thử `lat check` (`@lat.md/core` 0.1.3) trên một project vừa `brain init` ngày 2026-11-04 và gặp 27 lỗi. Không rule nào tắt được, vì lat chỉ hỗ trợ file ignore. Các lỗi gồm:
- tag fact `[2026-11-04|user]` bị đọc thành reference link hỏng, tức mọi fact đều lỗi;
- `brain.toml` không phải file `.md`;
- thiếu file index `<dir>/<dir>.md` ở mỗi thư mục;
- section của CONTEXT, AGENTS, PROOF và work chỉ có list hoặc bảng, không có đoạn mở đầu ≤ 250 ký tự;
- `[demo]:` trong journal bị hiểu thành định nghĩa reference.

Đổi format gốc cho hợp lat sẽ làm vỡ `gate`, `recall` và `trap-check` (ADR-005, ADR-010).

## Decision
- **Vault là dữ liệu dẫn xuất.** `brain lat build` ghi `_projects/<p>/.lat/lat.md/` từ memory gốc. Memory gốc giữ nguyên format và vẫn là nguồn sự thật duy nhất.
  - Cách dựng tất định và chỉ dùng stdlib, như ADR-010.
  - Xoá `.lat/` đi thì build lại ra y hệt. Brain chỉ xoá một `.lat/` có marker `.brain-generated`.
- **Graph dựng từ ID mà brain đã có, không bắt viết link tay:**
  - `ADR-NNN` / `D-NNN` → `decisions/ADR-…` (không có file ADR thì → `decisions/INDEX`);
  - `M-NNN` → section trong TRAPS;
  - `S-NNN` → `work/S-…`;
  - `B-NNN` → PROOF;
  - nguồn `file:src/x.py[#func][:dòng]` của fact → link vào code;
  - trigger trap là đường dẫn có `/` và không có glob → link vào code.

  Quy tắc khi link:
  - ID lạ để nguyên chữ;
  - không tự link trong chính file định nghĩa ID;
  - không đụng heading, code và frontmatter;
  - trong bảng thì link không kèm nhãn, vì `\|` làm lat parse hỏng.
- **Phần lat đòi mà brain không có thì tự sinh:**
  - index cho mỗi thư mục;
  - đoạn mở đầu cho section thiếu (hoặc có đoạn đầu > 250 ký tự);
  - escape `\[` cho ngoặc không phải link.

  Bỏ qua comment HTML, file `_*` (template), `brain.toml` và thư mục bắt đầu bằng dấu chấm.
- **`brain lat check`** chạy `lat check -- <vault>` với cwd là codebase, nên link code được kiểm trên code thật. Output đổi đường dẫn vault và số dòng về file gốc và dòng gốc (`CONTEXT.md:21`).
- **Lệnh lat khác** (`section`, `refs`, `locate`, `search`, `ui` …) chạy qua `brain lat <lệnh> …` trên vault vừa build.
- **lat là công cụ ngoài, tuỳ chọn.** Tìm theo thứ tự: env `BRAIN_LAT`, rồi `lat`, rồi `lat-core` trên PATH. Không có lat thì `build` vẫn chạy, còn `check` trả exit 2 kèm hướng dẫn cài.
- **Gate là opt-in:** `brain.toml [lat] gate = true` thì `brain gate` báo 🟡 khi có link hỏng. Mặc định tắt, vì gate chạy mỗi SessionStart và Stop, gọi Node sẽ tốn thêm khoảng 1 giây.

## Consequences
- Có graph giữa memory và code mà không đổi cách ghi memory. Fact hoặc trap trỏ tới file hay hàm đã bị xoá hoặc đổi tên sẽ bị `lat check` bắt. Đây là loại drift mà `gate` trước giờ không thấy.
- Link chỉ mạnh bằng các ID và `file:` mà agent ghi. Muốn graph dày hơn thì ghi nguồn `file:path#symbol` cho fact.
- Đoạn mở đầu tự sinh mang tính khuôn mẫu, nên `lat search` dựa vào nội dung bên dưới hơn là đoạn này.
- Viết link `[[...]]` trực tiếp trong memory gốc cũng được; build giữ nguyên.
- Chưa tiêm gì từ graph vào hook. `brain context` vẫn dùng code graph của ADR-010. Chỉ xét tiêm `lat refs` khi bench cho thấy cần.
