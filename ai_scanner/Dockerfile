FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY ai_scanner/requirements.txt ./ai_scanner/requirements.txt
RUN pip install -r ai_scanner/requirements.txt

COPY ai_scanner /app/ai_scanner

CMD ["python", "-u", "-m", "ai_scanner.main"]
