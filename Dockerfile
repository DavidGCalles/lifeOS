# LifeOS v3 — edge-bot (v3-FR-02a)
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY personas/ ./personas/
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "src.bot.main:app", "--host", "0.0.0.0", "--port", "8080"]
