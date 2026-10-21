# Playbook: Tính năng

**Bạn chịu trách nhiệm về thiết kế.** Hiểu trước, thiết kế dữ liệu, làm từng đơn vị kiểm được, chứng minh.

1. **Intake.** Phân loại tiny, normal hay high-risk.
   - normal: tạo `work/S-NNN-<slug>.md` từ `work/_template.md`, ghi proof `B-NNN`.
   - high-risk (đổi schema, API công khai, auth, tiền): thêm ADR trước khi code.
2. **Quyết định, trap và lịch sử.** Đối chiếu yêu cầu với `decisions/INDEX.md`, TRAPS và `brain recall "<chủ đề>"`. Các quy ước của khách hay của dự án có thể nằm trong journal cũ. Đổi chữ ký API thì chạy `brain graph uses` trước. Có quyết định về đúng chủ đề (định dạng dữ liệu, làm tròn, thư viện được phép…) thì code phải theo.
3. **Hiểu vùng bị chạm** bằng skill `explain`, hoặc đọc trực tiếp nếu vùng nhỏ.
4. **Gọi tên dữ liệu.** Chọn kiểu, bảng hoặc state machine sẽ mang logic, trước khi viết logic (`principles/model-the-domain.md`, `principles/foundations.md`). Có nhiều hình dạng hợp lý thì viết 2 phương án bằng vài dòng rồi chọn có lý do.
5. **Throughput checkpoint**, 4 dòng trong todo. Dòng không áp dụng thì ghi `n/a: <lý do>`.
   - Bước chặn phải làm trước:
   - Luồng việc độc lập:
   - State dùng chung (tách ra trước, chỉ serialize khi là bất biến thật):
   - Phân rã nhỏ nhất (một người làm là tốt nhất thì nói vì sao):
   Có hơn 1 luồng độc lập mà muốn giao subagent thì chấm Cổng 2 và đợi user duyệt.
6. **Làm từng đơn vị kiểm được** (`principles/verifiable-units.md`): sửa một phần, chạy test, xanh rồi mới làm tiếp. Thay đổi nhỏ nhất đạt mục tiêu (`principles/laziness.md`).
7. **Chứng minh** trên bề mặt thật: chạy feature, đọc giá trị, chạy test. Rồi `brain verify <B-ID>`.
8. **Thiết kế còn tranh cãi** thì chạy `cross-review` trước khi coi là xong.
9. **Ghi memory:** story `status: done` (chỉ khi proof đã ✅), fact mới vào CONTEXT, quyết định vào `decisions/INDEX.md`.

**Trả lời:** đã làm gì, chọn gì và vì sao (bảng phương án nếu có), throughput checkpoint, quyết định còn mở.
