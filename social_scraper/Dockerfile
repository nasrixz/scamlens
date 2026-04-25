FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY social_scraper/requirements.txt ./social_scraper/requirements.txt
RUN pip install -r social_scraper/requirements.txt

COPY social_scraper /app/social_scraper

CMD ["python", "-u", "-m", "social_scraper.main"]
