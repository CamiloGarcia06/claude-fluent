// Hash routing, not path routing. StaticFiles is mounted at the root and knows
// nothing about /progreso, so reloading a path route would 404 — with a hash
// the server only ever sees "/".
//
// The view modules are imported statically. They are six local files with no
// network between them, and a dynamic import that fails leaves a blank screen
// with nothing to fall back to; that trade only makes sense for anime.js,
// where the page is already usable without it.

import { $, ApiError, invalidateCatalog, clearOffline, showOffline, catalog } from "/ui.js";
import * as today from "/views/today.js";
import * as progress from "/views/progress.js";
import * as skill from "/views/skill.js";
import * as decks from "/views/decks.js";
import * as stuck from "/views/stuck.js";
import * as settings from "/views/settings.js";
import * as dashboard from "/views/dashboard.js";
import * as add from "/views/add.js";
import * as practice from "/views/practice.js";
import * as patterns from "/views/patterns.js";

const ROUTES = {
  hoy: today,
  progreso: progress,
  skill,
  mazos: decks,
  agregar: add,
  practica: practice,
  patrones: patterns,
  atascos: stuck,
  ajustes: settings,
  dashboard,
};

const DEFAULT_ROUTE = "hoy";

// A los 250 ms, no antes: /api/settings y /api/practice/patterns contestan en
// dos milisegundos, y un aviso que parpadea es peor que ninguno. Las que sí se
// hacen esperar son las que leen Anki — medidas entre 1 y 2 s.
const LOADING_AFTER_MS = 250;

function parse() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  return { name: parts[0] || DEFAULT_ROUTE, params: parts.slice(1) };
}

function markActive(name, params) {
  for (const link of document.querySelectorAll("#nav a")) {
    link.dataset.active = String(link.dataset.route === name);
  }
  for (const link of document.querySelectorAll("#skillbar a")) {
    link.dataset.active = String(name === "skill" && link.dataset.skill === params[0]);
  }
}

// The chips are a summary, so they never get in the way: never awaited, and if
// the catalogue cannot be read the sidebar simply carries no levels while the
// screen below says why. On the screens that read the catalogue — Progreso,
// las skills, Mazos y el Dashboard — es la misma promesa a través de
// ui.catalog(); sólo en Hoy es una petición que la pantalla no necesita, que
// es el precio de leer tu nivel sin entrar.
async function fillChips() {
  let data;
  try {
    data = await catalog();
  } catch {
    return;
  }
  for (const link of document.querySelectorAll("#skillbar a")) {
    const found = data.skills.find((s) => s.skill.toLowerCase() === link.dataset.skill);
    const chip = link.querySelector(".chip-level");
    chip.textContent = found ? found.current_level : "";
  }
}

async function navigate() {
  const { name, params } = parse();
  const view = ROUTES[name] || ROUTES[DEFAULT_ROUTE];

  // One fetch of the catalogue per navigation, shared by the bar and the view.
  // Dropping it here is what keeps it from going stale.
  invalidateCatalog();
  clearOffline();
  markActive(name, params);

  const root = $("view");
  root.replaceChildren();
  window.scrollTo(0, 0);

  const waiting = setTimeout(() => { $("loading").hidden = false; }, LOADING_AFTER_MS);

  try {
    await view.render(root, params);
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    // Anki closed or uvicorn down. The banner says which, and the empty view
    // below it is honest: there is nothing to show, not a stale copy.
    root.replaceChildren();
    showOffline(error.message);
  } finally {
    clearTimeout(waiting);
    $("loading").hidden = true;
  }

  fillChips();
}

export function start() {
  window.addEventListener("hashchange", navigate);
  navigate();
}
