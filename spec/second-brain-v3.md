# Second Brain v3 — Spec

> Trạng thái: **ACCEPTED 2026-10-21** · 2026-10-21 · package `D:\SecondBrainV3\Brain` v3.0.0-dev
> Quyết định nền: `decisions/ADR-001` … `ADR-008`.

## 1. Mục đích

Cho mỗi dự án một "second brain" để agent (Claude Code, omp) **biết đúng điều cần biết đúng lúc, làm việc theo quy trình có bằng chứng, và để lại tri thức sạch cho phiên sau**. Version sau phải chứng minh bằng benchmark là tốt hơn version trước.

v3 thiết kế lại từ đầu dựa trên số liệu dùng thật của v2 (4 dự án ở `D:\SecondBrainV2`, đo ngày 2026-10-21):

| Vấn đề v2 | Bằng chứng | Hướng sửa v3 |
|---|---|---|
| Nghi lễ đóng phiên bị bỏ | "Nghi lễ" có trong 6/113 session AFE; ✅ bịa vì không chạy Nghi lễ 3 (AFE MISTAKES.md:1106) | Stop hook + journal tự sinh (ADR-004) |
| Memory không được đọc | data-engineer mở MISTAKES 1/37 phiên; brief đủ mục 0/132 | Hook nạp trap theo `trigger:` khi sửa file (ADR-004) |
| Memory mục nát | TayCraft CONTEXT 151 KB, 1 dòng 6.674 ký tự; 🔴 PENDING sống 1 tháng sau khi xong | Fact có ngày + nguồn, gate báo quá hạn và quá cỡ (§4) |
| Nhiều sổ trùng nhau | sessions / MONITOR / runs.tsv / harvested.tsv; DECISIONS 152 KB song song 54 ADR | Một kho cho mỗi loại tri thức (ADR-005) |
| Phần không ai dùng | L2–L4, BOARD, MATURITY không tồn tại ở đâu; `_global` patterns/mistakes trống 5 tháng | Bỏ level, còn 3 module (ADR-003) |
| ✅ không đáng tin | TEST_MATRIX ✅ khi spec chưa từng chạy | Chỉ `brain verify` được ghi ✅ (§5) |
| Đo lường gắn omp, hardcode miền | `data-reviewer`, `DP-`, `dbt` trong agent_ops.py; harvest ghi đôi; N=1 không đối chứng | Adapter transcript + benchmark có baseline (ADR-007, ADR-008) |

Phần v2 đáng giữ: mục bẫy trong MISTAKES, CONTEXT §Bẫy/§Môi trường, ADR, TEST_MATRIX khi mỗi dòng trỏ proof thật (vf-airflow), brief cho subagent, backup + `diff-facts` của clean-memory.

## 2. Nguyên tắc

1. **Cấu trúc thắng lời dặn.** Mỗi luật phải có cái enforce (hook, lint, tool). Luật chỉ có chữ thì ghi rõ "chưa enforce" trong bảng luật ↔ enforcer.
2. **Một sự thật, một chỗ.** Mỗi loại tri thức có đúng một file. Không có bản sao ở codebase.
3. **Nạp đúng lúc.** Phiên mở chỉ nạp phần nhỏ nhất. Trap được nạp khi agent chạm file liên quan.
4. **Thứ bậc sự thật** (giữ từ v2.1): output chạy thật > fact có ngày + nguồn > fact không ngày > kiến thức model.
5. **Delta, không viết lại nguyên khối.** Viết lại CONTEXT phải qua `brain clean diff-facts`.
6. **Đo từ log, không từ lời tự khai.**
7. **Mọi 🔴 phải kèm việc cần làm ngay.**
8. **Version mới phải thắng benchmark** so với version cũ và baseline không memory.

## 3. Bố cục hub

```
D:\SecondBrainV3\                 (WSL: /mnt/d/SecondBrainV3)
├── Brain\                        package, git repo `second-brain`
│   ├── brain\                    package Python (CLI)
│   ├── templates\                khung project
│   ├── skills\                   lớp thực thi (lam, playbooks, principles, phụ)
│   ├── hooks\                    snippet settings.json cho Claude Code, wrapper cho omp
│   ├── bench\                    tasks\, brains\{none,v1,v2,v3}\, runner
│   ├── spec\  decisions\  tests\
├── _global\                      my-stack.md, traps.md (trap dùng chung nhiều dự án)
├── _projects\<p>\                brain của từng dự án (§4)
├── _metrics\                     runs.sqlite, bench\<date>-<brain>.jsonl
└── _archive\                     backup do `brain clean` tạo
```

Hub được tìm theo thứ tự: env `SECOND_BRAIN_V3_ROOT` → thư mục cha của package. Mọi đường dẫn lưu trong file đều viết dạng `D:/…`. CLI tự đổi sang `/mnt/d/…` khi chạy trong WSL (ADR-001).

## 4. Bố cục một project

```
_projects\<p>\
├── brain.toml
├── AGENTS.md        ≤ 60 dòng
├── CONTEXT.md       ≤ 120 dòng
├── TRAPS.md
├── PROOF.md
├── decisions\       INDEX.md + ADR-NNN-<slug>.md
├── work\            S-NNN-<slug>.md
└── journal\         YYYY-MM-DD-<session-id8>.md (tự sinh)
```

Ở codebase chỉ có **một block** trong `CLAUDE.md` (marker `<!-- SECOND-BRAIN-V3:START/END -->`) và hook trong `.claude/settings.json`. Gate báo 🔴 nếu thấy `MEMORY/` hoặc `HARNESS/` cũ trong codebase.

### brain.toml
```toml
version = 3
name = "demo"
codebase = "D:/code/demo"
agents = ["claude", "omp"]
modules = ["core"]                 # + "team", "ops"
[roles]                            # thay cho hardcode tên agent của v2
reviewer = ["data-reviewer"]
tester = ["local-tester"]
[limits]
context_lines = 120
line_chars = 400
fact_stale_days = 30
```

### CONTEXT.md — ảnh chụp hiện tại
Có 6 mục cố định: `## Mục tiêu` · `## Môi trường` · `## Kiến trúc` · `## Đang làm` · `## Việc tiếp theo` · `## Khoảng trống đã biết`.
Mỗi dòng fact kết thúc bằng tag `[YYYY-MM-DD|nguồn]`, trong đó nguồn là `cmd:…`, `file:…`, `ADR-NNN`, `S-NNN` hoặc `user`.
```markdown
- Next 16.2.11 + Tailwind v4 [2026-10-21|file:package.json]
- Deploy prod qua GitHub API, không dùng SSH [2026-10-12|ADR-049]
```
Gate báo các trường hợp sau:
- dòng không có tag → 🟡;
- fact quá `fact_stale_days` → 🟡, riêng fact nằm trong `Đang làm` / `Việc tiếp theo` → 🔴;
- vượt `context_lines` hoặc có dòng dài hơn `line_chars` → 🔴.

### TRAPS.md — thay MISTAKES
```markdown
## M-007 pnpm trong WSL xoá node_modules
trigger: package.json, pnpm-lock.yaml, kw:pnpm
seen: 2026-08-02, 2026-09-14
fix: chạy pnpm từ PowerShell; trong WSL dùng `npm ci --prefix`
enforce: none            # hoặc lint:<tên> / test:<path> / hook:<tên> khi đã lên bậc 3
```
- `trigger` nhận path glob hoặc `kw:` (từ khoá trong lệnh Bash hoặc prompt).
- `seen` ghi các ngày gặp lại. `brain promote` lấy trường này để gợi ý thăng cấp khi có từ 2 ngày trở lên.

### PROOF.md — thay TEST_MATRIX
```markdown
| ID | Behavior | cmd | Kết quả (do brain verify ghi) |
|---|---|---|---|
| B-001 | retry không ghi đôi | `pytest tests/test_load.py -k retry` | ✅ 2026-10-21 a1b2c3d |
```
- Cột kết quả chỉ do `brain verify` ghi, gồm ✅/❌, ngày và hash commit.
- `brain gate` đối chiếu cột kết quả với `_metrics/verify.log`. Có ✅ mà log không có dòng tương ứng → 🔴 (✅ bịa).
- Có mục `## Khoảng trống đã biết`, học theo mẫu vf-airflow.

### decisions/ — một kho quyết định
- `INDEX.md` là bảng một dòng cho mỗi quyết định: `ID · ngày · tóm tắt · trạng thái (active/superseded by …)`.
- Quyết định nhỏ chỉ cần một dòng trong INDEX, không cần file riêng.
- Quyết định bền thì có file `ADR-NNN-<slug>.md` theo khung Context / Decision / Consequences.

### work/S-NNN-<slug>.md — story = intake
```markdown
---
id: S-012
type: normal            # tiny không cần file; high-risk bắt buộc có ADR
status: doing           # todo | doing | done | dropped   (lint bắt buộc)
proof: [B-014]
adr: []
---
## Ý định
## Contract chạm vào
## Rủi ro + rollback
## Throughput checkpoint   (blocking · workstream độc lập · shared state · phân rã nhỏ nhất)
## Hình thái thực thi      (single | sub-agent | team — theo Cổng 2, user đã duyệt?)
```
Story chuyển `done` khi mọi `proof` đã ✅ ở commit hiện tại. `brain gate` kiểm điều kiện này.

### journal/ — tự sinh
Stop hook gọi `brain end` để viết journal từ transcript, tối đa 15 dòng: mục tiêu, file đã sửa, lệnh verify đã chạy, quyết định, trap đã chạm. Không viết tay.

## 5. CLI `brain`

Chạy bằng `python -m brain` (Windows) hoặc `python3 -m brain` (WSL). Package có shim `bin/brain.cmd` và `bin/brain`. Chỉ dùng stdlib, Python ≥ 3.11 (ADR-002).

| Lệnh | Làm gì | Ai gọi |
|---|---|---|
| `init [--name] [--path] [--modules]` | tạo `_projects/<p>`, merge block CLAUDE.md, cài hook | user, 1 lần |
| `start` | in gate 1 dòng + CONTEXT + 5 trap gần nhất + story `doing` | hook SessionStart |
| `trap-check <path\|text>` | in trap khớp trigger | hook PreToolUse / UserPromptSubmit |
| `gate` | kiểm sức khoẻ (§4), in 🔴 kèm việc cần làm | start, user |
| `verify [B-NNN…]` | chạy `cmd`, ghi kết quả + ngày + hash, ghi verify.log | agent, user |
| `end [--check]` | sinh journal; `--check` trả exit 2 nếu codebase có diff mà CONTEXT/story chưa cập nhật | hook Stop |
| `clean audit\|backup\|diff-facts\|retire` | port clean-memory v2 | user, hằng tuần |
| `promote` | trap có `seen` ≥ 2 mà `enforce: none` → gợi ý lên bậc 3 | user, hằng tuần |
| `stats [--since] [--by story\|agent\|version]` | số đo từ runs.sqlite (§8) | user |
| `ingest claude\|omp` | đọc transcript vào runs.sqlite | hook Stop, cron |
| `bench run\|report` | benchmark (§9) | user |

## 6. Hook (ADR-004)

`brain init` cài hook vào `<codebase>/.claude/settings.local.json`. File này được thêm vào `.git/info/exclude`, vì lệnh hook trỏ tới hub riêng của từng máy. Lệnh `brain hooks install|remove|status` dùng để cài lại, gỡ hoặc xem trạng thái.

| Sự kiện Claude Code | Lệnh | Tác dụng |
|---|---|---|
| SessionStart (`startup\|resume\|clear\|compact`) | `brain start --hook` | In gate, CONTEXT, quyết định đang hiệu lực, trap gần nhất, story đang làm. Ghi trạng thái đầu phiên. |
| UserPromptSubmit | `brain trap-check --hook --prompt` | Trap có `kw:` khớp prompt |
| PreToolUse `Read\|Edit\|Write\|MultiEdit\|NotebookEdit\|Bash\|PowerShell` | `brain trap-check --hook` | `additionalContext`: trap khớp path glob, hoặc `kw:` trong lệnh / nội dung sửa. Mỗi trap tối đa một lần mỗi phiên. |
| Stop | `brain end --check --hook` | Code đổi mà memory chưa đổi thì trả `{"decision":"block"}`, tối đa một lần. Cuối cùng ghi journal. |

Kiểm thực tế ngày 2026-10-21 bằng `claude -p`:
- Output SessionStart và `additionalContext` của PreToolUse đều tới được agent.
- Trên T07, agent áp dụng trap và tự cập nhật CONTEXT / TRAPS / decisions đúng định dạng.

**omp** (18.4.9, chạy trong WSL) có API extension. File `hooks/omp/brain-v3.ts` gọi cùng CLI qua `python3`:
- `before_agent_start` → `{message}` chứa output của `brain start`;
- `tool_call` → `{additionalContext}` từ `trap-check`;
- `agent_end` → `sendMessage(..., {deliverAs: "nextTurn", triggerTurn: true})` khi `end --check` trả block.

Nạp bằng `omp --hook /mnt/d/SecondBrainV3/Brain/hooks/omp/brain-v3.ts`. Đã kiểm bằng `omp -p` ngày 2026-10-21: context, trap và việc tự chạy lượt bổ sung đều hoạt động.

Chưa làm:
- PreToolUse `Agent` → `brain brief-lint` (cùng lúc port agent-ops, pha 5);
- SessionEnd → `brain ingest` (pha 5).

## 7. Lớp thực thi (ADR-006)

Viết lại từ pstack (MIT, ghi nguồn trong `LICENSE-THIRD-PARTY.md`), bằng tiếng Việt, nằm ở `skills/`:
- **`lam`** là router:
  - khớp task với một playbook;
  - chép nguyên văn các bước vào todo (bước bỏ qua ghi `skip: lý do`);
  - nêu principle nào đã đổi quyết định nào;
  - mỗi claim gắn nhãn **đo / suy / đoán**.
- **Playbook (8):** `dieu-tra` · `sua-bug` · `tinh-nang` · `refactor` · `hieu-nang` · `prototype` · `chay-qua-dem` · `tam-dung-tiep-tuc`.
- **Principle (12):** laziness · foundational-thinking · subtract-before-add · fix-root-causes · prove-it-works · make-operations-idempotent · model-the-domain · boundary-discipline · sequence-verifiable-units · explain-the-number · guard-the-context-window · encode-lessons-in-structure.
- **Skill phụ (5):** `hieu` (how) · `tdd` · `soi` (review đa model) · `sua-goc` (correct, bậc 3) · `nhat-ky` (decision log TSV).
- **Autonomy theo Harness:**
  - việc đảo ngược được thì cứ làm;
  - **spawn subagent/team phải qua Cổng 2 và được user duyệt**;
  - force-push, deploy, xoá data luôn phải dừng hỏi;
  - "cứ chạy / đi ngủ" là override, nhưng phải có overnight contract (goal · điều kiện done kiểm được · quyền · lối thoát).

## 8. Đo lường (ADR-008)

- Adapter `claude` đọc `~/.claude/projects/<slug>/*.jsonl` (và `subagents/`). Adapter `omp` port từ `agent_ops.py` và đọc `~/.omp/agent/sessions/**/*.jsonl` trong WSL.
- Cả hai đưa về một schema chung trong `_metrics/runs.sqlite`:
  - `runs(id, brain_version, project, agent, role, story, started, minutes_active, tokens_in, tokens_out, cost_usd, tool_errors, parent_run)`
  - `events(run_id, ts, kind, detail)`. `kind` ∈ `read_memory`, `trap_injected`, `trap_violated`, `verify`, `claim`, `claim_unbacked`, `end_ok`, `end_blocked`.
- `brain stats` báo:
  - phút / token / $ theo story;
  - vòng làm lại;
  - tỉ lệ trap được nạp trước khi chạm file;
  - tỉ lệ vi phạm trap;
  - claim không có lệnh chứng minh;
  - tỉ lệ đóng phiên sạch;
  - lỗi lọt (trap mới trỏ về story đã done).
- Khoá chống trùng là `(source, session_id, message_id)`, để sửa lỗi harvest ghi đôi của v2.

## 9. Benchmark (ADR-007)

Chi tiết cách chạy: `bench/README.md`.

- `bench/tasks/<id>/` gồm:
  - `task.toml`: prompt, loại, `memory_keywords`;
  - `repo/`: fixture;
  - `seed.toml`: tri thức trung lập (facts, traps, decisions, proofs);
  - `check.py`: checker ẩn, nằm ngoài thư mục chạy nên agent không thấy;
  - `solution/`: lời giải mẫu. `python -m bench validate` kiểm repo gốc fail và lời giải pass.
- `bench/brains/<v>.py` theo hợp đồng `setup(work, hub, seed) -> Env` · `memory_paths()` · `teardown()`. Các adapter có sẵn:
  - `none`;
  - `v1`;
  - `v2`: gọi `harness.sh init --level L1` của `D:\SecondBrainV2\Harness` qua Git Bash. Bản `.ps1` bị treo khi chạy từ runner.
- Chạy: `python -m bench run --brain none,v1,v2 --repeat 3 --model sonnet`. Mỗi lượt có:
  - repo, `git init` và một hub riêng trong `D:\_brainbench\…`;
  - `claude -p` với `--permission-mode bypassPermissions`, `--setting-sources project,local` (bỏ hook của user), `--strict-mcp-config`, `--no-session-persistence`.
- Prompt nào cũng có thêm câu "không hỏi lại, tự quyết", giống nhau cho mọi brain. Không gõ nghi lễ ("đọc"/"xong").
- **Điểm mỗi lượt:**
  - `pass`: checker ẩn;
  - `trap_avoided`;
  - `read_memory`: tool call chạm vào hub;
  - `memory_updated`: dòng mới trong memory chứa keyword;
  - `ran_tests`;
  - `claim_unbacked`: nói pass/xanh mà không có lệnh test (Bash/PowerShell);
  - `cost_usd`, `duration_s`, `tokens_in/out`, `turns`.
- `python -m bench report <jsonl…>` in trung bình ± độ lệch theo brain và ma trận pass theo task. Kết quả lưu ở `_metrics/bench/<ngày>-<label>.jsonl`.
- **8 task:**
  - T01: file sinh tự động (trap);
  - T02: slugify có đ/Đ (trap + proof);
  - T03: dùng fact API nội bộ;
  - T04: fact cổng DB quá hạn;
  - T05: ghi bài học cuối phiên;
  - T06: ADR tiền int + half-up;
  - T07: retry idempotent;
  - T08: đổi tên API, xoá tên cũ (ADR).

## 10. Module

| Module | Có gì |
|---|---|
| `core` | §4–§8, luôn bật |
| `team` | Cổng 2 đầy đủ (veto, chấm điểm, đội hình), playbook agent team |
| `ops` | control-room (port từ v2, đọc runs.sqlite), pha 6 |

## 11. Ngoài phạm vi
- Migrate project v2. v3 chỉ dùng cho dự án mới.
- Playbook xoay quanh PR (babysit, shipping, autopilot).
- Cursor / Copilot.

## 12. Câu hỏi mở (giải trong lúc làm)
1. omp có hook không? Kiểm ở pha 3.
2. Chạy headless omp cho bench như thế nào? Kiểm ở pha 1 (bước mở rộng).
3. `_global/traps.md`: tự gợi ý khi một trap xuất hiện ở ≥ 2 project, hay để user quyết?
