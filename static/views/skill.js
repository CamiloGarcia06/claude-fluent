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

function pointRow(point, data, skillName, levelName) {
  // `covered === null` es la cobertura todavía en vuelo. No es "no cubierto":
  // marcar el punto como hueco y ofrecer "generar" sería afirmar algo que
  // nadie miró aún, y cuarenta segundos después se desdice solo.
  const pending = data.covered === null;

  const li = el("li", "point");
  li.dataset.covered = pending ? "pending" : String(Boolean(point.covered_by));

  const name = el("span", "name");
  const title = el("span", "point-title", point.point);
  if (point.english) title.append(el("span", "point-en", point.english));

  // El acuerdo entre borradores es dónde mirar, no una nota: tres de tres es
  // el modelo seguro, uno de tres es el modelo dudando y ahí decidís vos. Un
  // punto que escribiste a mano no tiene acuerdo que mostrar, y es correcto:
  // no salió de ningún borrador.
  if (point.drafts && data.drafts) {
    const mark = el("span", "point-drafts");
    for (let i = 1; i <= data.drafts; i += 1) {
      const dot = el("span");
      dot.dataset.on = String(i <= point.drafts);
      mark.append(dot);
    }
    mark.title = `${point.drafts} de ${data.drafts} borradores nombraron este punto`;
    title.append(mark);
  }

  name.append(title);
  if (point.note) name.append(el("span", "point-note", point.note));
  li.append(name);

  if (pending) return li;

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

function syllabusFoot(data, onRegenerate) {
  const foot = el("p", "syllabus-note");
  const when = (data.generated || "").slice(0, 10);
  foot.append(el("span", null, data.edited
    ? `Temario editado a mano. Generado el ${when} con ${data.drafts} borradores.`
    : `Temario congelado el ${when}, de ${data.drafts} borradores. ` +
      `Editalo en data/syllabus/.`));

  const again = el("button", "ghost syllabus-again", "Regenerar");
  again.type = "button";
  again.addEventListener("click", () => {
    // Regenerar pisa el archivo, y si lo editaste ese trabajo no vuelve. Es la
    // única acción destructiva de esta pantalla, así que pregunta — y sólo
    // cuando hay algo que perder.
    const lost = data.edited
      ? "Editaste este temario a mano. Regenerarlo pisa esos cambios y no hay vuelta atrás. ¿Seguimos?"
      : "Volver a generar el temario tarda un par de minutos. ¿Seguimos?";
    if (window.confirm(lost)) onRegenerate();
  });
  foot.append(again);
  return foot;
}

function renderSyllabus(box, data, skillName, levelName, onRegenerate) {
  box.replaceChildren();

  if (!data.points.length) {
    box.append(el("p", "syllabus-note", "El modelo no devolvió ningún punto para este nivel."));
    return;
  }

  box.append(el("p", "syllabus-note", data.covered === null
    ? "Comparando el temario con tus mazos… cerca de un minuto."
    : `${data.covered} de ${data.total} puntos cubiertos por tus mazos.`));

  const list = el("ul", "rows");
  for (const point of data.points) {
    list.append(pointRow(point, data, skillName, levelName));
  }
  box.append(list, syllabusFoot(data, onRegenerate));
}

async function loadSyllabus(button, box, skillName, levelName, regenerate = false) {
  // Dos paneles pueden estar cargando a la vez y "Regenerar" puede pisar una
  // cobertura en vuelo, así que cada corrida deja su número en el panel y sólo
  // pinta si sigue siendo la última.
  const ticket = String(Number(box.dataset.run || 0) + 1);
  box.dataset.run = ticket;
  const mine = () => box.dataset.run === ticket;

  button.disabled = true;
  box.hidden = false;

  const again = () => loadSyllabus(button, box, skillName, levelName, true);
  const post = (path, extra) => getJSON(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ skill: skillName, level: levelName, ...extra }),
  });

  box.replaceChildren(el("p", "syllabus-note", regenerate
    ? "Generando el temario de nuevo: tres borradores y una fusión. Un par de minutos."
    : "Leyendo el temario…"));

  let painted = false;

  try {
    // El temario está congelado en disco: llega en milisegundos y se pinta
    // antes de pedir nada más. Al modelo sólo se lo llama si este nivel
    // todavía no tiene temario —una vez en su vida— o si pediste regenerarlo.
    let data = regenerate ? { frozen: false } : await getJSON(
      `/api/syllabus?skill=${encodeURIComponent(skillName)}` +
      `&level=${encodeURIComponent(levelName)}`);
    if (!mine()) return;

    if (!data.frozen) {
      box.replaceChildren(el("p", "syllabus-note", regenerate
        ? "Generando el temario de nuevo: tres borradores y una fusión. Un par de minutos."
        : "Primera vez de este nivel: tres borradores y una fusión. Un par de minutos."));
      data = await post("/api/syllabus", { regenerate });
      if (!mine()) return;
    }
    renderSyllabus(box, data, skillName, levelName, again);
    painted = true;

    // Y recién ahora la mitad lenta. Cambia con cada tarjeta que escribís, así
    // que se deriva siempre —pero con los puntos ya en pantalla, que es la
    // diferencia entre esperar y creer que empezó de cero.
    const covered = await post("/api/syllabus/coverage");
    if (!mine()) return;
    renderSyllabus(box, covered, skillName, levelName, again);
  } catch (error) {
    // El temario es un extra sobre una pantalla que ya sirve, así que su fallo
    // se queda dentro de su propio panel: no se tira al router ni borra la
    // lista de mazos que está arriba. Y si los puntos ya están pintados, el
    // aviso se agrega debajo: que se caiga la cobertura no es razón para
    // borrar el temario, que se leyó bien.
    if (!mine()) return;
    const note = el("p", "syllabus-note", error.message);
    if (painted) box.append(note); else box.replaceChildren(note);
  } finally {
    if (mine()) button.disabled = false;
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
