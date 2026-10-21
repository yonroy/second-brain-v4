# Second Brain v4 — Spec (delta trên v3)

> Trạng thái: **ACCEPTED 2026-10-21** · 2026-10-21 · package `D:\SecondBrainV4\Brain` v4.0.0-dev
> v4 = v3 (`spec/second-brain-v3.md`, vẫn còn hiệu lực ở mọi điểm không nêu dưới đây) + **lớp Recall**.
> Quyết định nền: ADR-009 … ADR-012.

## 1. Vấn đề
v3 chỉ đưa ra **ảnh chụp hiện tại** (CONTEXT, quyết định đang hiệu lực, trap). Các nguồn sau không bao giờ tới được agent:

| Tri thức | Nằm ở | v3 xử lý |
|---|---|---|
| Bài học của phiên cũ | `journal/*.md` | Không bao giờ được đưa ra |
| Fact đã dời khỏi CONTEXT | `_archive/<p>-clean-*/…`, `_archive/<p>-retired/` | Mất dấu |
| Vì sao một đoạn code tồn tại | `git log` của codebase | Không đọc |
| Ai dùng hàm này, có tham chiếu bằng chuỗi | Code | Agent tự grep, hay chỉ grep `*.py` (bench T12) |
| Quyết định | `decisions/` | In **tất cả** quyết định đang hiệu lực mỗi phiên, nên càng nhiều càng tốn token (v3 $0.30/lượt) |

## 2. Nguyên tắc (bổ sung cho v3 §2)
1. **Đưa ra theo liên quan, không theo số lượng.** Mỗi mẩu được tiêm phải gắn với file, lệnh hoặc prompt đang xảy ra.
2. **Tất định.** Cùng index và cùng sự kiện thì tiêm cùng nội dung: không LLM, không embedding.
3. **Có ngân sách.** Tổng ký tự tiêm mỗi phiên có trần. Mỗi mục chỉ tiêm một lần mỗi phiên (sổ ghi).
4. **Index là dữ liệu dẫn xuất.** `.index/` xoá đi thì `brain index --full` dựng lại y hệt. Không ai sửa tay.

## 3. Bố cục
```
D:\SecondBrainV4\            env SECOND_BRAIN_V4_ROOT · marker CLAUDE.md SECOND-BRAIN-V4
├── Brain\                   package (git clone của V3, remote `v3`)
└── _projects\<p>\           như v3, cộng:
    └── .index\
        ├── history.sqlite   FTS5 trên văn bản đã chuẩn hoá tiếng Việt
        └── code.sqlite      symbol · import · call · identifier trong mọi file text
```

## 4. Index lịch sử (`brain/recall/history.py`)
- **Đơn vị:** `(kind, ref, date, path, text, norm, files)`. `kind` ∈:
  - `journal`;
  - `decision` (gồm cả superseded);
  - `trap`, `work`;
  - `archive` (CONTEXT cũ và file đã retire);
  - `commit` (`git log --name-only`: subject, body, các file đổi);
  - `transcript` (digest: mục tiêu phiên và câu trả lời cuối, ≤ 400 ký tự).
- **Chuẩn hoá** (`brain/recall/text.py`): đổi `đ/Đ` thành `d` rồi NFD bỏ dấu và lowercase. FTS5 `unicode61 remove_diacritics 2` không đổi `đ`, đã kiểm ngày 2026-10-21.
- **Cập nhật tăng dần:** file theo `(path, mtime, size, sha1)`; commit tính từ hash mới nhất đã index. `brain index --full` dựng lại từ đầu.
- **Điểm khi truy vấn:** bm25 của FTS5. Nếu có ngữ cảnh file thì cộng điểm cho đơn vị có `files` chứa file đó. Có ngưỡng tối thiểu để không tiêm rác.

## 5. Code graph (`brain/recall/code.py`)
- **Python dùng `ast`:**
  - `def`, `class`, `method`, kèm dòng;
  - `import` / `from`;
  - tên được gọi (`Name`, `Attribute`);
  - chuỗi hằng trong `getattr(obj, "x")` và `"mod:func"`.
- **Ngôn ngữ khác** (js/ts/go/sql): regex định nghĩa và import. Đây là heuristic và spec ghi rõ.
- **Identifier trong mọi file text** (`.py .toml .json .yaml .yml .sql .md .ini .cfg .html .js .ts`), để bắt tham chiếu bằng chuỗi ngoài code.
- **Truy vấn:**
  - `defines(sym)`;
  - `uses(sym)` → `[(file, line, kind ∈ code|string|doc)]`;
  - `dependents(file)`;
  - `deps(file)`.
- **Phạm vi file:** `git ls-files` nếu có git, không thì duyệt thư mục và bỏ `.git`, `node_modules`, `.venv`, `.claude`.

## 6. Đưa ra cho agent (thay §6 của v3 ở các dòng dưới)
| Sự kiện | Lệnh | v4 làm gì |
|---|---|---|
| SessionStart | `brain start --hook` | Như v3, nhưng phần quyết định chỉ in **≤ 8 quyết định liên quan** (nhắc tới file trong `git diff`/commit 7 ngày gần nhất, hoặc story `doing`, hoặc ghi ngày ≤ 14 ngày). Còn lại in 1 dòng "N quyết định khác → `brain recall`". **Bù việc:** index tăng dần và ingest phiên trước nếu SessionEnd không chạy. |
| UserPromptSubmit | `brain recall --hook --prompt` | Tối đa 3 đơn vị lịch sử vượt ngưỡng |
| PreToolUse Read/Edit/Write/MultiEdit/Bash/PowerShell | `brain context --hook` | Trap như v3. Thêm **file context** (≤ 800 ký tự): tối đa 5 file phụ thuộc, tham chiếu chuỗi ngoài `.py`, commit gần nhất có lý do sửa file này, journal / quyết định / archive nhắc tới file. |
| PreToolUse Edit/MultiEdit xoá hoặc đổi tên `def`/`class` | (cùng lệnh) | Cảnh báo: "`X` còn được dùng ở a.py:12, data/schedules.json:3 …" |
| Stop / SessionEnd | như v3 | Thêm index tăng dần |

- **Ngân sách:** `brain.toml [recall] budget_chars = 4000` (tổng mỗi phiên), `file_chars = 800`, `prompt_hits = 3`.
- **Sổ ghi:** `.state/<sid>.ledger.json` ghi `{key: chars}`. `key` là `trap:M-007`, `file:src/x.py`, `hist:<kind>:<ref>`. Đây là bản tổng quát hoá của `traps.py`.

## 7. CLI mới
| Lệnh | Làm gì |
|---|---|
| `index [--full]` | Dựng hoặc cập nhật `.index/` |
| `recall "<q>" [--kind …] [--file path]` | Tìm lịch sử, in ref, ngày, đoạn trích |
| `graph uses\|defines\|dependents\|deps <x>` | Truy vấn code graph |
| `context <path>` | Xem trước nội dung hook sẽ tiêm khi Read file này |

## 8. Skill
- **Skill mới `recall`:** dùng `brain recall` khi gặp triệu chứng hoặc quyết định cũ, `brain graph uses` trước khi đổi hoặc xoá API, thay vì chỉ grep.
- **Sửa playbook trong `work`:**
  - `refactor`, `feature`: trước khi đổi API, chạy `brain graph uses`;
  - `bug-fix`: chạy `brain recall` theo triệu chứng;
  - `investigate`: dùng `recall` cho các câu hỏi "vì sao".

## 9. Đo (bổ sung cho v3 §8)
- `runs` thêm `recall_injected`, `context_injected`, `budget_used`. `events` thêm `injected:<key>`.
- `brain stats` thêm số lần tiêm theo loại, cộng proxy "agent mở file được gợi ý trong 5 tool call kế tiếp".

## 10. Benchmark (bổ sung cho v3 §9)
- **Seed** thêm `[[history]]` (`kind`, `date`, `text`, `files`) và `[repo_extra]` (sinh file nhiễu tất định).
- Adapter `v3` chạy **package V3 thật** (`D:\SecondBrainV3\Brain`). Adapter `v4` dựng giống hệt rồi chạy `brain index`.
- **8 task T17–T24:**
  - T17: lịch sử nằm trong journal;
  - T18: một ADR giữa 25 quyết định nhiễu;
  - T19: git log;
  - T20: chữ ký hàm có 7 caller và `getattr`;
  - T21: đổi tên cột có tham chiếu trong SQL và JSON;
  - T22: digest transcript;
  - T23: fact nằm trong archive;
  - T24: repo 40 file (đo hiệu quả).
- **Cổng chặn:** task nào v3 pass ≥ 2/3 thì phải làm khó thêm trước khi đo v4.

## 11. Ngoài phạm vi
- Truy hồi bằng embedding hoặc LLM;
- cognee;
- migrate project v3 sang v4;
- code graph chính xác cho ngôn ngữ ngoài Python.
