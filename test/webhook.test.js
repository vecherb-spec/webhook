import test from "node:test";
import assert from "node:assert/strict";
import request from "supertest";
import { createApp, signPayload } from "../src/app.js";

const SECRET = "test-secret";

test("GET /health reports ok", async () => {
  const app = createApp({ secret: SECRET });
  const res = await request(app).get("/health");
  assert.equal(res.status, 200);
  assert.equal(res.body.status, "ok");
  assert.equal(res.body.received, 0);
});

test("POST /webhook rejects a missing signature", async () => {
  const app = createApp({ secret: SECRET });
  const res = await request(app).post("/webhook").send({ type: "ping" });
  assert.equal(res.status, 401);
  assert.equal(res.body.error, "missing signature");
});

test("POST /webhook rejects an invalid signature", async () => {
  const app = createApp({ secret: SECRET });
  const res = await request(app)
    .post("/webhook")
    .set("x-webhook-signature", "sha256=deadbeef")
    .send({ type: "ping" });
  assert.equal(res.status, 401);
  assert.equal(res.body.error, "invalid signature");
});

test("POST /webhook accepts a correctly signed payload and stores it", async () => {
  const app = createApp({ secret: SECRET });
  const body = { type: "order.created", data: { id: 42 } };
  const payload = JSON.stringify(body);
  const signature = signPayload(Buffer.from(payload), SECRET);

  const res = await request(app)
    .post("/webhook")
    .set("Content-Type", "application/json")
    .set("x-webhook-signature", signature)
    .send(payload);

  assert.equal(res.status, 202);
  assert.equal(res.body.ok, true);
  assert.ok(res.body.id);

  const events = await request(app).get("/events");
  assert.equal(events.body.count, 1);
  assert.equal(events.body.events[0].type, "order.created");
  assert.deepEqual(events.body.events[0].payload, body);
});
