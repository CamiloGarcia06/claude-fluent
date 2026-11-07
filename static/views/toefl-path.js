// TOEFL · camino a B1 — la franja de arriba: qué toca hoy, la semana, cuántos de
// tus últimos diez textos ya son B1 y la misión del próximo.
//
// La meta es la del requisito de la maestría (B1), no la nota de ETS. El camino
// es una ventana de diez textos de primer intento, no un promedio: se mueve en
// cuanto escribís mejor. Los miércoles hay clase de PLN y no toca nada.

import { el, getJSON, ApiError } from "/ui.js";

const KIND_LABEL = { b1: "Texto B1", discussion: "Academic Discussion", email: "Email" };
const LEVELS = ["A1", "A2", "B1", "B2", "C1"];
const atLeastB1 = (level) => LEVELS.indexOf(level) >= LEVELS.indexOf("B1");

function todayLine(today) {
  switch (today.task) {
    case "new": return `Hoy toca un texto nuevo: ${KIND_LABEL[today.kind] ?? today.kind}.`;
    case "rewrite": return "Hoy toca reescribir tu texto más flojo de la semana, sin reloj.";
    case "rest": return "Hoy es miércoles: clase de PLN. No toca writing.";
    default: return "Fin de semana: lectura larga por gusto o conversación. El writing descansa.";
  }
}

function weekStrip(days) {
  const strip = el("ol", "b1-week");
  for (const d of days) {
    const li = el("li");
    li.dataset.task = d.task;
    li.dataset.today = String(d.today);
    li.dataset.done = String(d.done);
    const mark = d.done === true ? "✓"
      : d.task === "rest" ? "PLN"
      : d.task === "free" ? "·"
      : d.done === false && !d.today ? "✗"
      : d.task === "rewrite" ? "↺" : "✎";
    li.append(el("span", "b1-day", d.day.slice(0, 3)), el("span", "b1-mark", mark));
    li.title = d.task === "new" ? `Texto nuevo · ${KIND_LABEL[d.kind] ?? d.kind}`
      : d.task === "rewrite" ? "Reescribir" : d.task === "rest" ? "Clase de PLN" : "Libre";
    strip.append(li);
  }
  return strip;
}

function roadBox(road) {
  const box = el("div", "b1-road");
  box.append(el("p", "b1-road-head",
    road.count
      ? `${road.at_level} de ${road.count} ${road.count === 1 ? "texto" : "textos"} en ` +
        `${road.target_level} o más (cuentan los últimos ${road.window}) · ` +
        `meta: ${road.target} de ${road.window}`
      : `Meta: ${road.target} de tus últimos ${road.window} textos en ${road.target_level}.`));
  const dots = el("ol", "b1-dots");
  for (let i = 0; i < road.window; i++) {
    const level = road.levels[i];
    const dot = el("li", "", level ?? "");
    dot.dataset.state = !level ? "empty" : atLeastB1(level) ? "ok" : "short";
    dots.append(dot);
  }
  box.append(dots);
  if (road.ready) box.append(el("p", "toefl-verdict", "Listo: tu writing ya está en B1 de forma estable."));
  return box;
}

function missionBox(mission) {
  const box = el("div", "b1-mission");
  if (!mission.length) {
    box.append(el("p", "panel-note",
      "Con tu primer texto te digo qué te falta para B1: conectores, contraste, " +
      "razones, presente perfecto, condicional y relativo."));
    return box;
  }
  box.append(el("p", "toefl-label", "Misión del próximo texto"));
  for (const m of mission) {
    const card = el("div", "toefl-tip");
    card.append(
      el("span", "tag", `${m.label} · faltó en ${m.missed} de ${m.of}`),
      el("p", "", m.tip),
      el("p", "toefl-example", m.example),
    );
    box.append(card);
  }
  return box;
}

/** Pinta la franja en `box`. `actions.go(kind)` abre un texto nuevo de ese
 *  tipo; `actions.rewrite(r)` abre la reescritura del martes. Devuelve la
 *  misión, que la vista de writing muestra junto al enunciado. */
export async function paint(box, actions) {
  let data;
  try {
    data = await getJSON("/api/toefl/path");
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    box.replaceChildren(el("p", "foot-msg", error.message));
    return [];
  }
  const { today } = data;
  box.replaceChildren();

  const head = el("div", "panel-head");
  head.append(el("h2", "", "Camino a B1"),
    el("span", "sub", today.done === true ? "hoy: hecho ✓" : today.done === false ? "hoy: pendiente" : ""));
  box.append(head);

  const line = el("div", "b1-today");
  line.append(el("p", "", todayLine(today)));
  if (today.done === false && today.task === "new") {
    const go = el("button", "", `Empezar ${KIND_LABEL[today.kind] ?? today.kind}`);
    go.type = "button";
    go.addEventListener("click", () => actions.go(today.kind));
    line.append(go);
  }
  if (today.done === false && today.task === "rewrite" && today.rewrite) {
    const r = today.rewrite;
    line.append(el("p", "toefl-count",
      `${KIND_LABEL[r.item.kind] ?? r.item.kind} · salió ${r.level} (${r.score}/5)`));
    const go = el("button", "", "Reescribir");
    go.type = "button";
    go.addEventListener("click", () => actions.rewrite(r));
    line.append(go);
  }
  box.append(line, weekStrip(data.week), roadBox(data.road), missionBox(data.mission));
  return data.mission;
}
