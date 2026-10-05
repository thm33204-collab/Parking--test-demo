#!/bin/bash
# ==============================================================================
# Script tự động cài đặt môi trường cho Smart Parking trên AWS EC2 (Ubuntu Linux)
# ==============================================================================

set -e

echo "=========================================================="
echo "  BẮT ĐẦU CÀI ĐẶT SMART PARKING TRÊN AWS EC2 (UBUNTU)    "
echo "=========================================================="

# 1. Cập nhật danh sách gói hệ thống
echo "[1/5] Đang cập nhật gói hệ thống apt..."
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-vie \
    libgl1 \
    libglib2.0-0 \
    curl \
    git \
    nginx

# 2. Tạo môi trường ảo Python (Virtual Environment)
echo "[2/5] Đang thiết lập môi trường ảo Python venv..."
if [ -d "venv" ]; then
    echo "Thư mục venv đã tồn tại, tiến hành tái sử dụng."
else
    python3 -m venv venv
fi

# Kích hoạt venv
source venv/bin/activate

# 3. Nâng cấp pip và cài đặt thư viện
echo "[3/5] Đang cài đặt các thư viện Python từ requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Tạo các thư mục cần thiết và khởi tạo CSDL
echo "[4/5] Đang chuẩn bị thư mục và khởi tạo cơ sở dữ liệu SQLite..."
mkdir -p temp_uploads plates data
python init_db.py

# 5. Kiểm tra Tesseract OCR trên hệ thống
echo "[5/5] Kiểm tra phiên bản Tesseract OCR..."
tesseract --version || echo "Cảnh báo: Chưa nhận diện được lệnh tesseract trong PATH."

echo "=========================================================="
echo "        CÀI ĐẶT HOÀN TẤT THÀNH CÔNG!                      "
echo "=========================================================="
echo ""
echo "Bạn có thể khởi chạy server theo các cách sau:"
echo ""
echo "1. Chạy thử nghiệm trực tiếp (foreground):"
echo "   source venv/bin/activate"
echo "   python app.py"
echo ""
echo "2. Chạy với Gunicorn WSGI (khuyến nghị cho demo):"
echo "   source venv/bin/activate"
echo "   gunicorn --workers 2 --bind 0.0.0.0:5000 wsgi:app"
echo ""
echo "3. Chạy nền bằng systemd service (tự động bật khi reboot):"
echo "   sudo cp smart_parking.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable --now smart_parking"
echo ""
