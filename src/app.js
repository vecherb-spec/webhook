import crypto from "node:crypto";
import express from "express";

const DEFAULT_SECRET = "dev-secret";

/**
 * Timing-safe comparison of two hex-encoded signatures.
 */
function signaturesMatch(expected, provided) {
  if (typeof provided !== "string" || provided.length !== expected.length) {
    return false;
  }
  const a = Buffer.from(expected, "utf8");
  const b = Buffer.from(provided, "utf8");
  if (a.length !== b.length) {
    return false;
  }
  return crypto.timingSafeEqual(a, b);
}

/**
 * Compute the `sha256=<hex>` signature for a raw request body.
 */
export function signPayload(rawBody, secret) {
  const digest = crypto
    .createHmac("sha256", secret)
    .update(rawBody)
    .digest("hex");
  return `sha256=${digest}`;
}

/**
 * Build the Express application.
 *
 * The event store is intentionally in-memory: this service is a reference
 * webhook receiver used to exercise the development environment end to end.
 */
export function createApp({ secret = process.env.WEBHOOK_SECRET || DEFAULT_SECRET } = {}) {
  const app = express();
  const events = [];

  app.use(
    express.json({
      verify: (req, _res, buf) => {
        req.rawBody = buf;
      },
    })
  );

  app.get("/health", (_req, res) => {
    res.json({ status: "ok", received: events.length });
  });

  app.post("/webhook", (req, res) => {
    const signature = req.get("x-webhook-signature");
    if (!signature) {
      return res.status(401).json({ error: "missing signature" });
    }

    const expected = signPayload(req.rawBody ?? Buffer.alloc(0), secret);
    if (!signaturesMatch(expected, signature)) {
      return res.status(401).json({ error: "invalid signature" });
    }

    const event = {
      id: crypto.randomUUID(),
      receivedAt: new Date().toISOString(),
      type: req.body?.type ?? "unknown",
      payload: req.body ?? {},
    };
    events.push(event);

    return res.status(202).json({ ok: true, id: event.id });
  });

  app.get("/events", (_req, res) => {
    res.json({ count: events.length, events });
  });

  return app;
}

export default createApp;
