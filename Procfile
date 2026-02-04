web: gunicorn app:app
worker: rq worker -u $REDIS_URL automations
scheduler: python scheduler_runner.py
