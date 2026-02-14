# gunicorn_config.py
import multiprocessing

# Render free tier has limited memory, use fewer workers
workers = 2  # Use only 1 worker on free tier
worker_class = "sync"
worker_connections = 1000
timeout = 60  # Increase timeout to 120 seconds
keepalive = 5

# Preload app to reduce memory usage per worker
preload_app = True

# Limit request handling
max_requests = 1000
max_requests_jitter = 50

# Binding
bind = "0.0.0.0:10000"
