// Progreso — tu recorrido A1–C1 por skill.
//
// The hero is what to do next, not the word "Progreso": the same shape as Hoy,
// where the one focal point is the one action. The rails below are the
// diagnosis, and the holes at the bottom are what turns that diagnosis into
// the next batch to generate.

import {
  $, el, plural, percent, getJSON, catalog,
  loadMotion, staggerStep, DURATION_MS,
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
  $("add-cards").dataset.skill = next.skill;
  $("add-cards").dataset.level = next.level;
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

// Una fila por habilidad, no una por nivel. Con una por nivel eran veinte
// filas idénticas que decían "sin mazos" veinte veces —la misma palabra en la
// columna donde tendría que ir la información— y el panel más alto de la
// pantalla estaba dedicado a lo que menos dice. Agrupado son cinco filas, y
// cada nivel que falta es la puerta a generarlo, que es lo que la cabecera
// viene prometiendo.
function renderGaps(data) {
  const list = $("gaps");
  list.replaceChildren();

  const holes = data.skills.filter((skill) => skill.gaps.length);

  // No holes is good news, not an empty list to stare at.
  $("gaps-panel").hidden = holes.length === 0;
  if (!holes.length) return;

  for (const hole of holes) {
    const li = el("li", "gap-row");

    const link = el("a", "name", hole.skill);
    link.href = `#/skill/${slug(hole.skill)}`;

    const levels = el("span", "gap-levels");
    for (const level of hole.gaps) {
      const chip = el("a", "gap-level", level);
      chip.href = `#/agregar/${slug(hole.skill)}/${level}`;
      chip.title = `Generar las primeras tarjetas de ${hole.skill} ${level}`;
      levels.append(chip);
    }

    li.append(link, levels);
    list.append(li);
  }
}

// El riel entra como los medidores del tablero: escala desde la izquierda,
// escalonado, y todo termina a los 300 ms. Escala y no `width`, que reflowaría
// las cinco filas en cada cuadro.
function playEntrance() {
  loadMotion().then((motion) => {
    if (!motion) return;
    const { animate, stagger } = motion;

    const fills = document.querySelectorAll("#rails .seg-fill");
    if (fills.length) {
      animate(fills, {
        scaleX: [0, 1],
        duration: DURATION_MS,
        delay: stagger(staggerStep(fills.length)),
        ease: "outQuad",
      });
    }

    const rows = document.querySelectorAll("#gaps li");
    if (rows.length) {
      animate(rows, {
        opacity: [0, 1],
        y: [6, 0],
        duration: DURATION_MS,
        delay: stagger(staggerStep(rows.length)),
        ease: "outQuad",
      });
    }
  });
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
  playEntrance();

  // The deck named in the headline is the deck Anki opens, so the button does
  // what the sentence above it just promised.
  $("start").addEventListener("click", () =>
    handOverToAnki(
      `/api/study?deck=${encodeURIComponent($("start").dataset.deck)}`,
      $("start"), "Abriendo Anki…",
      (d) => `Anki está en “${d.deck}”, con ${plural(d.due, "tarjeta", "tarjetas")}. ` +
             `Si la ventana no saltó al frente, cambiá a ella.`));

  // El hueco viaja en la ruta, así que la pantalla de generación ya sabe qué
  // nivel venís a llenar y le pide al modelo términos para ese nivel.
  $("add-cards").addEventListener("click", () => {
    const { skill, level } = $("add-cards").dataset;
    location.hash = skill && level
      ? `#/agregar/${slug(skill)}/${level}`
      : "#/agregar";
  });
}
