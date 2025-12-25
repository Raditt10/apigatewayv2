from flask import Flask, request, render_template, redirect, url_for, jsonify
import boto3
import os
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Konfigurasi AWS
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")
AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
API_URL = os.getenv("API_GATEWAY_URL")

# Inisialisasi S3 Client
# Pastikan Credentials di Elastic Beanstalk Config SELALU UPDATE (Fresh Token)
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    aws_session_token=AWS_SESSION_TOKEN,
    region_name=AWS_REGION,
)

@app.route("/")
def index():
    try:
        response = requests.get(API_URL)
        # Jika API Gateway mengembalikan error, user list kosong dulu agar tidak crash
        if response.status_code != 200:
            users = []
            print(f"⚠️ Error fetching users: {response.text}")
        else:
            users = response.json()
    except Exception as e:
        users = []
        print(f"❌ Connection error to API Gateway: {e}")

    # Perbaikan format URL S3 agar konsisten
    s3_base_url = f"https://{S3_BUCKET}.s3.amazonaws.com/"
    return render_template("index.html", users=users, s3_bucket=s3_base_url)

@app.route("/users", methods=["POST"])
def add_user():
    name = request.form["name"]
    email = request.form["email"]
    institution = request.form["institution"]
    position = request.form["position"]
    phone = request.form["phone"]
    image = request.files["image"]

    # 1. Cek Email (Skip kalau error koneksi biar ga crash)
    try:
        check_response = requests.get(f"{API_URL}?email={email}")
        if check_response.status_code == 409:
            return jsonify({"error": "Email already exists"}), 409
    except:
        pass

    # 2. Upload ke S3
    image_url = ""
    if image:
        image_filename = f"users/{image.filename}"
        try:
            s3_client.upload_fileobj(image, S3_BUCKET, image_filename)
            image_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{image_filename}"
        except Exception as e:
            return jsonify({"error": f"S3 Upload Failed. Token Expired? Error: {str(e)}"}), 500

    # 3. Simpan ke API Gateway
    user_data = {
        "name": name,
        "email": email,
        "institution": institution,
        "position": position,
        "phone": phone,
        "image_url": image_url,
    }

    try:
        response = requests.post(API_URL, json=user_data)
        
        # ✅ PERBAIKAN: Cek apakah sukses (Code 200 atau 201)
        if response.status_code not in [200, 201]:
            # Jika gagal, TAMPILKAN ERROR JSON, jangan redirect!
            return jsonify({
                "message": "Gagal menyimpan data ke Backend",
                "status_code": response.status_code,
                "error_details": response.text
            }), response.status_code

    except Exception as e:
        return jsonify({"error": f"Connection to API Gateway failed: {str(e)}"}), 500

    return redirect(url_for("index"))

@app.route("/users/<int:user_id>/delete", methods=["DELETE"])
def delete_user(user_id):
    try:
        # Kirim request delete ke API Gateway
        response = requests.delete(f"{API_URL}/{user_id}")

        if response.status_code == 204:
            return jsonify({"message": "User deleted successfully"}), 200
        
        # Coba parse response JSON dari API Gateway
        try:
            return jsonify(response.json()), response.status_code
        except ValueError:
            # INI PERBAIKAN UTAMA: Menangkap error jika API Gateway balikin HTML error
            print(f"❌ Non-JSON response from API: {response.text}")
            return jsonify({"error": "Backend Error (Non-JSON response)"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    response = requests.get(f"{API_URL}/{user_id}")
    return jsonify(response.json()), response.status_code

@app.route("/users/<int:user_id>", methods=["PUT", "PATCH"])
def update_user(user_id):
    data = request.json
    response = requests.put(f"{API_URL}/{user_id}", json=data)

    if response.status_code == 200:
        return jsonify({"message": "User updated", "data": response.json()})
    else:
        return jsonify({"error": "Failed to update user"}), response.status_code

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)