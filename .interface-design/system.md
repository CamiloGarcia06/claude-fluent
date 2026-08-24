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
`--r-sm` 3px (day cells, rail segments) · `--r-md` 6px (nav items)

Anything with a drawn outline — buttons, pills, plates, the search field, the
repair panel — takes one of the two **hand-drawn corners** instead:

```
--r-rough:     9px 20px 12px 16px / 16px 10px 18px 12px
--r-rough-alt: 18px 9px 16px 12px / 11px 18px 12px 16px
```

Eight values, the two axes of each corner disagreeing slightly, so no corner
matches another and the outline reads as drawn rather than constructed.
**Alternate the two between neighbours** — the giveaway of the trick is every
box wobbling identically.

Deliberately modest. The widely copied version of this trick uses 255px/15px,
which is charming on a small button and a lens on a 1080px panel. Excalidraw's
own corners are restrained: what reads as hand-drawn there is the wobble of the
stroke, not the size of the arc.

The small squares keep `--r-sm`. A day cell or a rail segment given a 20px
corner stops being a square and becomes a pill.

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

**Text is Excalifont**, the Excalidraw hand, SIL OFL 1.1, vendored at
`static/fonts/` for the same reason anime.js is vendored: the app is local-only
and must work offline. One 25 KB subset covers every character the interface
renders; `font-display: swap` paints in the fallback first, and the system stack
stays behind it in `--font` so a missing glyph degrades instead of showing tofu.

**Figures stay `ui-monospace`.** This is now the strongest pairing in the
system, not a leftover: printed monospaced numerals inside handwritten text is
a form that was typeset and then filled in by hand, which is exactly what an
index card is. It also keeps `tabular-nums` — the animated streak counter would
jitter on a proportional hand font.

Sizes in use: **11 · 12 · 13 · 15 · 16 · 22 · 34** (28 for h1 under 880px).
The 22 arrived with the dashboard and is the only figure size outside the
utility band: the four stats and the ring's fraction. It is not a second hero
size — it never carries a sentence, only a number, and always in mono.
Weights: **500, 600** — 400 comes from the body default. Excalifont ships one
real weight, so 500 and 600 are synthesised. The hierarchy survives because it
never rested on weight alone: colour, family and size carry it.

**No negative tracking anywhere.** Large type used to tighten (`-0.022em` on
h1); a hand does not tighten, it collides. All headings sit at `0`.

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
One per screen. On Hoy it sits in the hero; on the Dashboard it sits under the
ring at full width — a 32px-padded button centred under a 160px circle reads as
a footnote. Two copies of it on one screen turn the focal point into
decoration, which is what merging Hoy into the Dashboard produced.
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

### Sidebar
`15rem` column · 1px `--rule-faint` right edge, no fill and no shadow ·
sticky, `max-height: 100vh`, scrolls on its own ·
items 14px `--ink-3`, `8px 12px`, 6px radius, 1px apart ·
hover `--ink` on `--paper-inset` ·
active `--ink` on `--paper-inset` + `inset 2px 0 0 --present` ·
section label mono 11/500 uppercase `.10em` `--ink-4` ·
level chip mono 11/500 `--ink-4`, `--present` when active
Under 880px it becomes a horizontal bar and the active rule moves to the
bottom edge.

### Rail segment (A1–C1)
8px tall track · 3px radius · `--paper-inset` + `inset 0 0 0 1px --rule-faint` ·
fill `--ink` at the maturity percentage · level letter mono 11 `--ink-4` below
- empty level — transparent, hairline only, `opacity .4`. **The calendar's
  "before you started" treatment.** A level you never began is not one you failed.
- current level — letter turns `--present`, plus a 2px `--present` bar 4px
  below the track. The same mark today's cell carries.

### Dashboard grid
The Dashboard's four sections are cells of **one** two-column grid
(`1.35fr 1fr`, 48px gap, `align-items: start`), never two independently stacked
columns. With a column per side each panel begins where the one above it ends,
so the second row lands at two different heights and stops reading as a row —
the reason the first build of this screen was dizzying. 1.35/1 because the week
needs width for seven columns and the ring does not grow either way.

**What may sit on the Dashboard:** the four sections of the wireframe and
nothing else. The 30-day calendar and the stuck cards stay on Hoy and Atascos,
where they already were. And the Dashboard is **last in the menu**: Hoy is
where you start, this is where you look.

### Stat strip (dashboard)
Four figures under the hero, `repeat(4, 1fr)`, divided by a 1px `--rule-faint`
**left border** on every cell but the first — no plates. Four bordered cards
would make each number a panel and flatten the hierarchy the hero just set; a
card is divided with ruled lines, not with frames.
label mono 11/500 uppercase `.10em` `--ink-4` · value mono 22/600 tabular
`--ink` · meta 13px `--ink-3`.
Under 880px it folds to two columns and the odd cells drop their rule.

**What may be a stat:** only what depends on showing up today. Precisión and
Tiempo estudiado were in the wireframe and stay out — they are cumulative, and
a cumulative figure has no action attached to it.

### Weekly bars
Seven columns, 96px track (72px under 880px), a 1px `--rule-faint` baseline and
no track fill. Bar `--ink`, `--r-sm` on the top corners only, `transform-origin:
bottom`. A day with no reviews draws **nothing** above the baseline — unmarked
paper, the calendar's rule. Days before the first ever review sit at
`opacity .4`. Today's column takes the accent: the letter turns `--present` and
a 2px `--present` bar sits 3px under the baseline — the same mark as today's
calendar cell and the level you stand on.
A single review is floored at 6 % of the track: below that the bar vanishes and
a day you did study reads as empty.

### Today's ring
160px, `r 56`, 10px stroke. Track `--paper-inset`, arc `--present`, round cap,
rotated `-90deg` so it starts at twelve. Centre: fraction mono 22/600 tabular
`--ink` over a mono 11 uppercase `--ink-4` unit.
It is **hecho hoy / (hecho + pendiente)** — the only fraction on the screen that
closes by showing up, which is why it may hold the accent. With both at zero it
draws no ring at all: an empty dial at 0 % is the bleakest possible reading of a
day with nothing scheduled.
It carries **no button.** The wireframe repeated "Empezar sesión" under it; two
copies of the primary action 400px apart turn the focal point into decoration.

### Skill meter (dashboard)
The rail's vocabulary in a single 8px segment: `--paper-inset` track with an
inset hairline, `--ink` fill at the maturity share, `transform-origin: left`.
A skill with no cards is transparent at `opacity .4` and its count reads `—`,
not `0 %` — a skill you never began is not one you failed.
The five-segment A1–C1 rail stays on Progreso: here the question is which skill
is furthest behind, not which level you are on.

### Generation table (Agregar)
**One table, not a panel per term.** The header FRONT · BACK · EJEMPLO is read
once at the top and each term is a group row inside it, carrying its count and
its deck picker on the right. A panel per term repeats the header three times
and turns a list into a stack of boxes.
**Nothing is ticked by default.** Every candidate is a decision — a screen that
arrives with thirty cards pre-approved is not an approval step.
Four columns on a hairline-separated list, never a bordered table: box · front ·
back · example. Example at 13px `--ink-3`, a step behind the translation.
A card you already own is shown at `opacity .55` with a mono `--ink-4` tag
saying which deck it is in, and its box is disabled — hiding it would leave you
wondering whether the model forgot it or you already had it. **No red:** an
existing card is not an error.
`editar` swaps the three cells for inputs bordered in `--rule-blue`, the same
mark the repair panel puts on the side that would change.

### Progress rows (Agregar)
One row per term: name · 8px track · state. Queued rows sit at `opacity .55`
(unmarked paper), the running one takes `--present` on its label — it is the
here and now of that screen — and a failed one is the one place `--alarm`
appears on this screen, because a `claude -p` that died is a failure of the
system.
The bar runs to `scaleX(.9)` over the measured 15s and only completes when the
answer lands. A bar that reaches 100 % and keeps waiting is worse than no bar.

### Proposed terms list
Its own two-column row (`14rem 1fr`), **not `.rows`**: there the second column
is a mono count with `white-space: nowrap`, so a whole sentence dropped into it
squeezed the first column to one character per line and printed the term
vertically. A reason is prose — 13px `--ink-3`, wrapping like prose.

### Deck picker
Suggestion first (tagged `· nuevo` when it does not exist yet), then every
existing deck, then "Mazo nuevo…", which opens skill + level + topic controls
and shows the resulting `Skill::Level::Topic` in mono `--ink-4` as you type.
The name is never free text: the convention is what every level in the app is
derived from, and a hand-typed path lands in "sin clasificar".

### Sticky action bar
The write decision stays on screen however long the list gets: `position:
sticky; bottom: 0`, `--paper` ground, 1px `--rule` top edge, count on the left
in 13px `--ink-3`, primary button on the right. Disabled at zero selected, and
its label carries the number — "Agregar 3 tarjetas", never a bare "Agregar".
**The outcome is reported in the bar itself**, right of the count: a write that
failed said so in the hero, a full screen of scrolling above the button that
had just been pressed, which is the same as not saying it. Red here only when
the write actually failed — the one licence `--alarm` has on this screen.

### Goal bar (Hoy)
Under the hero, before anything else: `12 de 40` in mono 16/600 on the left, the
backlog in 13px `--ink-3` on the right, and the 8px meter under both. The bar is
the rail's vocabulary again — `--paper-inset` track, `--ink` fill.
**What may be the headline:** the goal. The backlog is never the sentence at the
top; it sits in grey with its reason ("la meta es lo de hoy"), because a number
you cannot clear today is a bill, not an invitation.

### Topic chips (Hoy)
One chip per deck with cards due: topic on the left, count in mono `--ink-3` on
the right, hand-drawn outline alternating `--r-rough` / `--r-rough-alt`. A theme
is a deck, so picking one and opening it are the same act — and it is the only
shape available, since AnkiConnect cannot build a filtered deck out of two.

### Streak pill
mono 13/500 tabular · 8px 12px · 6px radius · `--paper-inset` on 1px `--rule-faint`

### Grace note
13px · `--kraft` on `--kraft-dim` · 8px 12px · 6px radius · `max-width: 48ch`

## Motion

Only Hoy and the Dashboard animate, and only on load. The review flow gets
nothing: anything you cross a hundred times must be instant.

**Budget: the whole entrance ends at 300ms.** `TOTAL_MS 300 · DURATION_MS 190`,
and the cascade takes whatever slack is left — `stagger = (300-190)/(n-1)`. Adding
decks or struggling cards changes the step, never the total.

| Element | Animation |
|---|---|
| Deck and struggling rows | `opacity [0,1]` + `y [6,0]`, staggered, `outQuad` |
| Calendar days | `opacity [0,1]` + `scale [.85,1]`, staggered, `outQuad` |
| Weekly bars | `scaleY [0,1]` from the base, staggered, `outQuad` |
| Skill meters | `scaleX [0,1]` from the left, staggered, `outQuad` |
| Today's ring | `stroke-dashoffset` from empty to its share over 300ms, `outExpo` |
| Streak | counts up to its value over 300ms, `outExpo`; skipped at zero — the pill on Hoy, the stat on the Dashboard |

`scaleY`/`scaleX` and not `height`/`width`: the bars and the meters would
reflow their whole row on every frame. `stroke-dashoffset` is the one property
animated that is neither opacity nor a transform — it repaints a stroke and
never touches layout, which is what the rule is actually protecting.

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
| Nothing done and nothing due today | The ring is not drawn at all — an empty dial at 0 % is the bleakest possible reading of a day with nothing scheduled. |
| No card clears the struggling gates | The whole "Vengo fallando" panel is hidden, not shown empty. A heading over an empty list invents a problem out of an absence of evidence. |
| A skill with no cards | Its meter is transparent at `opacity .4` and its figure reads `—`, not `0 %`. |

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
| ~~System font stack, no web font~~ → **Excalifont, vendored** | Reversed, and the old row predicted it: it was logged as "the known weak point… revisit with an embedded `@font-face` if it ever matters." Both objections turned out to be answerable — vendoring the file keeps the app offline-only, and `index.html` did not have to change because the face is declared in the stylesheet. **The hand-drawn direction is a skin and nothing more:** same DOM, same buttons, same keyboard, same focus, same resize. Only the painting of text and outlines changed. | 2026-08-18 |
| The hand is *handwriting*, not *whiteboard* | The distinction decides whether this looks right or looks like a mockup. A sketchy UI in the whiteboard sense says "provisional", which fights the whole premise of a daily ritual. But the accent was already defined as "the blue-black of writing ink", and a card written by hand is exactly that. The metaphor did not change; it got more literal. | 2026-08-18 |
| No colour was borrowed along with the hand | Excalidraw's palette is many bright strokes. Taking it would undo the single-accent rule the whole system rests on. The look is the line and the letter, never the colour. | 2026-08-18 |
| ~~No sidebar~~ → **left sidebar** | Reversed, because the premise changed rather than the taste. The sidebar was cut when navigation was two links and a column would have been furniture around an empty room. With Progreso, five skill libraries, Mazos, Atascos and Ajustes it is ten destinations, and ten links across one bar is a navigation product. Navigation only: no account, no plan, no brand mark beyond the wordmark. | 2026-08-18 |
| The accent means two things: the primary action, and here-and-now | It was on `#start` and today's calendar mark. Adding the current rail segment and the current sidebar item does not spend a second accent — it says the same word in three places. The rule to hold is the *meaning*, not the count of usages: nothing else may take `--present`. | 2026-08-18 |
| The active sidebar item is a 2px inset rule, not a fill | `--paper-inset` on `--paper` is two steps of lightness and reads as nothing. A rule of ink down the left edge is the index card's own margin rule, and it is the same mark today's cell carries under it. | 2026-08-18 |
| A level with no cards is drawn like a day not studied | Same emotional premise, same treatment: transparent, hairline only, `opacity .4`. A level you never started is not a level you failed, exactly as a day before you began is not a day you missed. | 2026-08-18 |
| Severity on the stuck cards is a mono label, never a colour | Where every default design reaches for red/amber/green. The list is already ordered by time lost, so colour adds no information and does add a verdict. | 2026-08-18 |
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
