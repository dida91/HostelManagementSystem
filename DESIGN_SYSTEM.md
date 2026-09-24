# Design System — "Phewa Dusk"

> **Phase 3 deliverable.** The visual language for the Kutumba hostel app. Tokens live in
> `apps/web/tailwind.config.ts` and `apps/web/app/globals.css`; components in
> `apps/web/components/`. This file is the reference: when code and this file disagree,
> fix one of them.

## The idea

Kutumba (कुटुम्ब) means *household*. It is a girls' hostel in Pokhara, the lake town
under the Annapurna range. The interface borrows that place, at dusk:

- **The lake is the canvas.** Deep, still, blue-green surfaces — never neutral black.
- **Light comes from the mountains.** One warm light source (alpenglow on
  Machhapuchhre) lights edges and hero moments from above. Everything else is calm.
- **Warm means act.** Marigold — the garlands of Tihar — marks the thing you can do next.
  Rhododendron crimson means stop or urgent. Everything that is not a decision stays in
  lake tones.
- **Two scripts, one voice.** Residents write in English and Nepali. One variable
  typeface family, designed for both, sets both.
- **3D is a place, not a gimmick.** Exactly two scenes: the Machhapuchhre horizon
  (identity) and the block model of the hostel's rooms (data). No spinning logos, no
  3D cards.

Boldness is spent in one place: the horizon scene. Every other surface is disciplined.

## Rejected defaults (review against the brief)

| Default we did not use | Why | What we did instead |
|---|---|---|
| Near-black + one neon accent | Reads as any dark dashboard | Hued lake blue-green base, warm multi-tone light drawn from Pokhara |
| Inter/Geist + serif display | Template pairing | Anek Latin + Anek Devanagari, one family, using its width axis for hierarchy |
| Identical rounded cards everywhere | "SaaS card kit" | Radii follow hierarchy (controls 10, panels 18, stage 28); lists and tables sit on panels, not in card grids |
| ALL-CAPS eyebrows, "A · B · C" meta strings, "→" buttons | Generated-page tells | Sentence-case labels; metadata as separate pills or columns; buttons name their action |
| Gradient washes as decoration | Noise | Gradients only as *light*: the horizon and a faint top-edge highlight |
| Fade-up on every section | Scattered motion | One orchestrated moment (the horizon light rising on dashboard/login); otherwise motion only answers people |

## Colour

Core palette:

| Token | Hex | Role |
|---|---|---|
| `lake-950` | `#0A1A20` | App canvas |
| `lake-900` | `#0E2229` | Sunken areas, sidebar, table headers |
| `lake-850` | `#12292F` | Panels |
| `lake-800` | `#173139` | Raised elements, hover |
| `lake-700` | `#21424B` | Selected, strong borders |
| `lake-600` | `#2F5864` | Muted fills, inactive data |
| `snow` | `#EDF3F2` | Primary text |
| `mist` | `#A9BCBF` | Secondary text |
| `stone` | `#7A9095` | Tertiary text, placeholders (≥ 4.5:1 on canvas) |
| `marigold` | `#F2B544` | Primary action, focus, current item |
| `alpenglow` | `#F08A76` | Light, highlights, 3D key light |
| `laligurans` | `#E5455F` | Danger, urgent, destructive |
| `terrace` | `#57BD8E` | Success, paid, approved |
| `glacier` | `#7FB7DB` | Information, links, neutral-positive data |

Text on marigold is `#231704`. Text on crimson is `snow`.

Charts follow the dataviz method (form first, colour by job, validated palette):

- **One series** (e.g. complaints by category): every bar in slot 1, sky `#3987e5`.
  Sorted, values at the bar tips, no legend box.
- **Categorical** (several series), in prayer-flag order — sky, fire, water, earth —
  stepped for the dark lake surface: `#3987e5`, `#d95926`, `#199e70`, `#c98500`,
  `#d55181`, `#9085e9`. Validated on the panel surface `#12292F` (dark mode): lightness
  band, chroma floor, CVD separation (worst adjacent ΔE 8.4), normal-vision floor (19.3)
  and contrast all pass. The flags' white fails the chroma floor and their red is the
  danger colour, so neither is a series colour.
- **Ordinal** (pipeline stages): one hue, stepped in lightness.
- **Ratios** (occupancy, collection): a meter whose track is a darker step of the
  same hue.
- Status colours (terrace, marigold, crimson) mean state only and never mark a series.

Status tones: every enum value maps to one of *neutral / info / progress / success /
warning / danger* (see `lib/labels.ts`). Colour is never the only signal: pills always
carry a text label.

## Typography

Family: **Anek Latin** with **Anek Devanagari** (variable weight 100–800, width 75–125),
loaded with `next/font`. Hierarchy uses the width axis as much as the weight:

| Style | Size / line | Weight | Width | Use |
|---|---|---|---|---|
| Display | 48 / 52 | 600 | 120 | Login and dashboard greeting |
| Title | 36 / 40 | 600 | 115 | Page titles |
| Heading | 21 / 28 | 600 | 108 | Section headings |
| Subheading | 16 / 24 | 600 | 104 | Panel titles |
| Body | 16 / 26 | 400 | 100 | Reading text (max ~70 characters per line) |
| UI | 14 / 20 | 500 | 100 | Controls, table cells |
| Small | 12 / 16 | 500 | 100 | Help text, captions |
| Figure | 36–48 / 1 | 600 | 118 | KPI numbers, tabular figures |

Rules: sentence case everywhere; letter-spacing −1.5% on Display/Title only; tabular
figures in tables and KPIs; numbers are right-aligned in tables.

## Space, radius, borders, depth

- **Spacing:** 4 px base — 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80. Page gutters 32 px
  (desktop) / 16 px (mobile). Sections 32–48 px apart.
- **Radius follows hierarchy:** controls 10 · panels 18 · stage (hero, 3D frames) 28 ·
  overlays 22 · pills full.
- **Borders:** hairline `rgba(237,243,242,.08)`, default `.14`, strong `.22`.
- **Depth:** every raised surface has a 1 px top highlight (`inset 0 1px 0
  rgba(255,255,255,.05)`) — the light from above.
  - `depth-panel`: highlight + `0 16px 40px -24px rgb(0 0 0 / .6)`
  - `depth-overlay`: `0 32px 80px -24px rgb(0 0 0 / .75)` + hairline ring
  - `glow-action`: `0 0 0 1px rgba(242,181,68,.5), 0 10px 30px -12px rgba(242,181,68,.5)`

## Surfaces

| Surface | Treatment | Used for |
|---|---|---|
| Canvas | `lake-950` + two faint radial lights (alpenglow top-right, glacier bottom-left) + 3 % film grain | Page background |
| Panel | `lake-850`, default border, `depth-panel` | Content groups, tables |
| Sunken | `lake-900` | Sidebar, table header, code-like values |
| Glass | `rgba(18,41,47,.72)` + `backdrop-blur(18px) saturate(1.4)` + hairline | Top bar, menus, modals, drawers, toasts, command palette — *overlays only* |
| Inset | `#0B1C22`, default border | Inputs |
| Stage | Horizon scene or its static fallback, radius 28 | Login hero, dashboard hero |

## Components

- **Buttons.** Primary (marigold, dark text, top highlight, `glow-action` on hover),
  secondary (lake-800 + border), ghost (text, hover fill), danger (crimson). Sizes
  sm 32 / md 40 / lg 48 px. Loading replaces the icon with a spinner and keeps the width.
  Labels name the action ("Record payment", not "Submit").
- **Inputs.** 44 px, inset surface, label above (14/500), help text below (12, mist),
  error below in crimson with an icon. The focus ring is 2 px marigold at 45 % plus a
  marigold border. Native `select` and `date` controls, styled, for accessibility and
  mobile keyboards.
- **Panels.** Header row (title, optional one-line description, actions). No nested panels.
- **Tables.** Sunken sticky header (12/500 mist), 52 px rows, hover `lake-800`,
  row selection shown by a marigold inner bar. Footer: "1–20 of 56" + previous/next.
  On narrow screens, tables scroll horizontally inside their panel with edge shadows.
- **Status pill.** Tone dot + label, full radius.
- **Modal.** Glass, radius 22, max width 560 px, scale-and-fade in (220 ms), Esc and
  backdrop close (blocked while saving). Destructive confirmations name the object.
- **Drawer.** Right-side glass sheet, 520 px, slides in (360 ms). Used for detail and
  edit, so the list stays in view.
- **Menu / dropdown.** Glass, radius 14, keyboard navigable.
- **Toasts.** Bottom-right, glass, tone edge; the message mirrors the action
  ("Payment recorded"). Auto-dismiss after 4 s; errors stay until dismissed.
- **Skeletons.** Rounded `lake-800` blocks with a slow shimmer; shaped like the content.
- **Empty state.** Icon, one sentence explaining what will appear, one primary action.
- **Error state.** What failed, in plain words, and a Retry button. 403 explains that
  the account's role cannot see this.
- **KPI tile.** Figure (Figure style), label, one line of context. Never a gradient.

## Navigation

- **Sidebar** (248 px, collapses to 72 px icons on desktop; off-canvas below 1024 px).
  The brand mark — the fishtail peak in marigold — sits at the top. Staff links are
  grouped: *Overview*, *Residents*, *Daily life*, *Money*, *Knowledge*. The current item
  gets a marigold bar, `snow` text and a `lake-800` fill.
- **Top bar** (glass, sticky): menu button (mobile), "Go to…" command palette (Ctrl/⌘ K),
  notifications bell with unread count, user menu (account, effects preference, sign out).
- **Page header:** title (Title style), one-line description, primary action on the right.

## Motion

| Token | Value | Use |
|---|---|---|
| `instant` | 90 ms | Press feedback |
| `quick` | 160 ms | Hover, state change |
| `base` | 220 ms | Menus, modals, toasts |
| `slow` | 360 ms | Drawers, page-level reveals |
| `cinematic` | 1400 ms | The horizon light rising (once per visit) |
| `ease-out` | `cubic-bezier(.22,1,.36,1)` | Entrances |
| `ease-in-out` | `cubic-bezier(.65,0,.35,1)` | Moves |

Motion answers people: opening, closing, confirming, loading → loaded. The only
unprompted motion is the horizon scene (slow mist and camera drift). With
`prefers-reduced-motion`, or with the *Reduce effects* preference, scenes render one still
frame and transforms are disabled.

## 3D visual language

| Scene | Where | Purpose | Behaviour |
|---|---|---|---|
| **Machhapuchhre horizon** | Login (full height), dashboard hero band | Identity, sense of place | Faceted low-poly ridge with the fishtail twin summit, snow by altitude, alpenglow key light from the right, glacier fill from the left, lake reflection, slow mist particles, ±2° camera drift, gentle pointer parallax |
| **Block model** | Rooms (warden/staff) | See occupancy at a glance | Each block drawn as stacked floors of room slabs coloured by occupancy (vacant, partly filled, full, maintenance, closed); hover to identify, click to open the room drawer; drag to orbit. A 2D grid shows the same data and is the keyboard/mobile path |

Rules:

1. At most one WebGL canvas per page. It is lazy-loaded (`next/dynamic`, no SSR), and
   a static CSS rendering of the same composition shows while it loads or if WebGL is
   unavailable.
2. Budget: ≤ 30k triangles, device-pixel ratio capped at 1.75, rendering paused when
   off-screen or when the tab is hidden.
3. Scenes are pure presentation: data arrives as props, choices leave as callbacks.
   No API calls inside `components/three`.
4. Text never sits directly on a moving scene: a scrim keeps contrast ≥ 4.5:1.
5. The horizon is decorative (`aria-hidden`). The block model is never the only way
   to reach a room.

## Voice

Sentence case, plain verbs, the user's words ("Notices", not "Announcements
management"). A button and its toast use the same verb. Errors say what happened and
what to do; empty screens invite the next action.
