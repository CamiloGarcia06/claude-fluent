// Today screen. Reads /api/today and paints it. It decides nothing.

const WEEKDAYS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
const MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

const $ = (id) => document.getElementById(id);

// Entrance motion. Today is opened once a day, so it earns an animation —
// unlike the review flow, where anything you cross 100 times must be instant.
// The whole entrance finishes at TOTAL_MS: the cascade takes the slack that the
// duration leaves, so adding decks or cards can never push it past the budget.
// A streak only becomes something you can lose once it is worth something.
const GRACE_NOTICE_FROM_DAYS = 7;

const TOTAL_MS = 300;
const DURATION_MS = 190;
const CASCADE_MS = TOTAL_MS - DURATION_MS;

const staggerStep = (count) => (count > 1 ? CASCADE_MS / (count - 1) : 0);

const prefersReducedMotion =
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Animation is a bonus, never a dependency: if the module fails to load the
// page is already rendered and stays fully usable.
async function loadMotion() {
  if (prefersReducedMotion) return null;
  try {
    return await import("/anime.esm.js");
  } catch {
    return null;
  }
}

// Build the date from its parts. `new Date("2026-08-18")` parses as UTC
// midnight, which lands on the previous day west of Greenwich.
function parseDate(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function formatLongDate(iso) {
  const d = parseDate(iso);
  const weekday = WEEKDAYS[d.getDay()];
  return `${weekday[0].toUpperCase()}${weekday.slice(1)} ${d.getDate()} de ${MONTHS[d.getMonth()]}`;
}

function plural(n, one, many) {
  return `${n} ${n === 1 ? one : many}`;
}

function row(name, count) {
  const li = document.createElement("li");
  const left = document.createElement("span");
  left.className = "name";
  left.textContent = name;
  const right = document.createElement("span");
  right.className = "count";
  right.textContent = count;
  li.append(left, right);
  return li;
}

function emptyRow(text) {
  const li = document.createElement("li");
  li.className = "empty";
  li.textContent = text;
  return li;
}

function streakLabel(days) {
  return days ? `Racha de ${plural(days, "día", "días")}` : "Todavía sin racha";
}

function renderHero(data) {
  $("date").textContent = formatLongDate(data.date);

  const due = data.due.total;
  $("due-headline").textContent = due
    ? `${plural(due, "tarjeta te espera", "tarjetas te esperan")} hoy`
    : "Hoy no te espera ninguna tarjeta";

  $("streak").textContent = streakLabel(data.streak.days);

  // Below a week there is no streak worth protecting, and the reassurance
  // reads as a warning about a rule you have not needed yet.
  const showGrace = streak.days >= GRACE_NOTICE_FROM_DAYS;
  $("grace").hidden = !showGrace;
  if (showGrace) {
    $("grace").textContent = streak.grace_left_this_month
      ? `Te queda ${plural(streak.grace_left_this_month, "día", "días")} de gracia este mes: faltar una vez no borra la racha.`
      : "Ya usaste tu día de gracia de este mes.";
  }
}

function renderCalendar(calendar) {
  const studied = calendar.filter((d) => d.studied).length;
  $("calendar-sub").textContent = `${plural(studied, "día", "días")} con estudio`;

  const grid = $("calendar");
  grid.replaceChildren();
  for (const day of calendar) {
    const cell = document.createElement("div");
    cell.className = "day";
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
    if (card.note_id) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "ghost repair-open";
      button.textContent = "Reparar";
      button.addEventListener("click", () => openRepair(card.note_id, name));
      li.append(button);
    }
    list.append(li);
  }
}

// ── Repair ────────────────────────────────────────────────────────────
// The model proposes, you approve. Nothing reaches Anki until you press
// Aceptar, and the server snapshots the note before it writes.

let proposal = null;

function side(label, value, changed) {
  const box = document.createElement("div");
  box.className = "side";
  box.dataset.changed = String(changed);
  const tag = document.createElement("span");
  tag.className = "side-label";
  tag.textContent = label;
  const text = document.createElement("div");
  text.className = "side-value";
  text.textContent = value || "—";
  box.append(tag, text);
  return box;
}

function renderDiff(data) {
  const diff = $("repair-diff");
  diff.replaceChildren();
  for (const name of Object.keys(data.current)) {
    const changed = data.changed.includes(name);
    const block = document.createElement("div");
    block.className = "field";
    block.dataset.changed = String(changed);

    const heading = document.createElement("div");
    heading.className = "field-name";
    heading.textContent = changed ? `${name} · cambia` : `${name} · igual`;

    block.append(heading, side("Antes", data.current[name], changed),
                 side("Después", data.proposal[name], changed));
    diff.append(block);
  }
}

function setRepairBusy(busy, message) {
  $("repair-status").textContent = message || "";
  $("repair-accept").disabled = busy || !proposal;
  document.querySelectorAll(".repair-open").forEach((b) => { b.disabled = busy; });
}

async function openRepair(noteId, name) {
  proposal = null;
  $("repair").hidden = false;
  $("repair-title").textContent = `Reparar “${name}”`;
  $("repair-diagnosis").textContent = "";
  $("repair-rationale").textContent = "";
  $("repair-diff").replaceChildren();
  setRepairBusy(true, "Pensando… esto tarda unos segundos.");
  $("repair").scrollIntoView({ block: "nearest" });

  try {
    const response = await fetch(`/api/repair/${noteId}`, { method: "POST" });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      setRepairBusy(false, detail.detail || `El servidor devolvió ${response.status}.`);
      return;
    }
    proposal = await response.json();
  } catch {
    setRepairBusy(false, "No se pudo hablar con el servidor.");
    return;
  }

  $("repair-diagnosis").textContent = proposal.diagnosis;
  $("repair-rationale").textContent = proposal.rationale;
  renderDiff(proposal);

  const changes = proposal.changed.length;
  setRepairBusy(false, changes
    ? `${changes === 1 ? "1 campo cambia" : `${changes} campos cambian`} · ${Math.round(proposal.duration_ms / 1000)}s`
    : "El modelo no propone cambios.");
  $("repair-accept").disabled = changes === 0;
}

function closeRepair() {
  proposal = null;
  $("repair").hidden = true;
  setRepairBusy(false, "");
}

async function acceptRepair() {
  if (!proposal) return;
  setRepairBusy(true, "Guardando…");

  let response;
  try {
    response = await fetch(`/api/apply/${proposal.note_id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fields: proposal.proposal }),
    });
  } catch {
    setRepairBusy(false, "No se pudo hablar con el servidor.");
    return;
  }

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    setRepairBusy(false, detail.detail || `El servidor devolvió ${response.status}.`);
    return;
  }

  closeRepair();
  await load({ withMotion: false });
}

$("repair-accept").addEventListener("click", acceptRepair);
$("repair-discard").addEventListener("click", closeRepair);

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
  const days_studied = data.streak.days;
  if (days_studied > 0) {
    const element = $("streak");
    const counter = { value: 0 };
    animate(counter, {
      value: days_studied,
      duration: TOTAL_MS,
      ease: "outExpo",
      onUpdate: () => {
        element.textContent = streakLabel(Math.round(counter.value));
      },
      onComplete: () => {
        element.textContent = streakLabel(days_studied);
      },
    });
  }
}

function showOffline(message) {
  const banner = $("offline");
  banner.textContent = message;
  banner.hidden = false;
  $("today").hidden = true;
}

async function load({ withMotion = true } = {}) {
  let response;
  try {
    response = await fetch("/api/today");
  } catch {
    showOffline("No se pudo hablar con el servidor. ¿Está corriendo uvicorn?");
    return;
  }

  if (response.status === 503) {
    showOffline("Anki no responde. Abrí Anki y comprobá que AnkiConnect está instalado.");
    return;
  }
  if (!response.ok) {
    showOffline(`El servidor devolvió ${response.status}.`);
    return;
  }

  const data = await response.json();
  $("offline").hidden = true;
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
    const response = await fetch(path, { method: "POST" });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      showHint(detail.detail || `El servidor devolvió ${response.status}.`);
      return;
    }
    const data = await response.json();
    showHint(done(data));
  } catch {
    showHint("No se pudo hablar con el servidor.");
  } finally {
    button.disabled = false;
  }
}

$("start").addEventListener("click", () =>
  handOverToAnki("/api/study", $("start"), "Abriendo Anki…",
    (d) => `Anki está en “${d.deck}”, con ${plural(d.due, "tarjeta", "tarjetas")}. ` +
           `Si la ventana no saltó al frente, cambiá a ella.`));

$("add-cards").addEventListener("click", () =>
  handOverToAnki("/api/add-cards", $("add-cards"), "Abriendo Anki…",
    () => "Anki abrió el diálogo de añadir. Si la ventana no saltó al frente, cambiá a ella."));

load();
