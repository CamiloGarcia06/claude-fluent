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

// ── El temario ───────────────────────────────────────────────────────
// La madurez dice si te acordás de tus tarjetas. El temario dice si tus
// tarjetas cubren el nivel, que es otra pregunta: siete mazos de presente
// simple llegan al 60 % de maduras y dejan sin ver la mitad del programa.
//
// Se pide a mano y no al entrar: es la llamada más lenta del app, cerca de un
// minuto cuando el nivel ya tiene mazos, y nadie quiere esperarla para leer
// una lista de mazos.

function pointRow(point, skillName, levelName) {
  const li = el("li", "point");
  li.dataset.covered = String(Boolean(point.covered_by));

  const name = el("span", "name");
  const title = el("span", "point-title", point.point);
  if (point.english) title.append(el("span", "point-en", point.english));
  name.append(title);
  if (point.note) name.append(el("span", "point-note", point.note));
  li.append(name);

  if (point.covered_by) {
    li.append(el("span", "count", point.covered_by));
    return li;
  }

  // Un punto sin cubrir es lo próximo a generar, y llega escrito en la caja
  // de Agregar en vez de obligarte a recordarlo y teclearlo de nuevo.
  const fill = el("a", "count", "generar");
  fill.href = `#/agregar/${slug(skillName)}/${levelName}/` +
              encodeURIComponent(point.point);
  li.append(fill);
  return li;
}

function renderSyllabus(box, data, skillName, levelName) {
  box.replaceChildren();

  if (!data.points.length) {
    box.append(el("p", "syllabus-note", "El modelo no devolvió ningún punto para este nivel."));
    return;
  }

  box.append(el("p", "syllabus-note",
    `${data.covered} de ${data.total} puntos cubiertos por tus mazos.`));

  const list = el("ul", "rows");
  for (const point of data.points) {
    list.append(pointRow(point, skillName, levelName));
  }
  box.append(list);
}

async function loadSyllabus(button, box, skillName, levelName) {
  button.disabled = true;
  box.hidden = false;
  box.replaceChildren(el("p", "syllabus-note",
    "Leyendo el temario y comparándolo con tus mazos… tarda cerca de un minuto."));

  try {
    const data = await getJSON("/api/syllabus", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ skill: skillName, level: levelName }),
    });
    renderSyllabus(box, data, skillName, levelName);
  } catch (error) {
    // El temario es un extra sobre una pantalla que ya sirve, así que su fallo
    // se queda dentro de su propio panel: no se tira al router ni borra la
    // lista de mazos que está arriba.
    box.replaceChildren(el("p", "syllabus-note", error.message));
  } finally {
    button.disabled = false;
    button.textContent = "Volver a leer el temario";
  }
}

function levelPanel(level, skill, threshold) {
  const section = el("section", "panel");

  const head = el("div", "panel-head");
  const heading = el("h2", null, level.level);
  if (level.level === skill.current_level) {
    heading.append(el("span", "rail-chip", "estás acá"));
  }
  head.append(heading);

  const meta = el("span", "panel-meta");
  meta.append(el("span", "sub", level.total
    ? `${percent(level.maturity)} maduras${level.maturity >= threshold ? " · sostenido" : ""}`
    : "hueco"));
  head.append(meta);
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

  const button = el("button", "ghost syllabus-open", "Ver temario");
  button.type = "button";
  const box = el("div", "syllabus");
  box.hidden = true;
  button.addEventListener("click", () =>
    loadSyllabus(button, box, skill.skill, level.level));
  meta.append(button);
  section.append(box);

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
