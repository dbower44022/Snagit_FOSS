# Emoji data

Numbered Steps, Stamps & Emoji PRD Section 4.2; implementation decision 2 (option A, 09-10-26).

`emoji.json` holds every fully qualified emoji of the nine picker categories, with its
character sequence (`char`, zero-width-joiner sequences stored whole), `name`, `group`,
`subgroup`, search `keywords`, and whether it takes a skin-tone modifier (`skin_tones`).
Skin-tone variants are not entries of their own: `snapmock/core/emoji_data.py` applies a
Fitzpatrick modifier to a capable emoji at placement time.

Data versions: Unicode emoji 16.0; CLDR (cldr-json) 48.2.0.

## Sources

- Names, groups, subgroups, and qualification: `emoji-test.txt` from the Unicode emoji data
  (https://unicode.org/Public/emoji/), © Unicode, Inc., under the Unicode License v3 (see
  `LICENSE` beside this file).
- Keywords: the English annotations of the Unicode Common Locale Data Repository (CLDR),
  from the `cldr-json` distribution (https://github.com/unicode-org/cldr-json,
  `cldr-annotations-full` and `cldr-annotations-derived-full`), under the same licence.

## Regenerating

    uv run python scripts/build_emoji_data.py --emoji-version 16.0 --cldr-version 48.2.0

The script downloads both sources, writes `emoji.json`, and updates the version line above.
Bump the versions when Unicode publishes a new emoji release.
