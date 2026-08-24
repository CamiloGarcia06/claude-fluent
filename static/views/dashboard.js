// Dashboard de progreso — la panorámica. Última del menú y no la de entrada:
// a Hoy se entra a empezar, aquí se entra a mirar.
//
// Es la Pantalla 1 del wireframe traída a la ficha de cartón, con sus cuatro
// secciones y ninguna más: actividad semanal · repaso de hoy · progreso por
// habilidad · mis mazos. El calendario de 30 días y las tarjetas atascadas se
// quedan en Hoy y en Atascos, donde ya estaban.
//
// Dos apartes deliberados, ambos escritos en .interface-design/system.md:
//
// · Precisión y Tiempo estudiado no están. Son métricas acumuladas, y este app
//   sólo muestra lo que depende de aparecer hoy. En su lugar la tira lleva los
//   días con estudio de la ventana y cuántas tarjetas están atascadas, que sí
//   se accionan: una manda a estudiar, la otra manda a reparar.
// · Sin buscador ni "+ Nuevo mazo" en la cabecera: buscar es la pantalla de
//   Mazos, y crear un mazo es una escritura en Anki que todavía no existe.

import {
  $, el, row, emptyRow, plural, percent, formatLongDate, weekdayInitial,
  getJSON, catalog, loadMotion, staggerStep, TOTAL_MS, DURATION_MS,
} from "/ui.js";
import { slug } from "/views/progress.js";

// Una semana de barras, no un mes: el calendario de Hoy dice si apareciste, y
// lo que una cuadrícula binaria no puede decir es cuánto.
const WEEK_DAYS = 7;

const RING_RADIUS = 56;
const RING_LENGTH = 2 * Math.PI * RING_RADIUS;

// Las cuatro secciones son celdas de una sola rejilla, no dos columnas
// apiladas por separado. Con dos columnas independientes cada panel empieza
// donde termina el de arriba, y "Progreso por habilidad" y "Mis mazos" quedan
// a alturas distintas: la fila deja de leerse como fila.
const MARKUP = `
<div id="dashboard" hidden>

  <section class="hero">
    <p id="date" class="date"></p>
    <h1>Dashboard de progreso</h1>
  </section>

  <section id="stats" class="stats"></section>

  <div class="dash">

    <section class="panel">
      <div class="panel-head">
        <h2>Actividad semanal</h2>
        <span class="sub" id="week-sub"></span>
      </div>
      <div id="week" class="week"></div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>Repaso de hoy</h2>
      </div>
      <div id="ring" class="ring"></div>
      <div class="ring-action">
        <button id="start" type="button">Empezar sesión</button>
        <button id="add-cards" type="button" hidden>Agregar tarjetas</button>
        <p id="start-hint" class="hint" hidden></p>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>Progreso por habilidad</h2>
        <a href="#/progreso">ver el recorrido</a>
      </div>
      <div id="meters" class="meters"></div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>Mis mazos</h2>
        <a href="#/mazos">ver todos</a>
      </div>
      <ul id="decks" class="rows"></ul>
    </section>

  </div>
</div>
`;

// ── La tira de figuras ────────────────────────────────────────────────
// Cuatro cifras separadas por la misma regla impresa que el resto, no cuatro
// cajas: una fila de plaquitas con borde haría de cada dato un panel más y
// aplanaría la página.

function stat(label, value, meta, id) {
  const node = el("div", "stat");
  node.append(el("span", "stat-label", label));
  const figure = el("span", "stat-value", value);
  if (id) figure.id = id;
  node.append(figure, el("span", "stat-meta", meta));
  return node;
}

function renderStats(data) {
  const studied = data.calendar.filter((d) => d.studied).length;
  const decksDue = data.due.decks.filter((d) => d.due > 0).length;
  const stuck = data.struggling_total;

  $("stats").replaceChildren(
    stat("Racha actual",
         plural(data.streak.days, "día", "días"),
         data.streak.days ? "sin faltar" : "empieza hoy",
         "stat-streak"),
    stat("Tarjetas hoy",
         String(data.due.total),
         decksDue ? `en ${plural(decksDue, "mazo", "mazos")}` : "nada pendiente"),
    stat("Días con estudio",
         `${studied} / ${data.window.days}`,
         "de la ventana"),
    stat("Atascos",
         String(stuck),
         stuck ? "tarjetas que cuestan" : "ninguna te frena"),
  );
}

// ── Actividad semanal ─────────────────────────────────────────────────
// Un día sin repasos es papel sin marcar, igual que en el calendario: sin
// relleno y sin borde. La ausencia nunca acusa, tampoco aquí.

function renderWeek(calendar) {
  const week = calendar.slice(-WEEK_DAYS);
  const peak = Math.max(...week.map((d) => d.reviews), 1);
  const total = week.reduce((sum, d) => sum + d.reviews, 0);

  $("week-sub").textContent = total
    ? `${plural(total, "repaso", "repasos")} en la semana`
    : "sin repasos esta semana";

  const grid = $("week");
  grid.replaceChildren();

  for (const [index, day] of week.entries()) {
    const col = el("div", "bar-col");
    col.dataset.today = String(index === week.length - 1);
    col.dataset.empty = String(day.reviews === 0);
    col.dataset.before = String(Boolean(day.before_start));
    col.title = day.before_start
      ? `${formatLongDate(day.date)} — antes de empezar`
      : `${formatLongDate(day.date)} — ${plural(day.reviews, "repaso", "repasos")}`;

    const track = el("div", "bar-track");
    const fill = el("div", "bar-fill");
    // Un repaso suelto tiene que verse: por debajo de un 6 % la barra
    // desaparece y el día parece vacío cuando no lo está.
    fill.style.height = day.reviews
      ? `${Math.max(6, Math.round((day.reviews / peak) * 100))}%`
      : "0%";
    track.append(fill);

    col.append(track, el("span", "bar-label", weekdayInitial(day.date)));
    grid.append(col);
  }
}

// ── El anillo — lo que va del día ─────────────────────────────────────
// No es el mazo entero ni la colección: es hoy. Lo hecho hoy contra lo hecho
// más lo que queda, que es la única fracción que se cierra apareciendo.

function ringSvg(share) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 160 160");
  svg.setAttribute("class", "ring-dial");
  svg.setAttribute("aria-hidden", "true");

  const circle = (className) => {
    const node = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    node.setAttribute("cx", "80");
    node.setAttribute("cy", "80");
    node.setAttribute("r", String(RING_RADIUS));
    node.setAttribute("class", className);
    return node;
  };

  const done = circle("ring-done");
  const offset = RING_LENGTH * (1 - share);
  done.style.strokeDasharray = String(RING_LENGTH);
  done.style.strokeDashoffset = String(offset);
  // La entrada lo lee de aquí y no del estilo: el valor final tiene que ser un
  // número, y `style.strokeDashoffset` ya es una cadena.
  done.dataset.offset = String(offset);

  svg.append(circle("ring-track"), done);
  return svg;
}

function renderRing(data) {
  const done = data.done.cards;
  const goal = data.goal;
  const pending = data.due.total;

  const panel = $("ring");
  panel.replaceChildren();

  // El anillo mide contra la meta, no contra el atraso. Contra 271 pendientes
  // nunca se cierra, y un anillo que no se puede cerrar deja de ser una meta.
  if (!pending && !done) {
    panel.append(el("p", "empty", "Hoy no hay nada programado."));
    return;
  }

  const dial = el("div", "ring-wrap");
  dial.append(ringSvg(goal ? Math.min(1, done / goal) : 0));

  const center = el("div", "ring-center");
  center.append(el("span", "ring-value", `${done} / ${goal}`),
                el("span", "ring-unit", "meta"));
  dial.append(center);

  const foot = el("p", "ring-foot", done >= goal
    ? "Meta cumplida."
    : `${plural(pending, "pendiente acumulada", "pendientes acumuladas")}`);

  panel.append(dial, foot);
}

// ── Progreso por habilidad ────────────────────────────────────────────
// Una barra por skill, el porcentaje de maduras. El detalle A1–C1 vive en
// Progreso: aquí la pregunta es cuál va última, no en qué nivel estás.

function meterRow(skill) {
  const link = el("a", "meter-row");
  link.href = `#/skill/${slug(skill.skill)}`;

  const name = el("span", "rail-name");
  name.append(el("span", "rail-skill", skill.skill),
              el("span", "rail-chip", skill.current_level));

  const meter = el("span", "meter");
  meter.dataset.empty = String(skill.total === 0);
  const fill = el("span", "meter-fill");
  fill.style.width = `${Math.round(skill.maturity * 100)}%`;
  meter.append(fill);

  link.title = skill.total
    ? `${skill.skill} — ${skill.mature} de ${skill.total} maduras`
    : `${skill.skill} — sin tarjetas`;

  link.append(name, meter, el("span", "count", skill.total ? percent(skill.maturity) : "—"));
  return link;
}

function renderMeters(data) {
  const meters = $("meters");
  meters.replaceChildren();
  for (const skill of data.skills) meters.append(meterRow(skill));
}

function renderDecks(decks) {
  const list = $("decks");
  list.replaceChildren();
  if (!decks.length) {
    list.append(emptyRow("Todavía no hay mazos en Anki."));
    return;
  }
  for (const deck of decks) {
    list.append(row(deck.deck, deck.due ? `${deck.due} para hoy` : "al día"));
  }
}

// Everything runs at once and lands together at TOTAL_MS. Only opacity,
// transforms and the ring's dash offset are touched, so nothing triggers
// layout and nothing is ever made unclickable: the button responds from the
// first frame.
function playEntrance(motion, data) {
  if (!motion) return;
  const { animate, stagger } = motion;

  // scaleY desde la base, no height: la altura reflowaría las siete columnas
  // en cada cuadro.
  const bars = document.querySelectorAll(".bar-fill");
  if (bars.length) {
    animate(bars, {
      scaleY: [0, 1],
      duration: DURATION_MS,
      delay: stagger(staggerStep(bars.length)),
      ease: "outQuad",
    });
  }

  const fills = document.querySelectorAll(".meter-fill");
  if (fills.length) {
    animate(fills, {
      scaleX: [0, 1],
      duration: DURATION_MS,
      delay: stagger(staggerStep(fills.length)),
      ease: "outQuad",
    });
  }

  const rows = document.querySelectorAll(".rows li");
  if (rows.length) {
    animate(rows, {
      opacity: [0, 1],
      y: [6, 0],
      duration: DURATION_MS,
      delay: stagger(staggerStep(rows.length)),
      ease: "outQuad",
    });
  }

  const arc = document.querySelector(".ring-done");
  if (arc) {
    animate(arc, {
      strokeDashoffset: [RING_LENGTH, Number(arc.dataset.offset)],
      duration: TOTAL_MS,
      ease: "outExpo",
    });
  }

  // La racha cuenta hacia arriba hasta su valor. En cero se salta: ahí la
  // cifra es una frase, no un número.
  const daysStudied = data.streak.days;
  const element = $("stat-streak");
  if (daysStudied > 0 && element) {
    const counter = { value: 0 };
    animate(counter, {
      value: daysStudied,
      duration: TOTAL_MS,
      ease: "outExpo",
      onUpdate: () => {
        element.textContent = plural(Math.round(counter.value), "día", "días");
      },
      onComplete: () => {
        element.textContent = plural(daysStudied, "día", "días");
      },
    });
  }
}

// This app neither runs reviews nor creates cards — Anki does both. Both
// buttons hand over to it rather than pretending to do the work here.
function showHint(text) {
  $("start-hint").textContent = text;
  $("start-hint").hidden = false;
}

async function handOverToAnki(path, button, working, done) {
  button.disabled = true;
  showHint(working);
  try {
    const data = await getJSON(path, { method: "POST" });
    showHint(done(data));
  } catch (error) {
    showHint(error.message);
  } finally {
    button.disabled = false;
  }
}

export async function render(root) {
  root.innerHTML = MARKUP;

  $("start").addEventListener("click", () =>
    handOverToAnki("/api/study", $("start"), "Abriendo Anki…",
      (d) => `Anki está en “${d.deck}”, con ${plural(d.due, "tarjeta", "tarjetas")}. ` +
             `Si la ventana no saltó al frente, cambiá a ella.`));

  // Agregar tarjetas es una pantalla de esta app, no el diálogo de Anki: el
  // modelo propone, vos aprobás y recién ahí se escribe. La escotilla a Anki
  // sigue estando, abajo de esa pantalla.
  $("add-cards").addEventListener("click", () => { location.hash = "#/agregar"; });

  // El catálogo ya lo pide la barra lateral en cada navegación, así que las
  // barras por habilidad no cuestan una petición extra: ui.catalog() reparte
  // la misma promesa.
  const [data, tree] = await Promise.all([getJSON("/api/today"), catalog()]);
  $("dashboard").hidden = false;

  $("date").textContent = formatLongDate(data.date);

  // Un botón que no lleva a ninguna parte es peor que ningún botón: sin nada
  // pendiente, "Empezar sesión" abriría Anki en una sesión vacía.
  $("start").hidden = data.due.total === 0;
  $("add-cards").hidden = data.due.total > 0;

  renderStats(data);
  renderWeek(data.calendar);
  renderRing(data);
  renderMeters(tree);
  renderDecks(data.due.decks);

  // Never awaited: the screen is already usable, the motion just catches up.
  loadMotion().then((motion) => playEntrance(motion, data));
}
