# Farm2Local

A location-aware agriculture marketplace connecting customers with nearby farms, fresh
products and farm experiences.

The project is built in phases. So far it has account registration and login with
role-based access, farm profiles, product listings with tracked inventory, a location
search that finds products on farms within a chosen radius, product reservations, and
bookable farm experiences. Grow-On-Demand is added in a later phase.

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

| Route                    | Page                                        | Access              |
| ------------------------ | ------------------------------------------- | ------------------- |
| `/`                      | Homepage                                    | Everyone            |
| `/login`                 | Login                                       | Signed-out visitors |
| `/register`              | Register                                    | Signed-out visitors |
| `/customer`              | Search nearby products and reserve them     | Customers           |
| `/customer/experiences`  | Find and reserve farm experiences           | Customers           |
| `/customer/reservations` | View and cancel reservations                | Customers           |
| `/farmer`                | Farm profile and products                   | Farmers             |
| `/farmer/events`         | Create and view farm events                 | Farmers             |
| `/farmer/reservations`   | View reservations and update their status   | Farmers             |

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
| `MARKETPLACE_TIMEZONE`        | Time zone that decides what "today" is             | `America/New_York`     |

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

## Products and Inventory

| Method  | Path                                   | Purpose                                 | Who may call it          | Success |
| ------- | -------------------------------------- | --------------------------------------- | ------------------------ | ------- |
| `POST`  | `/api/products`                        | Add a product to the farmer's farm      | Farmers with a farm      | `201`   |
| `GET`   | `/api/products/mine`                   | List the farmer's products              | Farmers                  | `200`   |
| `PUT`   | `/api/products/{product_id}`           | Replace a product's details             | The farmer who owns it   | `200`   |
| `PATCH` | `/api/products/{product_id}/inventory` | Set the quantity available              | The farmer who owns it   | `200`   |
| `GET`   | `/api/products/search`                 | Find products near a location           | Anyone, no token needed  | `200`   |

Rules the API enforces:

- **Ownership.** A product always belongs to the signed-in farmer's farm. A `farm_id` in a
  request body is ignored, and managing another farm's product returns `403`. A farmer
  with no farm yet receives `409` when adding a product.
- **Price.** Stored as `NUMERIC(10, 2)` and sent as text such as `"4.50"`, so no amount
  ever passes through a binary float. It must be more than zero with at most two decimal
  places.
- **Quantity.** A whole number of the product's unit, zero or more.
- **Inventory history.** Stock is written in exactly one place,
  `change_product_quantity` in `backend/app/services/products.py`, which adds an
  `inventory_history` row (`previous_quantity`, `new_quantity`, `changed_at`) in the same
  transaction. A new product's opening stock is its first history entry. `PUT` cannot
  change stock: a `quantity_available` in its body is ignored, so the history cannot be
  bypassed. Setting the quantity it already has records nothing.
- **Deactivation.** `PUT` with `"active": false` hides a product from customers while
  keeping it in the farmer's list.
- **Categories and units.** `category` is one of `VEGETABLES`, `FRUITS`, `EGGS`, `DAIRY`,
  `MEAT`, `HERBS`, `SEASONAL`, `OTHER`. `unit` is one of `LB`, `OZ`, `EACH`, `DOZEN`,
  `BUNCH`, `PINT`, `QUART`, `GALLON`.

## Geographic Search

`GET /api/products/search` returns active products on farms within a radius of a point.

| Parameter        | Required | Default    | Meaning                                                    |
| ---------------- | -------- | ---------- | ---------------------------------------------------------- |
| `latitude`       | yes      |            | Search point, -90 to 90                                    |
| `longitude`      | yes      |            | Search point, -180 to 180                                  |
| `radius_miles`   | no       | `25`       | Greater than 0, at most 500                                |
| `query`          | no       |            | Text matched anywhere in the product name, ignoring case   |
| `category`       | no       |            | One product category                                       |
| `available_only` | no       | `true`     | Only products in stock and inside their availability dates |
| `sort`           | no       | `distance` | `distance`, `price` or `harvest_date`                      |
| `limit`          | no       | `50`       | 1 to 100 results                                           |

Each result contains `product`, `farm`, `distance_miles`, `price`, `quantity_available`
and `harvest_date`.

How distance is calculated:

- `farms.location` is a PostGIS `geography(Point, 4326)` column that PostgreSQL generates
  from `latitude` and `longitude`. It is a stored generated column, so the two can never
  disagree and editing a farm's coordinates moves it in search with no extra code.
- The radius filter is `ST_DWithin(farms.location, search_point, radius_in_meters)`, which
  uses the GiST index on `farms.location`.
- `distance_miles` comes from `ST_Distance` on the same column, which measures along the
  Earth's surface in meters, converted to miles and rounded to two decimals.
- All of this runs inside PostgreSQL. The application never loads farms to measure
  distance itself.

Sorting: `distance` is nearest first, `price` is cheapest first, and `harvest_date` is most
recently harvested first with undated products last. Ties are broken by distance.

Inactive products are never returned. With `available_only=false`, products that are out
of stock or outside their availability dates are included as well. Dates are compared with
today's date in `MARKETPLACE_TIMEZONE`, not with the server's UTC clock.

Search coordinates are query parameters because the search is a `GET`. The customer
dashboard rounds a browser-provided location to three decimal places, about 100 meters,
before sending it.

## Reservations

Customers reserve products for pickup and reserve places at farm events. Both kinds of
reservation share one status lifecycle.

### Product reservations

| Method  | Path                                    | Purpose                                 | Who may call it                 | Success |
| ------- | --------------------------------------- | --------------------------------------- | ------------------------------- | ------- |
| `POST`  | `/api/reservations`                     | Reserve a quantity of a product         | Customers                       | `201`   |
| `GET`   | `/api/reservations/mine`                | The customer's own reservations         | Customers                       | `200`   |
| `GET`   | `/api/reservations/farm`                | Reservations for the farmer's products  | Farmers                         | `200`   |
| `PATCH` | `/api/reservations/{id}/status`         | Change a reservation's status           | Its customer or its farm's owner | `200`  |

A reservation needs `product_id`, `quantity`, `pickup_date` and `pickup_time`.

- **Quantity.** Must be greater than zero and no more than the stock available. Asking for
  more returns `409` with the amount that is left.
- **Stock is deducted when the reservation is made**, not when it is confirmed or
  collected. The deduction goes through the same function as every other stock change,
  so it appears in `inventory_history`.
- **Stock can never go negative.** The product row is locked (`SELECT ... FOR UPDATE`)
  before the stock is checked, so two customers reserving at the same moment are handled
  one after the other and the second sees the reduced stock. The stock change, its history
  row and the reservation are committed in one transaction. A database check constraint
  on `quantity_available` is a final backstop.
- **What can be reserved.** Only active products that are inside their availability dates.
  The pickup date cannot be in the past.

### Cancellation and inventory

- **Cancelling returns the reserved quantity to stock**, whether the customer or the farm
  cancels and whether the reservation was `PENDING` or `CONFIRMED`. The return is recorded
  in `inventory_history` like any other stock change.
- **Completing changes nothing.** The stock was already deducted when the reservation was
  made, so marking it `COMPLETED` leaves stock alone.
- **Stock is returned exactly once.** The reservation row is locked before its status is
  read, so two simultaneous cancellations cannot both return it, and a second cancellation
  of an already cancelled reservation is rejected with `409`.
- **A cancelled reservation cannot be reopened.** To reserve again, the customer makes a
  new reservation against whatever stock is then available.

### Farm events

| Method | Path                 | Purpose                                   | Who may call it         | Success |
| ------ | -------------------- | ----------------------------------------- | ----------------------- | ------- |
| `POST` | `/api/events`        | Create an event on the farmer's farm      | Farmers with a farm     | `201`   |
| `GET`  | `/api/events/mine`   | The farm's events with places remaining   | Farmers                 | `200`   |
| `GET`  | `/api/events/search` | Upcoming events near a location           | Anyone, no token needed | `200`   |

An event has a `title`, `description`, `event_type`, `event_date`, `start_time`, `end_time`,
a `price` per person (zero for a free event) and a `capacity`. `event_type` is one of
`STRAWBERRY_PICKING`, `APPLE_PICKING`, `PUMPKIN_PICKING`, `VEGETABLE_PICKING`, `FARM_TOUR`,
`OTHER`. The end time must be after the start time and the date cannot be in the past.

The search takes `latitude`, `longitude`, `radius_miles` and an optional `event_type`, uses
the same PostGIS distance as the product search, and returns events from today onward,
soonest first, each with its farm, `distance_miles` and `spots_remaining`.

### Event reservations

| Method  | Path                                     | Purpose                              | Who may call it                  | Success |
| ------- | ---------------------------------------- | ------------------------------------ | -------------------------------- | ------- |
| `POST`  | `/api/event-reservations`                | Reserve places for a party           | Customers                        | `201`   |
| `GET`   | `/api/event-reservations/mine`           | The customer's own reservations      | Customers                        | `200`   |
| `GET`   | `/api/event-reservations/farm`           | Reservations for the farm's events   | Farmers                          | `200`   |
| `PATCH` | `/api/event-reservations/{id}/status`    | Change a reservation's status        | Its customer or its farm's owner | `200`   |

- **Capacity is never exceeded.** The places taken are the sum of `party_size` over every
  reservation that is not cancelled. The event row is locked before that sum is read, so
  bookings for one event are processed one at a time. A party larger than what is left
  receives `409` with the number of places remaining.
- **Cancelling frees the places** immediately, because places are counted from the
  reservations themselves.
- Events that have already taken place cannot be reserved.

### Status changes

| From        | To          | Farm | Customer |
| ----------- | ----------- | ---- | -------- |
| `PENDING`   | `CONFIRMED` | yes  | no       |
| `PENDING`   | `CANCELLED` | yes  | yes      |
| `CONFIRMED` | `COMPLETED` | yes  | no       |
| `CONFIRMED` | `CANCELLED` | yes  | yes      |

`COMPLETED` and `CANCELLED` are final. A status the caller may never set returns `403`. A
change that is not allowed from the current status returns `409`. Anyone who is neither the
reservation's customer nor the owner of its farm receives `403`.

A farmer sees the customer's name on a reservation and nothing else about them.

## Testing

Backend tests (the stack must be running):

```bash
docker compose exec backend pytest
```

The suite creates its own `<POSTGRES_DB>_test` database, builds it by running the real
migrations, and wraps every test in a transaction that is rolled back. It never reads or
writes the development database.

`tests/test_reservation_concurrency.py` is the exception to the rollback rule. It starts
two threads on separate database connections to reserve the last units of a product, the
last places at an event, and to cancel one reservation from both sides at once. Those
tests commit for real, because row locks only act between transactions, and they empty
the test tables afterwards.

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
│   │   └── services/       Business logic: accounts, farms, products, search, reservations, events
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── api/            Typed calls to the backend
│       ├── auth/           Authentication state and route guards
│       ├── components/     Shared layout and form fields; farm, product, search, event and reservation components
│       ├── data/           Static reference data: US states, product and event options
│       ├── lib/            Formatting, coordinates, data loading and reservation helpers
│       ├── pages/          Dashboard frames, with customer/ and farmer/ pages inside them
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
| `geoalchemy2`       | PostGIS column types and spatial functions for SQLAlchemy   |
| `pydantic-settings` | Typed configuration loaded from environment variables       |
| `argon2-cffi`       | Argon2id password hashing                                   |
| `PyJWT`             | Signing and verifying access tokens                         |
| `email-validator`   | Email address validation behind Pydantic's `EmailStr`       |
| `tzdata`            | Time zone database for platforms without one, such as Windows |
| `httpx2`            | HTTP client required by FastAPI's test client (dev only)    |
| `@tailwindcss/vite` | Tailwind CSS integration for Vite                           |
| `jsdom`             | Browser environment for component tests (dev only)          |
