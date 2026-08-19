// Atascos — the cards you keep failing, what they cost, and the repair.
//
// The band at the top is the whole point: without the comparison the screen is
// a list of your mistakes and reads as a reproach. With it, it is a place where
// a handful of edits buy back real minutes.
//
// No colour anywhere, severity included. Red is reserved for failures of the
// system, and these cards are the work, not a verdict. The order already says
// which one hurts most.

import { $, el, emptyRow, plural, percent, minutes, getJSON } from "/ui.js";
import * as repair from "/repair.js";

const FILTERS = [
  { key: "todas", label: "Todas" },
  { key: "crítica", label: "Críticas" },
  { key: "alta", label: "Altas" },
  { key: "media", label: "Medias" },
];

const MARKUP = `
<div id="stuck">
  <section class="hero">
    <p id="date" class="date">Atascos</p>
    <h1 id="due-headline"></h1>
    <div class="hero-foot">
      <span id="impact-cards" class="streak"></span>
      <span id="impact-time" class="streak"></span>
    </div>
  </section>

  <section class="panel" id="stuck-panel">
    <div class="panel-head">
      <h2>Ordenadas por tiempo perdido</h2>
      <span class="sub" id="stuck-window"></span>
    </div>
    <div id="stuck-filters" class="filters"></div>
    <ul id="stuck-rows" class="rows"></ul>
  </section>
</div>
`;

let cards = [];
let active = "todas";

function cardRow(card) {
  const name = card.front || `carta ${card.card_id}`;
  const li = el("li", "stuck-row");

  const left = el("span", "name");
  left.append(el("span", "stuck-front", name));
  left.append(el("span", "tag", `${card.severity} · ${card.deck.split("::").pop()}`));

  const counts = el("span", "count",
    `${card.failures} de ${card.attempts} · ${Math.round(card.avg_duration_ms / 1000)} s · ${minutes(card.seconds_lost)}`);

  li.append(left, counts);
  const control = repair.button(card, name);
  if (control) li.append(control);
  return li;
}

function paint() {
  const shown = active === "todas"
    ? cards
    : cards.filter((c) => c.severity === active);

  const list = $("stuck-rows");
  list.replaceChildren();
  if (!shown.length) {
    list.append(emptyRow(cards.length
      ? "Ninguna tarjeta en esta severidad."
      : "Ninguna tarjeta llega a atascada. Nada que arreglar."));
  } else {
    for (const card of shown) list.append(cardRow(card));
  }

  for (const button of document.querySelectorAll("#stuck-filters button")) {
    button.dataset.active = String(button.dataset.key === active);
  }
}

function renderFilters() {
  const bar = $("stuck-filters");
  bar.replaceChildren();
  for (const filter of FILTERS) {
    const count = filter.key === "todas"
      ? cards.length
      : cards.filter((c) => c.severity === filter.key).length;
    if (!count && filter.key !== "todas") continue;

    const button = el("button", "chip", `${filter.label} (${count})`);
    button.type = "button";
    button.dataset.key = filter.key;
    button.addEventListener("click", () => { active = filter.key; paint(); });
    bar.append(button);
  }
}

function renderImpact(impact) {
  $("due-headline").textContent = impact.cards
    ? `${plural(impact.cards, "tarjeta te está costando", "tarjetas te están costando")} ${minutes(impact.seconds)}`
    : "Ninguna tarjeta te está costando de más";

  const hasContext = impact.cards > 0 && impact.total_cards > 0;
  $("impact-cards").hidden = !hasContext;
  $("impact-time").hidden = !hasContext;
  if (!hasContext) return;

  $("impact-cards").textContent =
    `${percent(impact.card_share)} de la colección (${impact.cards} de ${impact.total_cards})`;
  $("impact-time").textContent =
    `${percent(impact.time_share)} del tiempo (${minutes(impact.seconds)} de ${minutes(impact.total_seconds)})`;
}

async function load() {
  const data = await getJSON("/api/stuck");
  cards = data.cards;

  renderImpact(data.impact);
  $("stuck-window").textContent = `últimos ${data.window.days} días`;
  renderFilters();
  paint();
}

export async function render(root) {
  root.innerHTML = MARKUP;
  $("stuck").querySelector(".hero").after(repair.mount({ onApplied: load }));
  await load();
}
