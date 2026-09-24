FROM python:3.12-slim

WORKDIR /app

# Dependencias de sistema del Nivel 3: el binario de Tesseract con sus modelos
# de idioma (español e inglés) y las bibliotecas nativas que OpenCV enlaza en
# tiempo de ejecución.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-spa \
        tesseract-ocr-eng \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV GROQ_API_KEY="" \
    GROQ_MODEL=qwen/qwen3.8-27b \
    TESSERACT_CMD=/usr/bin/tesseract \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata \
    CORE_BASE_URL=http://plurione-core:8001 \
    RULES_BASE_URL=http://plurione-rules:8002 \
    STORAGE_VAULT_PATH=/app/storage_vault

EXPOSE 8003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
