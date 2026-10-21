# Second Brain v4

Package cho hub `D:\SecondBrainV4`, clone từ v3 (remote `v3`). v3 ở `D:\SecondBrainV3` và v2 ở `D:\SecondBrainV2` vẫn chạy song song, không bị đụng tới.

v4 = v3 + **lớp Recall**: index lịch sử dài và code graph. Spec: [spec/second-brain-v4.md](spec/second-brain-v4.md), ADR-009..012.

- Spec nền (v3, vẫn còn hiệu lực): [spec/second-brain-v3.md](spec/second-brain-v3.md) · Quyết định: [decisions/INDEX.md](decisions/INDEX.md)
- Benchmark so các version: [bench/README.md](bench/README.md). Baseline nằm ở `../_metrics/bench/20261021-baseline.md`.

**Trạng thái v3 (kế thừa):**
- ✅ pha 0: spec;
- ✅ pha 1: benchmark;
- ✅ pha 2: CLI core;
- ✅ pha 3: hook cho Claude Code và omp;
- ✅ pha 4: lớp thực thi (`skills/`: lam + 8 playbook + 12 nguyên tắc, hieu, tdd, soi, sua-goc, nhat-ky);
- ✅ pha 5: đo lường (`ingest`, `stats`, `brief-lint`, `clean`, `promote`);
- ✅ pha 6: bench v3.

**Trạng thái v4:**
- ✅ pha 0: spec;
- ✅ pha 1: hub V4 (env `SECOND_BRAIN_V4_ROOT`, marker `SECOND-BRAIN-V4`, `brain hooks migrate`);
- ⏳ pha 2: bench T17–T24;
- ⏳ pha 3: index;
- ⏳ pha 4: đưa ra cho agent;
- ⏳ pha 5: đo;
- ⏳ pha 6: bench v4;
- ⏳ pha 7: wiki.

## CLI `brain`

Chỉ dùng thư viện chuẩn, Python ≥ 3.11. Chạy từ bất kỳ thư mục nào:

```bash
python D:/SecondBrainV4/Brain/bin/brain.py <lệnh>    # Windows / Git Bash
bin/brain <lệnh>                                    # bash shim, tự chọn python3 hoặc python
bin\brain.cmd <lệnh>                                # cmd / PowerShell
```

| Lệnh | Làm gì |
|---|---|
| `init [--name N] [--path P]` | Tạo `_projects/<N>/` (brain.toml, AGENTS, CONTEXT, TRAPS, PROOF, decisions/, work/, journal/) và merge block vào `CLAUDE.md` của codebase. Idempotent, không ghi đè. |
| `gate [--strict]` | Kiểm: CONTEXT quá dài, fact không tag hoặc quá hạn, ID trùng, trap thiếu trigger, PROOF thiếu `cmd` hoặc có ✅ không nằm trong verify log, story sai status, memory v1/v2 còn trong codebase. |
| `verify [B-ID…]` | Chạy `cmd` trong PROOF.md, ghi `✅/❌ ngày commit` và một dòng vào `_metrics/verify.jsonl`. |
| `start [--hook]` | In gate, CONTEXT, các quyết định đang hiệu lực, 5 trap gần nhất và story đang làm. Ghi lại trạng thái đầu phiên. |
| `end [--check] [--hook]` | Sinh `journal/<ngày>-<sid>.md` từ transcript. `--check`: code đổi mà memory chưa đổi thì trả `{"decision":"block"}`, tối đa một lần mỗi phiên. |
| `trap-check [path\|lệnh] [--hook] [--prompt]` | In trap có `trigger` khớp (path glob hoặc `kw:`). Ở chế độ hook, mỗi trap chỉ báo một lần mỗi phiên. |
| `ingest [claude\|omp\|all] [--since D]` | Đọc transcript Claude Code (Windows) hoặc log omp (chạy trong WSL) vào `_metrics/runs.sqlite`. `--cwd/--name/--version 2 --patterns v2` để đo project v1/v2 làm baseline. |
| `stats [--by agent\|version\|ticket\|project] [--unbacked]` | Bảng số đo thực tế: phút, lỗi tool, token, $, đọc trap, trap được tiêm, Stop chặn, brief đủ, claim không bằng chứng. |
| `brief-lint [FILE\|-] [--hook]` | Kiểm brief subagent đủ mục (Mục tiêu · Không làm · Checklist · Đầu ra · Ngân sách). Hook PreToolUse `Agent` chỉ cảnh báo. |
| `clean backup\|verify-backup DIR\|diff-facts OLD NEW\|retire FILE…` | Port clean-memory v2: không xoá gì, retire cần backup trong ngày, viết lại CONTEXT lớn thì chạy diff-facts trước. |
| `promote [--min-days 2]` | Trap gặp ≥ 2 ngày mà chưa có enforcer, và trap trùng ở project khác (ứng viên `_global`). |
| `skills [install] [--global]` | Link skill lớp thực thi vào `<codebase>/.claude/skills/` (hoặc `~/.claude/skills`). `init` cài sẵn; thêm `--no-skills` nếu không muốn. |
| `hooks migrate` | Codebase đang có brain v3: gỡ block và hook của v3, cài lại hook v4, link skill về v4. **Đừng dùng `hooks remove` của v3**, vì nó gỡ cả hook v4. |
| `hooks [install\|remove\|status]` | Cài, gỡ hoặc xem hook trong `<codebase>/.claude/settings.local.json`. `init` cài sẵn; thêm `--no-hooks` nếu không muốn. |

## Hook

- **Claude Code:** `brain init` cài sẵn các hook: SessionStart, UserPromptSubmit, PreToolUse (trap + brief-lint cho `Agent`), Stop, SessionEnd (ingest). Xem spec §6.
- **omp** (WSL): `omp --hook /mnt/d/SecondBrainV4/Brain/hooks/omp/brain-v4.ts …`. Extension gọi cùng CLI bằng `python3` (đổi bằng env `BRAIN_PYTHON`). Muốn nạp mặc định thì thêm file này vào danh sách extension trong cấu hình omp.

Project được suy ra từ cwd: nằm trong codebase hoặc trong `_projects/<p>` là đủ. Có thể chỉ định bằng `--project <tên>`. Hub lấy từ env `SECOND_BRAIN_V4_ROOT`, mặc định là thư mục cha của package.

## Test

```bash
python -m unittest discover -s tests -t .                                     # Windows
wsl -e bash -lc 'cd /mnt/d/SecondBrainV4/Brain && python3 -m unittest discover -s tests -t .'
```
