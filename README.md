# Campus Delivery Robot Backend

Initial backend scaffold for the campus delivery robot project using:

- Django
- Django REST Framework
- Django Channels
- PostgreSQL
- Redis
- JWT authentication

## Project structure

- `config/` Django project settings, ASGI, URLs
- `apps/accounts/` custom user model and profile endpoints
- `apps/vendors/` vendor management
- `apps/menu/` menu item management
- `apps/orders/` order APIs and order lifecycle
- `apps/dispatch/` mock robot dispatch records
- `apps/notifications/` WebSocket consumer for live order updates

## Setup for Supabase

1. Create a virtual environment.
2. Install dependencies:
   `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your Supabase database host and password.
4. Start Redis locally:
   `docker compose up -d`
5. Run migrations against Supabase PostgreSQL:
   `python manage.py makemigrations`
   `python manage.py migrate`
6. Create an admin user:
   `python manage.py createsuperuser`
7. Start the server:
   `python manage.py runserver`

## Supabase values to copy

Get these from your Supabase project database settings:

- `POSTGRES_HOST`
- `POSTGRES_PASSWORD`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`

Keep `POSTGRES_SSLMODE=require` for Supabase.

If Supabase gives you a pooler URL like:
`postgresql://postgres.project-ref:[YOUR-PASSWORD]@aws-1-us-west-2.pooler.supabase.com:6543/postgres`

then use:

```env
POSTGRES_DB=postgres
POSTGRES_USER=postgres.project-ref
POSTGRES_PASSWORD=your-supabase-db-password
POSTGRES_HOST=aws-1-us-west-2.pooler.supabase.com
POSTGRES_PORT=6543
POSTGRES_SSLMODE=require
```

## Key API routes

- `GET /api/health/`
- `POST /api/auth/token/`
- `GET /api/accounts/me/`
- `GET|POST /api/vendors/`
- `GET|POST /api/menu/items/`
- `GET|POST /api/orders/`
- `POST /api/orders/<id>/status/`
- `GET /api/dispatch/`

## WebSocket

- `ws://localhost:8000/ws/orders/`

## Suggested next step

Connect the existing admin, user, and vendor frontends to these APIs and then add role-based permissions and a real robot provider adapter.
