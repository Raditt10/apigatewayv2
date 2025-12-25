# Gunakan Python versi ringan
FROM python:3.9-slim

# Set folder kerja
WORKDIR /app

# Copy file requirements dulu biar caching jalan
COPY requirements.txt .

# Install library
RUN pip install --no-cache-dir -r requirements.txt

# Copy sisa codingan
COPY . .

# Buka Port 5000 (PENTING!)
EXPOSE 5000

# Jalankan aplikasi
CMD ["python", "app.py"]