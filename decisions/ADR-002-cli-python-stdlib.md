# ADR-002 — Một CLI Python stdlib `brain`

**Ngày:** 2026-10-21 · **Trạng thái:** accepted

## Context
v2 có harness.ps1 và harness.sh viết lặp cùng logic (`pack` chỉ có trong bản sh), PowerShell 5.1 cần BOM, cộng 3 script Python cần PyYAML. Trên Windows `python3` chỉ là stub của Microsoft Store. `python` 3.14 có trên Windows và `python3` 3.14 có trong WSL.

## Decision
- Một package Python `brain`, chạy bằng `python -m brain`, có shim `bin/brain.cmd` (Windows) và `bin/brain` (bash).
- Chỉ dùng stdlib, Python ≥ 3.11. Config dùng TOML qua `tomllib`; ghi TOML bằng writer nhỏ tự viết.
- Mọi file ghi ra đều là UTF-8 không BOM, xuống dòng LF.

## Consequences
- Bỏ được BOM, PyYAML và việc giữ hai bản script.
- Hook gọi được cả từ Windows lẫn WSL.
