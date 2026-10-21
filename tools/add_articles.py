"""Helper: write article dicts from a batch module to content/articles/ as JSON.

Usage: python3 tools/add_articles.py tools/batch_x.py
The batch module defines ARTICLES = [ {...}, ... ] in the format described in build.py.
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(path):
    spec = importlib.util.spec_from_file_location("batch", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = ROOT / "content" / "articles"
    for a in mod.ARTICLES:
        f = out / f"{a['date']}-{a['slug']}.json"
        f.write_text(json.dumps(a, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        words = len(a["en"]["body"].split()), len(a["nl"]["body"].split())
        print(f"wrote {f.name}  (words en/nl: {words[0]}/{words[1]})")


if __name__ == "__main__":
    main(sys.argv[1])
