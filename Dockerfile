# Sử dụng Python 3.11 slim nhỏ gọn và bảo mật
FROM python:3.11-slim

# Thiết lập biến môi trường tránh sinh file .pyc và đệm log
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Cài đặt các gói hệ thống cần thiết cho Tesseract OCR và xử lý ảnh trên Linux
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-vie \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Sao chép file requirements và cài đặt các thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn vào container
COPY . .

# Tạo sẵn các thư mục lưu trữ tạm thời
RUN mkdir -p temp_uploads plates data

# Mở cổng 5000
EXPOSE 5000

# Khởi chạy ứng dụng bằng Gunicorn WSGI server
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "--timeout", "120", "wsgi:app"]
