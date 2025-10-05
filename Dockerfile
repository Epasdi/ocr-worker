FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    poppler-utils tesseract-ocr ghostscript libgl1 file \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV QUAR_DIR=/srv/quarantine
VOLUME ["/srv/quarantine"]

CMD ["python", "worker_run.py"]
