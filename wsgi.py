"""
WSGI Entry Point cho Smart Parking Web Application
Dùng để chạy với Gunicorn trên máy chủ Linux / AWS EC2 hoặc Docker:
    gunicorn --workers 2 --bind 0.0.0.0:5000 wsgi:app
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
