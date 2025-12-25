from flask import Flask, request, render_template, redirect, url_for, jsonify
import boto3
import os
import pymysql
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)

# --- KONFIGURASI S3 (Tetap Pakai Code Kamu) ---
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION")

# Menggunakan Instance Profile (LabInstanceProfile) supaya tidak perlu hardcode Access Key
s3_client = boto3.client("s3", region_name=AWS_REGION)

# --- FUNGSI KONEKSI DATABASE (BARU) ---
def get_db_connection():
    # Mengambil settingan yang tadi kita input di Elastic Beanstalk
    return pymysql.connect(
        host=os.getenv("RDS_HOSTNAME"),
        user=os.getenv("RDS_USERNAME"),
        password=os.getenv("RDS_PASSWORD"),
        database=os.getenv("RDS_DB_NAME"),
        port=int(os.getenv("RDS_PORT", 3306)),
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10
    )

# --- AUTO CREATE TABLE (Supaya tidak error table not found) ---
def init_db():
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    institution VARCHAR(255),
                    position VARCHAR(255),
                    phone VARCHAR(20),
                    image_url TEXT
                )
            """)
        connection.commit()
        connection.close()
        print("✅ Database connected & Table checked.")
    except Exception as e:
        print(f"❌ Database Error: {e}")

# Jalankan cek tabel saat aplikasi start
with app.app_context():
    init_db()

# --- ROUTES ---

@app.route("/")
def index():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users")
            users = cursor.fetchall()
        conn.close()
        return render_template("index.html", users=users)
    except Exception as e:
        return f"Error connecting to DB: {str(e)}"

@app.route("/users", methods=["POST"])
def add_user():
    name = request.form["name"]
    email = request.form["email"]
    institution = request.form["institution"]
    position = request.form["position"]
    phone = request.form["phone"]
    image = request.files["image"]

    # 1. Upload ke S3
    image_url = ""
    if image:
        filename = secure_filename(image.filename)
        # Tambahkan timestamp atau unique ID biar file tidak bentrok (opsional tapi disarankan)
        image_filename = f"users/{filename}" 
        try:
            s3_client.upload_fileobj(image, S3_BUCKET, image_filename)
            # Construct URL Public S3
            image_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{image_filename}"
        except Exception as e:
            return f"S3 Upload Error: {str(e)}"

    # 2. Simpan ke Database RDS
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = "INSERT INTO users (name, email, institution, position, phone, image_url) VALUES (%s, %s, %s, %s, %s, %s)"
            cursor.execute(sql, (name, email, institution, position, phone, image_url))
        conn.commit()
        conn.close()
    except pymysql.err.IntegrityError:
        return "Email already exists!"
    except Exception as e:
        return f"Database Insert Error: {str(e)}"

    return redirect(url_for("index"))

@app.route("/users/<int:user_id>/delete", methods=["POST"]) # HTML Form biasanya cuma support GET/POST
def delete_user(user_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        return f"Delete Error: {str(e)}"
    
    return redirect(url_for("index"))

@app.route("/health")
def health():
    return "Healthy", 200

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')