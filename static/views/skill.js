// One skill's library: its decks grouped by level, with the maturity of each
// and the level you are standing on. Five routes, one view — only the filter
// changes.
//
// It is not a review screen. Studying happens in Anki; the rows here only
// decide which deck it opens on.

import { $, el, plural, percent, getJSON, catalog } from "/ui.js";
import { rail, slug } from "/views/progress.js";

const topicOf = (deck) => deck.split("::").pop();

const MARKUP = `
<div id="skill">
  <section class="hero">
    <p id="date" class="date">Habilidad</p>
    <h1 id="due-headline"></h1>
    <p id="start-hint" class="hint" hidden></p>
    <div class="hero-foot">
      <span id="skill-standing" class="streak"></span>
      <span id="skill-rail" class="rail-solo"></span>
    </div>
  </section>
  <div id="levels"></div>
</div>
`;

function deckRow(deck) {
  const li = el("li");
  li.append(el("span", "name", topicOf(deck.deck)));

  const counts = deck.due
    ? `${deck.total} tarjetas · ${deck.due} para hoy`
    : `${plural(deck.total, "tarjeta", "tarjetas")} · al día`;
  li.append(el("span", "count", counts));

  if (deck.due > 0) {
    const study = el("button", "ghost", "Estudiar");
    study.type = "button";
    study.addEventListener("click", () => openInAnki(deck.deck, study));
    li.append(study);
  }
  return li;
}

function levelPanel(level, skill, threshold) {
  const section = el("section", "panel");

  const head = el("div", "panel-head");
  const heading = el("h2", null, level.level);
  if (level.level === skill.current_level) {
    heading.append(el("span", "rail-chip", "estás acá"));
  }
  head.append(heading);
  head.append(el("span", "sub", level.total
    ? `${percent(level.maturity)} maduras${level.maturity >= threshold ? " · sostenido" : ""}`
    : "hueco"));
  section.append(head);

  const list = el("ul", "rows");
  if (!level.decks.length) {
    // The hole is the finding, so it says what to do about it rather than
    // leaving a blank where a list should be — and the way out is one click,
    // carrying the level with it.
    const li = el("li", "empty");
    li.append(el("span", null, "Sin mazos en este nivel. "));
    const fill = el("a", null, "Generar las primeras tarjetas");
    fill.href = `#/agregar/${slug(skill.skill)}/${level.level}`;
    li.append(fill);
    list.append(li);
  } else {
    for (const deck of level.decks) list.append(deckRow(deck));
  }
  section.append(list);
  return section;
}

function showHint(text) {
  $("start-hint").textContent = text;
  $("start-hint").hidden = false;
}

async function openInAnki(deck, button) {
  button.disabled = true;
  showHint("Abriendo Anki…");
  try {
    const data = await getJSON(`/api/study?deck=${encodeURIComponent(deck)}`,
                               { method: "POST" });
    showHint(`Anki está en “${data.deck}”, con ${plural(data.due, "tarjeta", "tarjetas")}. ` +
             `Si la ventana no saltó al frente, cambiá a ella.`);
  } catch (error) {
    showHint(error.message);
  } finally {
    button.disabled = false;
  }
}

export async function render(root, params) {
  root.innerHTML = MARKUP;
  const data = await catalog();

  const skill = data.skills.find((s) => slug(s.skill) === params[0]);
  if (!skill) {
    $("due-headline").textContent = "Esa habilidad no existe";
    $("skill-standing").textContent = "Las habilidades son Grammar, Writing, Speaking, Listening y Reading.";
    return;
  }

  $("due-headline").textContent = skill.skill;
  $("skill-standing").textContent = skill.total
    ? `Estás en ${skill.current_level} · ${percent(skill.maturity)} maduras`
    : "Sin ninguna tarjeta todavía";
  $("skill-rail").append(rail(skill, data.maturity_threshold));

  const levels = $("levels");
  levels.className = "columns";
  for (const level of skill.levels) {
    levels.append(levelPanel(level, skill, data.maturity_threshold));
  }
}
