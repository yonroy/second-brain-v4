# Chia thành đơn vị kiểm được (Sequence Verifiable Units)

Xếp việc thành chuỗi đơn vị nhỏ, mỗi đơn vị kết thúc ở một trạng thái kiểm được. Chưa xanh thì không đi tiếp.

**Vì sao:** lỗi bắt được ngay ở đơn vị gây ra nó thì dễ khoanh vùng. Lỗi bắt được sau cả một loạt thì bị chôn, và bạn đã xây thêm trên nền hỏng.

- **Lúc làm:** trạng thái tốt → một thay đổi → chạy kiểm → đi tiếp. Trong một đợt sửa giống nhau, kiểm từng cái.
- **Lúc giao:** xếp commit theo thứ tự tự chứng minh: test đỏ trước, fix sau; bớt trước, dựng lại sau; đo baseline trước, tối ưu sau.
