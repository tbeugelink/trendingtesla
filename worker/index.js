// TrendingTesla worker: serves the static site from ./public and a tiny like counter at /api/likes.
// Likes are stored in one SQLite-backed Durable Object (no accounts, no personal data).
import { DurableObject } from "cloudflare:workers";

const SLUG = /^[a-z0-9-]{3,120}$/;

export class Likes extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.sql = ctx.storage.sql;
    this.sql.exec("CREATE TABLE IF NOT EXISTS likes (slug TEXT PRIMARY KEY, n INTEGER NOT NULL DEFAULT 0)");
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
}

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });

export default {
  async fetch(request, env) {
    const u = new URL(request.url);
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
