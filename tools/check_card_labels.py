#!/usr/bin/env python3
"""Every thumbnail card in public/ must carry the cyan rubric and the date.

List rows (pv-row) must not. Thumbnail cards must not include an excerpt, and
the shared .lmeta rule must keep the rubric line on one line.
"""
import json
import re
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
        kind = next((c for c in ("leadstory", "pv-lead", "lcard", "vcard", "pv-row", "pv-guide", "shc", "mini", "card") if c in classes), None)
        node = {"tag": tag, "class": classes, "kind": kind, "kids": []}
        if self.current is None and kind == "lcard" and "empty" in classes:
            kind = None
        if kind and self.current is None:
            above = kind in ("leadstory", "pv-lead") or (kind == "card" and "lead" in classes)
            self.current = {"kind": kind, "depth": len(self.stack), "has_img": False, "lmeta": False,
                            "lname": False, "ago": False, "excerpt": False, "listrow": kind == "pv-row",
                            "above": above, "step": 0, "img_at": None, "lmeta_at": None}
        if self.current is not None:
            thumb = tag == "img" or bool(classes & {"lim", "vim", "im", "th", "leadim", "shv", "pv-th"})
            if thumb:
                self.current["has_img"] = True
                self.current["step"] += 1
                if self.current["img_at"] is None:
                    self.current["img_at"] = self.current["step"]
            if "lmeta" in classes:
                self.current["lmeta"] = True
                self.current["step"] += 1
                if self.current["lmeta_at"] is None:
                    self.current["lmeta_at"] = self.current["step"]
            if "lname" in classes:
                self.current["lname"] = True
            if tag == "time" and "ago" in classes:
                self.current["ago"] = True
            if tag == "p" or "mdesc" in classes:
                self.current["excerpt"] = True
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


LMETA_RULE = re.compile(r"\.lmeta\{[^}]*\}")


def main():
    missing = []
    counts = {}
    files = 0
    nowrap_bad = 0
    for path in PUBLIC.rglob("*.html"):
        files += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        rule = LMETA_RULE.search(text)
        if rule is None or "nowrap" not in rule.group(0):
            nowrap_bad += 1
            missing.append(f"{path.relative_to(PUBLIC).as_posix()} lmeta nowrap missing")
        kind = page_type(path)
        parser = Cards()
        try:
            parser.feed(text)
        except Exception as exc:
            print(f"PARSE {path}: {exc}")
            return 1
        for card in parser.cards:
            rel = path.relative_to(PUBLIC).as_posix()
            if card["listrow"]:
                if card["lmeta"]:
                    bucket = counts.setdefault(kind, {"cards": 0, "missing": 0})
                    bucket["missing"] += 1
                    missing.append(f"{rel} pv-row leaked lmeta")
                continue
            if not card["has_img"]:
                continue
            ordered = card["img_at"] is not None and card["lmeta_at"] is not None and (
                card["lmeta_at"] < card["img_at"] if card["above"] else card["img_at"] < card["lmeta_at"])
            ok = card["lmeta"] and card["lname"] and card["ago"] and ordered and not card["excerpt"]
            bucket = counts.setdefault(kind, {"cards": 0, "missing": 0})
            bucket["cards"] += 1
            if not ok:
                bucket["missing"] += 1
                missing.append(
                    f"{rel} {card['kind']} lmeta={card['lmeta']} lname={card['lname']} ago={card['ago']} "
                    f"excerpt={card['excerpt']} above={card['above']} img_at={card['img_at']} lmeta_at={card['lmeta_at']}")
    print(f"files {files}")
    print(f"lmeta nowrap missing {nowrap_bad}")
    total = sum(v["cards"] for v in counts.values())
    bad = sum(v["missing"] for v in counts.values()) + nowrap_bad
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
