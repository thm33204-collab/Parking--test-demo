import cv2
import os
import shutil
import numpy as np
import pytesseract
import re
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'slot_booking.db')

def configure_tesseract():
    """Tự động phát hiện và cấu hình đường dẫn Tesseract OCR trên Windows và Linux (AWS EC2 / Docker)"""
    # 1. Kiểm tra biến môi trường TESSERACT_CMD nếu được chỉ định
    env_cmd = os.environ.get("TESSERACT_CMD")
    if env_cmd and os.path.exists(env_cmd):
        pytesseract.pytesseract.tesseract_cmd = env_cmd
        return env_cmd

    # 2. Tìm trong PATH hệ thống (mặc định trên Ubuntu / EC2 / Docker sau khi apt install tesseract-ocr)
    which_path = shutil.which("tesseract")
    if which_path:
        pytesseract.pytesseract.tesseract_cmd = which_path
        return which_path

    # 3. Các đường dẫn phổ biến trên Windows
    if os.name == 'nt':
        win_candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        ]
        for p in win_candidates:
            if os.path.exists(p):
                pytesseract.pytesseract.tesseract_cmd = p
                return p

    return "tesseract"

# Cấu hình ngay khi nạp module
configure_tesseract()

def detect_and_extract_number_plate(image_path):
    # Đường dẫn file mô hình Haar Cascade (hỗ trợ cả relative và absolute path an toàn với Unicode)
    harcascade = "model/haarcascade_russian_plate_number.xml"
    if not os.path.exists(harcascade):
        harcascade = os.path.join(BASE_DIR, "model", "haarcascade_russian_plate_number.xml")
    
    plate_cascade = cv2.CascadeClassifier(harcascade)
    if plate_cascade.empty():
        plate_cascade = cv2.CascadeClassifier(os.path.join(BASE_DIR, "model", "haarcascade_russian_plate_number.xml"))

    # Đọc ảnh an toàn với đường dẫn chứa ký tự tiếng Việt / Unicode
    img = None
    try:
        with open(image_path, 'rb') as f:
            file_bytes = np.asarray(bytearray(f.read()), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    except Exception:
        img = cv2.imread(image_path)

    if img is None:
        print("Error: Could not load image.")
        return None

    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img_gray = cv2.GaussianBlur(img_gray, (5, 5), 0)

    plates = ()
    if not plate_cascade.empty():
        try:
            plates = plate_cascade.detectMultiScale(img_gray, 1.1, 4)
        except Exception as e_cascade:
            print(f"Cascade detect warning: {e_cascade}")

    min_area = 500
    best_plate_img = None

    for (x, y, w, h) in plates:
        area = w * h
        if area > min_area:
            best_plate_img = img[y:y + h, x:x + w]
            break # Lấy vị trí biển số đầu tiên tìm thấy

    # Đảm bảo Tesseract đã được cấu hình trước khi OCR
    configure_tesseract()

    if best_plate_img is None:
        print("No plates detected using Haar Cascade. Trying OCR on the whole image...")
        # Tiền xử lý toàn bộ ảnh gốc để tối ưu khả năng đọc của Tesseract
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        
        try:
            text = pytesseract.image_to_string(gray, config='--psm 6')
            clean_text = re.sub(r'[^A-Za-z0-9]', '', text)
            if len(clean_text) >= 4:
                return clean_text
        except Exception as e_ocr:
            print(f"OCR Full Image Error: {e_ocr}")
        return None

    # Xử lý ảnh trực tiếp trong bộ nhớ để nhận diện OCR
    gray = cv2.cvtColor(best_plate_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    try:
        # Lưu file debug xử lý ảnh
        debug_dir = os.path.join(BASE_DIR, "plates")
        os.makedirs(debug_dir, exist_ok=True)
        cv2.imwrite(os.path.join(debug_dir, "processed_debug.jpg"), gray)
    except Exception as e_write:
        print(f"Debug write warning: {e_write}")

    try:
        text = pytesseract.image_to_string(gray, config='--psm 7')
        clean_text = re.sub(r'[^A-Za-z0-9]', '', text)
        return clean_text
    except Exception as e_ocr:
        print(f"OCR Cropped Plate Error: {e_ocr}")
        return None

def initialize_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create users table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            phnumber TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # Create bookings table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            slot_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            in_time TEXT NOT NULL,
            out_time TEXT NOT NULL,
            vehicle_number TEXT NOT NULL,
            mobile_number TEXT NOT NULL,
            status TEXT DEFAULT 'available',
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.commit()
    cursor.close()
    conn.close()
    print("Database initialized successfully.")

def match_with_database(extracted_text):
    if not extracted_text:
        print("No text extracted from the number plate.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    extracted_text_clean = extracted_text.replace(" ", "")

    cursor.execute('SELECT vehicle_number, date, in_time, out_time FROM bookings')
    bookings = cursor.fetchall()

    current_datetime = datetime.now()
    current_date = current_datetime.strftime('%Y-%m-%d')
    current_time = current_datetime.strftime('%H:%M')

    match_found = False

    for booking in bookings:
        vehicle_number, date, in_time, out_time = booking

        vehicle_number_clean = vehicle_number.replace(" ", "")

        print(f"Database Vehicle Number: {vehicle_number_clean}, Extracted Text: {extracted_text_clean}")

        if extracted_text_clean == vehicle_number_clean:
            print(f"Match found for vehicle number: {vehicle_number}")

            if date == current_date:
                print(f"Date matched: {date}")

                if in_time <= current_time <= out_time:
                    print(f"Current time {current_time} is within the range {in_time} to {out_time}.")
                    match_found = True
                else:
                    print(f"Current time {current_time} is NOT within the range {in_time} to {out_time}.")
            else:
                print(f"Date does not match. Database date: {date}, Current date: {current_date}")
        else:
            print(f"No match for vehicle number: {vehicle_number}")

    if not match_found:
        print("No matching vehicle number found in the database or date/time mismatch.")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    initialize_database()

    image_path = "image1.jpg"

    extracted_text = detect_and_extract_number_plate(image_path)
    print("Extracted Text:", extracted_text)

    match_with_database(extracted_text)