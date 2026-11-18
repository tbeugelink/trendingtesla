#!/usr/bin/env python3
"""Every thumbnail card in public/ must carry the cyan rubric and the date."""
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class Cards(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.cards = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        classes = set((ad.get("class") or "").split())
        kind = next((c for c in ("leadstory", "lcard", "vcard", "pv-row", "pv-guide", "shc", "mini", "card") if c in classes), None)
        node = {"tag": tag, "class": classes, "kind": kind, "kids": []}
        if self.current is None and kind:
            if kind == "pv-row" and "hasth" not in classes:
                kind = None
            elif kind == "lcard" and "empty" in classes:
                kind = None
        if kind and self.current is None:
            self.current = {"kind": kind, "depth": len(self.stack), "has_img": False, "lmeta": False, "lname": False, "ago": False}
        if self.current is not None:
            if tag == "img" or "lim" in classes or "vim" in classes or "im" in classes or "th" in classes or "leadim" in classes or "shv" in classes or "pv-th" in classes:
                if tag == "img" or classes & {"lim", "vim", "im", "th", "leadim", "shv", "pv-th"}:
                    self.current["has_img"] = True
            if "lmeta" in classes:
                self.current["lmeta"] = True
            if "lname" in classes:
                self.current["lname"] = True
            if tag == "time" and "ago" in classes:
                self.current["ago"] = True
        self.stack.append(node)
        if tag in VOID:
            self.stack.pop()
            if self.current and len(self.stack) == self.current["depth"]:
                self.cards.append(self.current)
                self.current = None

    def handle_endtag(self, tag):
        if not self.stack:
            return
        node = self.stack.pop()
        if self.current and len(self.stack) == self.current["depth"]:
            self.cards.append(self.current)
            self.current = None


def page_type(path: Path) -> str:
    rel = path.relative_to(PUBLIC).as_posix()
    parts = rel.split("/")
    if rel in ("index.html", "nl/index.html"):
        return "homepage"
    if "shorts" in parts:
        return "shorts"
    if "category" in parts and "news" in parts:
        return "news"
    if "guides" in parts or "gidsen" in parts:
        return "guides"
    if "agi" in parts:
        return "agi"
    if "briefing" in parts:
        return "briefing"
    if "preview" in parts:
        return "preview"
    hubs = {"tesla", "tesla-energy", "spacex", "starlink", "spacexsi", "neuralink", "boring",
            "ai", "cars", "semi", "robotaxi", "fsd", "optimus", "megapacks", "solar",
            "charging-network", "home-charging", "starship", "starship-vehicle", "falcons",
            "ai-compute", "datacenters", "chips", "ecosystem", "ecosysteem"}
    if parts[0] == "nl":
        parts = parts[1:]
    if parts and parts[0] in hubs and rel.endswith("index.html") and len(parts) <= 2:
        return "hub"
    if rel.endswith("index.html"):
        return "article"
    return "other"


def main():
    missing = []
    counts = {}
    files = 0
    for path in PUBLIC.rglob("*.html"):
        files += 1
        kind = page_type(path)
        parser = Cards()
        try:
            parser.feed(path.read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:
            print(f"PARSE {path}: {exc}")
            return 1
        for card in parser.cards:
            if not card["has_img"]:
                continue
            ok = card["lmeta"] and card["lname"] and card["ago"]
            bucket = counts.setdefault(kind, {"cards": 0, "missing": 0})
            bucket["cards"] += 1
            if not ok:
                bucket["missing"] += 1
                rel = path.relative_to(PUBLIC).as_posix()
                missing.append(f"{rel} {card['kind']} lmeta={card['lmeta']} lname={card['lname']} ago={card['ago']}")
    print(f"files {files}")
    total = sum(v["cards"] for v in counts.values())
    bad = sum(v["missing"] for v in counts.values())
    for kind in sorted(counts):
        row = counts[kind]
        print(f"{kind}\t{row['cards']}\tmissing {row['missing']}")
    print(f"total cards {total} missing {bad}")
    for line in missing[:40]:
        print("MISSING", line)
    # Search index is not HTML. Every record needs a rubric.
    for name in ("search-en.json", "search-nl.json"):
        rows = json.loads((PUBLIC / name).read_text(encoding="utf-8"))
        nok = sum(1 for row in rows if not str(row.get("k") or "").strip() or not row.get("ts"))
        print(f"{name}\t{len(rows)}\tmissing {nok}")
        bad += nok
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
