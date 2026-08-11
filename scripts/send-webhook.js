import { signPayload } from "../src/app.js";

const url = process.env.WEBHOOK_URL || "http://localhost:3000/webhook";
const secret = process.env.WEBHOOK_SECRET || "dev-secret";

const body = JSON.stringify({
  type: process.argv[2] || "demo.event",
  data: { message: "hello from send-webhook.js", ts: Date.now() },
});

const signature = signPayload(Buffer.from(body), secret);

const res = await fetch(url, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "x-webhook-signature": signature,
  },
  body,
});

console.log(`POST ${url} -> ${res.status}`);
console.log(await res.text());
