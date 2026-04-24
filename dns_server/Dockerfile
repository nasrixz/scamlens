FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY dns_server/requirements.txt ./dns_server/requirements.txt
RUN pip install -r dns_server/requirements.txt

COPY dns_server /app/dns_server

EXPOSE 53/udp 53/tcp 8053/tcp

CMD ["python", "-u", "-m", "dns_server.main"]
