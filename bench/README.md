# bench: so sánh các version Second Brain

Chạy cùng một bộ task cho mỗi "brain" (none / v1 / v2 / v3…). Mỗi brain được nạp **cùng một lượng tri thức**: `seed.toml` được adapter dựng thành định dạng riêng của version đó. Nhờ vậy chênh lệch đo được đến từ cách brain đưa tri thức tới agent, không đến từ lượng tri thức.

## Lệnh

Chạy từ `D:\SecondBrainV3\Brain`:

```bash
python -m bench list                       # task + brain có sẵn
python -m bench validate                   # repo gốc phải fail, repo + solution/ phải pass
python -m bench run --brain none,v1,v2 --task all --repeat 3 --model sonnet --label baseline --jobs 3
python -m bench report ../_metrics/bench/20261021-baseline.jsonl --out ../_metrics/bench/20261021-baseline.md
python -m unittest discover -s tests -t .  # test của adapter / chấm điểm / report
```

Mỗi lượt chạy để lại `D:\_brainbench\<label>-<giờ>\<task>-<brain>-r<n>\` (đổi chỗ bằng env `BRAINBENCH_DIR`). Trong đó:
- `work/`: repo sau khi agent làm;
- `hub/`: memory sau khi agent làm;
- `events.jsonl`: transcript stream-json;
- `stderr.txt`.

## Thêm một version

1. Viết `bench/brains/<tên>.py`, có một lớp con của `Brain`:
   - `setup(work, hub, seed)` dựng seed vào đúng định dạng của version, trả về `Env` (biến môi trường, `--add-dir`);
   - `memory_paths()` trả về các thư mục được coi là memory.
2. Đăng ký lớp đó vào `BRAINS` trong `bench/brains/__init__.py`.
3. Chạy `python -m bench run --brain <tên>,v2 …` rồi so bằng `report`.

## Thêm một task

Tạo `bench/tasks/T0N/`:
- `task.toml` gồm `id`, `title`, `kind`, `prompt`, `memory_keywords`;
- `repo/`;
- `seed.toml`;
- `check.py` có hàm `check(work, events) -> {"pass", "trap_avoided", "notes"}`;
- `solution/`.

Xong thì chạy `validate`.

## Giới hạn đã biết

- Chỉ một model mỗi batch. Mỗi lượt tốn khoảng 0,25–0,4 USD với Sonnet.
- `--setting-sources project,local` bỏ hook và settings của user, nhưng `~/.claude/CLAUDE.md` vẫn được nạp. Phần này giống nhau cho mọi brain.
- `read_memory` / `memory_updated` dựa trên đường dẫn và keyword. Đây là heuristic, cần đọc kèm transcript khi một con số trông bất thường.
- v2 chạy `harness.sh` vì `harness.ps1` bị treo khi gọi từ runner (2026-10-21, chưa rõ nguyên nhân).
