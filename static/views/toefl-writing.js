// TOEFL · writing — Write an Email (7 min) y Write for an Academic Discussion
// (10 min, 100 palabras), con el reloj del examen y la corrección de Claude con
// la rúbrica de ETS.
//
// El enunciado no se ve hasta apretar Empezar: en el examen el reloj arranca
// con él, y leerlo antes regala minutos que el día del examen no vas a tener.
//
// Después de la corrección se puede reescribir el mismo texto con las
// correcciones a la vista. Es donde se aprende el error; por eso va sin reloj y
// no cuenta para los consejos, que miden el primer intento.

import { $, el, getJSON, ApiError, waiting, working } from "/ui.js";

// Medido el 22-10: un email de 53 palabras tardó 25 s en corregirse (rúbrica,
// ocho correcciones y la versión en nivel 5).
const GRADE_ESTIMATE_MS = 25000;

const WORD = /[A-Za-z]+(?:['’][A-Za-z]+)*|\d+/g;
const countWords = (text) => (text.match(WORD) || []).length;

const clock = (seconds) =>
  `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

export function tipCard(tip) {
  const card = el("div", "toefl-tip");
  card.append(el("span", "tag", tip.label), el("p", "", tip.tip), el("p", "toefl-example", tip.example));
  return card;
}

function briefEmail(item) {
  const box = el("div", "toefl-brief");
  box.append(el("p", "", item.situation));
  const list = el("ul", "toefl-bullets");
  for (const bullet of item.bullets) list.append(el("li", "", bullet));
  box.append(el("p", "toefl-label", "En tu email:"), list);
  box.append(el("p", "toefl-mail", `To: ${item.to}`), el("p", "toefl-mail", `Subject: ${item.subject}`));
  return box;
}

function briefDiscussion(item) {
  const box = el("div", "toefl-brief");
  box.append(el("p", "toefl-label", `Profesor · ${item.course}`), el("p", "", item.professor));
  for (const post of item.posts) {
    const p = el("p", "toefl-post");
    p.append(el("span", "toefl-label", post.name), document.createTextNode(` ${post.text}`));
    box.append(p);
  }
  box.append(el("p", "toefl-label",
    "Escribí tu contribución: tu opinión, con razones y ejemplos, en tus palabras."));
  return box;
}

/** Monta el enunciado con su botón de Empezar. `ctx`: { kind, done } — `done`
 *  vuelve a leer la cabecera cuando la entrega ya cuenta. */
export function paint(item, ctx) {
  $("toefl-title").textContent = item.kind === "email" ? "Write an Email" : "Academic Discussion";
  $("toefl-meta").textContent = `${item.minutes} min`;
  const body = $("toefl-body");
  body.replaceChildren(el("p", "panel-note",
    `Tenés ${item.minutes} minutos desde que aparece el enunciado` +
    (item.min_words ? `, y un mínimo de ${item.min_words} palabras.` : ".") +
    " Al terminar el tiempo se entrega solo."));
  $("toefl-result").replaceChildren();

  const start = el("button", "", `Empezar (${item.minutes}:00)`);
  start.type = "button";
  start.addEventListener("click", () => compose(item, ctx, { timed: true, text: "" }));
  $("toefl-actions").replaceChildren(start);
}

function compose(item, ctx, { timed, text, firstText }) {
  const body = $("toefl-body");
  body.replaceChildren(item.kind === "email" ? briefEmail(item) : briefDiscussion(item));

  const box = el("textarea", "termbox toefl-text");
  box.rows = item.kind === "email" ? 10 : 12;
  box.spellcheck = false;   // el examen no tiene corrector
  box.value = text;
  const counter = el("p", "toefl-count");
  const paintCount = () => {
    const words = countWords(box.value);
    counter.textContent = item.min_words
      ? `${words} palabras · mínimo ${item.min_words}`
      : `${words} palabras`;
    counter.dataset.short = String(item.min_words > 0 && words < item.min_words);
  };
  box.addEventListener("input", paintCount);
  body.append(box, counter);
  paintCount();

  const send = el("button", "", timed ? "Entregar" : "Entregar la reescritura");
  send.type = "button";
  $("toefl-actions").replaceChildren(send);
  box.focus();

  const began = Date.now();
  let timer = null;
  const submit = () => {
    if (timer) clearInterval(timer);
    const seconds = Math.round((Date.now() - began) / 1000);
    deliver(item, ctx, box, send, { seconds: timed ? seconds : null, revision: !timed, firstText });
  };
  send.addEventListener("click", submit);

  if (!timed) {
    $("toefl-meta").textContent = "reescritura · sin reloj";
    return;
  }
  let left = item.minutes * 60;
  $("toefl-meta").textContent = clock(left);
  timer = setInterval(() => {
    // La vista se fue (otra pantalla): el reloj se apaga solo.
    if (!box.isConnected) { clearInterval(timer); return; }
    left -= 1;
    $("toefl-meta").textContent = clock(Math.max(left, 0));
    $("toefl-meta").dataset.urgent = String(left <= 60);
    if (left <= 0) submit();
  }, 1000);
}

async function deliver(item, ctx, box, send, { seconds, revision, firstText }) {
  const text = box.value;
  if (!text.trim()) {
    $("toefl-result").replaceChildren(el("p", "foot-msg",
      seconds === null ? "No escribiste nada." : "Se acabó el tiempo sin texto: no hay qué corregir."));
    return;
  }
  box.readOnly = true;
  working(send, true);
  const result = $("toefl-result");
  result.replaceChildren();
  const stop = waiting(result, GRADE_ESTIMATE_MS);
  let out;
  try {
    out = await getJSON("/api/toefl/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: item.kind, item_id: item.id, text, seconds, revision }),
    });
  } catch (error) {
    stop(false);
    box.readOnly = false;
    working(send, false);
    if (!(error instanceof ApiError)) throw error;
    result.replaceChildren(el("p", "foot-msg", `No se pudo corregir: ${error.message}`));
    return;
  }
  stop(true);
  feedback(item, ctx, out, firstText ?? text);
  ctx.done();
}

function feedback(item, ctx, out, firstText) {
  const result = $("toefl-result");
  result.replaceChildren();

  const verdict = el("p", out.score >= 4 ? "toefl-verdict" : "toefl-verdict toefl-wrong",
    `${out.score} / ${out.max_score}`);
  result.append(verdict);
  if (out.revision && out.first_score !== null) {
    result.append(el("p", "toefl-count", `Primera versión: ${out.first_score} / ${out.max_score}`));
  }
  result.append(el("p", "toefl-count",
    `${out.words} palabras · estimación de Claude con la rúbrica de ETS, no es una nota oficial`));
  if (out.summary) result.append(el("p", "panel-note", out.summary));

  const criteria = el("ul", "rows toefl-criteria");
  for (const c of out.criteria) {
    const li = el("li");
    li.dataset.ok = String(c.ok);
    li.append(el("span", "name", `${c.ok ? "✓" : "✗"} ${c.label}`), el("span", "toefl-comment", c.comment));
    criteria.append(li);
  }
  result.append(criteria);

  if (out.corrections.length) {
    result.append(el("h3", "toefl-subhead", "Correcciones"));
    const list = el("ul", "area-examples toefl-corrections");
    for (const c of out.corrections) {
      const li = el("li");
      li.append(el("span", "ex-wrong", c.wrong), el("span", "ex-right", c.right));
      if (c.why) li.append(el("span", "toefl-why", c.why));
      list.append(li);
    }
    result.append(list);
  }

  if (out.improved) {
    result.append(el("h3", "toefl-subhead", "Tu texto, en nivel 5"));
    result.append(el("p", "toefl-improved", out.improved));
  }
  for (const tip of out.tips) result.append(tipCard(tip));

  const again = el("button", "ghost", "Reescribir con las correcciones");
  again.type = "button";
  again.addEventListener("click", () => {
    compose(item, ctx, { timed: false, text: firstText, firstText });
    // Las correcciones quedan a la vista debajo mientras reescribís.
    $("toefl-result").prepend(el("p", "toefl-label", "Lo que te marqué la primera vez:"));
  });
  const next = el("button", "", "Siguiente");
  next.type = "button";
  next.addEventListener("click", ctx.next);
  $("toefl-actions").replaceChildren(next, again);
}
