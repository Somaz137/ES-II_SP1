---
name: Room Environment Safety Control
description: A calm green ward console that tells a caregiver, in words, what in one patient's room needs them and for how long.
colors:
  ward-green: "#0f4c3a"
  ward-green-ink: "#e6f2ec"
  ward-green-active: "#1c6b52"
  primary: "#12805c"
  primary-deep: "#0e6b4c"
  mint: "#d8f0e6"
  ground: "#f1f5f3"
  card: "#ffffff"
  border: "#dfe7e3"
  hairline: "#e3ebe7"
  ink: "#10231c"
  muted: "#51635b"
  input-stroke: "#7a8f85"
  neutral-tint: "#eef2f0"
  gap-fill: "#eceff0"
  alert-red: "#c62828"
  alert-red-deep: "#a91f1f"
  alert-red-tint: "#fdecea"
  alert-red-line: "#f3c9c4"
  hold-amber: "#a15c07"
  hold-amber-tint: "#fff4d6"
  hold-amber-hover: "#fdeab4"
  hold-amber-line: "#f0dca6"
typography:
  display:
    fontFamily: "ui-sans-serif, system-ui, Segoe UI, Roboto, sans-serif"
    fontSize: "clamp(1.75rem, 2.6vw, 2.5rem)"
    fontWeight: 700
    lineHeight: 1.1
    fontFeature: "tnum"
  headline:
    fontFamily: "ui-sans-serif, system-ui, Segoe UI, Roboto, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.45
    fontFeature: "tnum"
  title:
    fontFamily: "ui-sans-serif, system-ui, Segoe UI, Roboto, sans-serif"
    fontSize: "1rem"
    fontWeight: 700
    lineHeight: 1.45
    fontFeature: "tnum"
  body:
    fontFamily: "ui-sans-serif, system-ui, Segoe UI, Roboto, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tnum"
  label:
    fontFamily: "ui-sans-serif, system-ui, Segoe UI, Roboto, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.3
    fontFeature: "tnum"
rounded:
  swatch: "2px"
  inner: "6px"
  control: "8px"
  card: "14px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  gutter: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.card}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "40px"
  button-primary-hover:
    backgroundColor: "{colors.primary-deep}"
  button-outline:
    backgroundColor: "{colors.card}"
    textColor: "{colors.primary}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "36px"
  button-outline-hover:
    backgroundColor: "{colors.mint}"
  button-alert:
    backgroundColor: "{colors.alert-red}"
    textColor: "{colors.card}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "36px"
  button-alert-hover:
    backgroundColor: "{colors.alert-red-deep}"
  button-acknowledge:
    backgroundColor: "{colors.card}"
    textColor: "{colors.hold-amber}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "36px"
  button-acknowledge-hover:
    backgroundColor: "{colors.hold-amber-hover}"
  chip-within:
    backgroundColor: "{colors.mint}"
    textColor: "{colors.ward-green}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "4px 10px"
  chip-holding:
    backgroundColor: "{colors.hold-amber-tint}"
    textColor: "{colors.hold-amber}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "4px 10px"
  chip-alerting:
    backgroundColor: "{colors.alert-red-tint}"
    textColor: "{colors.alert-red}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "4px 10px"
  chip-neutral:
    backgroundColor: "{colors.neutral-tint}"
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "4px 10px"
  card:
    backgroundColor: "{colors.card}"
    rounded: "{rounded.card}"
    padding: "20px 24px"
  input-number:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "40px"
  nav-item:
    textColor: "{colors.ward-green-ink}"
    rounded: "{rounded.pill}"
    padding: "0 12px"
    height: "40px"
  nav-item-active:
    backgroundColor: "{colors.ward-green-active}"
    textColor: "{colors.card}"
  segmented-option-active:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.card}"
    rounded: "{rounded.inner}"
    padding: "6px 12px"
    height: "32px"
---

<!--
Provenance: recorded from the shipped build on feature/dashboard-pages at 3842751
(static/room.css, static/room.js, static/chart.js, templates/{room,overview,trends,events,limits,system}.html),
not from the plan. Direction contract: .impeccable/surfaces/templates-room-html.md, world "Green ward console",
seed: none (pinned); approved sketches in .impeccable/mocks/pages/. Finish review verdict was "fix"; its three
material fixes (number and unit held together by no-break spaces, last confirmed condition repeated when the
monitor is overdue, limit chips kept whole) are in 3842751. The comp-diff reproduction gate was not run: this
Impeccable version has no such command. No shipping rasters exist; every mark is CSS or inline SVG.
-->

# Design System: Room Environment Safety Control

## Overview

**Creative North Star: "The Green Ward Console"**

A calm clinical admin console. A deep ward-green sidebar frames white, softly rounded cards on a pale green-grey ground, and whatever needs the caregiver sits in a coloured attention row above everything else on every page. The page is read in one pass from the top: the attention row says what, how long, and now; the page's own content answers when and why below it.

Density is moderate and even: one 14px sans family with tabular figures, an 8px rhythm, hairline dividers inside cards, borders instead of shadows. Colour carries state and nothing else. Green means within the configured limits, amber means a hold timer is running or something waits to be acknowledged, red means alerting; muted grey means the value is not fresh. Every coloured mark sits beside words that say the same thing.

The system refuses decoration: no gradients, no glass, no elevation shadows, no ornamental charts, no decorative motion. State changes happen in one step.

**Key Characteristics:**
- Ward-green sidebar, pale ground, white 14px-radius cards with a 1px border and no shadow.
- One attention row on every page, tinted by the most urgent state, carrying its single action.
- Three status tones (green, amber, red) plus grey for not-fresh; never colour without words.
- One system sans family, tabular figures everywhere, sentence case, no letter-spacing.
- Charts are inline SVG: mint limit band, gaps left visibly empty, outside-limit stretches drawn in red.

## Colors

A restrained clinical palette: one deep green family for the frame and primary actions, neutral green-greys for surfaces, and two signal hues held back for state.

### Primary
- **Ward Green** (sidebar fill): the frame. Sidebar background on desktop, top bar on tablet, bottom navigation bar on phone; also the text colour of the within-limits chip.
- **Ward Green Ink** (sidebar text): navigation labels, sidebar foot text, the outlined Simulation tag and the sidebar focus ring.
- **Ward Green Active** (current-page pill): the filled pill behind the current navigation item; the top rule of the phone navigation bar.
- **Console Green** (`primary`): primary buttons, links, the active segmented option, the focus ring, within-limit dots, chart line, and the calm attention label.
- **Console Green Deep** (`primary-deep`): primary button hover only.
- **Mint Band** (`mint`): the configured-limit band in charts and range bars, the within-limits chip, outline-button hover, the pressed filter chip, text selection.

### Secondary
- **Hold Amber** (`hold-amber`) on **Amber Tint** (`hold-amber-tint`): a breach hold timer is running, something waits to be acknowledged, the monitor is overdue, or a value sits outside the band on a banded range track. `hold-amber-hover` is the Acknowledge button hover; `hold-amber-line` is the amber hairline.

### Tertiary
- **Alert Red** (`alert-red`) on **Red Tint** (`alert-red-tint`): alerting. The red attention row, the Silence alarm button, outside-limit chart stretches, the alerting reading dot, field errors. `alert-red-deep` is the red button hover; `alert-red-line` separates the compact red attention row.

### Neutral
- **Ward Ground** (`ground`): page background behind cards.
- **Card White** (`card`): cards, top bar, inputs, outline buttons, segmented control body.
- **Card Border** (`border`): the 1px outline of cards, the attention panel, the segmented control and unpressed filter chips.
- **Hairline** (`hairline`): row dividers inside cards, table rules, the top bar's bottom rule, chart gridlines.
- **Ink** (`ink`): body text and values; also the chart tooltip fill.
- **Muted** (`muted`): secondary text, units, ages, table headers, axis labels, and every retained or missing value.
- **Input Stroke** (`input-stroke`): text input borders, kept at 3.4:1 against white.
- **Neutral Tint** (`neutral-tint`): the neutral chip and the unbanded range track.
- **Gap Fill** (`gap-fill`): chart regions with no data, labelled "no data".

### Named Rules
**The Three Tones Rule.** Status uses exactly three hues: Console Green within limits, Hold Amber while a timer runs or an action waits, Alert Red when alerting. No fourth status hue, and none of the three is used decoratively.

**The Words Beside Colour Rule.** A dot, chip, row tint or chart stretch never carries state alone. Chips always contain words ("Above limit · 12 s", "No limit set"); dots always sit beside a text label; red chart stretches carry a text label ("above limit · 12 s").

**The Grey Means Not Fresh Rule.** A retained, estimated-before-ready or missing value renders in Muted, its dot hollow, its tone dropped. A value is never shown in a tone colour unless it is a fresh reading.

## Typography

**Display Font:** none distinct; the system sans stack serves every role.
**Body Font:** ui-sans-serif, system-ui, Segoe UI, Roboto, sans-serif.

**Character:** a plain operating-console voice. Hierarchy comes from size and weight (400, 600, 700), never from case, tracking or a second family. Tabular figures are on for the whole page so values and times align.

### Hierarchy
- **Display** (700, clamp 1.75rem to 2.5rem, 1.1): the reading number in an Overview tile; 1.75rem on phone. A word in place of a number ("Calibrating") drops to Headline size in Muted.
- **Headline** (700, 1.25rem): the page title in the top bar; the red attention row's main line on Overview; section headings on Patient limits; current values in Trends rows.
- **Title** (700, 1rem): card headings.
- **Body** (400, 0.875rem, 1.45): everything else; help text capped at 70ch. Emphasis inside body is 600.
- **Label** (600, 0.75rem, 1.3): chips, table headers, legend, chart notes, ages and axis ticks (axis ticks at 400).

### Named Rules
**The Sentence Case Rule.** No uppercase, no letter-spacing, no small labels above headings. A heading says what the card holds and stands alone.

**The Unit Stays With Its Number Rule.** A value and its unit, and a duration and its unit, are joined by a no-break space and never split across lines. A chip never wraps inside its pill; when space runs out it moves below the value whole.

## Layout

A fixed frame and a flowing content column. On desktop (1024px and up) a 232px ward-green sidebar is sticky at full height; to its right a 64px white top bar carries the page title on the left and the room, occupancy, monitor and alarm status on the right; under it the attention panel; then content in a 24px-padded column with 16px gaps between cards.

The attention panel is the first thing after the top bar on every page. On Overview it is a full card with one row per active state (alerting, to acknowledge, pending, calm), 24px side padding and a 140px label column. On every other page it collapses to a compact 48px edge-to-edge strip under the top bar.

Overview: five measurement tiles in an equal five-column grid, then a two-column row (fluid chart card plus a 360px recent-events card). Trends: one card of small multiples, a 192px label column beside each 96px chart, sharing one time axis. Patient limits: fluid form plus a 300 to 360px side stack. System: a full-width table then three equal columns.

Spacing follows an 8px rhythm with 4px half-steps (4, 8, 12, 16, 20, 24). Cards pad 20px by 24px; dividers inside cards are hairlines, not gaps.

Responsive: at 1279px and below, tiles go to a 3 + 2 grid, side-by-side columns stack, System goes to two columns. At 1023px and below the sidebar becomes a wrapping top navigation bar, the limits page stacks, and outer padding drops to 16px. At 640px and below navigation moves to a fixed bottom bar with icon over short label, each tile becomes a compact grid (name and chip on one line, value, range bar, age), tables reflow into stacked rows, and cards pad 16px.

### Named Rules
**The Attention Row First Rule.** On every page the attention panel sits directly under the top bar, above all page content, and holds that state's one action. Nothing is placed above it.

## Elevation & Depth

Flat. Depth comes from tonal layering only: ward-green frame, pale ground, white cards outlined by a 1px border, hairlines inside. No surface casts a shadow.

### Shadow Vocabulary
- **Input focus ring** (`box-shadow: 0 0 0 3px var(--mint), 0 0 0 4px var(--primary)`): text inputs on focus only.
- **Hollow status dot** (`box-shadow: inset 0 0 0 1.5px var(--muted)`): the outlined dot for unknown or not-fresh state.

Every other element focuses with a 3px Console Green outline, 2px offset (Ward Green Ink inside the sidebar).

### Named Rules
**The Border Not Shadow Rule.** Cards, panels and controls separate from the ground by a 1px Card Border on white. box-shadow appears only as a focus ring or a dot outline, never as elevation.

## Shapes

Two corner families. Containers are softly rounded (14px cards and attention panel; 8px buttons, inputs, segmented control, tooltip, form error; 6px segmented options). Anything that states a status or a place is a full pill (999px): chips, filter chips, navigation items, the Simulation tag. Dots are circles; the reading dot on a range bar is a 14px circle with a 2px white ring, 16px when alerting. Range tracks are 8px bars with 4px ends; legend swatches 16 by 10px with 2px corners. Icons are 18px stroked line drawings (1.75 stroke, round caps and joins) in currentColor, used only in navigation.

## Components

### Buttons
Plain and firm: one weight (600), no icons, one action per context.
- **Shape:** gently rounded (8px).
- **Primary:** Console Green fill, white text, 40px high, 16px side padding; Save on Patient limits.
- **Outline:** white fill, Console Green 1px border and text, 36px high; Mint on hover. Small variant 28px high with label-size text, used in table rows.
- **Alert:** Alert Red fill, white text; Silence alarm in the red attention row only.
- **Acknowledge:** white fill, Hold Amber border and text; amber hover tint; in the amber attention row only.
- **Text:** borderless, 8px side padding.
- **Focus:** 3px Console Green outline, 2px offset. **Disabled:** 55% opacity, not-allowed cursor (controls locked until signed in).

### Chips
- **Style:** full pill, 4px by 10px, Label type, tint background with the matching strong text: Mint with Ward Green, Amber Tint with Hold Amber, Red Tint with Alert Red, Neutral Tint with Muted.
- **Content:** always words, with a duration when a timer is involved ("Within limits", "Above limit · 12 s", "No limit set"); estimates name their source ("Calibrating · Bosch estimate"). Never an empty colour pill.
- **Filter chips (Events):** 32px pill, white with Card Border; Console Green border on hover; pressed is Mint with Console Green border and Ward Green 600 text.

### Cards / Containers
- **Corner Style:** 14px.
- **Background:** Card White on Ward Ground.
- **Shadow Strategy:** none (see Elevation & Depth).
- **Border:** 1px Card Border.
- **Internal Padding:** 20px by 24px (tiles 20px; limits page 24px; phone 16px). A card head pairs the Title heading with its control, 16px above the content.

### Inputs / Fields
- **Style:** 40px high, 1px Input Stroke, 8px radius, white, 16px tabular text; label above in 600 with 6px gap.
- **Hover:** border darkens to Muted.
- **Focus:** border Console Green plus the mint-and-green double ring.
- **Error:** Alert Red border and a 600 Alert Red message directly under the field; form-level errors in a Red Tint box.

### Navigation
- **Desktop:** vertical list in the sidebar, 40px pill items with an 18px line icon and the page name; hover is a faint white wash; current page is a Ward Green Active pill in white 600.
- **Tablet:** the same pills in a wrapping row across the top.
- **Phone:** fixed bottom bar in Ward Green, five equal items with icon above a short label, 48px high, safe-area padding.

### Segmented Control
A 2px-padded white group with Card Border and 8px corners; options are 32px, Label size, Muted; the pressed option fills Console Green with white 600 text. Chooses the chart's measurement or the time window.

### Attention Row (signature)
A full-width row tinted by its state: Red Tint for alerting, Amber Tint for to acknowledge, pending or monitor overdue, white for calm. Left, a fixed-width label in the state's strong colour ("Alerting", "To acknowledge", "No action needed"); centre, one sentence of what and how long, with a muted sub-line of since-when; right, the one action button. When the monitor is overdue the row repeats the last confirmed condition rather than going blank.

### Measurement Tile and Range Bar (signature)
A card per measurement: name, Display value with Muted unit, a status chip in words, a banded range bar, and a meta line with the configured range and age. The range bar is a Neutral Tint track (Amber Tint when a band exists) with the Mint band of configured limits, end ticks with the limit values, and a reading dot positioned at the value, coloured by tone. On each refresh the dot moves and the chip changes in one step; there is no animation.

### Charts
Inline SVG line charts. A 2px Console Green line with round joins; the configured band as a Mint rectangle with its limit values labelled in green 600; no-data stretches as a Gap Fill rectangle labelled "no data"; the parts of the line outside the band redrawn in 2.5px Alert Red with a red text label; the latest point a 4px dot with a white ring. Hairline gridlines, Muted 12px axis text, and a hover crosshair (dashed Muted line) with an Ink tooltip giving time and value with unit.

## Do's and Don'ts

### Do:
- **Do** put the attention panel directly under the top bar on every page, with that state's single action in the row.
- **Do** pair every status colour with words: chips contain text, dots sit beside a label, red chart stretches carry a label.
- **Do** render retained, missing or not-yet-calibrated values in Muted with a hollow dot, never in a tone colour.
- **Do** separate surfaces with a 1px Card Border on white and hairline dividers inside cards.
- **Do** join every number to its unit with a no-break space, and keep chips on one line.
- **Do** keep tabular figures on for all text.
- **Do** change state in one step; honour reduced motion by removing any transition.

### Don't:
- **Don't** use box-shadow for elevation; it is reserved for the input focus ring and the hollow dot.
- **Don't** use gradients, glass or blur, or ornamental chart fills.
- **Don't** introduce a fourth status hue or use green, amber or red for decoration.
- **Don't** set text in uppercase or with letter-spacing, and don't place small labels above headings.
- **Don't** draw a chart line across missing data; leave the gap visible and labelled.
- **Don't** add icons outside the navigation, and don't use glyph or emoji icons; navigation icons are stroked inline SVG.
