# ADR-001 — Hub riêng D:\SecondBrainV3, memory ở hub

**Ngày:** 2026-10-21 · **Trạng thái:** proposed

## Context
v2 để memory ở hub D:\SecondBrainV2. User muốn v3 tách hẳn để v2 giữ nguyên và so sánh được. Codebase còn bản MEMORY/ cũ đã gây đọc/ghi nhầm ở AFE (MONITOR M-029, phiên don-memory). omp/herdr chạy trong WSL, còn Claude Code chạy trên Windows.

## Decision
- Hub mới: `D:\SecondBrainV3\` với `Brain\`, `_global\`, `_projects\`, `_metrics\`, `_archive\`.
- Memory dự án ở `_projects\<p>\`, không có bản nào trong codebase. Codebase chỉ có block CLAUDE.md và hook.
- Tìm hub qua env `SECOND_BRAIN_V3_ROOT` (không dùng lại `SECOND_BRAIN_ROOT` của v2), fallback là thư mục cha của package.
- Đường dẫn lưu dạng `D:/…`. CLI tự đổi sang `/mnt/d/…` khi chạy trong WSL.

## Consequences
- v2 và v3 chạy song song mà không đụng nhau.
- `brain gate` phải phát hiện `MEMORY/` hoặc `HARNESS/` trong codebase.
- `_global` làm mới; my-stack.md lấy từ v2 làm gốc rồi sửa cho đúng.
