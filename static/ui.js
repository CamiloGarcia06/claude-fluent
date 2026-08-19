// Shared front-end pieces. Everything here was in app.js when the app was one
// screen; it moved out unchanged so the new screens reuse it rather than grow
// their own second version of the same thing.

const WEEKDAYS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
const MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

export const $ = (id) => document.getElementById(id);

export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

// ── Motion ────────────────────────────────────────────────────────────
// Only the Today screen animates, and only on load. Anything you cross a
// hundred times must be instant, so the other screens paint at once.
// The whole entrance finishes at TOTAL_MS: the cascade takes the slack that the
// duration leaves, so adding decks or cards can never push it past the budget.
export const TOTAL_MS = 300;
export const DURATION_MS = 190;
const CASCADE_MS = TOTAL_MS - DURATION_MS;

export const staggerStep = (count) => (count > 1 ? CASCADE_MS / (count - 1) : 0);

const prefersReducedMotion =
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Animation is a bonus, never a dependency: if the module fails to load the
// page is already rendered and stays fully usable.
export async function loadMotion() {
  if (prefersReducedMotion) return null;
  try {
    return await import("/anime.esm.js");
  } catch {
    return null;
  }
}

// ── Formatting ────────────────────────────────────────────────────────

// Build the date from its parts. `new Date("2026-08-18")` parses as UTC
// midnight, which lands on the previous day west of Greenwich.
function parseDate(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function formatLongDate(iso) {
  const d = parseDate(iso);
  const weekday = WEEKDAYS[d.getDay()];
  return `${weekday[0].toUpperCase()}${weekday.slice(1)} ${d.getDate()} de ${MONTHS[d.getMonth()]}`;
}

// L M X J V S D — the initial Spanish uses for each weekday, indexed by
// getDay(). Sunday and Saturday share an S and Monday and Wednesday an M, so
// the pair that collides takes X for miércoles, as a Spanish calendar does.
const WEEKDAY_INITIALS = ["D", "L", "M", "X", "J", "V", "S"];

export function weekdayInitial(iso) {
  return WEEKDAY_INITIALS[parseDate(iso).getDay()];
}

export function plural(n, one, many) {
  return `${n} ${n === 1 ? one : many}`;
}

export function percent(share) {
  return `${Math.round(share * 100)} %`;
}

export function minutes(seconds) {
  return `${Math.round(seconds / 60)} min`;
}

// ── Rows ──────────────────────────────────────────────────────────────

export function row(name, count) {
  const li = document.createElement("li");
  const left = el("span", "name", name);
  const right = el("span", "count", count);
  li.append(left, right);
  return li;
}

export function emptyRow(text) {
  const li = el("li", "empty", text);
  return li;
}

// ── Talking to the server ─────────────────────────────────────────────
// Every failure of this system is silent — Anki closed, uvicorn down — so the
// three cases that mean something get their own sentence, in one place. A view
// that lets this throw gets the banner for free.

export class ApiError extends Error {}

export async function getJSON(path, options) {
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new ApiError("No se pudo hablar con el servidor. ¿Está corriendo uvicorn?");
  }

  if (response.status === 503) {
    throw new ApiError("Anki no responde. Abrí Anki y comprobá que AnkiConnect está instalado.");
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new ApiError(detail.detail || `El servidor devolvió ${response.status}.`);
  }
  return response.json();
}

// The catalogue is read by the navbar chips and by whatever screen is mounting,
// so it is fetched once per navigation and shared. The router drops it on the
// way in, which is what keeps it from going stale.
let catalogPromise = null;

export function invalidateCatalog() {
  catalogPromise = null;
}

export function catalog() {
  if (!catalogPromise) catalogPromise = getJSON("/api/catalog");
  return catalogPromise;
}

export function showOffline(message) {
  const banner = $("offline");
  banner.textContent = message;
  banner.hidden = false;
}

export function clearOffline() {
  $("offline").hidden = true;
}
