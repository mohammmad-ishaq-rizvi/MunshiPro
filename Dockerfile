FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DUKAAN_DB_PATH=/data/dukaan.sqlite3
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin gosu && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py README.md ./
COPY src ./src
RUN useradd --create-home --uid 10001 appuser && mkdir -p /data && chown appuser:appuser /data
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8501')+'/_stcore/health', timeout=3)" || exit 1
CMD ["sh", "-c", "chown -R appuser:appuser /data && exec gosu appuser streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --server.headless=true"]
