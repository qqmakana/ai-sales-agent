# Production Deployment (Scale Ready)

This app is now set up for production scale with:
- Postgres database
- Redis queue + background worker
- Scheduler process
- Rate limiting
- SendGrid email support

## 1) Environment Variables
Create a `.env` file with:

```
SECRET_KEY=change-me
DATABASE_URL=postgresql://user:pass@host:5432/ai_sales_agent
REDIS_URL=redis://default:pass@host:6379/0
SENDGRID_API_KEY=your_key
SENDGRID_FROM_EMAIL=verified@yourdomain.com
```

## 2) Migrations
Initialize the database (run once) **from your host machine**:

```
set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_sales_agent
alembic upgrade head
```

## 3) Run Services (Docker)
```
docker compose up --build
```

This starts:
- Web app (Gunicorn)
- Worker (RQ)
- Scheduler
- Postgres
- Redis

Note: `AUTO_CREATE_DB` is disabled in Docker. Use Alembic for schema changes.

## 4) Run Services (Manual)
```
gunicorn app:app
rq worker -u $REDIS_URL automations
python scheduler_runner.py
```

## 5) Load Testing
```
locust
```
Open `http://localhost:8089` and set target host to your app URL.

## Notes
- For high volume email, use SendGrid instead of Gmail SMTP.
- Always run with Postgres + Redis in production.
