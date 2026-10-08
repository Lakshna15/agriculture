# Farm2Local

A location-aware agriculture marketplace connecting customers with nearby farms, fresh
products and farm experiences.

The project is built in phases. So far it has a running frontend, backend and PostGIS
database, account registration and login with role-based access, and farm profiles that
farmers create and manage. Products, search and reservations are added in later phases.

## Technology Stack

| Layer          | Technology                                             |
| -------------- | ------------------------------------------------------ |
| Frontend       | React, TypeScript, Vite, Tailwind CSS, React Router    |
| Backend        | Python, FastAPI, SQLAlchemy 2, Pydantic, Alembic       |
| Database       | PostgreSQL 17 with PostGIS 3.5                         |
| Authentication | Argon2id password hashes, JWT access tokens            |
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

The application starts with the example values, but `JWT_SECRET_KEY` signs every access
token, so replace the placeholder with a random value of your own:

```bash
docker compose run --rm --no-deps backend python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste the output into `.env` as `JWT_SECRET_KEY`. `.env` is ignored by version control.

### 2. Start the database and backend

```bash
docker compose up -d --build --wait
```

This starts two services:

| Service   | Address                 | Notes                                        |
| --------- | ----------------------- | -------------------------------------------- |
| `db`      | `localhost:5433`        | PostgreSQL + PostGIS, data in a named volume |
| `backend` | `http://localhost:8000` | FastAPI with auto-reload on code changes     |

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

| Route       | Page               | Access                         |
| ----------- | ------------------ | ------------------------------ |
| `/`         | Homepage           | Everyone                       |
| `/login`    | Login              | Signed-out visitors            |
| `/register` | Register           | Signed-out visitors            |
| `/customer` | Customer dashboard | Customers (placeholder content) |
| `/farmer`   | Farmer dashboard   | Farmers: create, view and edit their farm |

The dev server proxies `/api` to the backend, so the browser talks to a single origin and
the API does not enable cross-origin requests. Set `API_PROXY_TARGET` before `npm run dev`
if the backend is not on `http://localhost:8000`.

### Stopping

```bash
docker compose down
```

Database data is kept in the `farm2local_postgres_data` volume and survives restarts.
Add `-v` to remove the volume and start from an empty database.

## Environment Variables

Defined in `.env` (see `.env.example`).

| Variable                      | Purpose                                            | Example                |
| ----------------------------- | -------------------------------------------------- | ---------------------- |
| `POSTGRES_USER`               | Database user                                      | `farm2local`           |
| `POSTGRES_PASSWORD`           | Database password                                  | `change_me_local_only` |
| `POSTGRES_DB`                 | Database name                                      | `farm2local`           |
| `POSTGRES_HOST`               | Database host when the backend runs outside Docker | `localhost`            |
| `POSTGRES_PORT`               | Host port published for the database               | `5433`                 |
| `BACKEND_PORT`                | Host port published for the backend                | `8000`                 |
| `JWT_SECRET_KEY`              | Key that signs access tokens, 32 characters or more | a random value        |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Lifetime of an access token                        | `60`                   |

Inside the Compose network the backend always connects to `db:5432`. `POSTGRES_HOST` and
`POSTGRES_PORT` only matter when the backend is run directly on the host. The backend
refuses to start without a `JWT_SECRET_KEY` of sufficient length.

## Authentication

| Method | Path                 | Purpose                                         | Success |
| ------ | -------------------- | ----------------------------------------------- | ------- |
| `POST` | `/api/auth/register` | Create a `CUSTOMER` or `FARMER` account         | `201`   |
| `POST` | `/api/auth/login`    | Exchange email and password for an access token | `200`   |
| `GET`  | `/api/auth/me`       | Return the user that owns the bearer token      | `200`   |

Failures use consistent status codes: `401` for a missing, invalid or expired token and for
wrong credentials, `403` for a role that is not allowed, `409` for an email that is already
registered, and `422` for input that fails validation.

How it works:

- **Roles.** There are three roles: `CUSTOMER`, `FARMER` and `ADMIN`. Public registration
  accepts only the first two. A request for `ADMIN` is rejected by validation.
- **Passwords.** Stored only as Argon2id hashes and never returned by any endpoint. They
  must be 8 to 128 characters long.
- **Emails.** Trimmed and lowercased before they are stored, so sign-in is not
  case-sensitive. The database enforces both uniqueness and the normalized form.
- **Tokens.** HS256 JWTs that carry only the user id and an expiry. Each request loads the
  user from the database, so a deleted account or a changed role takes effect immediately.
- **Authorization.** `get_current_user` and `require_role(...)` in
  `backend/app/dependencies/auth.py` are the dependencies protected routes use. The
  frontend also hides pages by role, but that is a convenience and not a security boundary.
- **Login responses.** An unknown email and a wrong password produce the same response, and
  both run a full password-hash verification, so neither the body nor the response time
  reveals which emails are registered.

The frontend keeps the access token in `localStorage` so a session survives a page reload,
and validates it against `/api/auth/me` on load. This is simple and common for
single-page applications, at the cost that script running in the page could read the
token; the short token lifetime limits that exposure.

## Farms

| Method | Path                   | Purpose                             | Who may call it         | Success |
| ------ | ---------------------- | ----------------------------------- | ----------------------- | ------- |
| `POST` | `/api/farms`           | Create the signed-in farmer's farm  | Farmers                 | `201`   |
| `GET`  | `/api/farms/me`        | Return the signed-in farmer's farm  | Farmers                 | `200`   |
| `GET`  | `/api/farms/{farm_id}` | Return a farm profile               | Anyone, no token needed | `200`   |
| `PUT`  | `/api/farms/{farm_id}` | Replace a farm profile              | The farmer who owns it  | `200`   |

Rules the API enforces:

- **One farm per farmer.** A second `POST` returns `409`. A unique constraint on
  `farms.owner_id` backs the rule, so two simultaneous requests cannot both succeed.
- **Ownership.** The owner is always the signed-in user. An `owner_id` in a request body is
  ignored, and editing another farmer's farm returns `403`.
- **Roles.** Customers and administrators receive `403` from the farmer-only endpoints.
- **Coordinates.** Latitude must be between -90 and 90 and longitude between -180 and 180,
  in WGS 84 decimal degrees. The request schema and a database check both enforce the range.
  Coordinates are entered by hand; there is no geocoding.
- **Addresses.** Farms are in the United States: `state` is a two-letter state code and
  `zip_code` is a five-digit ZIP or ZIP+4.
- **Missing farm.** `GET /api/farms/me` returns `404` until the farmer creates a farm. The
  farmer dashboard treats that as its empty state.

Farm profiles are public because they are marketplace listings. A request with an invalid
or expired token to any protected endpoint returns `401`, and the frontend then ends the
session and returns to the login page.

## Testing

Backend tests (the stack must be running):

```bash
docker compose exec backend pytest
```

The suite creates its own `<POSTGRES_DB>_test` database, builds it by running the real
migrations, and wraps every test in a transaction that is rolled back. It never reads or
writes the development database.

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
│   │   ├── dependencies/   Request dependencies: current user, role checks
│   │   ├── models/         SQLAlchemy models
│   │   ├── routers/        API routes
│   │   ├── schemas/        Pydantic request and response models
│   │   └── services/       Business logic: accounts, tokens, farms
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── api/            Typed calls to the backend
│       ├── auth/           Authentication state and route guards
│       ├── components/     Shared layout, form fields and farm components
│       ├── data/           Static reference data such as US states
│       ├── pages/          One component per route
│       ├── test/           Test setup and helpers
│       ├── routes.tsx      Route table
│       └── main.tsx        Application entry point
├── docker-compose.yml
├── .env.example
└── README.md
```

## Significant Dependencies

| Dependency          | Why it is used                                              |
| ------------------- | ----------------------------------------------------------- |
| `psycopg` 3         | PostgreSQL driver used by SQLAlchemy                        |
| `pydantic-settings` | Typed configuration loaded from environment variables       |
| `argon2-cffi`       | Argon2id password hashing                                   |
| `PyJWT`             | Signing and verifying access tokens                         |
| `email-validator`   | Email address validation behind Pydantic's `EmailStr`       |
| `httpx2`            | HTTP client required by FastAPI's test client (dev only)    |
| `@tailwindcss/vite` | Tailwind CSS integration for Vite                           |
| `jsdom`             | Browser environment for component tests (dev only)          |
