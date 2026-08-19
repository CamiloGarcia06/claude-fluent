// Progreso — tu recorrido A1–C1 por skill.
//
// The hero is what to do next, not the word "Progreso": the same shape as Hoy,
// where the one focal point is the one action. The rails below are the
// diagnosis, and the holes at the bottom are what turns that diagnosis into
// the next batch to generate.

import {
  $, el, plural, percent, getJSON, catalog,
} from "/ui.js";

export const slug = (skill) => skill.toLowerCase();

// "Grammar::B1::Phrasal verbs" -> "Phrasal verbs". The full path is already
// spelled out by the skill and level beside it.
const topicOf = (deck) => deck.split("::").pop();

const MARKUP = `
<div id="progress">
  <section class="hero">
    <p id="date" class="date">Tu recorrido</p>
    <h1 id="due-headline"></h1>
    <button id="start" type="button" hidden>Empezar</button>
    <button id="add-cards" type="button" hidden>Agregar tarjetas</button>
    <p id="start-hint" class="hint" hidden></p>
    <div class="hero-foot">
      <span id="next-detail" class="streak" hidden></span>
    </div>
  </section>

  <section class="panel">
    <div class="panel-head">
      <h2>Progreso por habilidad</h2>
      <span class="sub" id="rail-sub"></span>
    </div>
    <div id="rails" class="rails"></div>
  </section>

  <section class="panel" id="gaps-panel" hidden>
    <div class="panel-head">
      <h2>Huecos de la colección</h2>
      <span class="sub">lo próximo a generar</span>
    </div>
    <ul id="gaps" class="rows"></ul>
  </section>
</div>
`;

function segment(level, skill) {
  const wrap = el("span", "seg-wrap");

  // An empty level is unmarked paper, exactly like a day you did not study:
  // no fill and no border, so an absence never reads as a failure. The state
  // sits on the wrapper so the current-level mark can hang below the bar
  // without the bar having to clip it.
  wrap.dataset.state = level.total === 0
    ? "empty"
    : (level.maturity >= skill.threshold ? "held" : "partial");
  wrap.dataset.current = String(level.level === skill.current_level);

  const seg = el("span", "seg");
  const fill = el("span", "seg-fill");
  fill.style.width = `${Math.round(level.maturity * 100)}%`;
  seg.append(fill);

  wrap.title = level.total === 0
    ? `${skill.skill} ${level.level} — sin tarjetas`
    : `${skill.skill} ${level.level} — ${level.mature} de ${level.total} maduras`;

  wrap.append(seg, el("span", "seg-label", level.level));
  return wrap;
}

/** The five A1–C1 segments for one skill. The skill screen reuses it. */
export function rail(skill, threshold) {
  const node = el("span", "rail");
  for (const level of skill.levels) {
    node.append(segment(level, { ...skill, threshold }));
  }
  return node;
}

function railRow(skill, threshold) {
  const link = el("a", "rail-row");
  link.href = `#/skill/${slug(skill.skill)}`;

  const name = el("span", "rail-name");
  name.append(el("span", "rail-skill", skill.skill),
              el("span", "rail-chip", skill.current_level));

  const count = el("span", "count", skill.total ? percent(skill.maturity) : "—");

  link.append(name, rail(skill, threshold), count);
  return link;
}

function renderNext(next) {
  const headline = $("due-headline");
  const detail = $("next-detail");

  if (!next) {
    headline.textContent = "Estás al día en las cinco habilidades.";
    return;
  }

  if (next.action === "study") {
    headline.textContent = `Seguís con ${topicOf(next.deck)}`;
    detail.hidden = false;
    detail.textContent = `${next.skill} · ${next.level} · ${plural(next.due, "tarjeta", "tarjetas")}`;
    $("start").hidden = false;
    $("start").dataset.deck = next.deck;
    return;
  }

  // A hole is not a weak level, it is a missing one, so the action is not
  // "study" — there is nothing there to study yet.
  headline.textContent = `Empezá por ${next.skill} ${next.level}`;
  detail.hidden = false;
  detail.textContent = "Todavía no hay ningún mazo en ese nivel";
  $("add-cards").hidden = false;
}

function renderRails(data) {
  const rails = $("rails");
  rails.replaceChildren();
  for (const skill of data.skills) {
    rails.append(railRow(skill, data.maturity_threshold));
  }
  $("rail-sub").textContent =
    `maduras al ${percent(data.maturity_threshold)} sostienen un nivel`;
}

function renderGaps(data) {
  const list = $("gaps");
  list.replaceChildren();

  const holes = data.skills.flatMap((skill) =>
    skill.gaps.map((level) => ({ skill: skill.skill, level })));

  // No holes is good news, not an empty list to stare at.
  $("gaps-panel").hidden = holes.length === 0;
  if (!holes.length) return;

  for (const hole of holes) {
    const li = el("li");
    const link = el("a", "name", `${hole.skill} ${hole.level}`);
    link.href = `#/skill/${slug(hole.skill)}`;
    li.append(link, el("span", "count", "sin mazos"));
    list.append(li);
  }
}

function showHint(text) {
  $("start-hint").textContent = text;
  $("start-hint").hidden = false;
}

async function handOverToAnki(path, button, working, done) {
  button.disabled = true;
  showHint(working);
  try {
    showHint(done(await getJSON(path, { method: "POST" })));
  } catch (error) {
    showHint(error.message);
  } finally {
    button.disabled = false;
  }
}

export async function render(root) {
  root.innerHTML = MARKUP;
  const data = await catalog();

  renderNext(data.next_up);
  renderRails(data);
  renderGaps(data);

  // The deck named in the headline is the deck Anki opens, so the button does
  // what the sentence above it just promised.
  $("start").addEventListener("click", () =>
    handOverToAnki(
      `/api/study?deck=${encodeURIComponent($("start").dataset.deck)}`,
      $("start"), "Abriendo Anki…",
      (d) => `Anki está en “${d.deck}”, con ${plural(d.due, "tarjeta", "tarjetas")}. ` +
             `Si la ventana no saltó al frente, cambiá a ella.`));

  $("add-cards").addEventListener("click", () =>
    handOverToAnki("/api/add-cards", $("add-cards"), "Abriendo Anki…",
      () => "Anki abrió el diálogo de añadir. Si la ventana no saltó al frente, cambiá a ella."));
}
