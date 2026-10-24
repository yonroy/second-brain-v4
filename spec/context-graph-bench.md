# Context Graph Bench: spec đo lường

> Trạng thái: **DRAFT 2026-10-24**. Đi cùng `brain/recall/cgraph.py` (mini context graph port từ Graphiti) và `bench/cgraph_eval.py` (harness offline).
> Mục tiêu: đo bằng công thức **chất lượng kiến trúc**, **hiệu quả context**, **cách AI đọc hiểu context** và **tốc độ / chi phí thực thi**. Mọi con số phải **trung thực, đầy đủ, truy được nguồn** (§10).

---

## 0. Câu hỏi bench phải trả lời

1. **Kiến trúc.** Graph có biểu diễn đúng thế giới không? Entity gộp đúng chưa, khoảng thời gian của fact đúng chưa, có tất định không?
2. **Truy hồi.** Với một câu hỏi, fact cần thiết có nằm trong danh sách ứng viên, và nằm ở hạng cao không?
3. **Phân bổ context.** Với ngân sách $B$ ký tự, phần được tiêm có **đủ**, **sạch** (không có giá trị cũ mâu thuẫn), **đặc** (ít nhiễu) và **rẻ** không?
4. **Đọc hiểu.** Khi context đủ, model có dùng đúng nó không? Khi context sai hoặc thiếu, model có bị lừa không? Lỗi nằm ở retrieval hay ở reading?
5. **Tốc độ / chi phí.** Ingest, truy vấn và cả phiên agent tốn bao nhiêu thời gian, token và tiền? Chi phí tăng theo cỡ dữ liệu ra sao?

Mỗi câu hỏi ứng với một tầng đo, từ A đến F. Một tầng chỉ có nghĩa khi tầng dưới nó đã được đo. Ví dụ: không kết luận về reader khi chưa biết context có đủ hay không.

---

## 1. Ký hiệu và mô hình hình thức

| Ký hiệu | Nghĩa |
|---|---|
| $H = \{\varepsilon_1,\dots,\varepsilon_N\}$ | Lịch sử: các episode (journal, ADR, commit…), mỗi episode có $t_{\text{ref}}(\varepsilon)$ và văn bản $\text{txt}(\varepsilon)$ |
| $G = (V, E)$ | Context graph: $V$ là entity, $E$ là fact edge |
| $e = (s, r, o, \varphi, [t_v, t_i), [\tau_c, \tau_x), \Pi)$ | Một fact: chủ thể, quan hệ, đối tượng, câu gốc $\varphi$, **valid time** $[t_v, t_i)$, **transaction time** $[\tau_c, \tau_x)$, tập episode chứng cứ $\Pi$ |
| $\mathcal{R}_f \subseteq \mathcal{R}$ | Quan hệ hàm (functional): mỗi $(s, r)$ có tối đa một giá trị đúng tại mỗi thời điểm |
| $q = (\text{txt}, t_q, \text{kind})$ | Câu hỏi. $t_q$ = "bây giờ" hoặc mốc as-of |
| $G^*(q)$ | Tập fact **vàng** bắt buộc phải có trong context để trả lời được |
| $Z^*(q)$ | Tập fact **cũ / mâu thuẫn**: cùng khoá $(s,r)$ với fact vàng nhưng $t_q \notin [t_v, t_i)$ |
| $L_q = (\ell_1,\dots,\ell_m)$ | Danh sách ứng viên đã xếp hạng (retriever $\mathcal{S}$) |
| $c(\ell)$ | Chi phí của một mục, tính bằng ký tự đã render (cộng 1 ký tự xuống dòng). Token $\approx c/\kappa$, với $\kappa$ đo thực tế (ký tự/token) cho từng model |
| $\pi(L_q, B) = S$ | Allocator: chọn $S \subseteq L_q$ có thứ tự sao cho $\sum_{\ell \in S} c(\ell) \le B$ |
| $M(q, S) = \hat a$ | Reader (LLM) trả lời từ context $S$ |
| $a^*(q)$ | Đáp án đúng |

Fact $e$ **hiệu lực** tại $t$ khi và chỉ khi $t_v \le t < t_i$, với $t_i = \varnothing$ nghĩa là còn mở. Context graph là pipeline gồm ba hàm:

$$
q \;\xrightarrow{\;\mathcal{S}\;}\; L_q \;\xrightarrow{\;\pi(\cdot, B)\;}\; S \;\xrightarrow{\;M\;}\; \hat a
$$

Bench đo **từng mũi tên riêng**, rồi đo cả chuỗi.

**Đơn vị chấm.** Fact vàng là **câu gốc** $\varphi$, được sinh duy nhất trong thế giới tổng hợp. Một mục $\ell$ "chứa" $g$ khi $\varphi(g)$ là chuỗi con của $\ell$. Cách chấm này độc lập với hệ: episode nguyên khối hay fact lẻ đều chấm được như nhau.

---

## 2. Tầng A: Kiến trúc graph

### A1. Entity resolution: B-cubed
Với mỗi dạng viết $f$ (CamelCase, kebab, snake, có cách, sai chính tả), $C(f)$ là cụm dự đoán và $C^*(f)$ là cụm vàng:

$$
P_{B^3} = \frac{1}{|F|}\sum_{f}\frac{|C(f)\cap C^*(f)|}{|C(f)|},\qquad
R_{B^3} = \frac{1}{|F|}\sum_{f}\frac{|C(f)\cap C^*(f)|}{|C^*(f)|},\qquad
F_1 = \frac{2PR}{P+R}
$$

- **Báo riêng** $u = $ số dạng viết **không nhận ra**. Đây là entity bị tách, nên BFS không tới được. B-cubed chỉ tính trên các dạng đã nhận nên không thấy lỗi này.
- **Gộp sai (over-merge)** nặng hơn tách sai, vì nó trộn fact của hai service. Báo $P$ trước $R$.

### A2. Đúng đắn thời gian
Với mỗi fact hàm $e$, khoảng dự đoán là $I_e = [t_v, t_i)$ và khoảng vàng là $I^*_e$, tính theo ngày:

$$
\text{IoU}_T(e) = \frac{|I_e \cap I^*_e|}{|I_e \cup I^*_e|},\qquad \overline{\text{IoU}}_T = \frac{1}{|E_f|}\sum_{e\in E_f}\text{IoU}_T(e)
$$

Khoảng mở được tính đến $t_{\text{end}}$ (ngày cuối của lịch sử).

**Invalidation P/R:** $\hat X$ là tập cạnh hệ đã đóng, $X^*$ là tập cạnh phải đóng.

$$
P_{\text{inv}} = \frac{|\hat X \cap X^*|}{|\hat X|},\qquad R_{\text{inv}} = \frac{|\hat X\cap X^*|}{|X^*|},\qquad \text{Exact}_T = \frac{1}{|E_f|}\sum_e \mathbb 1[I_e = I^*_e]
$$

**A2-late.** Cùng các số trên nhưng chỉ tính trên fact đến từ episode **đến muộn** (thứ tự ingest khác thứ tự valid time). Đây là trường hợp dễ sai nhất, đã gặp bug ngày 2026-10-24.

### A3. Nén và khử trùng

$$
\kappa_G = \frac{\sum_{\varepsilon\in H} |\text{txt}(\varepsilon)|}{\sum_{e\in E} c(e)}\quad(\text{tỷ lệ nén}),\qquad
\text{Dedup} = 1-\frac{|E|}{\#\text{lần fact được nói}},\qquad
\overline{|\Pi|} = \frac{1}{|E|}\sum_e |\Pi(e)|
$$

$\overline{|\Pi|}$ là số episode chứng cứ trung bình trên mỗi fact. Fact có $|\Pi|$ lớn được nhắc nhiều lần, nên đáng tin hơn.

### A4. Topology: giải thích nhiễu của BFS
- Bậc trung bình $\bar d$ và **hệ số Gini của bậc**:

$$
\text{Gini} = \frac{\sum_i\sum_j |d_i-d_j|}{2|V|^2\bar d}
$$

  Gini cao nghĩa là có hub, và BFS qua hub sẽ kéo cả trăm cạnh.
- Kích thước biên BFS ở độ sâu $h$: $|\mathcal N_h| \approx \sum_{j=1}^{h} \bar b^{\,j}$, với $\bar b$ là hệ số nhánh hiệu dụng.
- **Tỷ lệ tín hiệu của kênh BFS:**

$$
\text{SNR}_{\text{bfs}} = \frac{|G^* \cap \mathcal N_d|}{|\mathcal N_d|}
$$

  Số này cho biết vì sao cần trộn BFS với BM25 bằng RRF, thay vì dùng BFS một mình.

### A5. Tất định (cổng cứng)

$$
D = \mathbb 1\big[\,h(G_{\text{full}}) = h(G_{\text{full}}') = h(G_{\text{incremental}})\,\big]
$$

$h$ là hash của mọi bảng sau khi đã sắp xếp. $D = 0$ thì **dừng bench**: mọi số phía sau đều không lặp lại được (spec v4 §2.2).

### A6. Trích xuất (chế độ project, có nhãn tay)
Lấy mẫu $n \ge 50$ câu thật từ journal và ADR, gán nhãn entity và fact bằng tay. Báo precision/recall của `extract()` ở mức entity và mức fact.

---

## 3. Tầng B: Truy hồi (trước khi đóng gói)

Đặt $g_i = |\{x\in G^*: x \sqsubseteq \ell_i\}|$, tức số fact vàng mà mục hạng $i$ chứa. $k$ mặc định bằng 10.

| ID | Thước đo | Công thức |
|---|---|---|
| B1 | Recall@k | $\dfrac{|\{x\in G^*: \exists i\le k,\ x\sqsubseteq \ell_i\}|}{|G^*|}$ |
| B2 | Precision@k | $\dfrac{|\{i\le k: g_i>0\}|}{k}$ |
| B3 | MRR | $\dfrac{1}{\min\{i: g_i>0\}}$ (0 nếu không có) |
| B4 | nDCG@k | $\dfrac{\sum_{i\le k} g_i/\log_2(i+1)}{\sum_{i\le \min(k,|G^*|)} 1/\log_2(i+1)}$ |
| B5 | Path recall (multi-hop) | $\mathbb 1[G^* \subseteq L_q[{:}k]]$. Đủ **mọi** chặng mới tính |
| B6 | Stale@k | $\dfrac{|\{i\le k: \ell_i \cap Z^* \ne\varnothing\}|}{k}$ (càng thấp càng tốt) |
| B7 | Temporal top-1 | $\mathbb 1[\text{fact hàm hạng cao nhất của khoá }(s,r) \in G^*]$ |
| B8 | Đóng góp kênh | $\Delta_c = \text{Metric}(\text{all}) - \text{Metric}(\text{all}\setminus c)$, $c\in\{\text{bm25},\text{bfs}\}$ |
| B9 | Bổ sung giữa kênh | $\text{Overlap@k} = J(\text{top}_k^{\text{bm25}}, \text{top}_k^{\text{bfs}})$; trần fusion $=\text{Recall@k}(\text{bm25}\cup\text{bfs})$ |

**Fusion.** RRF có dạng

$$
\text{score}(e) = \sum_{c}\frac{1}{k_{\text{rrf}} + \text{rank}_c(e)}
$$

Bench quét $k_{\text{rrf}} \in \{1, 10, 60\}$: Graphiti dùng 1, Cormack et al. dùng 60. Báo độ nhạy $\partial\,\text{nDCG}/\partial k_{\text{rrf}}$ (sai phân). Overlap thấp mà trần fusion cao nghĩa là hai kênh bổ sung cho nhau, và fusion đáng giữ.

---

## 4. Tầng C: Phân bổ context (trọng tâm)

Đây là phần **thật sự tới được agent**. Ranking tốt mà đóng gói tệ thì vẫn hỏng.

### C0. Bài toán tối ưu
Allocator giải bài toán knapsack có ích lợi submodular:

$$
\max_{S\subseteq L_q}\; F(S)\quad \text{s.t.}\quad \sum_{\ell\in S} c(\ell)\le B
$$

$$
F(S) = \alpha\sum_{\ell\in S}\widetilde{\text{rel}}(\ell) \;+\; (1-\alpha)\,\frac{w\!\left(\bigcup_{\ell\in S}U_\ell\right)}{w\!\left(\bigcup_{\ell\in L_q}U_\ell\right)},\qquad w(u) = \log\!\left(1+\frac{m}{\text{df}(u)}\right)
$$

- $U_\ell$ là tập "đơn vị thông tin" của mục: term của câu cộng id entity.
- $\widetilde{\text{rel}}$ là điểm RRF đã chia cho giá trị lớn nhất.
- $F$ là tổng của một hàm modular và một hàm coverage có trọng số, nên **đơn điệu và submodular**.
- Greedy theo $\Delta F/c^r$, rồi so với singleton tốt nhất, cho đảm bảo $F(S_\pi) \ge \tfrac12(1-\tfrac1e)\,F(S_{\text{OPT}})$ (Khuller–Moss–Naor 1999; Lin & Bilmes 2010).

Ba policy được so: `topk` (đang dùng trong v4), `mmr` và `cover`. MMR greedy có dạng

$$
\ell^{\star}=\arg\max_{\ell\notin S}\;\lambda\,\widetilde{\text{rel}}(\ell)-(1-\lambda)\max_{j\in S}J(U_\ell,U_j)
$$

Đây là dạng chuẩn so với **tập đã chọn**. Graphiti dùng dạng một lượt, so với mọi ứng viên; nên đo cả hai.

### C1–C14. Thước đo trên context đã đóng gói $S$

| ID | Thước đo | Công thức | Tốt khi |
|---|---|---|---|
| C1 | Coverage | $\text{Cov} = \dfrac{|G^*\cap S|}{|G^*|}$ | ↑ |
| C2 | Answerable | $A = \mathbb 1[G^*\subseteq S]$ | ↑ |
| C3 | Stale contamination | $Z = \mathbb 1[S\cap Z^*\ne\varnothing]$; $\zeta = |S\cap Z^*|$ | ↓ |
| C4 | **Clean** (chỉ số chính) | $\text{Clean} = A\cdot(1-Z)$ | ↑ |
| C5 | Density (tín hiệu / ký tự) | $\rho = \dfrac{\sum_{\ell \in S,\ \ell\cap G^*\neq\varnothing} c(\ell)}{\sum_{\ell\in S}c(\ell)}$; nhiễu $= 1-\rho$ | ↑ |
| C6 | Dùng ngân sách | $U_B = \dfrac{\sum_{\ell\in S}c(\ell)}{B}$ | ≈1 khi còn thiếu, thấp khi đã đủ |
| C7 | Trùng lặp | $\text{Red} = \dfrac{2}{|S|(|S|-1)}\sum_{i<j}J(T_i,T_j)$ | ↓ |
| C8 | Đường cong ngân sách | $\text{Clean}(B)$ với $B\in\{300,600,1200,2400,4800\}$ | ↑, dốc sớm |
| C9 | AUBC | $\dfrac{1}{\log B_{\max}-\log B_{\min}}\displaystyle\int_{B_{\min}}^{B_{\max}}\text{Clean}(B)\,d\log B$ (trapezoid) | ↑ |
| C10 | Ngân sách đủ | $B^*_q = \min\{B: A_q(B)=1\}$; tỷ lệ overhead $\Omega_q = B^*_q \big/ \sum_{g\in G^*}c(g)\ \ (\ge 1)$ | $\Omega\to 1$ |
| C11 | Ích lợi biên | $\mu(B) = \dfrac{\Delta\,\text{Clean}}{\Delta \log_2 B}$ | dùng để chọn `budget_chars` |
| C12 | Khoảng cách tối ưu | $\text{Gap} = 1-\dfrac{F(S_\pi)}{F(S_{\text{OPT}})}$; OPT tìm bằng duyệt hết khi $m\le 20$ | ↓, phải $\le 1-\tfrac12(1-\tfrac1e)$ |
| C13 | Thông tin trên mỗi ký tự | $\text{IPC} = \dfrac{1000\cdot\text{Cov}}{\sum_{\ell \in S} c(\ell)}$ (coverage trên 1000 ký tự) | ↑ |
| C14 | Rủi ro "lạc giữa" | $p_i = \dfrac{i}{|S|-1}$ là vị trí tương đối của mục vàng; $\mu_{\text{mid}} = \overline{1-|2p_i-1|}$ (0 = ở mép, 1 = ở giữa) | ↓ |

**Bổ sung lý thuyết thông tin**, đo khi có ≥ 2 loại nguồn:
- Độ đa dạng nguồn $H(S) = -\sum_k p_k\log_2 p_k$, với $p_k$ là tỷ lệ ký tự thuộc loại $k$ (journal, decision, commit…).
- Coverage có trọng số tự-thông-tin $\sum_{u\in U(S)\cap U(G^*)} w(u) \big/ \sum_{u\in U(G^*)} w(u)$.

**Hệ chuẩn bắt buộc** trong mọi bảng:
- `recency`: dump episode mới nhất, là sàn dưới;
- `flat`: bm25 trên episode, tức v4 hiện tại;
- `oracle`: $S = G^*$ xếp theo thứ tự thời gian, là trần trên. Mọi chỉ số tầng C và D đều được chuẩn hoá giữa sàn và trần (§9).

---

## 5. Tầng D: AI đọc hiểu context

Tầng này cô lập reader: đưa **cùng một $S$** cho LLM, không cho tool. Sinh $S$ một lần, lưu lại, rồi phát lại y hệt cho mọi model và mọi format. Prompt cố định:

```
Chỉ dùng CONTEXT. Trả lời ngắn. Dòng cuối: NGUỒN: <số dòng đã dùng, cách nhau dấu phẩy> | hoặc KHÔNG ĐỦ
```

### D1. Độ đúng
- $\text{EM} = \mathbb 1[\text{norm}(\hat a) = \text{norm}(a^*)]$.
- Token-F1 giữa $\hat a$ và $a^*$.
- Đáp án là giá trị rời rạc (tên người, số giây, tên DB) nên **checker tất định** là đủ, không cần LLM judge.

### D2. Phân rã lỗi: retrieval hay reading? (công thức quan trọng nhất của tầng D)

$$
\text{Acc} = \underbrace{P(A)\,P(\text{đúng}\mid A)}_{\text{đủ context và đọc đúng}} + \underbrace{P(\neg A)\,P(\text{đúng}\mid \neg A)}_{\text{đoán / rò kiến thức}}
$$

Từ đó ra ba loại lỗi:

$$
E_{\text{ret}} = P(\neg A)\,\big(1-P(\text{đúng}\mid\neg A)\big),\qquad
E_{\text{read}} = P(A)\,\big(1-P(\text{đúng}\mid A)\big),\qquad
L_{\text{leak}} = P(\text{đúng}\mid\neg A)
$$

Ba đại lượng thoả $1-\text{Acc} = E_{\text{ret}} + E_{\text{read}}$.
- $E_{\text{ret}}$ cao thì phải sửa retriever hoặc allocator.
- $E_{\text{read}}$ cao thì phải sửa format render hoặc độ sạch.
- $L_{\text{leak}} > 0$ trên thế giới tổng hợp là dấu hiệu checker hoặc prompt có lỗi, vì tên trong thế giới là bịa nên model không thể biết trước.

### D3. Nhạy với mâu thuẫn

$$
\Delta_Z = P(\text{đúng}\mid A, Z=0) - P(\text{đúng}\mid A, Z=1)
$$

So với hai reader giả định:
- reader ngây thơ, chọn đều giữa các giá trị nhìn thấy: $E[\text{acc}] = \dfrac{1}{1+\zeta}$;
- reader theo ngày, chọn fact có $t_v$ lớn nhất.

LLM thật nằm gần reader nào cho biết nó có đọc nhãn thời gian `[t_v→t_i]` hay không.

### D4. Nhạy với vị trí ("lost in the middle")
Hồi quy logistic trên các câu có $A=1$:

$$
\text{logit}\,P(\text{đúng}) = \beta_0 + \beta_1 p + \beta_2 p^2 + \beta_3 |S|
$$

$\beta_2 > 0$ có ý nghĩa thống kê nghĩa là có hình chữ U (mép tốt, giữa tệ). Có thể thay hồi quy bằng accuracy theo 5 bin của $p$. Thí nghiệm hoán vị: cùng $S$, đặt fact vàng ở đầu / giữa / cuối.

### D5. Chịu nhiễu
Thêm $n_d$ câu nhiễu cùng chủ đề vào $S$ đủ, sao cho $\rho\in\{1, .5, .25, .1\}$, rồi ước lượng độ dốc $\partial\,\text{Acc}/\partial(1-\rho)$ bằng OLS. Độ dốc gần 0 nghĩa là model chịu nhiễu tốt, và khi đó có thể nới ngân sách mà không hại.

### D6. Bám nguồn (groundedness) và trích dẫn
$\hat C$ là tập dòng model ghi ở `NGUỒN`, $C^*$ là tập dòng chứa $G^*$:

$$
P_{\text{cite}} = \frac{|\hat C\cap C^*|}{|\hat C|},\qquad R_{\text{cite}} = \frac{|\hat C\cap C^*|}{|C^*|},\qquad \text{Use} = \frac{|\hat C|}{|S|}
$$

Use là tỷ lệ context thật sự được dùng. Use thấp kéo dài nghĩa là đang tiêm thừa. Số này nối với `suggested_files` / `followed_files` của spec v4 §9.

### D7. Biết từ chối
Trên các câu có $A=0$, $\text{Abst} = P(\text{"KHÔNG ĐỦ"}\mid\neg A)$. Đo kèm tỷ lệ từ chối sai $P(\text{"KHÔNG ĐỦ"}\mid A)$. Accuracy chọn lọc là Acc chỉ tính trên các câu model không từ chối.

### D8. Hiệu chỉnh (khi model trả kèm độ tin $\hat c$)

$$
\text{ECE} = \sum_{b=1}^{10}\frac{|\mathcal B_b|}{n}\,\big|\text{acc}(\mathcal B_b)-\overline{\hat c}(\mathcal B_b)\big|
$$

### D9. Format render
Cùng nội dung, so 3 format: bullet có nhãn thời gian (hiện tại), bảng `s | r | o | từ | đến`, văn xuôi. So theo $E_{\text{read}}$, $\Delta_Z$, token trên mỗi fact $= c/(\kappa\,|S|)$.

> Khi phải dùng LLM judge, ví dụ D6 cho câu trả lời tự do, thì judge phải đạt Cohen's $\kappa \ge 0.8$ so với chấm tay trên mẫu 50 câu, và báo $\kappa$ trong report.

---

## 6. Tầng E: Tốc độ và chi phí

### E1. Thành phần (microbench, đồng hồ `time.perf_counter_ns`, máy và Python ghi trong report)

| ID | Thước đo | Công thức / cách đo |
|---|---|---|
| E1.1 | Thông lượng ingest | $\theta = N_{\text{fact}}/T_{\text{ingest}}$ (fact/s), cả `--full` và incremental |
| E1.2 | Độ trễ truy vấn | p50 / p95 / p99 của `search` + `pack` qua ≥ 200 câu hỏi, warm cache. Ghi riêng cold start |
| E1.3 | Số mũ co giãn | Hồi quy $\log t = \log a + b\log N$ với $N\in\{10^2,10^3,10^4,10^5\}$ fact. Kỳ vọng $b\approx 1$ cho ingest, $b<1$ cho search |
| E1.4 | Độ phức tạp lý thuyết | `link` $O(L\cdot 4\cdot \text{LSH})$; BFS $O(\sum_{v\in\mathcal N_d}\deg v)$; `pack` $O(m\cdot|S|)$ cho greedy, $O(2^m)$ cho OPT. So với E1.3 |
| E1.5 | Bộ nhớ / đĩa | byte trên mỗi fact $= \text{size}(\texttt{cgraph.sqlite})/|E|$ |
| E1.6 | Overhead hook | $t_{\text{hook}}$ p95 của `brain context --hook`. Ngưỡng 300 ms, vì hook chạy ở mọi lần gọi tool |

### E2. Cấp phiên agent

| ID | Thước đo | Công thức |
|---|---|---|
| E2.1 | Thời gian thực | $T_{\text{wall}}$ (s), p50 và IQR |
| E2.2 | Số lượt / tool call | $n_{\text{turn}}$, $n_{\text{tool}}$ |
| E2.3 | Token | $T_{\text{in}}, T_{\text{out}}, T_{\text{cache-read}}, T_{\text{cache-write}}$ |
| E2.4 | Chi phí | $\$ = p_{\text{in}}T_{\text{in}} + p_{\text{out}}T_{\text{out}} + p_{\text{cr}}T_{\text{cr}} + p_{\text{cw}}T_{\text{cw}}$, giá ghi theo ngày chạy |
| E2.5 | Tỷ trọng tiêm | $\sigma = T_{\text{inj}}/T_{\text{in}}$, với $T_{\text{inj}} = \text{budget\_used}/\kappa$ (sổ ghi) |
| E2.6 | Chi phí trên mỗi task giải được | $\text{CPS} = \sum \$ \,/\, \#\text{pass}$ |
| E2.7 | Thời gian tới hành động đúng đầu tiên | $\text{TTFR}$ = chỉ số lượt của tool call đầu tiên chạm file vàng |
| E2.8 | Lượt tiết kiệm | $\Delta n_{\text{turn}} = n_{\text{turn}}^{\text{base}} - n_{\text{turn}}^{\text{sys}}$ (ghép cặp theo task) |

**Biên hiệu quả.** Vẽ mọi cấu hình (hệ × $B$ × policy) trên mặt phẳng (CPS, pass rate). Cấu hình $x$ **bị trội** khi tồn tại $y$ có $\text{pass}_y \ge \text{pass}_x$ và $\text{CPS}_y \le \text{CPS}_x$, trong đó ít nhất một bất đẳng thức là chặt. Chỉ giới thiệu cấu hình nằm trên biên Pareto.

---

## 7. Tầng F: Agent đầu cuối (task T25–T32)

Dựng trên bench hiện có (`bench/runner.py`, adapter `v4`), thêm adapter `v4cg` tiêm `cgraph.render(pack(...))` vào hook.

| Task | Đo đúng chỗ |
|---|---|
| T25 | Giá trị hiện tại sau 3 lần đổi (owner) và lịch sử có cả 3 |
| T26 | As-of: "config lúc sự cố ngày D" |
| T27 | Multi-hop 2 chặng: service A gọi B, timeout của B |
| T28 | Alias / sai chính tả trong prompt |
| T29 | Episode đến muộn làm đảo thứ tự |
| T30 | Hub: entity có > 50 cạnh nhiễu |
| T31 | Ngân sách chật (B = 600) |
| T32 | Câu hỏi mà context **không** đủ, đo D7 ở cấp agent |

**Chỉ số:** với $n$ lần chạy một task và $c$ lần pass:

$$
\widehat{p} = \frac{c}{n},\qquad \text{pass@}k = 1-\frac{\binom{n-c}{k}}{\binom{n}{k}},\qquad \text{pass}^{\wedge}k = \frac{\binom{c}{k}}{\binom{n}{k}}
$$

- pass@k: ít nhất 1 trong k lần pass.
- pass^k: **cả** k lần đều pass, tức độ tin cậy kiểu τ-bench. Với agent dùng thật, pass^k quan trọng hơn pass@k.

Kèm theo: trap tránh được, và **không hồi quy** T01–T24 (cổng cứng, §9).

---

## 8. Thống kê

1. **Thiết kế ghép cặp.** Mọi hệ chạy trên **cùng** câu hỏi, task và seed. Mọi so sánh đều tính trên hiệu số theo cặp.
2. **Khoảng tin cậy.** Bootstrap percentile 95% với 2000 mẫu và seed cố định. Với hiệu số thì dùng **paired bootstrap**, lấy mẫu lại theo câu hỏi.
3. **Kiểm định:**
   - Nhị phân (Clean, pass): McNemar chính xác. $b$ là số cặp A đúng B sai, $c$ là số cặp ngược lại; $p = 2\sum_{i\le\min(b,c)}\binom{b+c}{i}2^{-(b+c)}$, tương đương sign test.
   - Liên tục (Cov, $\rho$, $T_{\text{wall}}$): Wilcoxon signed-rank.
4. **Cỡ hiệu ứng.**
   - Tỷ lệ: Cohen's $h = 2\arcsin\sqrt{p_1}-2\arcsin\sqrt{p_2}$.
   - Liên tục: Cliff's $\delta = P(X>Y)-P(X<Y)$.
   - Luôn báo kèm p-value. p nhỏ mà hiệu ứng nhỏ thì không phải là kết quả.
5. **Nhiều so sánh.** Holm–Bonferroni trên họ so sánh khai báo **trước** khi chạy (§10.2).
6. **Cỡ mẫu (power).** McNemar với tỷ lệ cặp bất đồng $p_d$, hiệu cần thấy $\Delta$, $\alpha = .05$, power 80%:

$$
n \approx \frac{\left(z_{1-\alpha/2}\sqrt{p_d} + z_{1-\beta}\sqrt{p_d-\Delta^2}\right)^2}{\Delta^2}
$$

   Ví dụ: $p_d = .25$, $\Delta = .15$ cho $n \approx 85$ cặp. Bench offline đủ cỡ này dễ dàng (hàng trăm câu mỗi seed). Ở cấp agent, 8 task × 3 lần = 24 cặp chỉ đủ để thấy $\Delta \gtrsim .35$. Report phải **ghi rõ** giới hạn này.
7. **Phân rã phương sai (agent).** $\sigma^2_{\text{tổng}} = \sigma^2_{\text{task}} + \sigma^2_{\text{lần chạy}}$, ước lượng bằng ANOVA một chiều. $\sigma^2_{\text{lần chạy}}$ lớn thì tăng số lần chạy; $\sigma^2_{\text{task}}$ lớn thì tăng số task.
8. **Nhiều seed thế giới.** Offline chạy ≥ 3 seed. Báo trung bình, độ lệch chuẩn **giữa seed**, và kết luận chỉ khi dấu của hiệu số giống nhau ở mọi seed.

---

## 9. Chỉ số tổng hợp và cổng

**Cổng cứng.** Fail một cổng là fail, không cần tính điểm.
- $D = 1$ (tất định);
- không vượt ngân sách: $\max_q \sum_{S_q}c \le B$;
- T01–T24 không giảm quá CI của baseline;
- $L_{\text{leak}} \approx 0$ trên thế giới tổng hợp;
- p95 của $t_{\text{hook}}$ ≤ 300 ms.

**Chuẩn hoá theo sàn / trần.** Với mỗi chỉ số $m$ (đổi dấu nếu "càng thấp càng tốt"):

$$
\tilde m = \frac{m - m_{\text{recency}}}{m_{\text{oracle}} - m_{\text{recency}}}\in(-\infty, 1]
$$

$\tilde m = 1$ là ngang oracle. $\tilde m < 0$ là tệ hơn dump recency.

**Điểm chất lượng** (trọng số khai báo trước, sửa thì phải ghi ADR):

$$
Q = 0.30\,\widetilde{\text{Clean}} + 0.20\,\widetilde{\text{Acc}}_{\text{reader}} + 0.10\,\widetilde{\text{AUBC}} + 0.10\,\widetilde{(1-Z)} + 0.05\,\tilde\rho + 0.15\,\widetilde{\text{pass}^{\wedge}3} + 0.10\,\widetilde{(1/\text{CPS})}
$$

$Q$ chỉ để xếp hạng nhanh. **Quyết định dựa trên biên Pareto (§6) và từng chỉ số**, không dựa trên một con số. Report luôn in bảng thành phần ngay cạnh $Q$.

---

## 10. Phản hồi số liệu trung thực và đầy đủ

Đây là yêu cầu bắt buộc của bộ bench. Report thiếu bất kỳ mục nào dưới đây là **report không hợp lệ**.

### 10.1 Đầy đủ
- **Mọi lần chạy đều vào report**, gồm lần lỗi, timeout và crash. Không có cơ chế "chạy lại cho đến khi đẹp". Chạy lại chỉ được phép theo quy tắc của bench gốc (chết trước khi task bắt đầu) và phải được ghi lại.
- **Mẫu số luôn hiện rõ**: `18/24 (75%)`, không chỉ ghi `75%`.
- Mỗi số trung bình kèm **CI 95% và $n$**. Mỗi so sánh kèm **cỡ hiệu ứng và p** (sau Holm).
- Bảng theo **loại câu hỏi** và theo **seed**, không chỉ bảng gộp. Một hệ thắng trung bình mà thua ở một loại thì phải thấy được.
- Báo các chỉ số **bất lợi** cho hệ mới ngang hàng với chỉ số có lợi: độ trễ, chi phí, stale, rủi ro lạc giữa, số dạng viết không nhận ra.
- **Trần và sàn** (`oracle`, `recency`) luôn có mặt, để biết còn cách tối ưu bao xa.

### 10.2 Trung thực
- **Đăng ký trước.** Trước khi chạy, ghi vào report: giả thuyết, họ so sánh, chỉ số chính (`Clean@1200`), trọng số $Q$ và ngưỡng thành công. Đổi sau khi thấy số thì phải ghi "**post-hoc**" cạnh kết quả.
- **Tách số đã đo khỏi số suy luận.** Số đo ghi ✅ kèm lệnh chạy. Số ước lượng hoặc ngoại suy ghi ⚠ kèm lý do.
- **Kết quả âm được giữ nguyên.** Ví dụ wiki eval 2026-10-22 đã ghi rõ "v4.1 không nhanh hơn baseline". Bench này làm giống vậy.
- **Ghi giới hạn đã biết:** thế giới tổng hợp dễ hơn dữ liệu thật; trích xuất trong offline là hoàn hảo (cận trên); power thấp ở cấp agent (§8.6).
- **Không để harness tự khen mình.** Checker và generator vàng tách khỏi code của hệ được đo. Câu vàng phải chứa giá trị cụ thể, để "chứa chuỗi" không khớp nhầm.

### 10.3 Truy được nguồn
Mỗi report có khối provenance:

```
commit: <sha package>   dirty: no
cmd:    python -m bench.cgraph_eval --seeds 1,2,3 --out …
seeds:  1,2,3           python: 3.13.x   sqlite: 3.45.x   máy: …
model:  <id> (chỉ tầng D/F)   giá: <bảng giá, ngày>
raw:    _metrics/bench/<ngày>-cgraph.jsonl   (mỗi dòng = 1 câu hỏi × hệ × B, đủ mọi chỉ số)
```

Số trong report phải **tái sinh được từ `raw`** bằng `report`, không chép tay. Test kiểm điều này: chạy 2 lần cùng seed thì ra file giống hệt từng byte.

### 10.4 Vòng phản hồi
Mỗi report kết thúc bằng mục **"Số này nói gì → làm gì tiếp"**. Mỗi kết luận trỏ tới chỉ số và loại câu hỏi đã sinh ra nó. Ví dụ: "$E_{\text{read}}$ chiếm 70% lỗi khi $Z=1$, vậy thử format bảng (D9) trước khi nới ngân sách". Kết luận không trỏ được tới một con số thì bị xoá.

---

## 11. Lộ trình chạy

| Pha | Nội dung | Tầng | Chi phí |
|---|---|---|---|
| P0 | Harness offline `bench/cgraph_eval.py`: A1, B1–B4, C1–C9, C13–C14, sign test, bootstrap | A, B, C | 0 $ |
| P1 | Bổ sung A2 (IoU / invalidation P/R / late), A4, A5, B5–B9, C10–C12, provenance + `raw` jsonl, `oracle` | A, B, C | 0 $ |
| P2 | Microbench tốc độ E1.1–E1.6, quét $N$ | E1 | 0 $ |
| P3 | Reader bench: phát lại $S$ đã lưu cho 2 model, D1–D9 | D | ~ $n_q \times$ hệ × format lượt ngắn |
| P4 | Agent T25–T32, adapter `v4cg`, ≥ 3 lần mỗi ô | F, E2 | ~0,3 $ mỗi lượt |
| P5 | Phát lại trên project thật (journal / ADR thật, câu hỏi gán nhãn tay) | A6, C, D | thấp |

Trạng thái mã hiện tại (2026-10-24):
- `cgraph.py` đã viết và kiểm bằng tay trường hợp đổi owner 3 lần có episode đến muộn: khoảng thời gian đúng.
- `cgraph_eval.py` đã viết các chỉ số P0 nhưng **chưa chạy**. Chưa có số nào, nên chưa có kết luận nào.

## 12. Ngoài phạm vi
- Embedding và LLM extraction (ADR-010). Nếu thêm sau, chúng là một **hệ mới để so**, không thay chuẩn đo.
- Cộng đồng / label propagation của Graphiti: chưa có câu hỏi nào trong bench cần tới tóm tắt cụm.
