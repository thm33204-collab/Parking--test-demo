# 🚗 Smart Parking & Monitoring System (Flask Web Application)

Dự án quản lý bãi đỗ xe thông minh toàn diện (Full-stack) tích hợp công nghệ nhận diện biển số xe tự động (Computer Vision & OCR). 

Hệ thống được phát triển bằng ngôn ngữ Python sử dụng framework Flask cho Backend, cơ sở dữ liệu SQLite3, công nghệ nhận diện biển số Haar Cascade + Tesseract OCR, và giao diện Frontend hiện đại lấy cảm hứng từ các bản vẽ thiết kế (mockup) chuyên nghiệp.

---

## 📋 Yêu CẦU HỆ THỐNG
* **Hệ điều hành:** Windows (khuyến nghị)
* **Ngôn ngữ:** Python 3.8 trở lên (đã kiểm thử trên Python 3.10)
* **Công cụ OCR:** Tesseract OCR (bắt buộc để chạy tính năng quét biển số bằng AI)

---

## 🛠️ CẤU HÌNH & CÀI ĐẶT

### Bước 1: Cài đặt Tesseract OCR trên Windows
Để nhận diện biển số thực tế từ hình ảnh, hệ thống yêu cầu cài đặt Tesseract OCR.
Bạn có **2 cách** để cài đặt:

*   **Cách 1 (Tự động - Khuyên dùng):** Click đúp vào file `install_tesseract.bat` trong thư mục dự án để hệ thống tự động tải và cài đặt ngầm Tesseract OCR vào thư mục mặc định.
*   **Cách 2 (Thủ công):**
    1. Tải bộ cài đặt Tesseract OCR cho Windows tại: [Tesseract GitHub](https://github.com/UB-Mannheim/tesseract/wiki).
    2. Cài đặt vào thư mục mặc định: `C:\Program Files\Tesseract-OCR\tesseract.exe`.


### Bước 2: Kích hoạt môi trường ảo và cài đặt thư viện
Mở Command Prompt (`cmd`) tại thư mục chứa dự án `parking_test_demo` và thực hiện:

1. Kích hoạt môi trường ảo `venv` có sẵn:
   ```cmd
   venv\Scripts\activate
   ```
2. Cài đặt các thư viện cần thiết (nếu chưa cài đặt hoặc cài máy mới):
   ```cmd
   pip install Flask opencv-python numpy pytesseract
   ```

---

## 🚀 KHỞI CHẠY CHƯƠNG TRÌNH

1. Đảm bảo bạn đang ở thư mục `parking_test_demo`.
2. Chạy ứng dụng bằng lệnh:
   ```cmd
   venv\Scripts\python.exe app.py
   ```
3. Sau khi màn hình hiển thị thông tin khởi chạy thành công:
   ```
    * Serving Flask app 'app'
    * Debug mode: on
    * Running on http://127.0.0.1:5000
   ```
4. Mở trình duyệt web và truy cập địa chỉ: **[http://localhost:5000](http://localhost:5000)** hoặc **[http://127.0.0.1:5000](http://127.0.0.1:5000)**.

---

## 🔑 TÀI KHOẢN ĐĂNG NHẬP DEMO

* **Tài khoản Khách hàng (User):** Bạn có thể tự đăng ký tài khoản mới trực tiếp qua giao diện đăng ký (`/register`).
* **Tài khoản Quản trị viên (Admin / Bảo vệ):** Hệ thống tự động tạo sẵn tài khoản quản trị khi khởi chạy:
  * **Email:** `admin@gmail.com`
  * **Mật khẩu:** `123456`
  * *(Truy cập trực tiếp tại trang Đăng nhập Admin: `/admin_login`)*

---

## 🌟 CÁC GIAO DIỆN CHÍNH TRONG HỆ THỐNG

### 1. Bảng điều khiển Admin (Dashboard Admin)
* Quản lý các lượt đỗ xe hiện tại và các đặt chỗ trước theo ngày.
* Thống kê nhanh số lượng xe đang trong bãi và các lượt xe đã rời bãi.

### 2. Giao diện Xe vào (Vehicle Check-In) - `/vehicle_in`
Giao diện hiện đại được thiết kế theo đúng chuẩn mockup:
* **Quét biển số thông minh:** Hỗ trợ kéo thả hoặc bấm tải ảnh xe vào khu vực camera. Hệ thống sẽ tự động gọi AI nhận diện biển số xe và điền vào form.
* **Chỗ đỗ đề xuất:** Tự động hiển thị và chọn vị trí đỗ trống tối ưu, gợi ý Tầng, Khu vực và khoảng cách di chuyển.
* **Thông tin thời gian thực:** Đồng hồ cập nhật thời gian vào chuẩn xác theo giây.
* Nhấn nút **Xác nhận xe vào** (màu xanh) để tạo lượt gửi xe mới.

### 3. Giao diện Xe ra (Vehicle Check-Out) - `/vehicle_out`
* **Nhận dạng xe ra:** Kéo thả ảnh camera xe ra để quét biển số tự động hoặc nhập biển số thủ công để tìm kiếm lượt gửi xe.
* **Truy vấn trạng thái thời gian thực:** Sau khi xác định được biển số xe đang đỗ, hệ thống tự động hiển thị:
  * Thời gian vào thực tế và thời gian ra dự kiến.
  * Vị trí đỗ của xe (Slot, Tầng, Khu vực).
  * Tổng thời gian đã đỗ thực tế (định dạng Giờ + Phút).
  * **Phí tạm tính:** Tự động tính tiền theo giờ đỗ thực tế (ví dụ: Ô tô 20.000 VNĐ/giờ, Xe máy 5.000 VNĐ/giờ) hiển thị dạng thẻ tiền lớn màu cam nổi bật.
* Nhấn nút **Xác nhận xe ra** (màu cam) để giải phóng chỗ đỗ và hoàn tất thanh toán.

### 4. Nhận diện biển số mẫu (Plate OCR Demo) - `/plate_recognition_demo`
* Trang chuyên biệt để kiểm tra độ chính xác của bộ nhận diện hình ảnh Haar Cascade + Tesseract OCR.

### 5. Báo cáo thống kê (Report) - `/report`
* Biểu đồ doanh thu và lượt xe đỗ sinh động theo ngày.
* Tự động sinh dữ liệu mô phỏng của 30 ngày gần nhất nếu cơ sở dữ liệu trống để demo trực quan và đẹp mắt nhất.

---

## ☁️ TRIỂN KHAI LÊN ĐÁM MÂY (AWS EC2 / DOCKER)

Dự án đã được cấu hình hoàn chỉnh để triển khai lên dịch vụ điện toán đám mây **AWS EC2 (Ubuntu Linux)**:
* **Tự động tương thích hệ điều hành:** Mã nguồn tự động phát hiện đường dẫn Tesseract OCR trên cả Windows và Linux (AWS EC2 / Docker).
* **Docker & Docker Compose:** Sẵn sàng file `Dockerfile` và `docker-compose.yml` để chạy 1 lệnh duy nhất trên EC2.
* **Gunicorn & Systemd:** Tích hợp `wsgi.py`, `setup_ec2.sh` và `smart_parking.service` để chạy ngầm 24/7.
* **Nginx Reverse Proxy:** Sẵn sàng cấu hình chạy cổng 80 chuẩn HTTP.

👉 **Xem hướng dẫn chi tiết từng bước từ A đến Z tại:** [DEPLOY_AWS_EC2.md](DEPLOY_AWS_EC2.md)

