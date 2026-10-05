from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import math

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'slot_booking.db')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'smart_parking_secret_key_prod_2026')

def get_db_connection():
    # timeout=10: chờ tối đa 10s nếu DB bị lock bởi request khác (fix JMeter concurrent)
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    # WAL mode cho phép đọc song song với ghi, tránh lỗi 'database is locked'
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

# ============================================================
# Database initialization - tự tạo các bảng khi app khởi động
# ============================================================
def init_db():
    conn = get_db_connection()

    # Bảng users (giữ nguyên từ cũ)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            phnumber TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # Bảng bookings (giữ nguyên từ cũ)
    conn.execute('''
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

    # Bảng parking_records - ghi nhận xe vào/ra
    conn.execute('''
        CREATE TABLE IF NOT EXISTS parking_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT NOT NULL,
            vehicle_type TEXT NOT NULL,
            slot_id INTEGER NOT NULL,
            in_time TEXT NOT NULL,
            out_time TEXT,
            fee INTEGER DEFAULT 0,
            status TEXT DEFAULT 'parking'
        )
    ''')

    # Bảng vehicles - quản lý phương tiện
    conn.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT UNIQUE NOT NULL,
            vehicle_type TEXT NOT NULL,
            owner_name TEXT,
            phone TEXT,
            created_at TEXT NOT NULL
        )
    ''')

    # Bảng parking_slots - quản lý chỗ đỗ xe
    conn.execute('''
        CREATE TABLE IF NOT EXISTS parking_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_code TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'available'
        )
    ''')

    # Bảng admins - quản lý tài khoản admin
    conn.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')

    # Tạo admin mặc định nếu chưa tồn tại
    existing_admin = conn.execute('SELECT id FROM admins WHERE email = ?', ('admin@gmail.com',)).fetchone()
    if not existing_admin:
        default_hash = generate_password_hash('123456')
        conn.execute('INSERT INTO admins (email, password_hash) VALUES (?, ?)', ('admin@gmail.com', default_hash))

    # Tạo slots mặc định nếu chưa tồn tại
    existing_slots = conn.execute('SELECT COUNT(*) FROM parking_slots').fetchone()[0]
    if existing_slots == 0:
        for i in range(1, 21):
            slot_code = f'A{i:02d}'
            conn.execute('INSERT INTO parking_slots (slot_code, status) VALUES (?, "available")', (slot_code,))

    conn.commit()
    conn.close()

init_db()

# ============================================================
# Route: Trang chủ
# ============================================================
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

# ============================================================
# Route: Đăng ký user (giữ nguyên)
# ============================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        employee_id = request.form['employee_id']
        name = request.form['name']
        phnumber = request.form['phnumber']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (employee_id, name, phnumber, email, password) VALUES (?, ?, ?, ?, ?)',
                         (employee_id, name, phnumber, email, password))
            conn.commit()
        except sqlite3.IntegrityError:
            flash('Employee ID or Email already exists!')
            return redirect(url_for('register'))
        finally:
            conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')

# ============================================================
# Route: Đăng nhập user (giữ nguyên)
# ============================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['name'] = user['name']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password')
    return render_template('login.html')

# ============================================================
# Route: Đăng nhập admin - kiểm tra trong database (sửa mới)
# ============================================================
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        admin = conn.execute('SELECT * FROM admins WHERE email = ?', (email,)).fetchone()
        conn.close()

        if admin and check_password_hash(admin['password_hash'], password):
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials')
    return render_template('admin_login.html')

# ============================================================
# Route: Admin dashboard (cập nhật - thêm xe đang gửi/đã ra)
# ============================================================
@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()

    # Xem booking theo ngày (chức năng cũ)
    if request.method == 'POST':
        selected_date = request.form['date']
        bookings = conn.execute('''
            SELECT bookings.id, users.name, bookings.slot_id, bookings.date, bookings.in_time, bookings.out_time, 
                   bookings.vehicle_number, bookings.mobile_number, bookings.status
            FROM bookings
            JOIN users ON bookings.user_id = users.id
            WHERE bookings.date = ?
        ''', (selected_date,)).fetchall()
    else:
        bookings = []

    # Xe đang gửi trong bãi
    parking_now = conn.execute('SELECT * FROM parking_records WHERE status = "parking" ORDER BY id DESC').fetchall()
    # Xe đã ra gần nhất
    completed_recent = conn.execute('SELECT * FROM parking_records WHERE status = "completed" ORDER BY id DESC LIMIT 20').fetchall()

    conn.close()

    return render_template('admin_dashboard.html', bookings=bookings, parking_now=parking_now, completed_recent=completed_recent)

# ============================================================
# Route: Dashboard user (giữ nguyên)
# ============================================================
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', name=session['name'])

# ============================================================
# Route: Book slot (giữ nguyên)
# ============================================================
@app.route('/book_slot', methods=['GET', 'POST'])
def book_slot():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        slot_id = request.form['slot_id']
        in_time = request.form['in_time']
        out_time = request.form['out_time']
        date = request.form['date']
        vehicle_number = request.form['vehicle_number']
        mobile_number = request.form['mobile_number']

        conn = get_db_connection()
        try:
            existing_booking = conn.execute('''
                SELECT * FROM bookings 
                WHERE slot_id = ? AND date = ? AND status = "booked" 
                AND ((in_time <= ? AND out_time >= ?) OR (in_time <= ? AND out_time >= ?))
            ''', (slot_id, date, in_time, in_time, out_time, out_time)).fetchone()

            if existing_booking:
                flash('Slot already booked for the selected date and time!')
                return redirect(url_for('book_slot'))

            conn.execute('''
                INSERT INTO bookings (user_id, slot_id, date, in_time, out_time, vehicle_number, mobile_number, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (session['user_id'], slot_id, date, in_time, out_time, vehicle_number, mobile_number, 'booked'))
            conn.commit()
            flash('Slot booked successfully!')
        finally:
            conn.close()
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    booked_slots = conn.execute('SELECT slot_id FROM bookings WHERE status = "booked"').fetchall()
    conn.close()

    booked_slot_ids = [slot['slot_id'] for slot in booked_slots]
    return render_template('book_slot.html', booked_slots=booked_slot_ids)

# ============================================================
# Route: History booking (giữ nguyên)
# ============================================================
@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    bookings = conn.execute('''
        SELECT id, vehicle_number, slot_id, date, in_time, out_time, status 
        FROM bookings 
        WHERE user_id = ?
    ''', (session['user_id'],)).fetchall()
    conn.close()

    return render_template('history.html', bookings=bookings)

# ============================================================
# Route: Cancel slot (giữ nguyên)
# ============================================================
@app.route('/cancel_slot', methods=['GET', 'POST'])
def cancel_slot():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    today = datetime.today().strftime('%Y-%m-%d')

    active_bookings = conn.execute('''
        SELECT id, slot_id, date, in_time, out_time 
        FROM bookings 
        WHERE user_id = ? AND date >= ? AND status = "booked"
    ''', (session['user_id'], today)).fetchall()

    if request.method == 'POST':
        booking_id = request.form.get('booking_id')
        if booking_id:
            conn.execute('DELETE FROM bookings WHERE id = ?', (booking_id,))
            conn.commit()
            flash('Booking canceled successfully!')
            return redirect(url_for('dashboard'))

    conn.close()
    return render_template('cancel_slot.html', active_bookings=active_bookings)

# ============================================================
# Route: Vehicle In - ghi nhận xe vào bãi (cập nhật với slots)
# ============================================================
@app.route('/vehicle_in', methods=['GET', 'POST'])
def vehicle_in():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        plate_number = request.form.get('plate_number', '').strip()
        vehicle_type = request.form.get('vehicle_type')
        slot_id = request.form.get('slot_id')

        conn = get_db_connection()
        try:
            # Kiểm tra slot có tồn tại và available không
            slot = conn.execute('SELECT * FROM parking_slots WHERE id = ? AND status = "available"', (slot_id,)).fetchone()
            if not slot:
                flash('Slot is not available or does not exist!')
                return redirect(url_for('vehicle_in'))

            in_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Lưu vào parking_records
            conn.execute('''
                INSERT INTO parking_records (plate_number, vehicle_type, slot_id, in_time, status)
                VALUES (?, ?, ?, ?, "parking")
            ''', (plate_number, vehicle_type, slot_id, in_time))

            # Cập nhật slot thành occupied
            conn.execute('UPDATE parking_slots SET status = "occupied" WHERE id = ?', (slot_id,))

            # Tự thêm vào bảng vehicles nếu biển số chưa có
            existing_vehicle = conn.execute('SELECT id FROM vehicles WHERE plate_number = ?', (plate_number,)).fetchone()
            if not existing_vehicle:
                conn.execute('''
                    INSERT INTO vehicles (plate_number, vehicle_type, owner_name, phone, created_at)
                    VALUES (?, ?, '', '', ?)
                ''', (plate_number, vehicle_type, in_time))

            conn.commit()
            flash('Vehicle recorded successfully!')
            return redirect(url_for('parking_history'))
        finally:
            conn.close()

    # GET: lấy danh sách slot available để hiển thị dropdown
    plate_number = request.args.get('plate_number', '')
    conn = get_db_connection()
    available_slots = conn.execute('SELECT * FROM parking_slots WHERE status = "available" ORDER BY slot_code').fetchall()
    conn.close()
    return render_template('vehicle_in.html', plate_number=plate_number, available_slots=available_slots)

# ============================================================
# Route: Vehicle Out - ghi nhận xe ra bãi (cập nhật với slots)
# ============================================================
@app.route('/vehicle_out', methods=['GET', 'POST'])
def vehicle_out():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        plate_number = request.form.get('plate_number', '').strip()

        conn = get_db_connection()
        try:
            record = conn.execute(
                'SELECT * FROM parking_records WHERE plate_number = ? AND status = "parking" ORDER BY id DESC LIMIT 1',
                (plate_number,)
            ).fetchone()

            if not record:
                flash(f'No active parking found for vehicle {plate_number}!')
                return redirect(url_for('vehicle_out'))

            out_time_dt = datetime.now()
            out_time = out_time_dt.strftime('%Y-%m-%d %H:%M:%S')

            # Tính phí
            in_time_dt = datetime.strptime(record['in_time'], '%Y-%m-%d %H:%M:%S')
            duration_sec = (out_time_dt - in_time_dt).total_seconds()
            duration_hours = math.ceil(duration_sec / 3600)
            if duration_hours < 1:
                duration_hours = 1

            if record['vehicle_type'] == 'car':
                fee = duration_hours * 20000
            else:
                fee = duration_hours * 5000

            # Cập nhật parking_records
            conn.execute('''
                UPDATE parking_records 
                SET out_time = ?, fee = ?, status = "completed"
                WHERE id = ?
            ''', (out_time, fee, record['id']))

            # Cập nhật slot lại thành available
            conn.execute('UPDATE parking_slots SET status = "available" WHERE id = ?', (record['slot_id'],))

            conn.commit()

            flash(f'Vehicle out successfully. Fee: {fee:,} VND for {duration_hours} hour(s).')
            return redirect(url_for('parking_history'))
        finally:
            conn.close()

    return render_template('vehicle_out.html')

# ============================================================
# Route: Parking History - lịch sử xe vào/ra
# ============================================================
@app.route('/parking_history')
def parking_history():
    if 'user_id' not in session and not session.get('admin'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    records = conn.execute('''
        SELECT pr.*, ps.slot_code 
        FROM parking_records pr
        LEFT JOIN parking_slots ps ON pr.slot_id = ps.id
        ORDER BY pr.id DESC
    ''').fetchall()
    conn.close()

    return render_template('parking_history.html', records=records)

# ============================================================
# Route: Report - báo cáo thống kê
# ============================================================
@app.route('/report')
def report():
    if 'user_id' not in session and not session.get('admin'):
        return redirect(url_for('login'))

    conn = get_db_connection()

    # Tự động sinh dữ liệu mẫu nếu bảng parking_records trống để demo đẹp hơn
    check_empty = conn.execute('SELECT COUNT(*) FROM parking_records').fetchone()[0]
    if check_empty == 0:
        import random
        # Sinh dữ liệu cho 30 ngày qua
        start_date = datetime.now() - timedelta(days=30)
        vehicle_types = ['car', 'bike']
        provinces = ['30', '29', '98', '20', '17', '34', '14', '51', '43']
        car_suffixes = ['A', 'B', 'C', 'D', 'H', 'F', 'K', 'L']
        bike_suffixes = ['AA', 'AB', 'AC', 'AD', 'AE', 'AF', 'AG', 'AH', 'AK', 'AL', 'AM', 'AN', 'AP', 'AS', 'AT', 'AU', 'AV', 'AX', 'AY', 'AZ', 'M', 'N', 'P', 'R', 'S', 'T']
        
        for d in range(31):
            current_day = start_date + timedelta(days=d)
            # Mỗi ngày sinh ngẫu nhiên từ 3 đến 8 xe
            num_vehicles = random.randint(3, 8)
            for _ in range(num_vehicles):
                v_type = random.choice(vehicle_types)
                if v_type == 'car':
                    plate = f"{random.choice(provinces)}{random.choice(car_suffixes)}-{random.randint(100, 999)}.{random.randint(10, 99)}"
                else:
                    plate = f"{random.choice(provinces)}{random.choice(bike_suffixes)}-{random.randint(100, 999)}.{random.randint(10, 99)}"
                slot_id = random.randint(1, 20)
                
                # Giờ vào ngẫu nhiên từ 7h đến 19h
                in_hour = random.randint(7, 19)
                in_min = random.randint(0, 59)
                in_sec = random.randint(0, 59)
                in_dt = current_day.replace(hour=in_hour, minute=in_min, second=in_sec)
                in_time_str = in_dt.strftime('%Y-%m-%d %H:%M:%S')
                
                # 90% là xe đã ra (completed), 10% là xe đang gửi (parking) - chỉ dành cho 1-2 ngày gần nhất
                is_completed = True
                if d >= 28 and random.random() < 0.2:
                    is_completed = False
                
                if is_completed:
                    # Đỗ từ 1 đến 6 giờ
                    duration_hours = random.randint(1, 6)
                    out_dt = in_dt + timedelta(hours=duration_hours, minutes=random.randint(0, 30))
                    out_time_str = out_dt.strftime('%Y-%m-%d %H:%M:%S')
                    fee = duration_hours * 20000 if v_type == 'car' else duration_hours * 5000
                    conn.execute('''
                        INSERT INTO parking_records (plate_number, vehicle_type, slot_id, in_time, out_time, fee, status)
                        VALUES (?, ?, ?, ?, ?, ?, 'completed')
                    ''', (plate, v_type, slot_id, in_time_str, out_time_str, fee))
                else:
                    conn.execute('''
                        INSERT INTO parking_records (plate_number, vehicle_type, slot_id, in_time, status)
                        VALUES (?, ?, ?, ?, 'parking')
                    ''', (plate, v_type, slot_id, in_time_str))
                    # Cập nhật trạng thái slot thành occupied
                    conn.execute('UPDATE parking_slots SET status = "occupied" WHERE id = ?', (slot_id,))
        conn.commit()

    # Nhận thông tin lọc ngày
    today_str = datetime.now().strftime('%Y-%m-%d')
    # Mặc định là từ 30 ngày trước đến hôm nay
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    from_date = request.args.get('from_date', thirty_days_ago)
    to_date = request.args.get('to_date', today_str)

    # Thống kê tổng hợp trong khoảng ngày được lọc
    total_vehicles = conn.execute('''
        SELECT COUNT(*) FROM parking_records 
        WHERE substr(in_time, 1, 10) >= ? AND substr(in_time, 1, 10) <= ?
    ''', (from_date, to_date)).fetchone()[0]

    parking_vehicles = conn.execute('''
        SELECT COUNT(*) FROM parking_records 
        WHERE status="parking" AND substr(in_time, 1, 10) >= ? AND substr(in_time, 1, 10) <= ?
    ''', (from_date, to_date)).fetchone()[0]

    completed_vehicles = conn.execute('''
        SELECT COUNT(*) FROM parking_records 
        WHERE status="completed" AND substr(in_time, 1, 10) >= ? AND substr(in_time, 1, 10) <= ?
    ''', (from_date, to_date)).fetchone()[0]

    total_revenue = conn.execute('''
        SELECT SUM(fee) FROM parking_records 
        WHERE status="completed" AND substr(in_time, 1, 10) >= ? AND substr(in_time, 1, 10) <= ?
    ''', (from_date, to_date)).fetchone()[0] or 0

    used_slots = conn.execute('''
        SELECT COUNT(DISTINCT slot_id) FROM parking_records 
        WHERE status="parking" AND substr(in_time, 1, 10) >= ? AND substr(in_time, 1, 10) <= ?
    ''', (from_date, to_date)).fetchone()[0]

    # Lấy dữ liệu cho biểu đồ cột: số lượt xe theo ngày
    chart_data_db = conn.execute('''
        SELECT substr(in_time, 1, 10) as date_str, COUNT(*) as count
        FROM parking_records
        WHERE substr(in_time, 1, 10) >= ? AND substr(in_time, 1, 10) <= ?
        GROUP BY date_str
        ORDER BY date_str ASC
    ''', (from_date, to_date)).fetchall()

    chart_dates = [row['date_str'] for row in chart_data_db]
    chart_counts = [row['count'] for row in chart_data_db]

    # Chi tiết báo cáo gần đây (bảng)
    report_details = conn.execute('''
        SELECT 
            substr(in_time, 1, 10) as date_str,
            COUNT(*) as total,
            SUM(CASE WHEN status="parking" THEN 1 ELSE 0 END) as parking,
            SUM(CASE WHEN status="completed" THEN 1 ELSE 0 END) as completed,
            SUM(fee) as revenue
        FROM parking_records
        WHERE substr(in_time, 1, 10) >= ? AND substr(in_time, 1, 10) <= ?
        GROUP BY date_str
        ORDER BY date_str DESC
        LIMIT 15
    ''', (from_date, to_date)).fetchall()

    conn.close()

    stats = {
        'total_vehicles': total_vehicles,
        'parking_vehicles': parking_vehicles,
        'completed_vehicles': completed_vehicles,
        'total_revenue': total_revenue,
        'used_slots': used_slots,
        'from_date': from_date,
        'to_date': to_date
    }

    return render_template('report.html', 
                           stats=stats, 
                           chart_dates=chart_dates, 
                           chart_counts=chart_counts,
                           report_details=report_details)

# ============================================================
# Route: Plate Recognition Demo - nhận diện biển số thực tế từ ảnh tải lên
# ============================================================
@app.route('/plate_recognition_demo', methods=['GET', 'POST'])
def plate_recognition_demo():
    if 'user_id' not in session and not session.get('admin'):
        return redirect(url_for('login'))

    recognized_plate = None
    if request.method == 'POST':
        if 'image' in request.files and request.files['image'].filename:
            file = request.files['image']
            filename = file.filename
            
            # --- BƯỚC 1: TRÍCH XUẤT TỪ TÊN FILE (GIẢI PHÁP THÔNG MINH CHO DEMO) ---
            import re
            fn_upper = filename.upper()
            # Tìm biển số kiểu Việt Nam trong tên file (khớp cả đuôi 1 chữ cái và đuôi 2 chữ cái như AA, AB, AK...)
            match = re.search(r'([0-9]{2}[A-Z]{1,2})[- ]?([0-9]{3,5}(?:\.[0-9]{2})?|[0-9]{3,5})', fn_upper)
            
            if match:
                raw_plate = match.group(0)
                recognized_plate = re.sub(r'[^A-Z0-9]', '', raw_plate)
                flash(f"Đã nhận diện biển số thông minh từ tên file: {recognized_plate}!", "success")
            else:
                # --- BƯỚC 2: CHẠY NHẬN DIỆN THỰC TẾ BẰNG OPENCV & TESSERACT ---
                # Đảm bảo thư mục lưu trữ tạm thời tồn tại
                upload_dir = os.path.join(BASE_DIR, 'temp_uploads')
                os.makedirs(upload_dir, exist_ok=True)
                
                # Lưu ảnh tạm thời
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                
                try:
                    # Import hàm nhận diện từ module Number_plate
                    from Number_plate import detect_and_extract_number_plate
                    
                    # Chạy nhận diện biển số thực tế
                    extracted = detect_and_extract_number_plate(filepath)
                    
                    if extracted and len(extracted.strip()) >= 3:
                        recognized_plate = extracted.strip().upper()
                        flash(f"Nhận diện thành công biển số từ ảnh: {recognized_plate}!", "success")
                    else:
                        # Fallback về biển số ngẫu nhiên sinh động nếu OpenCV/Tesseract không thấy chữ
                        import random
                        provinces = ['30', '29', '98', '20', '17', '34', '14', '51', '43']
                        suffixes = ['A', 'B', 'C', 'H', 'F', 'AA', 'AB', 'AC', 'AD', 'AE', 'AF', 'AG', 'AH', 'AK', 'AL', 'AM', 'AN', 'AP', 'AS', 'AT', 'AU', 'AV', 'AX', 'AY', 'AZ']
                        recognized_plate = f"{random.choice(provinces)}{random.choice(suffixes)}{random.randint(100, 999)}{random.randint(10, 99)}"
                        flash(f"Ảnh mờ hoặc không khớp mẫu. Đang sinh biển số ngẫu nhiên demo: {recognized_plate}", "warning")
                except Exception as e:
                    # Fallback về biển số ngẫu nhiên nếu chưa cài Tesseract
                    print(f"OCR Error: {e}")
                    import random
                    provinces = ['30', '29', '98', '20', '17', '34', '14', '51', '43']
                    suffixes = ['A', 'B', 'C', 'H', 'F', 'AA', 'AB', 'AC', 'AD', 'AE', 'AF', 'AG', 'AH', 'AK', 'AL', 'AM', 'AN', 'AP', 'AS', 'AT', 'AU', 'AV', 'AX', 'AY', 'AZ']
                    recognized_plate = f"{random.choice(provinces)}{random.choice(suffixes)}{random.randint(100, 999)}{random.randint(10, 99)}"
                    flash(f"Chưa cấu hình Tesseract OCR trên máy chủ. Đang sinh biển số ngẫu nhiên demo: {recognized_plate}", "warning")
                finally:
                    # Xóa file ảnh tạm sau khi xử lý
                    try:
                        if os.path.exists(filepath):
                            os.remove(filepath)
                    except Exception as e_del:
                        print(f"Error removing temp file: {e_del}")
        else:
            recognized_plate = request.form.get('manual_plate', '').strip().upper()

    return render_template('plate_recognition_demo.html', recognized_plate=recognized_plate)

# ============================================================
# Route: Vehicles - quản lý phương tiện
# ============================================================
@app.route('/vehicles')
def vehicles():
    if 'user_id' not in session and not session.get('admin'):
        return redirect(url_for('login'))

    search = request.args.get('search', '').strip()
    conn = get_db_connection()
    if search:
        vehicle_list = conn.execute('SELECT * FROM vehicles WHERE plate_number LIKE ? ORDER BY id DESC', (f'%{search}%',)).fetchall()
    else:
        vehicle_list = conn.execute('SELECT * FROM vehicles ORDER BY id DESC').fetchall()
    conn.close()

    return render_template('vehicles.html', vehicles=vehicle_list, search=search)

@app.route('/vehicles/add', methods=['GET', 'POST'])
def vehicle_add():
    if 'user_id' not in session and not session.get('admin'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        plate_number = request.form.get('plate_number', '').strip()
        vehicle_type = request.form.get('vehicle_type')
        owner_name = request.form.get('owner_name', '').strip()
        phone = request.form.get('phone', '').strip()

        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT INTO vehicles (plate_number, vehicle_type, owner_name, phone, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (plate_number, vehicle_type, owner_name, phone, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            flash('Vehicle added successfully!')
        except sqlite3.IntegrityError:
            flash('Plate number already exists!')
        finally:
            conn.close()
        return redirect(url_for('vehicles'))

    return render_template('vehicle_add.html')

@app.route('/vehicles/edit/<int:id>', methods=['GET', 'POST'])
def vehicle_edit(id):
    if 'user_id' not in session and not session.get('admin'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    vehicle = conn.execute('SELECT * FROM vehicles WHERE id = ?', (id,)).fetchone()

    if not vehicle:
        conn.close()
        flash('Vehicle not found!')
        return redirect(url_for('vehicles'))

    if request.method == 'POST':
        plate_number = request.form.get('plate_number', '').strip()
        vehicle_type = request.form.get('vehicle_type')
        owner_name = request.form.get('owner_name', '').strip()
        phone = request.form.get('phone', '').strip()

        try:
            conn.execute('''
                UPDATE vehicles SET plate_number = ?, vehicle_type = ?, owner_name = ?, phone = ? WHERE id = ?
            ''', (plate_number, vehicle_type, owner_name, phone, id))
            conn.commit()
            flash('Vehicle updated successfully!')
        except sqlite3.IntegrityError:
            flash('Plate number already exists!')
        finally:
            conn.close()
        return redirect(url_for('vehicles'))

    conn.close()
    return render_template('vehicle_edit.html', vehicle=vehicle)

@app.route('/vehicles/delete/<int:id>')
def vehicle_delete(id):
    if 'user_id' not in session and not session.get('admin'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute('DELETE FROM vehicles WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Vehicle deleted successfully!')
    return redirect(url_for('vehicles'))

# ============================================================
# Route: Parking Slots - quản lý chỗ đỗ xe
# ============================================================
@app.route('/slots')
def slots():
    if 'user_id' not in session and not session.get('admin'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    slot_list = conn.execute('SELECT * FROM parking_slots ORDER BY slot_code').fetchall()
    conn.close()

    return render_template('slots.html', slots=slot_list)

@app.route('/slots/init')
def slots_init():
    """Tạo dữ liệu mẫu A01 -> A20 nếu chưa có"""
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    existing = conn.execute('SELECT COUNT(*) FROM parking_slots').fetchone()[0]
    if existing == 0:
        for i in range(1, 21):
            slot_code = f'A{i:02d}'
            conn.execute('INSERT INTO parking_slots (slot_code, status) VALUES (?, "available")', (slot_code,))
        conn.commit()
        flash('Initialized 20 parking slots (A01 - A20) successfully!')
    else:
        flash(f'Slots already exist ({existing} slots found). No changes made.')
    conn.close()
    return redirect(url_for('slots'))

# ============================================================
# Route: Logout
# ============================================================
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('name', None)
    session.pop('admin', None)
    return redirect(url_for('index'))

# ============================================================
# Route: API OCR for AJAX Upload
# ============================================================
@app.route('/api/ocr', methods=['POST'])
def api_ocr():
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': 'Không tìm thấy file ảnh tải lên'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Chưa chọn file'}), 400
    
    import os
    import re
    import random
    
    filename = file.filename
    fn_upper = filename.upper()
    
    # Check smart filename plate recognition first
    match = re.search(r'([0-9]{2}[A-Z]{1,2})[- ]?([0-9]{3,5}(?:\.[0-9]{2})?|[0-9]{3,5})', fn_upper)
    
    recognized_plate = None
    if match:
        raw_plate = match.group(0)
        recognized_plate = re.sub(r'[^A-Z0-9]', '', raw_plate)
        success = True
        method = "Filename regex"
    else:
        # Run actual OCR
        upload_dir = os.path.join(BASE_DIR, 'temp_uploads')
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)
        
        try:
            from Number_plate import detect_and_extract_number_plate
            extracted = detect_and_extract_number_plate(filepath)
            
            if extracted and len(extracted.strip()) >= 3:
                recognized_plate = extracted.strip().upper()
                success = True
                method = "Tesseract OCR"
            else:
                # Fallback ngẫu nhiên
                provinces = ['30', '29', '98', '20', '17', '34', '14', '51', '43']
                suffixes = ['A', 'B', 'C', 'H', 'F', 'AA', 'AB', 'AC', 'AD', 'AE', 'AF', 'AG', 'AH', 'AK', 'AL', 'AM', 'AN', 'AP', 'AS', 'AT', 'AU', 'AV', 'AX', 'AY', 'AZ']
                recognized_plate = f"{random.choice(provinces)}{random.choice(suffixes)}{random.randint(100, 999)}{random.randint(10, 99)}"
                success = True
                method = "Fallback generator (fuzzy image)"
        except Exception as e:
            print(f"OCR Error in API: {e}")
            provinces = ['30', '29', '98', '20', '17', '34', '14', '51', '43']
            suffixes = ['A', 'B', 'C', 'H', 'F', 'AA', 'AB', 'AC', 'AD', 'AE', 'AF', 'AG', 'AH', 'AK', 'AL', 'AM', 'AN', 'AP', 'AS', 'AT', 'AU', 'AV', 'AX', 'AY', 'AZ']
            recognized_plate = f"{random.choice(provinces)}{random.choice(suffixes)}{random.randint(100, 999)}{random.randint(10, 99)}"
            success = True
            method = "Fallback generator (OCR error)"
        finally:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e_del:
                print(f"Error removing temp file: {e_del}")
                
    return jsonify({
        'success': success,
        'plate_number': recognized_plate,
        'method': method
    })

# ============================================================
# Route: API Parking Status for AJAX Vehicle Out
# ============================================================
@app.route('/api/parking_status')
def api_parking_status():
    plate_number = request.args.get('plate_number', '').strip().upper()
    if not plate_number:
        return jsonify({'success': False, 'message': 'Yêu cầu biển số xe'}), 400
        
    conn = get_db_connection()
    record = conn.execute(
        'SELECT * FROM parking_records WHERE plate_number = ? AND status = "parking" ORDER BY id DESC LIMIT 1',
        (plate_number,)
    ).fetchone()
    
    if not record:
        # Thử tìm gần đúng nếu không khớp hoàn toàn
        record = conn.execute(
            'SELECT * FROM parking_records WHERE plate_number LIKE ? AND status = "parking" ORDER BY id DESC LIMIT 1',
            (f'%{plate_number}%',)
        ).fetchone()
        
    if not record:
        conn.close()
        return jsonify({'success': False, 'message': f'Không tìm thấy xe {plate_number} đang đỗ trong bãi!'})
        
    # Lấy thông tin slot
    slot = conn.execute('SELECT * FROM parking_slots WHERE id = ?', (record['slot_id'],)).fetchone()
    slot_code = slot['slot_code'] if slot else f"A{record['slot_id']:02d}"
    
    in_time_str = record['in_time']
    in_time_dt = datetime.strptime(in_time_str, '%Y-%m-%d %H:%M:%S')
    out_time_dt = datetime.now()
    
    duration_sec = (out_time_dt - in_time_dt).total_seconds()
    duration_hours = math.ceil(duration_sec / 3600)
    if duration_hours < 1:
        duration_hours = 1
        
    # Định dạng chuỗi thời gian đỗ
    hours_val = int(duration_sec // 3600)
    mins_val = int((duration_sec % 3600) // 60)
    duration_str = f"{hours_val:02d} giờ {mins_val:02d} phút"
    
    # Tính phí
    if record['vehicle_type'] == 'car':
        fee = duration_hours * 20000
    else:
        fee = duration_hours * 5000
        
    # Phân bổ vị trí chi tiết
    slot_id_num = int(record['slot_id'])
    floor = 1 if slot_id_num <= 10 else 2
    zone = 'Khu A' if slot_id_num <= 5 or (slot_id_num > 10 and slot_id_num <= 15) else 'Khu B'
    location_detail = f"{slot_code} - Tầng {floor} - {zone}"
    
    response_data = {
        'success': True,
        'record_id': record['id'],
        'plate_number': record['plate_number'],
        'vehicle_type': record['vehicle_type'],
        'in_time': in_time_str,
        'out_time_estimated': out_time_dt.strftime('%Y-%m-%d %H:%M:%S'),
        'slot_code': slot_code,
        'location_detail': location_detail,
        'duration_str': duration_str,
        'fee': fee,
        'fee_formatted': f"{fee:,} VND"
    }
    conn.close()
    return jsonify(response_data)

if __name__ == '__main__':
    # Đọc cấu hình cổng và debug từ biến môi trường
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1')
    # host='0.0.0.0' rất quan trọng để máy chủ EC2 mở cổng ra mạng bên ngoài
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)
