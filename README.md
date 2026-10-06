# Farm2Local

A location-aware agriculture marketplace connecting customers with nearby farms, fresh
products and farm experiences.

The project is built in phases. The current state is the foundation: a running frontend,
backend and PostGIS database with migrations and tests wired up. Marketplace features are
added in later phases.

## Technology Stack

| Layer          | Technology                                             |
| -------------- | ------------------------------------------------------ |
| Frontend       | React, TypeScript, Vite, Tailwind CSS, React Router    |
| Backend        | Python, FastAPI, SQLAlchemy 2, Pydantic, Alembic       |
| Database       | PostgreSQL 17 with PostGIS 3.5                         |
| Infrastructure | Docker Compose                                         |
| Testing        | Pytest, Vitest, React Testing Library                  |

## Prerequisites

- Docker Desktop (or Docker Engine with the Compose plugin)
- Node.js 22 or newer

Python does not need to be installed on the host. The backend runs in a container.

## Local Setup

All commands are run from the repository root unless stated otherwise.

### 1. Create the environment file

```bash
cp .env.example .env
```

The defaults work as they are. Change `POSTGRES_PASSWORD` if you want a different local
password. `.env` is ignored by version control.

### 2. Start the database and backend

```bash
docker compose up -d --build --wait
```

This starts two services:

| Service   | Address                 | Notes                                    |
| --------- | ----------------------- | ---------------------------------------- |
| `db`      | `localhost:5433`        | PostgreSQL + PostGIS, data in a named volume |
| `backend` | `http://localhost:8000` | FastAPI with auto-reload on code changes |

### 3. Apply database migrations

```bash
docker compose exec backend alembic upgrade head
```

### 4. Check the backend

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{ "status": "ok" }
```

The endpoint runs a query against PostgreSQL, so a `200` confirms the API can reach the
database. It returns `503` when the database is unavailable. Interactive API documentation
is served at `http://localhost:8000/docs`.

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

| Route       | Page                             |
| ----------- | -------------------------------- |
| `/`         | Homepage                         |
| `/login`    | Login (placeholder)              |
| `/register` | Register (placeholder)           |
| `/customer` | Customer dashboard (placeholder) |
| `/farmer`   | Farmer dashboard (placeholder)   |

### Stopping

```bash
docker compose down
```

Database data is kept in the `farm2local_postgres_data` volume and survives restarts.
Add `-v` to remove the volume and start from an empty database.

## Environment Variables

Defined in `.env` (see `.env.example`).

| Variable            | Purpose                                           | Example                |
| ------------------- | ------------------------------------------------- | ---------------------- |
| `POSTGRES_USER`     | Database user                                     | `farm2local`           |
| `POSTGRES_PASSWORD` | Database password                                 | `change_me_local_only` |
| `POSTGRES_DB`       | Database name                                     | `farm2local`           |
| `POSTGRES_HOST`     | Database host when the backend runs outside Docker | `localhost`           |
| `POSTGRES_PORT`     | Host port published for the database              | `5433`                 |
| `BACKEND_PORT`      | Host port published for the backend               | `8000`                 |

Inside the Compose network the backend always connects to `db:5432`. `POSTGRES_HOST` and
`POSTGRES_PORT` only matter when the backend is run directly on the host.

## Testing

Backend tests (the stack must be running):

```bash
docker compose exec backend pytest
```

Frontend tests and type-checked production build:

```bash
cd frontend
npm test
npm run build
```

## Database Migrations

Schema changes are managed with Alembic. The database URL is built from the same
environment variables the application uses, so there is no connection string in
`alembic.ini`.

```bash
# Apply all migrations
docker compose exec backend alembic upgrade head

# Create a migration from model changes
docker compose exec backend alembic revision --autogenerate -m "describe the change"

# Show the current revision
docker compose exec backend alembic current
```

## Running the Backend Without Docker

The backend can also run directly on the host with Python 3.11 or newer. The database
still comes from Docker Compose.

```bash
docker compose up -d --wait db
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

On Windows machines with Smart App Control or a similar application-control policy
enabled, unsigned native extensions shipped by SQLAlchemy and psycopg can be blocked from
loading. Running the backend in its container, as described above, avoids this.

## Project Structure

```
farm2local/
├── backend/
│   ├── alembic/            Migration environment and versions
│   ├── app/
│   │   ├── main.py         FastAPI application
│   │   ├── config.py       Settings loaded from the environment
│   │   ├── database.py     Engine, session factory and session dependency
│   │   ├── models/         SQLAlchemy models
│   │   ├── routers/        API routes
│   │   └── schemas/        Pydantic request and response models
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/     Shared layout and UI components
│       ├── pages/          One component per route
│       ├── routes.tsx      Route table
│       └── main.tsx        Application entry point
├── docker-compose.yml
├── .env.example
└── README.md
```

## Significant Dependencies

| Dependency          | Why it is used                                             |
| ------------------- | ---------------------------------------------------------- |
| `psycopg` 3         | PostgreSQL driver used by SQLAlchemy                       |
| `pydantic-settings` | Typed configuration loaded from environment variables      |
| `httpx2`            | HTTP client required by FastAPI's test client (dev only)   |
| `@tailwindcss/vite` | Tailwind CSS integration for Vite                          |
| `jsdom`             | Browser environment for component tests (dev only)         |
