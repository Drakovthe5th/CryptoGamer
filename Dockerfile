FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN pip uninstall -y pytoncenter && pip install --no-cache-dir pytoncenter==0.0.14

RUN pip install --no-cache-dir -r requirements.txt

# Add health check for wallet status
HEALTHCHECK --interval=30s --timeout=10s \
  CMD curl -f http://localhost:5000/api/wallet/status || exit 1

CMD ["python", "bot.py"]  # For worker
# For web service:
# CMD ["gunicorn", "--worker-tmp-dir", "/dev/shm", "--workers", "2", "--threads", "4", "--worker-class", "gthread", "app:app"]