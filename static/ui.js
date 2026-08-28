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

// Un lado del par antes/después. Vive acá y no en repair.js porque la práctica
// de escritura dibuja exactamente la misma pieza —lo que escribiste contra lo
// correcto— y dos copias de esto se separarían al primer retoque.
// `mark` es opcional y sólo la práctica lo usa: en el panel de reparación
// "Antes" no está mal, es el estado actual de la tarjeta, y una cruz ahí
// significaría otra cosa.
export function side(label, value, changed, mark) {
  const box = el("div", "side");
  box.dataset.changed = String(changed);
  if (mark) box.dataset.mark = mark;

  // `value` puede venir como texto o como nodo. La práctica pasa un fragmento
  // con las palabras que cambian marcadas; el panel de reparación pasa el campo
  // pelado, y sigue funcionando igual.
  const shown = el("div", "side-value");
  if (value instanceof Node) shown.append(value);
  else shown.textContent = value || "—";

  box.append(el("span", "side-label", label), shown);
  return box;
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

// ── La espera ─────────────────────────────────────────────────────────
// Siete llamadas al modelo en el app y cada una contaba la espera a su manera:
// dos con barra, tres con una frase quieta, y el botón que la disparó siempre
// gris al 45 % — que es como se dibuja "no podés", no "estoy pensando". Esto
// es la barra honesta que ya vivía en Agregar y en el compositor, sacada a una
// pieza sola para que las siete digan lo mismo.
//
// Dos reglas, y las dos ya estaban escritas en otro lado del proyecto: **la
// barra ocupa el lugar donde va a aparecer la respuesta**, y **la frase va al
// lado del botón que apretaste**.

/** Arranca la espera dentro de `container` y devuelve cómo terminarla.
 *
 *  Corre hasta el 90 % en el tiempo medido y espera ahí: una barra que llega
 *  al 100 % y sigue esperando es peor que ninguna. `stop(true)` la completa y
 *  la saca; `stop(false)` la saca sin más, que es lo que corresponde cuando lo
 *  que llegó fue un error. */
export function waiting(container, estimate, before) {
  const track = el("span", "gen-track wait");
  const bar = el("span", "gen-bar");
  track.append(bar);
  // `before` para cuando la respuesta llena una región que ya tiene algo
  // arriba: en el temario los puntos están pintados y lo que falta es la
  // cobertura, así que la barra va bajo la frase que la anuncia y no al pie de
  // dieciocho filas, donde nadie la está mirando.
  container.insertBefore(track, before ?? null);

  // En el mismo cuadro no hay transición que animar: el navegador ve un solo
  // valor. El salto de cuadro es lo que la convierte en un recorrido.
  requestAnimationFrame(() => {
    bar.style.transition = `transform ${estimate}ms linear`;
    bar.style.transform = "scaleX(0.9)";
  });

  return (done = true) => {
    if (!done) { track.remove(); return; }
    bar.style.transition = "transform 160ms cubic-bezier(.23,1,.32,1)";
    bar.style.transform = "scaleX(1)";
    setTimeout(() => track.remove(), 170);
  };
}

/** El botón que disparó la llamada. Sigue sin poder apretarse, pero lo dice de
 *  otra manera: conserva su tinta en vez de irse al 45 %, que es el gris de
 *  "esto no está disponible". */
export function working(button, on) {
  if (!button) return;
  button.disabled = on;
  button.dataset.working = String(on);
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
