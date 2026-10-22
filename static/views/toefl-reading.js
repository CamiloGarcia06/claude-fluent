// TOEFL · reading — Read in Daily Life y Read an Academic Passage: un texto y
// sus preguntas de opción múltiple, con reloj y sin modelo al corregir.
//
// El texto no se ve hasta apretar Empezar, como en writing: el reloj mide
// lectura más respuestas, que es lo que el examen te cobra. No se corta solo;
// pasado el ritmo del examen, el reloj cambia de color y seguís.
//
// Al corregir, la frase que responde cada pregunta se marca en el texto con
// su número: lo que entrena no es saber la respuesta, es saber dónde estaba.

import { $, el, getJSON, ApiError, working } from "/ui.js";
import { tipCard } from "/views/toefl-writing.js";

const LETTERS = "ABCD";

const clock = (seconds) =>
  `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

const TITLES = { daily: "Read in Daily Life", academic: "Read an Academic Passage" };

/** Monta la consigna con su botón de Empezar. `ctx`: { next, done }. */
export function paint(item, ctx) {
  $("toefl-title").textContent = TITLES[item.kind];
  $("toefl-meta").textContent = `ritmo del examen ≈ ${clock(item.target_seconds)}`;
  $("toefl-body").replaceChildren(el("p", "panel-note",
    `Un texto de ${item.words} palabras y ${item.questions.length} preguntas. El reloj ` +
    `arranca con Empezar; leyendo a ritmo de examen te lleva unos ${clock(item.target_seconds)}. ` +
    "Si pasás de ahí no se corta: el reloj cambia de color y seguís."));
  $("toefl-result").replaceChildren();

  const start = el("button", "", "Empezar");
  start.type = "button";
  start.addEventListener("click", () => compose(item, ctx));
  $("toefl-actions").replaceChildren(start);
}

function passage(item) {
  const box = el("div", "toefl-brief toefl-passage");
  box.append(el("p", "toefl-label", `${item.genre} · ${item.title}`));
  for (const text of item.paragraphs) box.append(el("p", "toefl-para", text));
  return box;
}

function compose(item, ctx) {
  const body = $("toefl-body");
  const chosen = item.questions.map(() => null);
  const list = el("ol", "toefl-questions");
  item.questions.forEach((q, qi) => {
    const li = el("li", "toefl-q");
    li.append(el("p", "toefl-prompt", q.prompt));
    q.options.forEach((option, oi) => {
      const label = el("label", "toefl-option");
      const radio = el("input");
      radio.type = "radio";
      radio.name = `q${qi}`;
      radio.addEventListener("change", () => { chosen[qi] = oi; paintCount(); });
      label.append(radio, el("span", "toefl-letter", `(${LETTERS[oi]})`), el("span", "", option));
      li.append(label);
    });
    list.append(li);
  });
  const counter = el("p", "toefl-count");
  const paintCount = () => {
    const done = chosen.filter((c) => c !== null).length;
    counter.textContent = `${done} de ${chosen.length} respondidas`;
  };
  body.replaceChildren(passage(item), list, counter);
  paintCount();

  const send = el("button", "", "Entregar");
  send.type = "button";
  $("toefl-actions").replaceChildren(send);

  const began = Date.now();
  const elapsed = () => Math.round((Date.now() - began) / 1000);
  const meta = $("toefl-meta");
  const tick = () => {
    const seconds = elapsed();
    meta.textContent = `${clock(seconds)} · ritmo del examen ${clock(item.target_seconds)}`;
    meta.dataset.urgent = String(seconds > item.target_seconds);
  };
  tick();
  const timer = setInterval(() => {
    if (!list.isConnected) { clearInterval(timer); return; }
    tick();
  }, 1000);

  send.addEventListener("click", async () => {
    const missing = chosen.filter((c) => c === null).length;
    if (missing && send.dataset.confirm !== "true") {
      send.dataset.confirm = "true";
      send.textContent = `Entregar igual (${missing} sin responder)`;
      return;
    }
    clearInterval(timer);
    const seconds = elapsed();
    working(send, true);
    let out;
    try {
      out = await getJSON("/api/toefl/read", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: item.kind, item_id: item.id, answers: chosen, seconds }),
      });
    } catch (error) {
      working(send, false);
      if (!(error instanceof ApiError)) throw error;
      $("toefl-result").replaceChildren(el("p", "foot-msg", `No se pudo corregir: ${error.message}`));
      return;
    }
    meta.dataset.urgent = "false";
    feedback(item, ctx, out, list, seconds);
    ctx.done();
  });
}

// Envuelve en <mark> la primera aparición de cada cita, con el número de su
// pregunta. Si dos citas se pisan, la segunda se marca solo en la lista.
function markEvidence(item, results) {
  const paras = [...$("toefl-body").querySelectorAll(".toefl-para")];
  item.paragraphs.forEach((text, pi) => {
    const hits = [];
    results.forEach((r, qi) => {
      const at = text.indexOf(r.evidence);
      if (at < 0) return;
      const end = at + r.evidence.length;
      if (hits.some((h) => at < h.end && end > h.at)) return;
      hits.push({ at, end, qi, correct: r.correct });
    });
    if (!hits.length) return;
    hits.sort((a, b) => a.at - b.at);
    const p = paras[pi];
    p.replaceChildren();
    let cursor = 0;
    for (const h of hits) {
      p.append(document.createTextNode(text.slice(cursor, h.at)));
      const mark = el("mark", "toefl-evidence", text.slice(h.at, h.end));
      mark.dataset.q = String(h.qi + 1);
      mark.dataset.correct = String(h.correct);
      p.append(mark);
      cursor = h.end;
    }
    p.append(document.createTextNode(text.slice(cursor)));
  });
}

function feedback(item, ctx, out, list, seconds) {
  markEvidence(item, out.results);
  [...list.children].forEach((li, qi) => {
    const r = out.results[qi];
    li.dataset.correct = String(r.correct);
    [...li.querySelectorAll(".toefl-option")].forEach((label, oi) => {
      label.querySelector("input").disabled = true;
      if (oi === r.answer) label.dataset.state = "right";
      else if (oi === r.chosen) label.dataset.state = "wrong";
    });
    const note = el("p", "toefl-why");
    note.append(el("span", "tag", `${r.correct ? "✓" : "✗"} ${r.label} · marca ${qi + 1} en el texto`),
      document.createTextNode(` ${r.why}`));
    li.append(note);
  });

  const result = $("toefl-result");
  result.replaceChildren(el("p", out.score === out.total ? "toefl-verdict" : "toefl-verdict toefl-wrong",
    `${out.score} de ${out.total}`));
  const slow = seconds > out.target_seconds;
  result.append(el("p", slow ? "toefl-count toefl-slow" : "toefl-count",
    `Tardaste ${clock(seconds)} · ritmo del examen ≈ ${clock(out.target_seconds)} ` +
    "(150 palabras por minuto y 30 s por pregunta; orientativo)"));
  if (slow) {
    result.append(el("p", "panel-note",
      "Te pasaste del ritmo. En el examen el tiempo es por módulo: leé primero la pregunta, " +
      "buscá en el texto la palabra clave y leé solo esa parte; no hace falta entender cada palabra."));
  }
  for (const tip of out.tips) result.append(tipCard(tip));

  const next = el("button", "", "Siguiente");
  next.type = "button";
  next.addEventListener("click", ctx.next);
  $("toefl-actions").replaceChildren(next);
  $("toefl-body").scrollIntoView({ behavior: "smooth", block: "start" });
}
