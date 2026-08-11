# webhook

A minimal webhook receiver service (Node.js + Express) with HMAC-SHA256
signature verification. It is small on purpose: it doubles as a reference
service for exercising the Cloud Agent development environment end to end.

## Requirements

- Node.js >= 20 (the repo is developed against Node 22)

## Install

```bash
npm install
```

## Run

```bash
npm start        # start the server on PORT (default 3000)
npm run dev      # start with --watch for local development
```

Configuration via environment variables:

- `PORT` — port to listen on (default `3000`)
- `WEBHOOK_SECRET` — shared secret used to verify signatures (default `dev-secret`)

## Endpoints

| Method | Path       | Description                                             |
| ------ | ---------- | ------------------------------------------------------- |
| GET    | `/health`  | Liveness probe; reports the number of received events.  |
| POST   | `/webhook` | Receives an event. Requires a valid signature header.   |
| GET    | `/events`  | Lists the events received so far (in-memory).           |

### Signature scheme

Requests to `/webhook` must include an `x-webhook-signature` header of the form
`sha256=<hex>`, where `<hex>` is the HMAC-SHA256 of the raw request body keyed by
`WEBHOOK_SECRET`. Unsigned or incorrectly signed requests are rejected with
`401`.

## Send a test webhook

With the server running:

```bash
npm start &
node scripts/send-webhook.js order.created
curl -s http://localhost:3000/events | jq
```

## Test and lint

```bash
npm test         # node:test + supertest
npm run lint     # eslint
```
