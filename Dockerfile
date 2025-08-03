FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "bot.py"]  # For worker
# For web service:
# CMD ["gunicorn", "--worker-tmp-dir", "/dev/shm", "--workers", "2", "--threads", "4", "--worker-class", "gthread", "app:app"]