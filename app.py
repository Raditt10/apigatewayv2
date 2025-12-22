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

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    aws_session_token=AWS_SESSION_TOKEN,
    region_name=AWS_REGION,
)

@app.route("/")
def index():
    response = requests.get(API_URL)
    users = response.json()
    return render_template("index.html", users=users, s3_bucket=f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/")

@app.route("/users", methods=["POST"])
def add_user():
    name = request.form["name"]
    email = request.form["email"]
    institution = request.form["institution"]
    position = request.form["position"]
    phone = request.form["phone"]
    image = request.files["image"]

    # 1️⃣ Cek apakah email sudah ada di database
    check_response = requests.get(f"{API_URL}?email={email}")
    
    if check_response.status_code == 409:  # Jika email sudah ada
        print("❌ Email already exists, stopping process")  # Debugging log
        return jsonify({"error": "Email already exists"}), 409

    # 2️⃣ Jika email belum ada, lanjut upload gambar
    image_url = ""
    if image:
        image_filename = f"users/{image.filename}"
        try:
            s3_client.upload_fileobj(image, S3_BUCKET, image_filename)
            image_url = f"https://{S3_BUCKET}.s3-{AWS_REGION}.amazonaws.com/{image_filename}"
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # 3️⃣ Simpan user ke database
    user_data = {
        "name": name,
        "email": email,
        "institution": institution,
        "position": position,
        "phone": phone,
        "image_url": image_url,
    }

    response = requests.post(API_URL, json=user_data)

    if response.status_code == 409:
        print("❌ API returned 409, email conflict")  # Debugging log
        return jsonify({"error": "Email already exists"}), 409

    return redirect(url_for("index"))

@app.route("/users/<int:user_id>/delete", methods=["DELETE"])
def delete_user(user_id):
    response = requests.delete(f"{API_URL}/{user_id}")

    if response.status_code == 204:
        return jsonify({"message": "User deleted successfully"}), 200
    
    try:
        return jsonify(response.json()), response.status_code
    except request.exceptions.JSONDecodeError:
        return jsonify({"error": "Unexpected empty response"}), response.status_code

@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    response = requests.get(f"{API_URL}/{user_id}")
    return jsonify(response.json()), response.status_code

@app.route("/users/<int:user_id>", methods=["PUT", "PATCH"])
def update_user(user_id):
    data = request.json
    response = requests.put(f"{API_URL}/{user_id}", json=data)

    if response.status_code == 200:
        return jsonify({"message": "Used sudah diupdate", "data": response.json()})
    else:
        return jsonify({"error": "Failed to update user"}), response.status_code

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')