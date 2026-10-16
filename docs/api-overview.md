# API Overview

The backend is a FastAPI application. Every endpoint below is under `/api` except the health
check. Interactive documentation generated from the code is served at
`http://localhost:8000/docs`, and the OpenAPI schema at `http://localhost:8000/openapi.json`.

## Conventions

**Authentication.** Protected endpoints take an access token in the `Authorization: Bearer
<token>` header. A token comes from `POST /api/auth/login`. It is an HS256 JWT holding only
the user id and an expiry (60 minutes by default). Each request loads the user again, so a
changed role or a deleted account takes effect immediately.

**Roles.** `CUSTOMER` and `FARMER` can register. `ADMIN` exists in the model but cannot be
chosen at registration. Role and ownership checks happen in the backend; the frontend
hiding a page is a convenience, never the security boundary.

**Errors.** Every error is JSON with a `detail` field.

| Status | Meaning |
| ------ | ------- |
| `401` | No token, an invalid or expired token, or wrong login credentials |
| `403` | Signed in, but the role or ownership does not allow it |
| `404` | The resource does not exist (or, where noted, is someone else's) |
| `409` | A conflict with current state: not enough stock, already joined, wrong status |
| `413` | The request body is over 1 MiB |
| `422` | Validation failed; `detail` lists each problem's `type`, `loc` and `msg` |
| `429` | Too many failed logins; see `Retry-After` |
| `500` | An unexpected error; the response says nothing about the cause |
| `503` | Only from `/health`: the database cannot be reached |

A `422` body never repeats the submitted value, so a rejected password is not sent back.

**Money and quantities.** Prices are decimals sent as strings with two places, such as
`"4.50"`, so no amount passes through a binary float. Quantities are whole numbers of the
product's unit.

**Dates.** Calendar dates are ISO `YYYY-MM-DD`, times `HH:MM:SS`, timestamps ISO 8601 in UTC.
"Today" for pickup dates, event dates and availability means today in
`MARKETPLACE_TIMEZONE`, not on the server's UTC clock.

**Every response** carries `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: no-referrer` and `Cache-Control: no-store`. No CORS headers are sent; the
frontend calls the API from the same origin through the dev server's proxy.

## Endpoints

48 operations in total. "Public" means no token is needed.

### Health and accounts

| Method | Path | Purpose | Access | Success |
| ------ | ---- | ------- | ------ | ------- |
| `GET` | `/health` | Checks the API can query the database | Public | `200` (`503` if not) |
| `POST` | `/api/auth/register` | Create a `CUSTOMER` or `FARMER` account | Public | `201` |
| `POST` | `/api/auth/login` | Exchange email and password for a token | Public | `200` |
| `GET` | `/api/auth/me` | The user who owns the token | Signed in | `200` |

- Passwords are 8 to 128 characters, stored only as Argon2id hashes and never returned.
- Emails are trimmed and lowercased, so sign-in ignores case; the database enforces the
  normalized form and uniqueness (`409` for a repeat).
- An unknown email and a wrong password give the same `401`, and both run a full hash
  check, so neither the body nor the timing reveals which emails exist.
- After 5 failed logins for one email in 15 minutes, or 50 from one client address,
  logins get `429` with `Retry-After`. The check runs before the password, so a correct
  guess during the lockout is refused too.

### Farms

| Method | Path | Purpose | Access | Success |
| ------ | ---- | ------- | ------ | ------- |
| `POST` | `/api/farms` | Create the signed-in farmer's farm | Farmers | `201` |
| `GET` | `/api/farms/me` | The signed-in farmer's farm | Farmers | `200` |
| `GET` | `/api/farms/{farm_id}` | A farm's public profile | Public | `200` |
| `PUT` | `/api/farms/{farm_id}` | Replace a farm profile | The farm's owner | `200` |

- One farm per farmer: a second `POST` is `409`, backed by a unique constraint.
- The owner is always the signed-in user; an `owner_id` in the body is ignored.
- Coordinates are WGS 84 decimal degrees, checked by the schema and the database. `state`
  is a two-letter US state code, `zip_code` a five-digit ZIP or ZIP+4.
- `GET /api/farms/me` is `404` until the farm exists; the farmer dashboard treats that as
  its empty state.

### Products and inventory

| Method | Path | Purpose | Access | Success |
| ------ | ---- | ------- | ------ | ------- |
| `POST` | `/api/products` | Add a product to the farmer's farm | Farmers with a farm | `201` |
| `GET` | `/api/products/mine` | The farmer's products, hidden ones included | Farmers | `200` |
| `PUT` | `/api/products/{product_id}` | Replace a product's details | The farm's owner | `200` |
| `PATCH` | `/api/products/{product_id}/inventory` | Set the quantity available | The farm's owner | `200` |
| `GET` | `/api/products/search` | Products on farms near a point | Public | `200` |

- A product belongs to the signed-in farmer's farm; a `farm_id` in the body is ignored. A
  farmer without a farm gets `409` when adding one.
- `category` is one of `VEGETABLES`, `FRUITS`, `EGGS`, `DAIRY`, `MEAT`, `HERBS`, `SEASONAL`,
  `OTHER`; `unit` one of `LB`, `OZ`, `EACH`, `DOZEN`, `BUNCH`, `PINT`, `QUART`, `GALLON`.
- Stock changes only through `PATCH .../inventory` (and reservations), and every change
  writes an `inventory_history` row in the same transaction. `PUT` ignores
  `quantity_available`, so the history cannot be bypassed.
- `PUT` with `"active": false` hides a product from customers but keeps it in the
  farmer's list.

**Search parameters** for `GET /api/products/search`:

| Parameter | Default | Meaning |
| --------- | ------- | ------- |
| `latitude`, `longitude` | required | The search point |
| `radius_miles` | `25` | More than 0, at most 500 |
| `query` | | Text anywhere in the product name, ignoring case |
| `category` | | One product category |
| `available_only` | `true` | Only products in stock and inside their availability dates today |
| `sort` | `distance` | `distance` (nearest), `price` (cheapest) or `harvest_date` (most recent, undated last) |
| `limit` | `50` | 1 to 100 |

Each result has `product`, `farm`, `distance_miles`, `price`, `quantity_available` and
`harvest_date`. Inactive products never appear. See [Geographic search](architecture.md#geographic-search).

### Reservations and farm experiences

| Method | Path | Purpose | Access | Success |
| ------ | ---- | ------- | ------ | ------- |
| `POST` | `/api/reservations` | Reserve a quantity of a product | Customers | `201` |
| `GET` | `/api/reservations/mine` | The customer's product reservations | Customers | `200` |
| `GET` | `/api/reservations/farm` | Reservations for the farmer's products | Farmers | `200` |
| `PATCH` | `/api/reservations/{reservation_id}/status` | Change a reservation's status | Its customer or the farm's owner | `200` |
| `POST` | `/api/events` | Create an event on the farmer's farm | Farmers with a farm | `201` |
| `GET` | `/api/events/mine` | The farm's events with places remaining | Farmers | `200` |
| `GET` | `/api/events/search` | Upcoming events near a point | Public | `200` |
| `POST` | `/api/event-reservations` | Book places for a party | Customers | `201` |
| `GET` | `/api/event-reservations/mine` | The customer's bookings | Customers | `200` |
| `GET` | `/api/event-reservations/farm` | Bookings for the farm's events | Farmers | `200` |
| `PATCH` | `/api/event-reservations/{reservation_id}/status` | Change a booking's status | Its customer or the farm's owner | `200` |

- A product reservation takes `product_id`, `quantity`, `pickup_date` and `pickup_time`.
  Stock is deducted when it is made, under a row lock on the product, so stock never goes
  negative even when customers reserve at the same moment. Asking for more than is left
  is `409` with the amount remaining.
- Cancelling returns the reserved quantity to stock exactly once; completing changes
  nothing, because the stock was already deducted.
- An event has a `title`, `description`, `event_type` (`STRAWBERRY_PICKING`,
  `APPLE_PICKING`, `PUMPKIN_PICKING`, `VEGETABLE_PICKING`, `FARM_TOUR`, `OTHER`),
  `event_date`, `start_time`, `end_time`, a per-person `price` (zero is free) and a
  `capacity`. Bookings lock the event, so capacity is never exceeded; a party too large
  for what is left is `409`.
- Event search takes the same `latitude`, `longitude`, `radius_miles` and `limit` as the
  product search, plus an optional `event_type`, and returns events from today on.

**Status changes** are shared by both kinds of reservation:

| From | To | Farm | Customer |
| ---- | -- | ---- | -------- |
| `PENDING` | `CONFIRMED` | yes | no |
| `PENDING` | `CANCELLED` | yes | yes |
| `CONFIRMED` | `COMPLETED` | yes | no |
| `CONFIRMED` | `CANCELLED` | yes | yes |

`COMPLETED` and `CANCELLED` are final. A status the caller may never set is `403`; a change
not allowed from the current status is `409`. A farmer sees a customer's name on a
reservation and nothing else about them.

### Grow-On-Demand

| Method | Path | Purpose | Access | Success |
| ------ | ---- | ------- | ------ | ------- |
| `POST` | `/api/crop-requests` | Ask nearby farmers for a crop | Customers | `201` |
| `GET` | `/api/crop-requests/mine` | The customer's requests | Customers | `200` |
| `POST` | `/api/crop-requests/{request_id}/cancel` | Withdraw an open request | Its customer | `200` |
| `GET` | `/api/demand` | Combined demand near the farmer's farm | Farmers with a farm | `200` |
| `POST` | `/api/grow-offers` | Offer to grow a crop | Farmers with a farm | `201` |
| `GET` | `/api/grow-offers/mine` | The farm's offers with progress | Farmers | `200` |
| `GET` | `/api/grow-offers/search` | Joinable offers near a point | Public | `200` |
| `GET` | `/api/grow-offers/{offer_id}` | One offer with its farm and progress | Public | `200` |
| `POST` | `/api/grow-offers/{offer_id}/cancel` | Call off an open or confirmed offer | The farm's owner | `200` |
| `POST` | `/api/grow-offers/{offer_id}/complete` | Close an offer whose crop was ready | The farm's owner | `200` |
| `GET` | `/api/grow-offers/{offer_id}/updates` | The crop journey, oldest first | Public | `200` |
| `POST` | `/api/grow-offers/{offer_id}/updates` | Post a crop update | The farm's owner | `201` |
| `POST` | `/api/crop-commitments` | Commit to part of an offer | Customers | `201` |
| `GET` | `/api/crop-commitments/mine` | The customer's commitments | Customers | `200` |
| `POST` | `/api/crop-polls` | Ask nearby customers what to grow | Farmers with a farm | `201` |
| `GET` | `/api/crop-polls/mine` | The farm's polls with vote counts | Farmers | `200` |
| `POST` | `/api/crop-polls/{poll_id}/close` | Stop accepting votes | The farm's owner | `200` |
| `GET` | `/api/crop-polls/search` | Open polls on farms near a point | Public | `200` |
| `POST` | `/api/crop-votes` | Vote for one option | Customers | `201` |
| `GET` | `/api/crop-votes/mine` | The options the customer chose | Customers | `200` |

The rules behind these endpoints, including what farmers can and cannot see, are in
[grow-on-demand.md](grow-on-demand.md). Grow-offer search takes the nearby-search
parameters plus an optional `crop`.

### Notifications

| Method | Path | Purpose | Access | Success |
| ------ | ---- | ------- | ------ | ------- |
| `GET` | `/api/notifications` | The 50 most recent, newest first | Signed in | `200` |
| `GET` | `/api/notifications/unread-count` | How many are unread | Signed in | `200` |
| `POST` | `/api/notifications/{notification_id}/read` | Mark one as read | Its recipient | `200` |
| `POST` | `/api/notifications/read-all` | Mark all as read | Signed in | `204` |

Every notification endpoint works on the caller's own notifications; another user's
notification id is `404`.

## Analytics side effects

Some endpoints record an `application_events` row for the analytics pipeline. Actions
(reservations, bookings, crop requests, grow offers, commitments and stock changes) record
it in the same transaction, so a refused request records nothing. Product search and the
public farm profile record anonymous browsing events; a failure there is logged and never
affects the response. Responses are unchanged either way. See
[data-pipeline.md](data-pipeline.md).
