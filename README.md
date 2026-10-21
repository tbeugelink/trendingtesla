# trendingtesla.com

Static, bilingual (EN at `/`, NL at `/nl/`) Tesla news site.

- Articles: `content/articles/YYYY-MM-DD-slug.json` (format described at the top of `build.py`)
- Build: `python3 build.py` → writes the full site to `public/`
- Deploy: push to `main`; Cloudflare deploys `public/` automatically (see `wrangler.jsonc`)

`public/` is generated — never edit it by hand, always rebuild.
