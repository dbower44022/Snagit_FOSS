# Built-in stamps

Numbered Steps, Stamps & Emoji PRD Section 3.3; implementation decision 3 (option B, 09-10-26).

`stamp_index.json` catalogues every stamp: `id` (`category/name`), `name`, `category`,
`filename`, `tags` (search), `default_size`, `colorizable`, and `source`. Every stamp is
colorizable: its strokes and fills use the placeholder `#FF0000` (the primary colour) and,
where a second region exists, `#0000FF` (the secondary colour), which `StampItem`
substitutes at render time (PRD 3.2).

## Sources

42 stamps are Tabler Icons glyphs from release v3.46.0, `icons/outline/`
(https://github.com/tabler/tabler-icons, MIT, author Paweł Kuna; see `LICENSE` beside this
file). Each file is the release's SVG with `width` and `height` set to 64, `currentColor`
replaced by `#FF0000`, and a comment naming the glyph. The `source` field of the index reads
`tabler:<glyph>` for these:

- `status/approved.svg`
- `status/rejected.svg`
- `status/attention.svg`
- `status/question.svg`
- `status/info.svg`
- `status/star.svg`
- `status/heart.svg`
- `status/thumbs-up.svg`
- `status/thumbs-down.svg`
- `arrows/curved-arrow-cw.svg`
- `arrows/curved-arrow-ccw.svg`
- `arrows/thick-arrow-right.svg`
- `arrows/thick-arrow-left.svg`
- `arrows/thick-arrow-up.svg`
- `arrows/thick-arrow-down.svg`
- `arrows/double-arrow-horizontal.svg`
- `arrows/double-arrow-vertical.svg`
- `arrows/pointer-hand.svg`
- `arrows/magnifying-glass.svg`
- `arrows/target.svg`
- `ui/cursor-arrow.svg`
- `ui/cursor-hand.svg`
- `ui/drag.svg`
- `ui/scroll.svg`
- `ui/key.svg`
- `shapes/checkmark.svg`
- `shapes/x-mark.svg`
- `shapes/plus.svg`
- `shapes/minus.svg`
- `shapes/warning.svg`
- `shapes/lock.svg`
- `shapes/unlock.svg`
- `shapes/eye.svg`
- `shapes/eye-off.svg`
- `shapes/bolt.svg`
- `shapes/gear.svg`
- `shapes/pencil.svg`
- `shapes/trash.svg`
- `shapes/link.svg`
- `shapes/unlink.svg`
- `shapes/bookmark.svg`
- `decorative/speech-bubble.svg`

14 stamps are hand-authored by SnapMock on the 64 by 64 viewport (MIT, the
project licence); the `source` field reads `snapmock`:

- `status/draft.svg`
- `ui/click.svg`
- `ui/double-click.svg`
- `ui/right-click.svg`
- `ui/tap.svg`
- `decorative/starburst.svg`
- `decorative/thought-bubble.svg`
- `decorative/ribbon.svg`
- `decorative/bracket-left.svg`
- `decorative/bracket-right.svg`
- `decorative/brackets.svg`
- `decorative/swoosh.svg`
- `decorative/circle-highlight.svg`
- `decorative/box-highlight.svg`

## Adding a stamp

Add the SVG under its category directory on a 64 by 64 viewport with `#FF0000` for the
primary colour, then add its entry to `stamp_index.json`. Custom stamps a user imports live
under the application data directory (`stamps/custom/`) with their own index and never here.
