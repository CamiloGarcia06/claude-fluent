// Mazos — the flat view of the whole collection, no grouping by skill.
//
// It exists for what the skill screens cannot cover: the decks that follow no
// convention, and finding one by name. Unclassified decks sort first — a deck
// the app cannot read is exactly the one worth seeing.
//
// Renaming and archiving are not here yet. AnkiConnect has no renameDeck, so
// it is createDeck + changeDeck + deleteDecks, and that needs a record on disk
// before it may run.

import { $, el, emptyRow, plural, percent, catalog } from "/ui.js";
import { slug } from "/views/progress.js";

const MARKUP = `
<div id="decks-view">
  <section class="hero">
    <p id="date" class="date">Colección</p>
    <h1 id="due-headline"></h1>
    <div class="hero-foot">
      <input id="deck-search" class="search" type="search"
             placeholder="Buscar por nombre…" autocomplete="off" spellcheck="false">
    </div>
  </section>

  <section class="panel">
    <div class="panel-head">
      <h2>Todos los mazos</h2>
      <span class="sub" id="deck-count"></span>
      <!-- Un mazo no se crea vacío: se crea escribiéndole la primera tarjeta,
           y eso pasa en Agregar. -->
      <a href="#/agregar">+ mazo nuevo</a>
    </div>
    <ul id="deck-rows" class="rows"></ul>
  </section>
</div>
`;

function flatten(data) {
  const unclassified = data.unclassified.decks.map((deck) => ({
    ...deck, label: data.unclassified.label, href: null,
  }));

  const classified = data.skills.flatMap((skill) =>
    skill.levels.flatMap((level) =>
      level.decks.map((deck) => ({
        ...deck,
        label: `${skill.skill} · ${level.level}`,
        href: `#/skill/${slug(skill.skill)}`,
      }))));

  // Unclassified first, then alphabetical inside each group.
  return [
    ...unclassified.sort((a, b) => a.deck.localeCompare(b.deck)),
    ...classified.sort((a, b) => a.deck.localeCompare(b.deck)),
  ];
}

function deckRow(deck) {
  // Tres columnas, no una fila flex: con flex la etiqueta empezaba donde
  // terminaba el nombre y las cifras donde terminaba la etiqueta, así que
  // ninguna de las dos se alineaba entre filas.
  const li = el("li", "deck-row");

  const name = deck.href ? el("a", "name", deck.deck) : el("span", "name", deck.deck);
  if (deck.href) name.href = deck.href;

  const meta = el("span", "tag", deck.label);
  const counts = el("span", "count", deck.total
    ? `${deck.total} · ${percent(deck.maturity)} maduras${deck.due ? ` · ${deck.due} hoy` : ""}`
    : "vacío");

  li.append(name, meta, counts);
  return li;
}

function paint(rows, query) {
  const needle = query.trim().toLowerCase();
  const shown = needle
    ? rows.filter((d) => d.deck.toLowerCase().includes(needle))
    : rows;

  const list = $("deck-rows");
  list.replaceChildren();
  if (!shown.length) {
    list.append(emptyRow(needle
      ? `Ningún mazo coincide con “${query.trim()}”.`
      : "Todavía no hay mazos en Anki."));
  } else {
    for (const deck of shown) list.append(deckRow(deck));
  }

  $("deck-count").textContent = needle
    ? `${shown.length} de ${rows.length}`
    : plural(rows.length, "mazo", "mazos");
}

export async function render(root) {
  root.innerHTML = MARKUP;
  const data = await catalog();
  const rows = flatten(data);

  const loose = data.unclassified.decks.length;
  $("due-headline").textContent = loose
    ? `${plural(loose, "mazo sin clasificar", "mazos sin clasificar")}`
    : `${plural(rows.length, "mazo", "mazos")} en la colección`;

  paint(rows, "");
  $("deck-search").addEventListener("input", (e) => paint(rows, e.target.value));
}
