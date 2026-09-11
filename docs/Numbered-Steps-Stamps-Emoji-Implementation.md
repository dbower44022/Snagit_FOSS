# Numbered Steps, Stamps, and Emoji Implementation Notes

Last Updated: 09-11-26 00:15 · Revision 1.1

Implements the SnapMock Numbered Steps, Stamps & Emoji product requirements document (version 1.3 at the start of the work, `PRDs/SnapMock-Numbered-Steps-Stamps-Emoji-PRD.html`) in the three phases defined by `docs/Numbered-Steps-Stamps-Emoji-Kickoff-Prompt.md` (revision 1.0). A session pasting that prompt starts at the first phase not marked done in Section 1. `docs/General-UI-Implementation-Kickoff-Prompt.md` (revision 1.1) governs the standards; the General UI implementation notes (`docs/General-UI-Implementation.md`) hold the walk table of Section 17.2 that this work extends.

Starting state, verified at commit 565c587 on 09-10-26 (the kickoff names ea5f36b; 565c587 adds only the kickoff prompt and the General UI notes 1.29 pointer): the two stubs `NumberedStepItem` and `StampItem`, no stamp library, no emoji tool, no shadow and no fill or stroke opacity on any item; the suite passes 1043 tests with 13 skipped and one environmental deselection; ruff and mypy are clean. `PyQt6.QtSvg` imports, Qt lists Noto Color Emoji as a colour emoji family, and the Tabler release, the Unicode emoji test file (version 16.0), and the CLDR English annotations download from this machine.

## 1. Phase status

| Phase | Scope | Status | Commits |
|---|---|---|---|
| 1 | Numbered Step (PRD Section 2): the decisions, the item, the tool and the bar, editing, close-out | Done | 78314f7 to 35a3a39, then this close-out commit |
| 2 | Stamp / Sticker (PRD Section 3): the library, the item, the tool, the bar, and the library panel, close-out | Next | |
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

In commit order. Step 1, 78314f7: the decisions of Section 2; PRD 1.4. Step 2, 1be23f0: `snapmock/items/shadow.py` (Technical Architecture PRD 1.17, Section 10 row) with `ShadowMixin` (the five properties, `shadow_rect`, `paint_shadow`, the serialization pair) and `blur_image` (three NumPy box passes over a premultiplied image); `NumberedStepItem` rebuilt on `VectorItem`: `number_value`, `display_mode` with `letter_for` and `roman_for`, `custom_text`, `badge_shape` and `badge_path` for the eight shapes with `badge_center` and `badge_rect` (the pin's head above its point), `badge_color`, `border_color`, and `border_width` as the vector fill and stroke, `badge_size` clamped 16 to 128, `text_color`, `font_family`, `font_size` with `auto_font_pixel_size`, `font_weight`, `border_style`, `fill_opacity` and `stroke_opacity` as alpha at paint time, the label (`label_rect`, the connector, the pill), `shape` with the 24 px minimum, `boundingRect` including the shadow, `scale_geometry`, `serialize` with the Section 5 keys and `deserialize` with the stub's `number` and `bg_color` as fallbacks, `type_name` "Numbered Step"; the constants and the enums `BadgeShape`, `DisplayMode`, `FontWeight`, `LabelPosition` in `config/constants.py`; `ResizeImageCommand`'s snapshot follows. Step 3, 1605c89: `NumberedStepTool` (click, drag with a dashed preview, the per-project counter in a `WeakKeyDictionary` by scene with `next_number`, `set_next_number`, and the first-activation rule, `place`, the hints with the two-second "Placed Step N", `animate_placement` with `ANIMATIONS_ENABLED`, the Section 1.3 messages for a locked or hidden layer, `numbered_step_cursor`); the Tool Options Bar's `enum` and `check` control kinds, `badge_shape_icon`, and the seven new `SHARED_CONTROLS` entries; `MainWindow.renumber_all_steps`; `snapmock/commands/marker_commands.py` (Technical Architecture PRD 1.18) with `steps_in_reading_order` and `RenumberStepsCommand`; the theme codec's five new enum types; General UI notes 1.31 (the Section 17.2 walk row); General UI PRD 2.10 (silence 1). Step 4, 35a3a39: `snapmock/ui/step_inline_editor.py` (Technical Architecture PRD 1.19) with `StepInlineEditor`; `MainWindow.open_marker_editor`, `close_marker_editor`, `marker_editor`, `_step_set_as_starting_number`, `_step_toggle_text_mode`; the Select tool's and the step tool's double-click routes and the step tool's selecting click; the three context menu rows in `build_item_context_menu`; the Property Panel's Numbered Step and Shadow sections with their populate and handlers. Step 5, this commit: PRD 1.5, General UI PRD 2.11, these notes.

Silences found while building, decided as the code says and recorded as PRD 1.5 rows: Shift during a drag changes nothing (one size per badge); a click on an existing step with the step tool selects it; Renumber leaves text-mode steps out and moves the counter past the renumbered set; Escape in the inline editor closes without applying and focus leaving applies; colour strings are Qt's `#AARRGGBB`; Border Width keeps the shared 0 to 20 px range and Font Weight is a dropdown; the two opacities sit in the Numbered Step section beside Appearance's Opacity; auto font sizing uses a per-shape interior; the shadow pulse of Section 2.2 is deferred.

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
- Colour values are written in Qt's `#AARRGGBB` form, as every other item writes them, not the Section 5 table's `#RRGGBB` (Phase 1).
- Shift during a drag-to-size changes nothing; the badge has one size (Phase 1, Section 2.2).
- The placement animation has no drop shadow pulse (Phase 1, Section 2.2; deferred).
- A click on an existing step with the Numbered Step tool selects it rather than placing over it (Phase 1, Sections 2.2 and 2.8).
- Renumber All Steps leaves text-mode steps out and moves the tool's counter past the renumbered set (Phase 1, Sections 2.3 and 6.1).
- Escape in the inline editor closes without applying; Enter and focus leaving apply (Phase 1, Section 2.8).
- Border Width keeps the shared control's 0 to 20 px range and Font Weight is a dropdown rather than a toggle (Phase 1, Section 2.7).
- The Property Panel shows the numbered step's Fill Opacity and Stroke Opacity in its Numbered Step section beside Appearance's Opacity, not in place of it (Phase 1; General UI PRD 8.3).

## 7. Tests

Phase 1: `tests/test_numbered_step_item.py` (33: the defaults, the fill and stroke aliases, the size clamp, every shape's rects, the pin anchor, the 24 px hit area, letters to AA and beyond, roman 1 to 3999, the modes, auto font size at 16 and 128 px, the explicit size, the label at four positions, the pill padding, the centre and edge pixel checks, the shadow's pixels and bounding rect, the two opacities, `blur_image`, `scale_geometry`, `clone`, the round trip of every key, the stub-key fallback, unknown enum values); `tests/test_tools/test_numbered_step_tool.py` (21: identity, cursor, and hints, click placement and undo, drag-to-size, the ten-pixel threshold, the clamp, the creation defaults, text mode and the counter, the locked and hidden layer messages, the counter across a tool switch, across projects, and from a loaded file, the Starting Number, the bar's controls in order with the shape glyphs, edits reaching the defaults and a placed item, a theme change read back, Renumber All with undo and its message, the codec round trip, a saved and applied preset, `RenumberStepsCommand`'s assignments, the animation); `tests/test_numbered_step_editing.py` (16: the editor's fields and hint, Enter with Tab as one undo entry, Escape, text mode, the double-click from both tools and the selecting click, a second editor finishing the first, a non-marker refused, the context rows for one step only and their labels, Set as Starting Number reaching the tool and the bar, Convert with undo and redo, the two messages, Renumber across layers and into a group with undo, the panel's sections for a step and a rectangle, the panel's edits as commands, mixed values across two steps). Two existing tests moved to the new constructor and one to `next_number`. The accessibility audit (`tests/test_accessibility.py`) passes over the new bar, the panel sections, and the editor. The full suite at the step 4 commit ran 1113 tests with 13 skipped and the one environmental deselection (`test_font_combo_reflects_text_item_font`): 1112 passed and one, the animation test, failed on timing under a loaded machine (it read the scale before the first frame); the close-out commit relaxes that assertion to the range the animation runs through. Ruff and mypy are clean at every commit.

**Next required step:** Phase 2 step 1, the library: `snapmock/core/stamp_library.py` (Technical Architecture PRD Section 10 row) with the index model, `stamp_index.json` loaded once and cached, the custom directory under the application data directory merged in, the `#FF0000` and `#0000FF` substitution, the `QSvgRenderer` cache, the missing-stamp placeholder, and the SVG import; the built-in set per decision 3 under `snapmock/resources/stamps/<category>/` with the index, a README naming the Tabler release and the hand-authored files, and the licence files. Then the item (step 2), the tool, the bar, and the library panel (step 3), and the phase close-out (step 4).

## Change Log

| Rev | Date (MM-DD-YY HH:MM) | Author | Change |
|---|---|---|---|
| 1.1 | 09-11-26 00:15 | Claude (Claude Code) | Phase 1 done: the phase table, Section 3 (what Phase 1 built, the silences found while building), Section 6 (eight deviations added), Section 7 (the tests and the suite count), the next required step. PRD 1.5, General UI PRD 2.11, Technical Architecture PRD 1.19 (1.17 to 1.19 across the phase). |
| 1.0 | 09-10-26 23:45 | Claude (Claude Code) | Initial notes: the starting state, the phase table, the four decisions (1 B, 2 A, 3 B, 4 B) and the fourteen silences as chosen 09-10-26, the deviations they imply, the next required step. PRD 1.4. |
