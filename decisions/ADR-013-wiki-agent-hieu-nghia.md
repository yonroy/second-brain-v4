# ADR-013 — Wiki tra theo nghĩa: agent hiểu, brain tìm (thay chỗ cognee)

**Ngày:** 2026-10-22 · **Trạng thái:** accepted 2026-10-22 (bản rút gọn, xem Quyết định cuối)

## Context
User cần tra wiki kiến thức (`D:\SecondBrain\AI Agentic\wiki`, 79 trang) **theo nghĩa**, không chỉ theo từ khoá, và muốn một lựa chọn thay cognee. Cognee có embedding và graph, nhưng cần server, venv nặng, và LLM để dựng graph (tốn quota). Như vậy là trái ADR-010.

Đo ngày 2026-10-22: đưa nguyên câu hỏi (đã diễn đạt khác chữ với tiêu đề trang) vào FTS5 thì chỉ đúng trang **8/18**.

## Decision
- **Phần hiểu nghĩa giao cho agent.** Skill `wiki` bắt agent viết lại câu hỏi thành 3–6 cách hỏi (Việt/Anh, đồng nghĩa, thuật ngữ, tên cụ thể), rồi gọi `brain wiki search "…" "…"`.
- **Brain gộp kết quả bằng reciprocal-rank fusion.** Mỗi cách hỏi chạy một truy vấn FTS5 riêng; trang được nhiều cách hỏi cùng tìm ra sẽ nổi lên (`khớp k/n cách hỏi`). Kết quả trả về tiêu đề, tóm tắt, mục khớp và đoạn khớp, để agent `Read` đúng chỗ.
- **Khi từ khoá trượt, agent chọn theo nghĩa** từ `brain wiki map`: mỗi trang một dòng gồm đường dẫn, tiêu đề, tag và tóm tắt.
- **Có quan hệ giữa trang:** `brain wiki related` cho out-link, back-link và trang cùng tag.
- **Index ở mức hub:** `<hub>/.index/wiki.sqlite`, cấu hình `<hub>/wiki.toml`. Index tăng dần mỗi lần tra, không cần nhớ chạy `index`.
- **Hook prompt tuỳ chọn và tắt mặc định.** Khi bật, nó chỉ tiêm con trỏ (≤ 2 trang khớp mạnh), không tiêm nội dung trang.

## Consequences
- Vẫn stdlib, tất định ở phần brain, không server, không tốn quota khi index.
- Chất lượng phụ thuộc agent có chịu viết nhiều cách hỏi hay không. Vì vậy phải đo bằng `bench.wiki_eval`, so với agent không có v4.1 (tự đọc `index.md` và grep).
- Khi wiki lên hàng nghìn trang, hoặc eval cho thấy fusion vẫn trượt nhiều, mới xét thêm embedding local (`sqlite-vec` cộng một model nhỏ) như một mode của `wiki.search`. Giao diện CLI và skill giữ nguyên.

## Kết quả eval (2026-10-22, `docs/bench/20261022-wiki-eval.md`)
- Search thô: 8/18 đúng. Agent tự đọc `index.md`: **18/18, 14 giây/câu**. Skill `wiki` bản map-first: 18/18, 39 giây/câu.
- Kết luận: phần hiểu nghĩa đúng là đến từ agent đọc danh mục. Nhưng ở cỡ wiki hiện tại, skill và search **không thắng** baseline mà còn chậm hơn.
- Giữ `brain wiki map` / `search` / `related` như công cụ. Có bật skill mặc định hay không thì chờ user quyết; cần eval thêm cho wiki lớn, danh mục cũ, và câu hỏi về chi tiết sâu.

## Quyết định cuối (user chốt 2026-10-22: phương án 1+2)
- **Mặc định:** agent đọc danh mục và chọn theo nghĩa. Có một dòng trong CLAUDE block, SessionStart và SCHEMA.md của wiki: "`brain wiki map` (hoặc index.md), chọn trang theo nghĩa rồi Read".
- **`brain wiki map|search|related`** được giữ làm công cụ. `map` thay cho index.md khi index.md cũ.
- **Skill `wiki` là opt-in** (`brain skills install --only wiki`), không cài cùng `init`.
- **Hook prompt** vẫn tắt.
- **Xét lại khi:** wiki vượt khoảng 300 trang, hoặc có eval câu hỏi chi tiết sâu.
