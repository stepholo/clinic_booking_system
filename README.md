# CareConnect Clinic Booking System

Clinic Booking System is a Django + Django REST Framework backend for managing clinic users, doctors, patients, schedules, and appointments.

## Design Decisions

### 1. Domain split by app
The codebase is split into focused Django apps:
- `users`: authentication and user accounts
- `doctors`: doctor profiles and related endpoints
- `patients`: patient records
- `schedules`: doctor schedule definitions and slot logic
- `bookings`: appointment booking flow

This keeps each area modular and easier to evolve independently.

### 2. Multi-database routing
The project uses a router (`clinic_platform/clinic_platform/router.py`) to isolate write/read traffic by app:
- `user_db`: users, doctors, patients, schedules, auth/session/admin data
- `booking_db`: appointments/bookings

Why:
- clearer data ownership boundaries
- easier operational scaling later
- reduced risk of accidental cross-domain writes

### 3. API-first docs and discoverability
OpenAPI docs are generated with drf-spectacular and exposed as:
- `/api/schema/`
- `/api/docs/` (Swagger UI)
- `/api/redoc/` (ReDoc)

The root route `/` serves a human-friendly API home page with quick links and platform status.

### 4. Pragmatic caching strategy
Caching supports two modes:
- Redis cache when enabled/configured
- LocMem fallback for local/dev environments

This keeps local setup simple while still supporting production-grade cache behavior.

## Running Locally

### Prerequisites
- Python 3.12+
- PostgreSQL 15+ (recommended)
- Git

### 1. Clone and enter project
```bash
git clone <your-repo-url>
cd "Clinic Booking System"/clinic_platform
```

### 2. Create and activate virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install --upgrade pip
pip install -r requirements-dev.txt
```

### 4. Configure environment variables
Create a `.env` file in `clinic_platform/` (same folder as `manage.py`).

Example:
```env
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# User DB (primary service domain)
USER_DB_NAME=clinic_user
USER_DB_USER=postgres
USER_DB_PASSWORD=postgres
USER_DB_HOST=127.0.0.1
USER_DB_PORT=5432

# Booking DB (appointments domain)
BOOKING_DB_NAME=clinic_booking
BOOKING_DB_USER=postgres
BOOKING_DB_PASSWORD=postgres
BOOKING_DB_HOST=127.0.0.1
BOOKING_DB_PORT=5432

# Optional API behavior tuning
JWT_ACCESS_EXPIRATION_DAYS=1
JWT_REFRESH_EXPIRATION_DAYS=7
API_PAGE_SIZE=20
CACHE_TTL_SECONDS=60

# Redis optional
USE_REDIS_CACHE=False
REDIS_URL=
```

Note: The settings also support `DATABASE_URL`, and common Postgres env vars (`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`) for container platforms.

### 5. Create databases
Create both databases in PostgreSQL:
- `clinic_user`
- `clinic_booking`

You can use `psql` or your preferred Postgres client.

### 6. Run migrations
```bash
python manage.py migrate --database user_db
python manage.py migrate --database booking_db
```

### 7. Create an admin user
```bash
python manage.py createsuperuser --database=user_db
```

### 8. Start development server
```bash
python manage.py runserver
```

Useful local URLs:
- Home: `http://127.0.0.1:8000/`
- Swagger: `http://127.0.0.1:8000/api/docs/`
- ReDoc: `http://127.0.0.1:8000/api/redoc/`
- Admin: `http://127.0.0.1:8000/admin/`

## Testing

Run tests with pytest:
```bash
pytest clinic_platform/tests -q
```

Pytest configuration is in `clinic_platform/pytest.ini`.

## CI/CD - Brief Overview

CI/CD is configured in `.circleci/config.yml` with two jobs:

### 1. `test` job
- Uses Python 3.12 + Postgres 15 service containers
- Installs dependencies from `requirements-dev.txt`
- Waits for Postgres readiness
- Creates a second CI database for bookings
- Runs migrations for both aliases:
	- `user_db`
	- `booking_db`
- Executes pytest suites

### 2. `deploy` job
- Runs only after successful tests
- Runs only on `main`
- Installs Railway CLI
- Deploys with `railway up` using project/service/env identifiers

Required CircleCI environment variables for deploy:
- `RAILWAY_API_TOKEN`
- `RAILWAY_APP_PROJECT_ID`
- `RAILWAY_APP_SERVICE_ID`
- optional: `RAILWAY_ENVIRONMENT_NAME` (defaults to `production`)

## Deployment Information

- Public URL of deployed application:
	- https://clinicbookingsystem-production-6435.up.railway.app/
- Branch that triggers deployment:
	- `main`
- How deployment is triggered:
	- A push to `main` triggers the CircleCI workflow.
	- CircleCI runs the `test` job first.
	- If tests pass, CircleCI runs the `deploy` job, which executes `railway up` against the configured Railway project/environment/service.

### Brief Pipeline Description

The pipeline validates code quality and deployment safety by running automated tests before release. It provisions Python and Postgres in CI, installs dependencies, waits for database readiness, runs migrations on both aliases (`user_db` and `booking_db`), and executes pytest suites. Only after these checks succeed on `main` does the deploy stage publish the latest version to Railway.

## Deployment Notes (Railway)

- Ensure the app service has database variables available (`DATABASE_PUBLIC_URL` or equivalent PG/USER_DB/BOOKING_DB vars).
- If `createsuperuser` fails with a local socket error, it usually means DB env vars are missing in the running service shell.
- Run migrations on both database aliases after each schema-affecting deploy.

## Project Structure (Top-Level)

```text
Clinic Booking System/
	README.md
	clinic_platform/
		manage.py
		clinic_platform/
			settings.py
			router.py
			urls.py
		users/
		doctors/
		patients/
		schedules/
		bookings/
		templates/
		tests/
```

## AI Reflection

1. What did you use AI for across the four sections?
    - System Design
        - Get trade-offs between system designs that could be used
        - Draw system design and data flow diagrams
        - Understand the edge cases of the assignment scenerio

    - API Implementations
        - Code Generation
        - Debugging 
        - Testing the API endpoints
        - Ensuring all edge cases are met
        - Ensuring there is no race conditions and double booking
        - Ensure Code documentation and type hints meets the global standard
    
    - Deployment & CI/CD
        - Configuring the database for local and production environment
        - Assisted in setting up CI/CD in CircleCI
        - Assisted in setting up Railway hosting

2. Give one example where an AI suggestion improved your work. What did you prompt it with?
    ```
        After hosting the API, I realised that there was nothing showing for the home url path of my endpoint. I come up with a prompt to suggest creating a home page for our API.
        Here below is the prompt.
         "I have successfully deployed and accessed it, 
          the home url path has nothing to show, what can we include there? I was suggesting maybe the available apis, admin, swagger, schema, and redoc.
          Can you work on the background coloring, include animations and ensure that every url fits within its box.
          can you make it slightly darker,
          Can you redesign the whole of it so that on one end, maybe right side, we can scroll through the redoc, the payload and expected response.
          when the links are clicked on the home page, they should open in another tab
          The name CareConnect Clinic Booking API should be centre aligned
          On the swagger, can we add a section showing how to run and access the apis"
    ```

3. Give one example where AI output was wrong or incomplete and how you caught it.

    - During code generation for bookings/models.py, the AI used foregin key on the user's      instead of decoupling them. I run the code with the mistake out of curiousity of what would go wrong. I used the error log I got to debug the issue.

4. Name two decisions you made without AI. Why did you trust your own judgment there?\

    - The framework to use - Since this was an MVP, I needed a framework that would enable data consistency and since I new Django was the best choice becouse of inbuild ORM
    - Using Railway to host the API - I needed a hosting platform that would enable persistence after deployment without disruption of the provided compute resources.