// TrendingTesla worker: serves the static site from ./public, a tiny like counter at /api/likes
// and the contact form at /api/contact (sent by email to the address in the CONTACT_TO variable).
// Likes are stored in one SQLite-backed Durable Object (no accounts, no personal data).
import { DurableObject } from "cloudflare:workers";
import { EmailMessage } from "cloudflare:email";
import { REDIRECTS } from "./redirects.js";

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
  new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json", "cache-control": "no-store", "x-robots-tag": "noindex" } });

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

// Original scheme. Cloudflare terminates TLS, so request.url is often https even when
// the browser asked for http. CF-Visitor still has the scheme the visitor used.
function originalScheme(request, url) {
  const raw = request.headers.get("CF-Visitor");
  if (raw) {
    try {
      const scheme = JSON.parse(raw).scheme;
      if (scheme === "http" || scheme === "https") return scheme;
    } catch (e) {}
  }
  return url.protocol === "http:" ? "http" : "https";
}

// Pretty URLs are directories. Files (a dot in the last segment) and /api/ stay as they are.
function needsSlash(pathname) {
  if (pathname === "/" || pathname.endsWith("/") || pathname.startsWith("/api/")) return false;
  return !/\.[A-Za-z0-9]{1,8}$/.test(pathname);
}

function withSlash(pathname) {
  return needsSlash(pathname) ? pathname + "/" : pathname;
}

// /about/index.html and /index.html are the same document as the directory URL.
function canonicalPath(pathname) {
  let p = pathname;
  if (p === "/index.html" || p.endsWith("/index.html")) {
    p = p.slice(0, -"index.html".length);
    if (!p) p = "/";
  }
  return withSlash(p);
}

function redirect301(url) {
  const headers = { Location: url, "Cache-Control": "public, max-age=3600" };
  return new Response(null, { status: 301, headers });
}

function gone() {
  return new Response("Gone", { status: 410, headers: { "content-type": "text/plain", "x-robots-tag": "noindex" } });
}

// Numbered archive pages that no longer exist. /archive/ and /nl/archive/ stay.
function archiveHome(pathname) {
  const m = pathname.match(/^(\/nl)?\/archive\/(\d+)\/$/);
  if (!m) return null;
  return (m[1] || "") + "/archive/";
}

// Old WordPress URLs. Real feeds are /feed.xml and /nl/feed.xml, not /feed/.
function isWordpressGone(pathname) {
  const p = pathname.toLowerCase();
  if (p === "/xmlrpc.php" || p === "/wp-login.php") return true;
  if (p === "/wp-includes" || p.startsWith("/wp-includes/")) return true;
  if (p === "/wp-content" || p.startsWith("/wp-content/")) return true;
  if (p === "/wp-admin" || p.startsWith("/wp-admin/")) return true;
  if (p === "/feed" || p === "/feed/" || p === "/comments/feed" || p === "/comments/feed/") return true;
  if (/\/feed\/$/.test(p)) return true;
  return false;
}

// Static assets answer a missing trailing slash with 307. Crawlers should see 301.
function slashTo301(response, request) {
  if (request.method !== "GET" && request.method !== "HEAD") return response;
  if (response.status !== 307 && response.status !== 308) return response;
  const loc = response.headers.get("Location");
  if (!loc) return response;
  let target;
  try { target = new URL(loc, request.url); } catch (e) { return response; }
  const from = new URL(request.url);
  const bare = (p) => (p.length > 1 && p.endsWith("/") ? p.slice(0, -1) : p);
  if (target.origin === from.origin && bare(target.pathname) === bare(from.pathname) && target.pathname !== from.pathname) {
    return redirect301(target.toString());
  }
  return response;
}

export default {
  async fetch(request, env) {
    const u = new URL(request.url);
    const host = u.hostname.toLowerCase();
    const onSite = host === "trendingtesla.com" || host === "www.trendingtesla.com";
    const scheme = originalScheme(request, u);
    const path = canonicalPath(u.pathname);
    // Removed articles: 301 to the closest kept article, or to a model/category page.
    // Map lives in worker/redirects.js (same pairs as content/redirects.json).
    const moved = REDIRECTS[path];
    const getLike = request.method === "GET" || request.method === "HEAD";
    // old WordPress addresses from the domain's previous site (?p=1, ?feed=rss2, ?s=..., ?author=1) showed the
    // home page and were reported as duplicates by Search Console: tell crawlers they are gone for good
    const wpGone = ["p", "s", "feed", "author", "cat", "replytocom", "page_id", "attachment_id", "m", "tag"]
      .some((k) => u.searchParams.has(k));
    if (getLike && isWordpressGone(path)) return gone();
    if (getLike && wpGone && (path === "/" || path === "/nl/")) return gone();
    if (getLike) {
      // www, http, a missing slash, /index.html and a stray query fold into one 301.
      // /api/ keeps its query. Everything else drops it so ?q= and ?utm_ do not become extra URLs.
      const origin = onSite ? "https://trendingtesla.com" : u.origin;
      const destPath = moved || path;
      const dest = new URL(destPath, origin);
      dest.search = destPath.startsWith("/api/") ? u.search : "";
      const visitor = onSite ? `${scheme}://${host}${u.pathname}${u.search}` : `${u.origin}${u.pathname}${u.search}`;
      if (visitor !== dest.toString()) return redirect301(dest.toString());
    } else if (onSite && (host !== "trendingtesla.com" || scheme !== "https")) {
      const dest = new URL(u.pathname + u.search, "https://trendingtesla.com");
      return redirect301(dest.toString());
    }
    if (u.pathname === "/api/contact") return contact(request, env);
    if (u.pathname === "/api/likes") {
      const stub = env.LIKES.get(env.LIKES.idFromName("all"));
      // Googlebot sometimes sends HEAD. A 405 on that path showed up as an "other 4xx".
      if (request.method === "GET" || request.method === "HEAD") {
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
    const assets = slashTo301(await env.ASSETS.fetch(request), request);
    const archiveTo = archiveHome(path);
    if (getLike && archiveTo && assets.status === 404) {
      const origin = onSite ? "https://trendingtesla.com" : u.origin;
      return redirect301(origin + archiveTo);
    }
    return withCache(u.pathname, assets);
  },
};

// Hashed and static files (the /img/opt/ name is a content hash; fonts and other
// images, plus any CSS or JS file) can sit in the browser for a year.
// HTML, feeds, sitemaps and the search index stay revalidated so a publish shows up.
const LONG_CACHE = "public, max-age=31536000, immutable";
const SHORT_CACHE = "public, max-age=0, must-revalidate";
const LONG_FILE = /\.(?:avif|webp|jpe?g|png|gif|svg|ico|woff2?|ttf|otf|css|js|mjs)$/i;
const FEED_NOINDEX = new Set(["/feed.xml", "/nl/feed.xml", "/news-sitemap.xml"]);

function cacheControl(pathname) {
  return LONG_FILE.test(pathname) ? LONG_CACHE : SHORT_CACHE;
}

function withCache(pathname, response) {
  const headers = new Headers(response.headers);
  headers.set("Cache-Control", cacheControl(pathname));
  if (FEED_NOINDEX.has(pathname)) headers.set("X-Robots-Tag", "noindex");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}
