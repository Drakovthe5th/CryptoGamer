web: gunicorn --worker-tmp-dir /dev/shm --workers 2 --threads 4 --worker-class gthread app:app
worker: python bot.py