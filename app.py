import sqlite3
import os
import pandas as pd
import base64
import io
from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime
import json

app = Flask(__name__)

# 데이터베이스 파일명
DB_PATH = "market.db"

# 이미지 폴더 고정 경로
BASE_IMG_PATH = r"C:\Users\new\Desktop\image\clean_images"

# 카테고리 ID 매핑
CATEGORY_MAP = {
    1: '과일', 2: '채소', 3: '양곡/견과류', 4: '정육/계란', 5: '수산/건해산물', 
    6: '양념/가루/오일', 7: '반찬/냉장/냉동/즉석식품', 8: '면류/통조림/간편식품', 
    9: '유제품/베이커리', 10: '생수/음료/커피/차', 11: '과자/시리얼/빙과', 
    12: '바디케어/베이비', 13: '주방/세제/세탁/청소', 14: '생활/잡화', 
    15: '대용량/식자재', 16: '세트상품'
}
CATEGORIES = list(CATEGORY_MAP.values()) + ['기타']

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products 
                 (id TEXT PRIMARY KEY, name TEXT, price INTEGER, stock INTEGER, category TEXT, icon TEXT, tags TEXT, isClosed INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (orderNumber TEXT PRIMARY KEY, name TEXT, phone TEXT, address TEXT, detail TEXT, gate TEXT, items TEXT, total TEXT, status TEXT, payment TEXT, date TEXT, cart TEXT, userId TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id TEXT PRIMARY KEY, password TEXT, name TEXT, nickname TEXT, phone TEXT, email TEXT, address TEXT, detail_addr TEXT, gate_pw TEXT, is_admin INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, content TEXT, rating INTEGER)''')
    
    # 관리자 계정
    c.execute("INSERT OR IGNORE INTO users (id, password, name, nickname, is_admin) VALUES ('admin', '3150', '관리자', '관리자형님', 1)")
    conn.commit()
    conn.close()

init_db()

def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/init', methods=['GET'])
def get_initial_data():
    conn = get_db_conn()
    products = [dict(row) for row in conn.execute("SELECT * FROM products").fetchall()]
    orders = [dict(row) for row in conn.execute("SELECT * FROM orders ORDER BY orderNumber DESC LIMIT 10").fetchall()]
    reviews = [dict(row) for row in conn.execute("SELECT * FROM reviews ORDER BY id DESC").fetchall()]
    notice_row = conn.execute("SELECT value FROM settings WHERE key='notice'").fetchone()
    settings = {'notice': notice_row['value'] if notice_row else '', 'categories': CATEGORIES}
    conn.close()
    return jsonify({'products': products, 'orders': orders, 'settings': settings, 'reviews': reviews})

@app.route('/api/register', methods=['POST'])
def register():
    d = request.json
    conn = get_db_conn()
    try:
        conn.execute("INSERT INTO users (id, password, name, nickname, phone, email, address, detail_addr, gate_pw) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (d['id'], d['password'], d['name'], d['nickname'], d['phone'], d['email'], d['address'], d['detail_addr'], d['gate_pw']))
        conn.commit()
        return jsonify("SUCCESS")
    except Exception as e:
        return jsonify({'error': '이미 존재하는 아이디입니다.'}), 400
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    d = request.json
    conn = get_db_conn()
    user = conn.execute("SELECT * FROM users WHERE id=? AND password=?", (d['id'], d['password'])).fetchone()
    conn.close()
    if user: return jsonify(dict(user))
    else: return jsonify({'error': '아이디 또는 비밀번호가 틀렸습니다.'}), 400

@app.route('/api/admin/users', methods=['GET'])
def get_users():
    conn = get_db_conn()
    users = [dict(row) for row in conn.execute("SELECT * FROM users WHERE is_admin=0").fetchall()]
    conn.close()
    return jsonify(users)

@app.route('/api/admin/send_msg', methods=['POST'])
def send_msg():
    d = request.json
    print(f"---[문자전송] 수신: {d['phone']}, 내용: {d['msg']}---")
    return jsonify("전송 완료")

@app.route('/api/order', methods=['POST'])
def save_order():
    d = request.json
    conn = get_db_conn()
    conn.execute("INSERT INTO orders (orderNumber, name, phone, address, detail, gate, items, total, status, payment, date, cart, userId) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 (str(d['orderNumber']), d['name'], d['phone'], d['address'], d['detail'], d['gate'], d['items'], d['total'], d['status'], d['payment'], d['date'], json.dumps(d['cart']), d.get('userId', 'guest')))
    for item in d['cart']:
        conn.execute("UPDATE products SET stock = stock - 1 WHERE id = ?", (str(item['id']),))
    conn.commit()
    conn.close()
    return jsonify("SUCCESS")

@app.route('/api/product', methods=['POST'])
def save_product():
    d = request.json
    p_id = str(d.get('id')) if d.get('id') else str(int(datetime.now().timestamp() * 1000))
    conn = get_db_conn()
    exist = conn.execute("SELECT 1 FROM products WHERE id=?", (p_id,)).fetchone()
    if exist:
        conn.execute("UPDATE products SET name=?, price=?, stock=?, category=?, icon=? WHERE id=?",
                     (d['name'], d['price'], d['stock'], d['category'], d['icon'], p_id))
    else:
        conn.execute("INSERT INTO products (id, name, price, stock, category, icon, tags, isClosed) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (p_id, d['name'], d['price'], d['stock'], d['category'], d['icon'], '[]', 0))
    conn.commit()
    conn.close()
    return jsonify("SUCCESS")

@app.route('/api/product/delete', methods=['POST'])
def delete_product():
    conn = get_db_conn()
    conn.execute("DELETE FROM products WHERE id=?", (str(request.json['id']),))
    conn.commit()
    conn.close()
    return jsonify("SUCCESS")

@app.route('/api/product/delete-all', methods=['POST'])
def delete_all_products():
    conn = get_db_conn()
    conn.execute("DELETE FROM products")
    conn.commit()
    conn.close()
    return jsonify("모든 상품이 삭제되었습니다.")

@app.route('/api/product/delete-category', methods=['POST'])
def delete_category_products():
    target_cat = request.json.get('category')
    conn = get_db_conn()
    conn.execute("DELETE FROM products WHERE category=?", (target_cat,))
    conn.commit()
    conn.close()
    return jsonify(f"'{target_cat}' 카테고리 상품 삭제 완료")

@app.route('/api/upload/excel', methods=['POST'])
def upload_excel():
    try:
        if 'file' not in request.files: return jsonify({'error': '파일 없음'}), 400
        file = request.files['file']
        df = pd.read_excel(file).fillna('')
        df.columns = [str(c).strip() for c in df.columns]
        cat_col = '카테고리' if '카테고리' in df.columns else '카테고리ID'

        conn = get_db_conn()
        count = 0
        for idx, row in df.iterrows():
            p_id = str(int(datetime.now().timestamp() * 1000) + idx)
            raw_cat = str(row.get(cat_col, '')).strip()
            cat_name = '기타'
            if raw_cat in CATEGORY_MAP.values(): cat_name = raw_cat
            else:
                try: cat_name = CATEGORY_MAP.get(int(float(raw_cat)), '기타')
                except: pass
            
            p_name = str(row.get('상품명', '이름없음')).strip()
            p_spec = str(row.get('규격', '')).strip()
            full_name = f"{p_name} ({p_spec})" if p_spec else p_name
            p_price = str(row.get('가격', 0))
            img_filename = str(row.get('이미지파일명', '')).strip()
            
            icon_data = '🍎'
            if img_filename:
                path = os.path.join(BASE_IMG_PATH, img_filename)
                if os.path.exists(path):
                    try:
                        with open(path, "rb") as f:
                            encoded = base64.b64encode(f.read()).decode('utf-8')
                            ext = img_filename.split('.')[-1].lower()
                            mime = 'jpeg' if ext in ['jpg','jpeg'] else 'png'
                            icon_data = f"data:image/{mime};base64,{encoded}"
                    except: pass
            
            conn.execute("INSERT INTO products (id, name, price, stock, category, icon, tags, isClosed) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (p_id, full_name, p_price, 100, cat_name, icon_data, '[]', 0))
            count += 1
        conn.commit()
        conn.close()
        return jsonify(f"상품 {count}개 등록 성공")
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/admin/download/orders', methods=['GET'])
def download_orders_excel():
    conn = get_db_conn()
    df = pd.read_sql("SELECT * FROM orders ORDER BY orderNumber DESC", conn)
    conn.close()
    output = io.BytesIO()
    df = df.drop(columns=['cart'], errors='ignore')
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    fname = f"주문목록_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(output, as_attachment=True, download_name=fname, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/api/admin/download/users', methods=['GET'])
def download_users_excel():
    conn = get_db_conn()
    df = pd.read_sql("SELECT * FROM users WHERE is_admin=0", conn)
    conn.close()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    fname = f"회원목록_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(output, as_attachment=True, download_name=fname, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/api/settings', methods=['POST'])
def save_settings():
    conn = get_db_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('notice', ?)", (request.json['notice'],))
    conn.commit()
    return jsonify("SUCCESS")

@app.route('/api/review', methods=['POST'])
def add_review():
    d = request.json
    conn = get_db_conn()
    conn.execute("INSERT INTO reviews (name, content, rating) VALUES (?, ?, ?)", (d['name'], d['content'], d['rating']))
    conn.commit()
    return jsonify("SUCCESS")

@app.route('/api/admin/orders', methods=['GET'])
def get_all_orders():
    conn = get_db_conn()
    orders = [dict(row) for row in conn.execute("SELECT * FROM orders ORDER BY orderNumber DESC").fetchall()]
    return jsonify(orders)

if __name__ == '__main__':
    app.run(debug=True, port=5000)