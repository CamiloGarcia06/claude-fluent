# Design System — claude-fluent

Applies to `static/`. Written after the Today screen; hold to these values when
adding screens rather than reinventing them.

## Direction

**Personality:** La ficha de cartón — an index card and a Leitner box, not a
dashboard. Quiet, printed, handled daily.

**Foundation:** Cool. Real index card stock is cool white with a printed
blue-grey rule, not warm cream. Warm cream + terracotta was rejected explicitly:
it is the most common look in AI-generated design.

**Depth:** Borders-only. Paper does not levitate. No shadows anywhere except
one inset hairline used to draw a printed rule.

**Feel:** Constancia sin culpa. The screen never reproaches. This is a design
constraint with structural consequences, not a mood word — see the decisions
below.

**Human:** One person, fifteen minutes before work. Opens it, sees what today
holds, starts. Everything else is secondary and must look it.

## Tokens

### Spacing
Base: 4px
Scale: 4, 8, 12, 16, 24, 32, 48 → `--s1` … `--s7`

### Radius
`--r-sm` 3px (day cells) · `--r-md` 6px (buttons, pills, plates)
Small elements get small radius. Nothing above 6px on this screen.

### Colors

```
--paper        #fbfbfa    page ground
--paper-inset  #f4f4f2    recessed: unstudied days, streak pill
--ink          #1b1d20    primary   — headlines, values, studied days
--ink-2        #4a4e54    secondary — body
--ink-3        #7c8188    tertiary  — metadata, counts
--ink-4        #a8adb4    muted     — labels, empty states
--rule         rgba(27,29,32,.13)    panel-head hairline
--rule-faint   rgba(27,29,32,.07)    row separators, printed rule
--rule-blue    rgba(42,85,128,.30)   today's ring — the card's blue ruling
--present      #2a5580    THE ACCENT — writing ink
--kraft        #8a6f4a    divider-tab tan — the grace day
--alarm        #a8342a    system failure only, never the person
```

Dark mode keeps one hue per role and shifts only lightness. `--present`
brightens to `#7ba9d4`; shadows are not used, so nothing needs re-tuning.

**Red is only ever a failure of the system** (`--alarm`), never an action and
never a state of the person. See the reversal in the decisions table.

### Typography

Font: system stack (`ui-sans-serif, system-ui, …`) + `ui-monospace` for figures.
No web font: the app is local-only and must work offline, and adding one would
mean touching `index.html`.

Sizes in use: **11 · 12 · 13 · 15 · 16 · 34** (28 for h1 under 880px).
Weights: **500, 600** only — 400 comes from the body default.

This is not a ratio scale, deliberately. It is one hero size (34) and a tight
utility band (11–16). Inside that band the separation comes from **weight,
colour and family**, not size:

```
value  16/600  --ink        mono for figures
row    15/400  --ink
meta   13/400  --ink-3
count  12/500  --ink-3   mono, tabular-nums
label  11/500  --ink-4   mono, uppercase, .10em tracking
```

Large type tightens: h1 is `-0.022em`, h2 `-0.006em`.
Every figure that can change gets `font-variant-numeric: tabular-nums`.

## Patterns

### Button primary (`#start`)
48px min-height · 16px 32px padding · 6px radius · 16px/600 ·
filled `--present`, text `--present-ink` ·
hover `brightness(1.08)` · active `scale(.975)` · 110–140ms `cubic-bezier(.23,1,.32,1)`

### Calendar day
`aspect-ratio: 1` · 3px radius · 8px gap · 10 per row
- unstudied — `--paper-inset` + `inset 0 0 0 1px --rule-faint`. **Never a border, never a fill.**
- studied — solid `--ink`, no ring
- before the first ever review — transparent, hairline only, `opacity .4`. Days
  the app did not exist for are not days you missed, and drawing them like
  unstudied days turns an empty history into a wall of failure.
- today — `:last-child`; ring in `--rule-blue` plus a 2px `--present` bar 6px below

### List row (`.rows li`)
flex, baseline-aligned · 12px 8px padding · 1px `--rule-faint` bottom, none on last ·
name 15px `--ink`, flex:1 · count mono 12px tabular `--ink-3`, nowrap

### Panel head
flex, space-between, baseline · 8px bottom padding · 1px `--rule` bottom ·
h2 16/600 `--ink` · action link 12px `--ink-3`
Panels themselves carry **no border and no background**.

### Streak pill
mono 13/500 tabular · 8px 12px · 6px radius · `--paper-inset` on 1px `--rule-faint`

### Grace note
13px · `--kraft` on `--kraft-dim` · 8px 12px · 6px radius · `max-width: 48ch`

## Motion

Only the Today screen animates, and only on load. The review flow gets nothing:
anything you cross a hundred times must be instant.

**Budget: the whole entrance ends at 300ms.** `TOTAL_MS 300 · DURATION_MS 190`,
and the cascade takes whatever slack is left — `stagger = (300-190)/(n-1)`. Adding
decks or struggling cards changes the step, never the total.

| Element | Animation |
|---|---|
| Calendar days | `opacity [0,1]` + `scale [.85,1]`, staggered, `outQuad` |
| Deck and struggling rows | `opacity [0,1]` + `y [6,0]`, staggered, `outQuad` |
| Streak | counts up to its value over 300ms, `outExpo`; skipped at zero |

Rules that hold for anything added later:

- **Only `opacity` and transforms.** Never width/height/margin — they trigger
  layout and drop frames.
- **Never blocking.** Nothing is awaited and nothing is made unclickable: the
  start button responds from the first frame.
- **Motion is a bonus, never a dependency.** `anime.esm.js` loads through a
  dynamic import inside a try/catch, and the initial hidden state is set by the
  animation, not by CSS. If the module fails, the page renders normally instead
  of staying invisible.
- **`prefers-reduced-motion` skips the import entirely.**
- anime.js v4.5.0 is vendored at `static/anime.esm.js`, not pulled from a CDN:
  the app is local-only and a failed import would take the whole module down.

### Repair panel
Bordered plate (1px `--rule`, 6px radius, 24px padding) — the one boxed region
on the screen, because it is a modal task sitting inside a passive page.
Before/after in two equal columns; unchanged fields drop to `opacity .55` so the
eye lands only on what would change. The "después" side of a changed field takes
a `--rule-blue` border. **No red anywhere:** a stuck card is work in progress,
not a verdict.

### Buttons
- primary `.actions button` — 40px min-height · 12px 24px · 14px/600 · filled `--present`
- ghost `.ghost` — 13px/500 `--ink-2` on transparent, 1px `--rule`
- disabled — `opacity .45`, `cursor: default`

## Empty states

The screen must read as well on day one as on day one hundred. Full data is the
easy case; these are the ones that decide whether it feels encouraging.

| Condition | Behaviour |
|---|---|
| Nothing due | `#start` hidden and disabled, `#add-cards` takes its place as the primary action. A button that leads nowhere is worse than no button. |
| Calendar days before the first review | Hairline only at `opacity .4` — see the pattern above |
| Streak under 7 days | The grace-day notice is hidden. There is no streak worth protecting yet, and reassurance about a rule you have not needed reads as a warning. |
| No card clears the struggling gates | The whole "Vengo fallando" panel is hidden, not shown empty. A heading over an empty list invents a problem out of an absence of evidence. |

## Rejected defaults

| Default | Instead |
|---|---|
| GitHub contribution graph (green, intensity ramp) | Monochrome ink; absence is unmarked paper |
| Row of bordered stat cards | One sentence in 34px — it reads as a sentence |
| Red/amber on the failing cards | No colour at all; they are the work, not a verdict |
| Red as the accent | Reversed — see the decisions table |
| A border around every panel and row | Hairlines between, air around |
| Warm cream + terracotta | Cool card stock + margin red |

## Decisions

| Decision | Rationale | Date |
|---|---|---|
| A day not studied is paper, not a hole | The whole emotional premise. Empty cells carry no border and no fill, so absence never accuses. This is what rules out the contribution-graph pattern. | 2026-08-18 |
| ~~Red means the present~~ → **the accent is writing ink, `#2a5580`** | Reversed. Two problems with the red. Red reads as danger or error in every interface anyone has used, and `Empezar` is the most positive action on the screen. And `--present` `#b23a2e` sat ten degrees of hue from `--alarm` `#a8342a`, so the action colour and the error colour were nearly indistinguishable — the accent was competing with the one thing that must never be missed. Blue-black ink is just as native to the index-card world and carries none of that. **Red is now reserved entirely for `--alarm`.** | 2026-08-18 |
| One accent, on `#start`, `#add-cards` and today's calendar mark | Still one accent used with intention — only the hue changed. | 2026-08-18 |
| No red anywhere in "vengo fallando" | Where a default design reaches for red. These are cards being worked on; colouring them red is a reproach. | 2026-08-18 |
| The grace sentence gets its own kraft plate | "faltar una vez no borra la racha" does the emotional work of the screen. Muted grey fine print buries it. | 2026-08-18 |
| Borders-only depth | It is a tool and the metaphor is paper. Mixing depth strategies is the fastest way to look unsystematic. | 2026-08-18 |
| Panels and rows lose their boxes | Six bordered rows read as a parking lot, and boxes make every region a peer of every other. Hierarchy comes from space and tone. | 2026-08-18 |
| The hero carries no box | With a border it becomes a peer of the panels below. It is not one — it is the only focal point. | 2026-08-18 |
| System font stack, no web font | Local-only app, must work offline, and a web font would mean editing `index.html`. **Known weak point:** this is where the design is closest to a default. Revisit with an embedded `@font-face` if it ever matters. | 2026-08-18 |
| One hue per role, lightness only, across themes | Different hues for different surfaces fragment the space. Dark mode inverts values, not identity. | 2026-08-18 |

## Consistency checks

- Spacing on the 4px grid. No raw px outside the `--s*` scale.
- Borders-only. If a shadow appears, it is a bug (the one inset hairline aside).
- Colours from the palette above. No literal hex in component rules.
- `[hidden] { display: none !important; }` must stay: the page toggles four
  elements with the attribute, and any `display` rule would outrank the UA
  stylesheet and strand them visible.
- New figures get `tabular-nums`. New interactive elements get hover, active
  and `:focus-visible`.
