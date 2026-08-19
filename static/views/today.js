// Today screen. Reads /api/today and paints it. It decides nothing.
//
// The markup moved here from index.html when the app grew a router: index.html
// is a shell now, and every screen carries its own. Ids and classes are exactly
// the ones styles.css already targets.

import {
  $, el, row, emptyRow, plural, formatLongDate, getJSON,
  loadMotion, staggerStep, TOTAL_MS, DURATION_MS,
} from "/ui.js";
import * as repair from "/repair.js";

// A streak only becomes something you can lose once it is worth something.
const GRACE_NOTICE_FROM_DAYS = 7;

const MARKUP = `
<div id="today" hidden>

  <section class="hero">
    <p id="date" class="date"></p>
    <h1 id="due-headline"></h1>
    <button id="start" type="button">Empezar</button>
    <button id="add-cards" type="button" hidden>Agregar tarjetas</button>
    <p id="start-hint" class="hint" hidden></p>
    <div class="hero-foot">
      <span id="streak" class="streak"></span>
      <span id="grace" class="grace" hidden></span>
    </div>
  </section>

  <div class="columns">

    <div class="col">
      <section class="panel">
        <div class="panel-head">
          <h2>Últimos 30 días</h2>
        </div>
        <p id="calendar-sub" class="sub"></p>
        <div id="calendar" class="calendar"></div>
      </section>

      <section class="panel" id="struggling-panel" hidden>
        <div class="panel-head">
          <h2>Vengo fallando</h2>
          <a id="struggling-all" href="#/atascos" hidden></a>
        </div>
        <ul id="struggling" class="rows"></ul>
      </section>
    </div>

    <div class="col">
      <section class="panel">
        <div class="panel-head">
          <h2>Mis mazos</h2>
          <a href="#/mazos">ver todos</a>
        </div>
        <ul id="decks" class="rows"></ul>
      </section>
    </div>

  </div>
</div>
`;

function streakLabel(days) {
  return days ? `Racha de ${plural(days, "día", "días")}` : "Todavía sin racha";
}

function renderHero(data) {
  $("date").textContent = formatLongDate(data.date);

  const due = data.due.total;
  $("due-headline").textContent = due
    ? `${plural(due, "tarjeta te espera", "tarjetas te esperan")} hoy`
    : "Hoy no te espera ninguna tarjeta";

  // A button that leads nowhere is worse than no button: with nothing due,
  // "Empezar" would hand Anki an empty session, so adding cards takes the
  // primary slot instead.
  $("start").hidden = due === 0;
  $("add-cards").hidden = due > 0;

  $("streak").textContent = streakLabel(data.streak.days);

  // Below a week there is no streak worth protecting, and the reassurance
  // reads as a warning about a rule you have not needed yet.
  const showGrace = data.streak.days >= GRACE_NOTICE_FROM_DAYS;
  $("grace").hidden = !showGrace;
  if (showGrace) {
    $("grace").textContent = data.streak.grace_left_this_month
      ? `Te queda ${plural(data.streak.grace_left_this_month, "día", "días")} de gracia este mes: faltar una vez no borra la racha.`
      : "Ya usaste tu día de gracia de este mes.";
  }
}

function renderCalendar(calendar) {
  const studied = calendar.filter((d) => d.studied).length;
  $("calendar-sub").textContent = `${plural(studied, "día", "días")} con estudio`;

  const grid = $("calendar");
  grid.replaceChildren();
  for (const day of calendar) {
    const cell = el("div", "day");
    cell.dataset.studied = String(day.studied);
    cell.dataset.before = String(Boolean(day.before_start));
    cell.title = day.before_start
      ? `${formatLongDate(day.date)} — antes de empezar`
      : `${formatLongDate(day.date)} — ${plural(day.reviews, "repaso", "repasos")}`;
    grid.append(cell);
  }
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

function renderStruggling(cards) {
  const list = $("struggling");
  list.replaceChildren();

  // Nothing qualifying means nothing to say. An empty panel headed "Vengo
  // fallando" invents a problem out of an absence of evidence.
  $("struggling-panel").hidden = cards.length === 0;
  if (!cards.length) return;

  const link = $("struggling-all");
  link.hidden = false;
  link.textContent = `ver las ${cards.length}`;

  for (const card of cards) {
    const name = card.front || `carta ${card.card_id}`;
    const li = row(name, `${card.failures} fallos de ${card.attempts}`);
    const control = repair.button(card, name);
    if (control) li.append(control);
    list.append(li);
  }
}

// Everything runs at once and lands together at TOTAL_MS. Only opacity and
// transform are touched, so nothing triggers layout and nothing is ever made
// unclickable: the start button responds from the first frame.
function playEntrance(motion, data) {
  if (!motion) return;
  const { animate, stagger } = motion;

  const days = document.querySelectorAll(".day");
  if (days.length) {
    animate(days, {
      opacity: [0, 1],
      scale: [0.85, 1],
      duration: DURATION_MS,
      delay: stagger(staggerStep(days.length)),
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

  // The streak counts up to its value. Skipped at zero, where the label is a
  // sentence rather than a number.
  const daysStudied = data.streak.days;
  if (daysStudied > 0) {
    const element = $("streak");
    const counter = { value: 0 };
    animate(counter, {
      value: daysStudied,
      duration: TOTAL_MS,
      ease: "outExpo",
      onUpdate: () => { element.textContent = streakLabel(Math.round(counter.value)); },
      onComplete: () => { element.textContent = streakLabel(daysStudied); },
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

async function load({ withMotion = true } = {}) {
  const data = await getJSON("/api/today");
  $("today").hidden = false;

  renderHero(data);
  renderCalendar(data.calendar);
  renderDecks(data.due.decks);
  renderStruggling(data.struggling);

  // Only on the initial load of Today, and never awaited: the screen is
  // already usable, the motion just catches up.
  if (withMotion) {
    loadMotion().then((motion) => playEntrance(motion, data));
  }
}

export async function render(root) {
  root.innerHTML = MARKUP;
  $("today").querySelector(".hero").after(
    repair.mount({ onApplied: () => load({ withMotion: false }) }),
  );

  $("start").addEventListener("click", () =>
    handOverToAnki("/api/study", $("start"), "Abriendo Anki…",
      (d) => `Anki está en “${d.deck}”, con ${plural(d.due, "tarjeta", "tarjetas")}. ` +
             `Si la ventana no saltó al frente, cambiá a ella.`));

  $("add-cards").addEventListener("click", () =>
    handOverToAnki("/api/add-cards", $("add-cards"), "Abriendo Anki…",
      () => "Anki abrió el diálogo de añadir. Si la ventana no saltó al frente, cambiá a ella."));

  await load();
}

