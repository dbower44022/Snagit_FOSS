# Numbered Steps, Stamps, and Emoji Implementation Notes

Last Updated: 09-10-26 23:45 · Revision 1.0

Implements the SnapMock Numbered Steps, Stamps & Emoji product requirements document (version 1.3 at the start of the work, `PRDs/SnapMock-Numbered-Steps-Stamps-Emoji-PRD.html`) in the three phases defined by `docs/Numbered-Steps-Stamps-Emoji-Kickoff-Prompt.md` (revision 1.0). A session pasting that prompt starts at the first phase not marked done in Section 1. `docs/General-UI-Implementation-Kickoff-Prompt.md` (revision 1.1) governs the standards; the General UI implementation notes (`docs/General-UI-Implementation.md`) hold the walk table of Section 17.2 that this work extends.

Starting state, verified at commit 565c587 on 09-10-26 (the kickoff names ea5f36b; 565c587 adds only the kickoff prompt and the General UI notes 1.29 pointer): the two stubs `NumberedStepItem` and `StampItem`, no stamp library, no emoji tool, no shadow and no fill or stroke opacity on any item; the suite passes 1043 tests with 13 skipped and one environmental deselection; ruff and mypy are clean. `PyQt6.QtSvg` imports, Qt lists Noto Color Emoji as a colour emoji family, and the Tabler release, the Unicode emoji test file (version 16.0), and the CLDR English annotations download from this machine.

## 1. Phase status

| Phase | Scope | Status | Commits |
|---|---|---|---|
| 1 | Numbered Step (PRD Section 2): the decisions, the item, the tool and the bar, editing, close-out | In progress | this commit |
| 2 | Stamp / Sticker (PRD Section 3): the library, the item, the tool, the bar, and the library panel, close-out | Not started | |
| 3 | Emoji (PRD Section 4): the data and the font, the item and the tool, the picker and the bar, close-out of the work | Not started | |

## 2. Decisions

### 2.1 Taken at the start of Phase 1 (09-10-26)

Presented with the consequential decision template and chosen by Doug on 09-10-26: the recommendation in every case.

| Decision | Choice | Effect |
|---|---|---|
| 1 Where the shadow and the two opacities live | B, a shared helper for the three new items | `snapmock/items/shadow.py` (Technical Architecture PRD Section 10 row) carries the five shadow properties (`shadow_enabled`, `shadow_color`, `shadow_offset_x`, `shadow_offset_y`, `shadow_blur`), their serialization keys, and the painting: an offset, blurred copy of the item's shape from a cached image, drawn inside the item's `paint`, never through a Qt graphics effect, so the display, the raster exports, and the thumbnails agree. `NumberedStepItem`, `StampItem`, and `EmojiItem` mix it in; `fill_opacity` and `stroke_opacity` live on `NumberedStepItem` alone. The Property Panel shows the Shadow section, and the two opacity sliders, only when every selected item carries them. The tool PRD's defaults (`#00000066`, offset 2 and 2, blur 4) win over Technical Architecture PRD 4.3's for these three items. The cost: a rectangle still has no shadow after this work, so the Basic Shape and Text item work that General UI Phase 6 decision 6.2 named still owes the adoption, now by mixing in; the panel's sections depend on the item type; the Technical Architecture PRD carries a row saying the common vector properties of Section 4.3 are built for three items first. The SVG export draws no shadow, recorded as a deviation. The alternatives: option A, the base classes (`VectorItem` gains the opacities, `SnapGraphicsItem` the shadow, every item repainted and reserialized), the architecture document's stated model but twelve item types reopened in a marker-tool kickoff; option C, defer, which would have shipped the numbered step without the shadow the PRD turns on by default. |
| 2 Where the emoji names, keywords, and categories come from | A, bundled Unicode data | A script under `scripts/` converts the Unicode emoji test file (`emoji-test.txt`, groups, subgroups, names, every sequence and its status; fully qualified entries kept) and the CLDR English annotations (keywords) once into one JSON file under `snapmock/resources/emoji/` (Section 10 row), with a README naming the versions and the Unicode licence. Each entry holds the character sequence, name, group, subgroup, keywords, and whether it takes a skin-tone modifier; zero-width-joiner sequences are stored whole. No runtime dependency: Technical Architecture PRD 9.1 holds. The cost: a generator to maintain and a data version to bump when Unicode publishes; about 1 MB in the repository and every installer. The alternatives: the `emoji` package from PyPI, the first required package beyond the three, which carries no CLDR keywords or categories and so needs the data file anyway; `unicodedata` names only (Unicode 15.0 in this Python), which has no categories, no keywords, and no list of which characters are emoji. |
| 3 Where the built-in stamps come from | B, Tabler Icons as the base | The named stamps that exist as Tabler glyphs are copied from the Tabler release the vendored subset's README names into `snapmock/resources/stamps/<category>/` under the MIT licence already in the tree, with their stroke set to `#FF0000` so every one is colorizable; the ten or so Tabler lacks (the DRAFT text stamp, the click and tap ripples, the starburst, the ribbon, the swooshes, the highlight rings) are hand-authored on the 64 by 64 viewport. A stamp README names the release and lists the hand-authored files; the licence files sit beside the stamps. The cost: the set reads as line icons rather than stickers; "non-colorizable" is an empty class in the initial set; the Tabler README and the stamp README both say which files are which. The alternatives: fifty hand-authored pieces of artwork whose quality the session cannot judge; five placeholders and a tool that is not useful until someone draws. |
| 4 Whether the emoji font is bundled | B, not bundled | `emoji_font_family()` in `snapmock/core/emoji_data.py` returns the installed colour emoji family (Noto Color Emoji, Segoe UI Emoji, Apple Color Emoji, or any family whose name contains "emoji") or None; the Emoji tool explains "Emoji needs a colour emoji font installed" through the Section 1.3 message when it is None. PRD 1.4 records the departure from Section 4.7 and from the Section 8.3 bullet on the bundled font. The cost: a bare Linux container shows the message instead of emoji. The alternative, bundling the 10.8 MB Noto Color Emoji file (Apache-2.0, with a SIL Open Font License 1.1 component per the Debian copyright file), belongs to a packaging kickoff that builds the AppImage, where the size belongs. |

### 2.2 The kickoff's fourteen silences

Each decided as the kickoff recommended, on 09-10-26.

| Silence | Decision |
|---|---|
| Which options list wins for the Tool Options Bar | The tool PRD's Sections 2.7, 3.6, and 4.5, the detailed ones. General UI PRD 5.3's two rows gain a row saying so, as the Phase 4 kickoff treated the tool PRDs as the owners of each tool's options. |
| The serialization `type` key | The class name, as every `ITEM_REGISTRY` entry; the PRD's `"numbered_step"` example gains a row. The Section 5 property keys are used as written; the stub's keys (`number`, `bg_color`) are read as fallbacks so a file saved today still loads. |
| The Renumber command | `RenumberStepsCommand` in `snapmock/commands/marker_commands.py` (Section 10 row) beside `ChangeStampCommand` and `ChangeEmojiCommand`, each one command with its own undo, per Section 6; Section 2.3's macro wording is superseded by 6.1 (a PRD row). |
| The placement animations | A `QVariantAnimation` on the item's scale (150 ms scale-up for steps and stamps, 200 ms pop-in for emoji), started after the command is pushed, with a module flag the tests set so the item lands at scale 1 at once; not a command and not saved. "Placed Step N" is shown for two seconds through the status bar's hint and then the tool's idle hint returns. |
| The stamp's fill and stroke opacity (Section 3.5) | Not built; a stamp has one `opacity` per Technical Architecture PRD 4.3 and General UI PRD 8.3 ("Non-vector items (Stamp, Emoji, Blur) show a single Opacity slider"). A PRD row records that Sections 3.5 and 3.6 disagree with both and that the single opacity wins. |
| Custom stamp import routes | The Custom tab's Import SVG button and its drop target only; no File > Import row (File > Import Image imports images) and no Preferences > Stamps category (General UI PRD 11.3 lists none). A PRD row. |
| Preferences > Emoji (the global skin tone) | Not built; the skin tone is remembered per session as Section 4.2 also says. A PRD row. |
| The stamp cursor and the emoji cursor | The crosshair with a 24 px preview of the active stamp or emoji at the lower right, built in `ui/cursors.py`; the plain crosshair when none is selected. |
| Double-click routing | `SelectTool.mouse_double_click` owns double-clicks on items today; a double-click on a numbered step, a stamp, or an emoji while the Select tool is active enters the item's edit (inline, the library, the picker) from there, and while the placing tool is active it does the same; one helper on the window, `open_marker_editor(item)`, serves both. |
| The RasterRegion layer type (General UI notes Section 18.1, silence 7) | Nothing in this PRD creates a raster layer, so this work assigns nothing; the type stays for a later raster kickoff. The pointer stops here. |
| Snagit export | `NumberedStepItem` and `StampItem` stay unsupported and `EmojiItem` joins them, with the writer's warning; no Snagit mapping is attempted. |
| The 24 px minimum hit area | `shape()` returns the union of the item's shape and a centred 24 by 24 square when the item is smaller. |
| The "Reset Size" context row | `stamp_size` back to the index's `default_size`, `emoji_size` back to 48, one `ModifyPropertyCommand`. |
| Group members | A numbered step inside a group renumbers with the rest (the walk includes members); a stamp or emoji inside a group cannot be double-click edited without Ungroup, as the Group and Ungroup kickoff decided for every member. |

## 3. What Phase 1 built

In progress. Step 1, this commit: the decisions above; the PRD at 1.4.

## 4. What Phase 2 built

Not started.

## 5. What Phase 3 built

Not started.

## 6. Deviations from the PRD

Each has its PRD 1.4 row.

- The shadow is painted for the three marker items only (decision 1); the Property Panel's Shadow section shows for them alone until the Basic Shape and Text item work adopts the helper.
- The SVG export draws no shadow (decision 1).
- The emoji font is not bundled (decision 4): Section 4.7's fallback and the Section 8.3 bullet on the bundled font are departed from on purpose.
- A stamp has one opacity, not a fill and a stroke opacity (silence 5).
- Custom stamps are imported through the library panel's Custom tab only; File > Import and Preferences > Stamps of Section 3.8 are not built (silence 6).
- Preferences > Emoji of Section 4.2 is not built; the skin tone is a session memory (silence 7).
- The serialization `type` key is the class name, not the `"numbered_step"` of Section 7.4 (silence 2).

## 7. Tests

Recorded per phase as each closes.

**Next required step:** Phase 1 step 2, the item: `NumberedStepItem` rebuilt on `VectorItem` with the twenty-two properties, the eight badge shapes, the display modes, the label line, the shadow helper of decision 1, `shape` with the 24 px minimum, `scale_geometry`, `clone`, and `serialize` and `deserialize` reading the stub's keys as fallbacks; tests in a new `tests/test_numbered_step_item.py`.

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.0 | 09-10-26 23:45 | Claude (Claude Code) | Initial notes: the starting state, the phase table, the four decisions (1 B, 2 A, 3 B, 4 B) and the fourteen silences as chosen 09-10-26, the deviations they imply, the next required step. PRD 1.4. |
