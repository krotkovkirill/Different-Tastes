FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DT_HEADLESS=1 \
    FLET_FORCE_WEB_SERVER=1 \
    DT_HOST=0.0.0.0 \
    PORT=8550 \
    DT_DATA_DIR=/data

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 app \
    && mkdir /data && chown app:app /data
COPY --chown=app:app 1vDT/ ./1vDT/
USER app
EXPOSE 8550
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8550')+'/',timeout=4)"
CMD ["python", "1vDT/main.py"]
