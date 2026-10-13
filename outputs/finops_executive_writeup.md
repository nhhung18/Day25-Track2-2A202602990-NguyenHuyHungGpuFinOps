# Báo Cáo Kỹ Thuật FinOps: Tối Ưu Hóa Chi Phí GPU Tại NimbusAI

> **Khóa học:** AICB · Phase 2 · Track 2 (Infrastructure) · Day 25  
> **Tác giả:** FinOps Lead Engineer  
> **Dự án:** NimbusAI GPU FinOps Optimization  
> **Thời điểm:** Tháng 6/2026  

---

## Tóm Tắt Điều Hành (Executive Summary)

NimbusAI — một startup LLM đang mở rộng quy mô — đối mặt với hóa đơn GPU leo thang mất kiểm soát. Bằng việc chuyển dịch tư duy từ quản lý chi phí theo giờ máy chủ (`$/GPU-giờ`) sang quản lý kinh tế đơn vị theo sản lượng token (`$/1M-token`), dự án đã kiểm toán toàn diện hiệu năng phần cứng, tái cấu trúc chiến lược mua sắm và tối ưu hóa luồng suy luận.

Kết quả đạt được:
- **Chi phí vận hành hàng tháng:** Giảm từ **$27,133** xuống **$14,626/tháng** (tiết kiệm **$12,507/tháng**, tương đương **46.1%**).
- **Đơn giá suy luận (Unit Economics):** Cắt giảm từ **$6.488/1M-token** xuống **$1.126/1M-token** (giảm **82.6%**).
- **Phát thải carbon & năng lượng:** Tiết kiệm **4,579 kg CO2e** (-92.1%) bằng chiến lược dịch chuyển địa lý các tác vụ huấn luyện gián đoạn sang vùng điện sạch.

---

## 1. So Sánh Toàn Diện: Baseline vs. Optimized

| Chỉ số cốt lõi | Baseline (Trước tối ưu) | Optimized (Sau tối ưu) | Mức chênh lệch & Tiết kiệm |
|---|---|---|---|
| **Tổng chi phí GPU / tháng** | **$27,133** | **$14,626** | **-$12,507 (-46.1%)** |
| **Chi phí Inference / ngày** | $48.87 / ngày | $8.48 / ngày | -$40.39 / ngày (-82.6%) |
| **Đơn giá phục vụ ($/1M-token)** | **$6.488** | **$1.126** | **-82.6%** |
| **Chi phí mua sắm GPU / tháng** | $25,667 | $15,627 | -$10,040 (-39.1%) |
| **Chi phí lãng phí Idle / tháng** | $600 | $0 | -$600 (-100%) |
| **Lãng phí do hạ tầng sai kích cỡ (Util-Lie)**| $655 | $0 | -$655 (-100%) |

---

## 2. Phân Tích Chi Tiết Từng Đòn Bẩy (Savings by Lever)

Biểu đồ Waterfall (`outputs/savings.png`) thể hiện 4 đòn bẩy đóng góp vào tổng mức tiết kiệm $12,507/tháng:

| Thứ hạng | Đòn bẩy tối ưu | Số tiền tiết kiệm (USD/tháng) | Tỷ trọng đóng góp |
|:---:|---|:---:|:---:|
| 1 | **Purchasing Strategy (Spot + Reserved)** | **$10,040** | **80.3%** |
| 2 | **Inference Levers (Cascade + Cache + Batch)** | **$1,212** | **9.7%** |
| 3 | **Right-size Util-Lies (Hạ cấp GPU bị nghẽn)** | **$655** | **5.2%** |
| 4 | **Kill Idle GPUs (Tắt máy chạy không ban đêm)** | **$600** | **4.8%** |

### Đòn bẩy đóng góp lớn nhất: Purchasing Strategy ($10,040/tháng - 80.3%)
- **Nguyên nhân:** Đội ngũ kỹ thuật trước đây phụ thuộc 100% vào giá On-demand đắt đỏ ($2.50/hr đối với H100, $1.79/hr đối với A100).
- **Giải pháp chuyển đổi:**
  - Áp dụng công thức điểm hòa vốn: Với mức chiết khấu 3-year Reserved là 45%, điểm hòa vốn là `1 - 0.45 = 55%` duty cycle (~13.2 giờ/ngày). Các dịch vụ inference chạy 24/7 (`job-infer-chat`, `job-infer-rag`, `job-infer-search`) được chuyển sang hợp đồng Reserved 3 năm, tiết kiệm tức thì 40–45%.
  - Đối với các job training và batch evaluation ngắt quãng được (`interruptible=1` như `job-train-llm`, `job-train-embed`, `job-finetune`), chuyển sang cơ chế Spot Instance có lưu checkpoint tự động. Mặc dù chịu 3% overhead ghi checkpoint và 0.5h rework khi bị thu hồi, chi phí thực tế vẫn rẻ hơn On-demand tới 40–58%.

### Đòn bẩy hiệu quả đơn vị cao nhất: Inference Levers (-82.6% $/1M-token)
Mặc dù đóng góp $1,212 vào hóa đơn mẫu hiện tại, đòn bẩy này có tác động sống còn khi quy mô token tăng từ hàng triệu lên hàng tỷ token:
1. **Cascade Routing:** 80% truy vấn đơn giản được điều hướng tự động sang mô hình nhỏ (`small`: $0.20/$0.40 per 1M), giảm 15 lần chi phí so với mô hình lớn (`large`: $3.00/$15.00 per 1M).
2. **Prompt Caching:** Tận dụng system prompt tĩnh của tính năng Chat và Doc-QA, hưởng chiết khấu 90% cho input token đọc lại.
3. **Batch API:** Gom các tác vụ offline/eval đêm với chiết khấu 50%. Khi kết hợp Batch + Prompt Cache, chi phí chỉ còn 5% so với nguyên giá.

---

## 3. Bản Chất Của "GPU-Util Lie" & Tác Động Tài Chính

### Cơ chế kỹ thuật: Tại sao `nvidia-smi` đánh lừa kỹ sư?
- Lệnh `nvidia-smi` đo thông số **GPU Utilization %** dựa trên tỷ lệ thời gian mà bộ định thời GPU (GPU clock) có ít nhất một kernel đang active. Nó **không đo thông lượng tính toán (FLOPs)**.
- Khi kernel bị nghẽn băng thông bộ nhớ (memory stall), chờ truy xuất HBM, hoặc kernel quá nhỏ chịu overhead khởi tạo (kernel launch overhead), GPU clock vẫn báo 100% bận trong khi Tensor Cores phần lớn không làm việc.

### Phát hiện tại NimbusAI:
- Telemetry ghi nhận **`gpu-h100-4`** đạt **98.2% GPU-Util** nhưng **MFU chỉ đạt 0.194 (19.4%)**.
- Tương tự, **`gpu-a10g-1`** báo **96.9% GPU-Util** nhưng MFU chỉ đạt **0.268**.

### Tác động tài chính:
NimbusAI đang trả **$2.50/giờ** cho H100 để nhận lại năng lực tương đương một con chip A100 ($1.79/giờ). Bằng cách hạ cấp (right-size) các GPU này và cấu hình lại batch size/FP8 kernel, công ty tiết kiệm ngay **$655/tháng** mà không làm suy giảm thông lượng ứng dụng.

---

## 4. Báo Cáo Triển Khai 5 Phần Mở Rộng ("Your Turn" Extensions)

### Extension 1 — Cải thiện `recommend_tier()` với Interruption Risk & Term Duration
- **Mô tả:** Mở rộng thuật toán phân loại tier bằng cách đưa vào rủi ro thu hồi Spot theo kiến trúc phần cứng (`H100`: 3%, `A100`: 5%, `A10G`: 12%, `L4`: 15%) và so sánh thời hạn cam kết 1 năm (20% off) vs. 3 năm (45% off).
- **Kết quả đo lường:**
  - Đối với các job ngắn ngày (`job-dev-sandbox`: 22 ngày, `job-finetune`: 3 ngày), thuật toán ngăn chặn việc khóa hợp đồng dài hạn nếu không có cơ chế chia sẻ tài nguyên toàn công ty.
  - Các job có nguy cơ gián đoạn cao trên GPU commodity được gắn cờ cảnh báo rework overhead.
- **Insight:** Không bao giờ cam kết Reserved 3 năm cho các workload có vòng đời ngắn hơn 6 tháng trừ khi năng lực đó nằm trong generic compute pool.

### Extension 2 — Right-sizing theo MBU & VRAM Economics
- **Mô tả:** Xây dựng bảng phân tích chỉ số kinh tế bộ nhớ: `$/GB-VRAM-giờ` và chi phí băng thông `$/(TB/s-giờ)` cho 7 dòng GPU trong catalog.
- **Kết quả đo lường:**
  | GPU Type | On-demand ($/hr) | VRAM (GB) | Peak BW (TB/s) | $/GB-hr | $/(TB/s-hr) |
  |---|:---:|:---:|:---:|:---:|:---:|
  | **MI300X** | $1.95 | 192 | 5.30 | $0.0102 | **$0.368** (Tối ưu nhất) |
  | **B200** | $5.09 | 192 | 8.00 | $0.0265 | $0.636 |
  | **H100** | $2.50 | 80 | 3.35 | $0.0312 | $0.746 |
  | **A100** | $1.79 | 80 | 2.00 | $0.0224 | $0.895 |
  | **A10G** | $1.00 | 24 | 0.60 | $0.0417 | $1.667 |
  | **L4** | $0.80 | 24 | 0.30 | $0.0333 | **$2.667** (Đắt nhất theo BW) |
- **Insight then chốt:** *"Tại sao không chọn GPU rẻ nhất theo $/GPU-giờ?"* Vì decode LLM bị nghẽn băng thông bộ nhớ (memory bandwidth-bound). L4 có giá thuê theo giờ rẻ nhất ($0.80) nhưng giá trên mỗi TB/s băng thông lại đắt gấp 3.5 lần H100 và gấp 7.2 lần MI300X. Chọn L4 cho LLM decode dẫn đến tụt tốc độ tok/s/user, buộc phải thuê nhiều GPU hơn và làm tổng hóa đơn tăng vọt!

### Extension 3 — Kinh tế học Prompt Cache (`cache_is_worth_it()`)
- **Mô tả:** Thiết lập hàm kiểm tra ngưỡng hòa vốn cho prompt caching dựa trên phụ phí ghi (`write_cost_per_m`) và chiết khấu đọc (`read_discount=0.10`).
- **Công thức:**  
  $$\text{Break-even reads} = \frac{\text{Write Cost}}{\text{Input Price} \times (1 - \text{Read Discount})}$$
- **Kết quả đo lường:**
  - Với chi phí ghi cache 1.25x giá đọc ($3.75/1M vs $3.00/1M) và chiết khấu đọc 90%, điểm hòa vốn là **1.39 lần đọc**.
  - Trong log `token_usage.csv`, các tác vụ Chat và Doc-QA có tần suất đọc lại trung bình đạt **~3.5 lần** đối với system prompt tĩnh. Do đó `cache_is_worth_it()` trả về `True`, khẳng định bật cache đem lại lợi ích kinh tế thực sự.

### Extension 4 — Ngân sách Reasoning (Reasoning Budget)
- **Mô tả:** Tách riêng chi phí tiền tệ ($) và năng lượng điện (Wh) cho nhóm request suy luận chuyên sâu (`is_reasoning=1`).
- **Kết quả đo lường:**
  - Tỷ trọng lượng truy vấn: **8.4%** (201 / 2,400 requests).
  - Tỷ trọng chi phí tối ưu: **16.5%** ($1.40 / $8.48).
  - Tỷ trọng tiêu thụ năng lượng: **94.0%** (29,788 Wh / 31,675 Wh).
- **Insight & Quy tắc định tuyến:**
  - Reasoning tiêu tốn năng lượng gấp ~80 lần vì mô hình phải tự sinh hàng ngàn token suy nghĩ ẩn (thinking chain tokens) trong giai đoạn decode tuần tự.
  - Đề xuất chính sách: Áp dụng Classifier lọc độ khó; chỉ kích hoạt reasoning cho bài toán toán học/lập trình phức tạp hoặc khi model confidence < 0.85. Việc giới hạn reasoning ở 5% traffic sẽ tiết kiệm ~45% tổng năng lượng inference của toàn công ty.

### Extension 5 — Lịch Trình Nhận Thức Carbon (Carbon-Aware Scheduling)
- **Mô tả:** Phân tích lượng điện tiêu thụ của các job training/batch ngắt quãng (13,083 kWh) trên 5 vùng điện toán đám mây.
- **Kết quả so sánh 5 vùng:**
  | Vùng triển khai | Cường độ Carbon (gCO2/kWh) | Giá điện ($/kWh) | Tổng Carbon (kg CO2e) | Tiền điện ($) |
  |---|:---:|:---:|:---:|:---:|
  | **`europe-north1`** (Na Uy - Thủy điện) | **30** | $0.090 | **392.5** | $1,177.47 |
  | **`us-east-wa`** (Washington - Rẻ nhất) | 90 | **$0.055** | 1,177.5 | **$719.57** |
  | **`us-west-2`** (Oregon - Thủy điện) | 120 | $0.070 | 1,570.0 | $915.81 |
  | **`us-east-1`** (Virginia - Baseline) | 380 | $0.120 | 4,971.5 | $1,569.96 |
  | **`europe-central2`** (Ba Lan - Than đá) | 660 | $0.180 | 8,634.8 | $2,354.94 |
- **Kết quả tối ưu:**
  - Di chuyển các job ngắt quãng từ `us-east-1` sang `europe-north1` giúp **cắt giảm 4,579.1 kg CO2e (-92.1%)** và **tiết kiệm $392.49 tiền điện (-25.0%)**.
  - Nếu ưu tiên chi phí điện tối thiểu: chuyển sang `us-east-wa` tiết kiệm tới **$850.39 tiền điện (-54.2%)** và vẫn giảm được 76.3% phát thải carbon.
  - Do các job training không có yêu cầu khắt khe về độ trễ mạng người dùng (latency-insensitive), việc dịch chuyển địa lý toàn cầu mang lại lợi ích kép không rủi ro.

---

## 5. Khuyến Nghị Chiến Lược Cho Ban Lãnh Đạo NimbusAI

Nếu đảm nhiệm vị trí FinOps Lead tại NimbusAI, 3 hành động ưu tiên cao nhất cần triển khai ngay trong tháng đầu tiên là:

1. **Tuần 1 — Khóa van rò rỉ suy luận (Inference Governance):**
   - Triển khai **Cascade Routing proxy** (mô hình nhỏ mặc định, fallback mô hình lớn khi task score > threshold) và kích hoạt **Prompt Caching** trên API Gateway.
   - Hành động này hoàn toàn nằm ở tầng phần mềm (không phụ thuộc hợp đồng phần cứng), mang lại hiệu quả cắt giảm **82.6% chi phí suy luận** ngay ngày đầu tiên.

2. **Tuần 2 — Chuyển dịch hợp đồng mua sắm (Commitment Portfolio):**
   - Chuyển toàn bộ 3 dịch vụ inference chạy 24/7 sang hợp đồng **3-year Reserved Instance** để chốt mức chiết khấu 45%.
   - Thiết lập Kubernetes Daemonset tự động lưu checkpoint vào shared S3/GCS mỗi 30 phút cho các job training và chuyển đổi 100% sang **Spot Instances**.
   - Mang lại mức tiết kiệm bằng tiền mặt lớn nhất: **$10,040 mỗi tháng**.

3. **Tuần 3 & 4 — Thực thi văn hóa chi phí (Automated Governance & Chargeback):**
   - Với chỉ số Tag Coverage hiện tại đạt **92%** (vượt ngưỡng an toàn 80%), chính thức kích hoạt **Chargeback tự động** định kỳ hàng tháng theo chuẩn **FOCUS 1.x**.
   - Cài đặt K8s descheduler tự động hạ tải (kill/suspend) các GPU có mức utilization dưới 10% kéo dài quá 30 phút vào ban đêm, triệt tiêu hoàn toàn khoản lãng phí $600/tháng do GPU chạy rỗng.

