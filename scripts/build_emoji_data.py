"""Build ``snapmock/resources/emoji/emoji.json`` from the Unicode emoji data and CLDR.

Numbered Steps, Stamps, and Emoji implementation decision 2 (option A): the picker's
categories, names, keywords, and skin-tone capability come from one bundled JSON file
generated here from two published sources, with no runtime dependency:

- ``emoji-test.txt`` from the Unicode emoji data release (groups, subgroups, names, every
  sequence with its qualification status);
- the English CLDR annotations from the ``cldr-json`` distribution (search keywords).

Run from the repository root::

    uv run python scripts/build_emoji_data.py --emoji-version 16.0 --cldr-version 48.2.0

The script downloads both sources unless ``--source-dir`` names a directory that already
holds ``emoji-test.txt``, ``annotations.json``, and ``annotationsDerived.json``. It writes
``emoji.json`` and refreshes the README's version line. Only fully qualified entries are
kept; skin-tone variants are folded into their base emoji as a capability flag, so a
sequence with a Fitzpatrick modifier never appears as an entry of its own.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "snapmock" / "resources" / "emoji"
OUT_FILE = OUT_DIR / "emoji.json"

EMOJI_TEST_URL = "https://unicode.org/Public/emoji/{version}/emoji-test.txt"
CLDR_BASE = "https://raw.githubusercontent.com/unicode-org/cldr-json/{tag}/cldr-json/"
ANNOTATIONS_URL = CLDR_BASE + "cldr-annotations-full/annotations/en/annotations.json"
DERIVED_URL = CLDR_BASE + "cldr-annotations-derived-full/annotationsDerived/en/annotations.json"

SKIN_TONE_MODIFIERS = {0x1F3FB, 0x1F3FC, 0x1F3FD, 0x1F3FE, 0x1F3FF}
"""The Fitzpatrick modifiers, light to dark (Unicode TR51)."""
GROUPS = (
    "Smileys & Emotion",
    "People & Body",
    "Animals & Nature",
    "Food & Drink",
    "Travel & Places",
    "Activities",
    "Objects",
    "Symbols",
    "Flags",
)
"""The nine picker categories of PRD 4.2, in order; the file's Component group is left out."""
VARIATION_SELECTOR = "️"
ZERO_WIDTH_JOINER = "‍"

_LINE = re.compile(
    r"^(?P<codes>[0-9A-F ]+?)\s*;\s*(?P<status>[a-z-]+)\s*#\s*(?P<char>\S+)\s+"
    r"E(?P<ver>[\d.]+)\s+(?P<name>.+)$"
)


def _fetch(url: str, target: Path) -> None:
    print(f"fetching {url}")
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310
        target.write_bytes(response.read())


def _strip_tones(chars: str) -> str:
    return "".join(c for c in chars if ord(c) not in SKIN_TONE_MODIFIERS)


def build(source_dir: Path, emoji_version: str, cldr_version: str) -> dict[str, object]:
    test_lines = (source_dir / "emoji-test.txt").read_text(encoding="utf-8").splitlines()
    annotations = json.loads((source_dir / "annotations.json").read_text(encoding="utf-8"))
    derived = json.loads((source_dir / "annotationsDerived.json").read_text(encoding="utf-8"))
    keywords: dict[str, list[str]] = {}
    for data in (annotations["annotations"], derived["annotationsDerived"]):
        for char, entry in data["annotations"].items():
            words = entry.get("default", [])
            if words:
                keywords.setdefault(char, [])
                for w in words:
                    if w not in keywords[char]:
                        keywords[char].append(w)

    group = subgroup = ""
    entries: dict[str, dict[str, object]] = {}
    order: list[str] = []
    toned: dict[str, list[int]] = {}
    """Base sequence to the indices of its zero-width-joiner components that take a tone."""
    for line in test_lines:
        if line.startswith("# group:"):
            group = line.split(":", 1)[1].strip()
            continue
        if line.startswith("# subgroup:"):
            subgroup = line.split(":", 1)[1].strip()
            continue
        if not line or line.startswith("#"):
            continue
        match = _LINE.match(line)
        if match is None or match.group("status") != "fully-qualified":
            continue
        if group not in GROUPS:
            continue
        codes = [int(c, 16) for c in match.group("codes").split()]
        chars = "".join(chr(c) for c in codes)
        if any(c in SKIN_TONE_MODIFIERS for c in codes):
            base = _strip_tones(chars)
            if base not in toned:
                toned[base] = [
                    index
                    for index, part in enumerate(chars.split(ZERO_WIDTH_JOINER))
                    if any(ord(c) in SKIN_TONE_MODIFIERS for c in part)
                ]
            continue
        name = match.group("name").strip()
        entries[chars] = {
            "char": chars,
            "name": name[:1].upper() + name[1:],
            "group": group,
            "subgroup": subgroup,
            "keywords": [],
            "skin_tones": False,
            "tone_slots": [],
        }
        order.append(chars)

    for chars, entry in entries.items():
        slots = toned.get(chars) or toned.get(chars.replace(VARIATION_SELECTOR, ""))
        entry["skin_tones"] = slots is not None
        entry["tone_slots"] = list(slots) if slots else []
        words = list(keywords.get(chars, []))
        bare = chars.replace(VARIATION_SELECTOR, "")
        if not words and bare != chars:
            words = list(keywords.get(bare, []))
        entry["keywords"] = [w for w in words if w.casefold() != str(entry["name"]).casefold()]

    return {
        "format_version": 1,
        "emoji_version": emoji_version,
        "cldr_version": cldr_version,
        "groups": list(GROUPS),
        "emoji": [entries[c] for c in order],
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emoji-version", required=True, help="e.g. 16.0")
    parser.add_argument("--cldr-version", required=True, help="the cldr-json version, e.g. 48.2.0")
    parser.add_argument("--cldr-tag", default="main", help="the cldr-json git ref to fetch from")
    parser.add_argument("--source-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    source = args.source_dir or (OUT_DIR / "_sources")
    source.mkdir(parents=True, exist_ok=True)
    if args.source_dir is None:
        _fetch(EMOJI_TEST_URL.format(version=args.emoji_version), source / "emoji-test.txt")
        _fetch(ANNOTATIONS_URL.format(tag=args.cldr_tag), source / "annotations.json")
        _fetch(DERIVED_URL.format(tag=args.cldr_tag), source / "annotationsDerived.json")
    data = build(source, args.emoji_version, args.cldr_version)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    count = len(data["emoji"])  # type: ignore[arg-type]
    print(f"wrote {OUT_FILE} with {count} emoji ({OUT_FILE.stat().st_size // 1024} KB)")
    readme = OUT_DIR / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        versions = f"Unicode emoji {args.emoji_version}; CLDR (cldr-json) {args.cldr_version}."
        text = re.sub(r"Data versions: .*", f"Data versions: {versions}", text)
        readme.write_text(text, encoding="utf-8")
    if args.source_dir is None:
        for child in source.iterdir():
            child.unlink()
        source.rmdir()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
