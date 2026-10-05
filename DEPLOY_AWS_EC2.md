# 🚀 HƯỚNG DẪN TRIỂN KHAI DỰ ÁN SMART PARKING LÊN AWS EC2 (TỪ A ĐẾN Z)

Tài liệu này hướng dẫn chi tiết từng bước cách đưa ứng dụng **Smart Parking Web App (Flask + OpenCV + Tesseract OCR + SQLite)** lên máy chủ đám mây **AWS EC2 (Elastic Compute Cloud)** để phục vụ học tập, demo trực tuyến cho giáo viên, hội đồng hoặc đối tác.

---

## 📑 MỤC LỤC
1. [Kiến trúc hệ thống triển khai](#1-kiến-trúc-hệ-thống-triển-khai)
2. [Bước 1: Khởi tạo máy chủ AWS EC2](#bước-1-khởi-tạo-máy-chủ-aws-ec2)
3. [Bước 2: Cấu hình tường lửa Security Group (Bắt buộc)](#bước-2-cấu-hình-tường-lửa-security-group-bắt-buộc)
4. [Bước 3: Kết nối SSH vào máy chủ EC2](#bước-3-kết-nối-ssh-vào-máy-chủ-ec2)
5. [Bước 4: Đẩy mã nguồn dự án lên EC2](#bước-4-đẩy-mã-nguồn-dự-án-lên-ec2)
6. [Bước 5: Khởi chạy ứng dụng trên EC2](#bước-5-khởi-chạy-ứng-dụng-trên-ec2)
   * [Cách 1: Triển khai nhanh bằng Docker & Docker Compose (Khuyên dùng)](#cách-1-triển-khai-bằng-docker--docker-compose-nhanh-nhất--tối-ưu-nhất)
   * [Cách 2: Triển khai trực tiếp với Python Venv + Gunicorn + Systemd](#cách-2-triển-khai-trực-tiếp-với-gunicorn--systemd)
   * [Cách 3: Cấu hình thêm Nginx Reverse Proxy (Chạy cổng 80 chuẩn)](#cách-3-tùy-chọn-cấu-hình-nginx-reverse-proxy-cổng-80)
7. [Bước 6: Truy cập và kiểm thử Demo](#bước-6-truy-cập-và-kiểm-thử-demo)
8. [Bước 7: Khắc phục sự cố thường gặp (Troubleshooting)](#bước-7-khắc-phục-sự-cố-thường-gặp)

---

## 1. KIẾN TRÚC HỆ THỐNG TRIỂN KHAI

```text
  [ Trình duyệt Người Dùng / Khách hàng / Admin ]
                     │
                     ▼
         Internet (Port 80 / 5000)
                     │
                     ▼
   [ AWS EC2 Instance (Ubuntu 22.04 LTS) ]
   ├── AWS Security Group (Mở Port 22, 80, 5000)
   ├── Nginx (Port 80 -> Reverse Proxy sang Port 5000)
   └── Gunicorn WSGI Server (Chạy ngầm với Systemd / Docker)
       └── Flask Application (app.py)
           ├── OpenCV & Tesseract OCR (Nhận diện biển số xe)
           └── SQLite Database (slot_booking.db - WAL Mode)
```

---

## BƯỚC 1: KHỞI TẠO MÁY CHỦ AWS EC2

1. Đăng nhập vào trang quản trị: **[AWS Management Console](https://aws.amazon.com/console/)**.
2. Chọn khu vực (Region) gần Việt Nam nhất (ví dụ: **Singapore - ap-southeast-1**).
3. Tìm kiếm dịch vụ **EC2** trên thanh tìm kiếm và click vào **Instances** -> **Launch Instances**.
4. Thiết lập các thông số cơ bản:
   * **Name and tags:** `smart-parking-demo`
   * **Application and OS Images (Amazon Machine Image - AMI):**
     * Chọn **Ubuntu**.
     * Phiên bản: **Ubuntu Server 22.04 LTS (HVM)** hoặc **Ubuntu Server 24.04 LTS** (Có nhãn *Free tier eligible*).
   * **Instance Type:**
     * `t2.micro` (1 vCPU, 1 GiB RAM - Miễn phí Free Tier).
     * *Lưu ý:* Nếu bạn muốn OCR xử lý nhanh và mượt hơn khi nhiều người test cùng lúc, có thể cân nhắc chọn `t3.small` (2 vCPU, 2 GiB RAM).
   * **Key Pair (Login):**
     * Bấm **Create new key pair**.
     * Đặt tên: `smart-parking-key`.
     * Key pair type: **RSA**.
     * Private key file format: **.pem** (dùng cho OpenSSH/PowerShell/Linux/Mac).
     * Bấm **Create key pair** và lưu file `smart-parking-key.pem` về thư mục an toàn trên máy tính của bạn.
   * **Configure Storage:**
     * Tăng từ `8 GiB` lên **`20 GiB` hoặc `30 GiB` gp3** (AWS Free Tier cho phép tối đa 30 GiB ổ đĩa EBS miễn phí).

---

## BƯỚC 2: CẤU HÌNH TƯỜNG LỬA SECURITY GROUP (BẮT BUỘC)

Tại mục **Network settings** khi tạo Instance (hoặc cấu hình sau tại thẻ Security Groups):
Chọn **Create security group** và thêm các quy tắc mở cổng (Inbound Rules) như sau:

| Type | Protocol | Port Range | Source | Mô tả |
| :--- | :--- | :--- | :--- | :--- |
| **SSH** | TCP | `22` | Anywhere (`0.0.0.0/0`) hoặc My IP | Cho phép bạn kết nối dòng lệnh từ máy tính cá nhân |
| **HTTP** | TCP | `80` | Anywhere (`0.0.0.0/0`) | Cho phép mọi người truy cập website qua cổng chuẩn HTTP |
| **Custom TCP** | TCP | `5000` | Anywhere (`0.0.0.0/0`) | Cho phép truy cập trực tiếp vào Flask/Gunicorn |

Bấm **Launch instance** và đợi khoảng 1-2 phút cho đến khi Instance chuyển sang trạng thái **Running** (màu xanh).

---

## BƯỚC 3: KẾT NỐI SSH VÀO MÁY CHỦ EC2

Lấy địa chỉ **Public IPv4 address** của máy chủ EC2 (Ví dụ: `54.254.123.45`).

### Trên máy tính cá nhân (Windows PowerShell hoặc CMD):

1. Mở PowerShell và di chuyển tới thư mục chứa file key `.pem`:
   ```powershell
   cd "C:\duong\dan\chua\file\key"
   ```

2. Phân quyền cho file key (nếu gặp lỗi permissions too open trên Windows):
   ```powershell
   icacls.exe smart-parking-key.pem /reset
   icacls.exe smart-parking-key.pem /grant:r "$($env:username):(R)"
   icacls.exe smart-parking-key.pem /inheritance:r
   ```

3. Kết nối SSH vào máy chủ EC2:
   ```bash
   ssh -i "smart-parking-key.pem" ubuntu@<PUBLIC_IP_EC2>
   ```
   *(Thay `<PUBLIC_IP_EC2>` bằng địa chỉ IP Public của máy bạn)*

---

## BƯỚC 4: ĐẨY MÃ NGUỒN DỰ ÁN LÊN EC2

Bạn có thể lựa chọn 1 trong 3 cách sau:

### Cách A: Sử dụng Git (Tiện lợi nhất)
1. Đẩy dự án hiện tại lên GitHub / GitLab (lưu ý file `.gitignore` đã được tạo sẵn để không đẩy thư mục `venv` nặng của Windows).
2. Trên terminal EC2, chạy:
   ```bash
   git clone <URL_REPO_GITHUB_CUA_BAN>
   cd Smart-Parking/parking_test_demo
   ```

### Cách B: Sử dụng lệnh SCP từ máy Windows
Mở thêm 1 cửa sổ PowerShell mới trên máy tính của bạn và chạy lệnh sao chép toàn bộ thư mục:
```powershell
# Chạy từ máy tính cá nhân
scp -i "smart-parking-key.pem" -r "c:\Hưởng 2 chuyên đề\chuyên đề 1\Smart-Parking\parking_test_demo" ubuntu@<PUBLIC_IP_EC2>:/home/ubuntu/
```

### Cách C: Dùng phần mềm giao diện WinSCP / FileZilla
1. Mở **WinSCP** (hoặc **FileZilla**).
2. Host name: Điền IP Public của EC2.
3. User name: `ubuntu`.
4. Chọn xác thực bằng Private key: Trỏ tới file `smart-parking-key.pem` (hoặc chuyển thành `.ppk` qua PuTTYgen).
5. Kéo thả thư mục `parking_test_demo` từ máy bạn sang thư mục `/home/ubuntu/` trên EC2.

---

## BƯỚC 5: KHỞI CHẠY ỨNG DỤNG TRÊN EC2

Sau khi mã nguồn đã nằm trong thư mục `/home/ubuntu/parking_test_demo` trên EC2, chọn **Cách 1** (Docker - khuyên dùng) hoặc **Cách 2** (Truyền thống).

---

### CÁCH 1: TRIỂN KHAI BẰNG DOCKER & DOCKER COMPOSE (NHANH NHẤT & TỐI ƯU NHẤT)

Docker đóng gói toàn bộ Python, Tesseract OCR, các thư viện Linux vào một môi trường độc lập, tránh mọi lỗi thiếu thư viện hệ thống.

1. **Cài đặt Docker trên EC2 (chỉ chạy 1 lần duy nhất):**
   ```bash
   sudo apt-get update
   sudo apt-get install -y docker.io docker-compose-v2
   sudo usermod -aG docker $USER
   newgrp docker
   ```

2. **Di chuyển vào thư mục dự án và khởi chạy:**
   ```bash
   cd /home/ubuntu/parking_test_demo
   docker compose up -d --build
   ```

3. **Kiểm tra trạng thái container:**
   ```bash
   docker compose ps
   docker compose logs -f
   ```
   *(Nhấn `Ctrl + C` để thoát màn hình xem log)*

4. **Khi cần dừng hoặc khởi động lại:**
   * Dừng app: `docker compose down`
   * Khởi động lại: `docker compose restart`
   * Xem log trực tiếp: `docker compose logs -f`

---

### CÁCH 2: TRIỂN KHAI TRỰC TIẾP VỚI GUNICORN + SYSTEMD

Nếu không muốn dùng Docker, bạn có thể chạy trực tiếp trên hệ điều hành Ubuntu:

1. **Chạy script tự động cài đặt toàn bộ phụ thuộc:**
   ```bash
   cd /home/ubuntu/parking_test_demo
   chmod +x setup_ec2.sh
   ./setup_ec2.sh
   ```

2. **Chạy thử nghiệm trực tiếp (Test nhanh):**
   ```bash
   source venv/bin/activate
   python app.py
   ```
   *Lúc này bạn có thể vào `http://<PUBLIC_IP_EC2>:5000` để thử. Bấm `Ctrl + C` để dừng.*

3. **Cài đặt Systemd Service để ứng dụng chạy ngầm liên tục 24/7:**
   * Chỉnh sửa đường dẫn trong file service (nếu thư mục của bạn khác `/home/ubuntu/parking_test_demo`):
     ```bash
     nano smart_parking.service
     ```
   * Sao chép file service vào thư mục hệ thống:
     ```bash
     sudo cp smart_parking.service /etc/systemd/system/
     sudo systemctl daemon-reload
     sudo systemctl enable smart_parking
     sudo systemctl start smart_parking
     ```
   * Kiểm tra trạng thái dịch vụ:
     ```bash
     sudo systemctl status smart_parking
     ```

---

### CÁCH 3: (TÙY CHỌN) CẤU HÌNH NGINX REVERSE PROXY (CỔNG 80)

Nếu bạn muốn người dùng truy cập trực tiếp bằng `http://<PUBLIC_IP_EC2>` mà **không cần phải gõ thêm cổng `:5000`**:

1. Sao chép cấu hình Nginx:
   ```bash
   sudo cp nginx_smart_parking.conf /etc/nginx/sites-available/smart_parking
   sudo ln -s /etc/nginx/sites-available/smart_parking /etc/nginx/sites-enabled/
   sudo rm -f /etc/nginx/sites-enabled/default
   ```
2. Kiểm tra cú pháp cấu hình và tải lại Nginx:
   ```bash
   sudo nginx -t
   sudo systemctl restart nginx
   ```

---

## BƯỚC 6: TRUY CẬP VÀ KIỂM THỬ DEMO

1. Mở trình duyệt web bất kỳ (Chrome, Edge, Safari...) trên máy tính hoặc điện thoại.
2. Nhập địa chỉ:
   * Nếu chạy qua cổng 5000: **`http://<PUBLIC_IP_EC2>:5000`**
   * Nếu đã cài Nginx (cổng 80): **`http://<PUBLIC_IP_EC2>`**
3. **Tài khoản đăng nhập quản trị viên mặc định:**
   * **URL:** `/admin_login`
   * **Email:** `admin@gmail.com`
   * **Mật khẩu:** `123456`
4. **Các tính năng demo kiểm tra ngay:**
   * **Xe vào (`/vehicle_in`):** Tải ảnh xe có biển số lên -> Hệ thống tự động kích hoạt Tesseract OCR nhận diện biển số -> Chọn chỗ đỗ -> Bấm Xác nhận.
   * **Xe ra (`/vehicle_out`):** Nhập hoặc quét ảnh biển số ra -> Hệ thống tự động tính thời gian đỗ thực tế và tính phí đỗ xe -> Xác nhận xe ra giải phóng slot.
   * **OCR Demo (`/plate_recognition_demo`):** Tải ảnh bất kỳ trong thư mục `data/` để thử khả năng đọc biển số.
   * **Báo cáo doanh thu (`/report`):** Xem biểu đồ thống kê trực quan.

---

## BƯỚC 7: KHẮC PHỤC SỰ CỐ THƯỜNG GẶP

### 1. Không mở được trang web trên trình duyệt (ERR_CONNECTION_TIMED_OUT)
* **Nguyên nhân:** Chưa cấu hình mở cổng trong Security Group trên AWS EC2.
* **Cách sửa:** Vào trang quản trị EC2 Console -> Chọn Instance -> Thẻ **Security** -> Click vào **Security Groups** -> Chọn **Edit inbound rules** -> Thêm rule:
  * Port 5000: Custom TCP, Source: `0.0.0.0/0`
  * Port 80: HTTP, Source: `0.0.0.0/0`
  * Bấm **Save rules**.

### 2. Tắt cửa sổ SSH là trang web bị sập
* **Nguyên nhân:** Bạn đang chạy `python app.py` trực tiếp ở foreground.
* **Cách sửa:** Sử dụng **Docker** (`docker compose up -d`) hoặc **Systemd Service** (`sudo systemctl start smart_parking`). Khi đó ứng dụng sẽ chạy độc lập ở chế độ background.

### 3. Lỗi `libGL.so.1: cannot open shared object file` trên Linux
* **Nguyên nhân:** Thiếu thư viện đồ họa hệ thống của OpenCV.
* **Cách sửa:** Dự án đã được chuyển sang `opencv-python-headless`. Nếu vẫn gặp trên Linux thủ công, chạy lệnh:
  ```bash
  sudo apt-get install -y libgl1 libglib2.0-0
  ```

### 4. Lỗi nhận diện Tesseract OCR
* **Cách sửa:** Kiểm tra xem tesseract đã được cài trên Linux chưa:
  ```bash
  tesseract --version
  ```
  Nếu chưa có: `sudo apt-get install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-vie`. Code trong `Number_plate.py` đã được cập nhật tự động tìm đường dẫn của Tesseract trên cả Windows và Linux.

### 5. Xem log theo thời gian thực để debug
* Với Docker:
  ```bash
  docker compose logs -f --tail 50
  ```
* Với Systemd:
  ```bash
  sudo journalctl -u smart_parking -f
  ```

---
*Chúc bạn triển khai thành công sản phẩm demo lên AWS EC2!*
