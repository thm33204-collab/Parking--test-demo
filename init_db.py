"""
Script khởi tạo toàn bộ cấu trúc cơ sở dữ liệu cho Smart Parking.
Hỗ trợ chạy độc lập trên cả Windows và Linux (AWS EC2 / Docker).
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import init_db

if __name__ == '__main__':
    print("Dang khoi tao co so du lieu Smart Parking...")
    init_db()
    print("Khoi tao co so du lieu thanh cong!")