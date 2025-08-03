#!/bin/bash

# Start unified server
gunicorn --worker-tmp-dir /dev/shm --workers 2 --threads 4 --worker-class gthread server:app