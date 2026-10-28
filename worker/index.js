// TrendingTesla worker: serves the static site from ./public, a tiny like counter at /api/likes
// and the contact form at /api/contact (sent by email to the address in the CONTACT_TO variable).
// Likes are stored in one SQLite-backed Durable Object (no accounts, no personal data).
import { DurableObject } from "cloudflare:workers";
import { EmailMessage } from "cloudflare:email";

const SLUG = /^[a-z0-9-]{3,120}$/;

export class Likes extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.sql = ctx.storage.sql;
    this.sql.exec("CREATE TABLE IF NOT EXISTS likes (slug TEXT PRIMARY KEY, n INTEGER NOT NULL DEFAULT 0)");
    this.sql.exec("CREATE TABLE IF NOT EXISTS contact_rate (k TEXT PRIMARY KEY, n INTEGER NOT NULL, t INTEGER NOT NULL)");
  }
  get(slugs) {
    const out = {};
    for (const s of slugs) {
      const r = this.sql.exec("SELECT n FROM likes WHERE slug = ?", s).toArray();
      out[s] = r.length ? r[0].n : 0;
    }
    return out;
  }
  change(slug, d) {
    this.sql.exec("INSERT INTO likes (slug, n) VALUES (?, 0) ON CONFLICT(slug) DO NOTHING", slug);
    this.sql.exec("UPDATE likes SET n = MAX(0, n + ?) WHERE slug = ?", d, slug);
    return this.get([slug])[slug];
  }
  // allow `max` contact messages per key (hashed IP) per hour, and 50 per hour in total
  allow(key, max) {
    const hour = Math.floor(Date.now() / 3600000);
    this.sql.exec("DELETE FROM contact_rate WHERE t < ?", hour);
    for (const [k, m] of [[key, max], ["*", 50]]) {
      const r = this.sql.exec("SELECT n FROM contact_rate WHERE k = ?", k).toArray();
      if (r.length && r[0].n >= m) return false;
    }
    for (const k of [key, "*"]) {
      this.sql.exec("INSERT INTO contact_rate (k, n, t) VALUES (?, 1, ?) ON CONFLICT(k) DO UPDATE SET n = n + 1", k, hour);
    }
    // wipe the hashed IPs automatically shortly after the hour ends
    this.ctx.storage.setAlarm((hour + 1) * 3600000 + 60000);
    return true;
  }
  alarm() {
    this.sql.exec("DELETE FROM contact_rate WHERE t < ?", Math.floor(Date.now() / 3600000));
  }
}

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });

const clean = (s, n) => String(s || "").replace(/\r/g, "").slice(0, n).trim();
const oneLine = (s) => s.replace(/[\n\t]+/g, " ");
const b64 = (s) => btoa(String.fromCharCode(...new TextEncoder().encode(s)));
const b64lines = (s) => b64(s).replace(/.{76}/g, "$&\r\n");

async function contact(request, env) {
  if (request.method !== "POST") return json({ error: "method" }, 405);
  const origin = request.headers.get("origin") || "";
  if (origin && !/^https:\/\/(www\.)?trendingtesla\.com$/.test(origin)) return json({ error: "origin" }, 403);
  let body = {};
  try { body = await request.json(); } catch (e) {}
  if (body.website) return json({ ok: true }); // honeypot: bots fill it, people never see it
  const name = oneLine(clean(body.name, 100));
  const email = oneLine(clean(body.email, 200));
  const message = clean(body.message, 5000);
  const page = oneLine(clean(body.page, 200));
  const lang = body.lang === "nl" ? "nl" : "en";
  if (!name || !message || !/^[^\s@<>"]+@[^\s@<>"]+\.[^\s@<>"]+$/.test(email)) return json({ error: "invalid" }, 400);
  if (!env.MAIL || !env.CONTACT_TO) return json({ error: "not configured" }, 503);
  const ip = request.headers.get("cf-connecting-ip") || "?";
  const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(ip + "tt"))))
    .slice(0, 8).map((b) => b.toString(16).padStart(2, "0")).join("");
  const stub = env.LIKES.get(env.LIKES.idFromName("all"));
  if (!(await stub.allow(hash, 5))) return json({ error: "too many" }, 429);

  const from = "contact@trendingtesla.com";
  const subject = `Contactformulier: ${name}`;
  const text = `Naam: ${name}\nE-mail: ${email}\nTaal: ${lang}\nPagina: ${page}\n\n${message}\n`;
  const id = `<${crypto.randomUUID()}@trendingtesla.com>`;
  const raw = [
    `From: TrendingTesla contact <${from}>`,
    `To: <${env.CONTACT_TO}>`,
    `Reply-To: ${b64name(name)} <${email}>`,
    `Subject: =?UTF-8?B?${b64(subject)}?=`,
    `Message-ID: ${id}`,
    `Date: ${new Date().toUTCString()}`,
    "MIME-Version: 1.0",
    "Content-Type: text/plain; charset=UTF-8",
    "Content-Transfer-Encoding: base64",
    "",
    b64lines(text),
  ].join("\r\n");
  try {
    await env.MAIL.send(new EmailMessage(from, env.CONTACT_TO, raw));
  } catch (e) {
    return json({ error: "send failed", detail: String(e).slice(0, 200) }, 502);
  }
  return json({ ok: true });
}

function b64name(n) {
  return `=?UTF-8?B?${b64(n)}?=`;
}

export default {
  async fetch(request, env) {
    const u = new URL(request.url);
    if (u.pathname === "/api/contact") return contact(request, env);
    if (u.pathname === "/api/likes") {
      const stub = env.LIKES.get(env.LIKES.idFromName("all"));
      if (request.method === "GET") {
        const slugs = (u.searchParams.get("s") || "").split(",").filter((s) => SLUG.test(s)).slice(0, 60);
        return json(await stub.get(slugs));
      }
      if (request.method === "POST") {
        let body = {};
        try { body = await request.json(); } catch (e) {}
        const slug = String(body.slug || "");
        const d = body.d === -1 ? -1 : 1;
        if (!SLUG.test(slug)) return json({ error: "bad slug" }, 400);
        return json({ slug, n: await stub.change(slug, d) });
      }
      return json({ error: "method" }, 405);
    }
    return env.ASSETS.fetch(request);
  },
};
