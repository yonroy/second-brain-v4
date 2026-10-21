# Second Brain v3

Package cho hub `D:\SecondBrainV3` (hub v2 ở `D:\SecondBrainV2` vẫn chạy song song, không bị đụng tới).

- Spec: [spec/second-brain-v3.md](spec/second-brain-v3.md) · Quyết định: [decisions/INDEX.md](decisions/INDEX.md)
- Benchmark so các version: [bench/README.md](bench/README.md). Baseline nằm ở `../_metrics/bench/20261021-baseline.md`.

**Trạng thái:**
- ✅ pha 0: spec;
- ✅ pha 1: benchmark;
- ✅ pha 2: CLI core;
- ⏳ pha 3: hook (`trap-check`, cài `.claude/settings.json`);
- ⏳ pha 4: lớp thực thi;
- ⏳ pha 5: stats;
- ⏳ pha 6: bench v3;
- ⏳ pha 7: dogfood.

## CLI `brain`

Chỉ dùng thư viện chuẩn, Python ≥ 3.11. Chạy từ bất kỳ thư mục nào:

```bash
python D:/SecondBrainV3/Brain/bin/brain.py <lệnh>    # Windows / Git Bash
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

Project được suy ra từ cwd: nằm trong codebase hoặc trong `_projects/<p>` là đủ. Có thể chỉ định bằng `--project <tên>`. Hub lấy từ env `SECOND_BRAIN_V3_ROOT`, mặc định là thư mục cha của package.

## Test

```bash
python -m unittest discover -s tests -t .                                     # Windows
wsl -e bash -lc 'cd /mnt/d/SecondBrainV3/Brain && python3 -m unittest discover -s tests -t .'
```
