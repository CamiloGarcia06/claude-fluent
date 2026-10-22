// TOEFL — entrenar las dos tareas que más puntos dan por hora de estudio:
// Build a Sentence y Complete the Words, con el formato del iBT de enero 2026.
//
// Practicar no llama al modelo: el banco está en disco y la corrección es texto
// contra texto, así que responde al instante. El modelo sólo entra al rellenar
// el banco, y la barra de espera ocupa el lugar donde va a aparecer el
// ejercicio nuevo.
//
// El consejo sale de los últimos diez intentos de cada patrón, no de una
// historia: es lo que cambia cuando mejorás.

import { $, el, getJSON, ApiError, emptyRow, row, waiting, working } from "/ui.js";

// Medido el 22-10 contra claude -p: ocho frases 27 s, tres párrafos 23 s.
const REFILL_ESTIMATE_MS = 25000;

const TABS = [
  { kind: "sentence", label: "Build a Sentence", batch: "8 frases" },
  { kind: "words", label: "Complete the Words", batch: "3 párrafos" },
];

const MARKUP = `
<div id="toefl">
  <section class="hero">
    <p class="date">TOEFL · entrenamiento</p>
    <h1 id="toefl-headline"></h1>
    <p class="hero-note" id="toefl-tip"></p>
    <div id="toefl-tabs" class="filters"></div>
  </section>

  <section class="panel" id="toefl-exercise">
    <div class="panel-head">
      <h2 id="toefl-title"></h2>
      <span class="sub" id="toefl-meta"></span>
    </div>
    <div id="toefl-body"></div>
    <div class="actions" id="toefl-actions"></div>
    <div id="toefl-result"></div>
  </section>

  <section class="panel">
    <div class="panel-head">
      <h2>Cómo vienen tus patrones</h2>
      <span class="sub">últimos 10 intentos de cada uno</span>
    </div>
    <ul id="toefl-rows" class="rows"></ul>
  </section>
</div>
`;

let kind = "sentence";
let overview = null;
let current = null;

const tab = () => TABS.find((t) => t.kind === kind);

// ── Cabecera y patrones ───────────────────────────────────────────────

function paintHeader() {
  const data = overview[kind];
  const focus = data.patterns.find((p) => p.key === data.focus);
  if (focus) {
    $("toefl-headline").textContent = `Tu punto débil: ${focus.label.toLowerCase()}`;
    $("toefl-tip").textContent =
      `${focus.misses} de ${focus.tries} mal en los últimos intentos. ${focus.tip} ` +
      "Los próximos ejercicios van primero por ahí.";
  } else {
    $("toefl-headline").textContent = tab().label;
    $("toefl-tip").textContent =
      "Con unos cuantos intentos por patrón te digo dónde estás perdiendo puntos. " +
      "Hasta entonces, practicá: no hace falta que te salga bien.";
  }

  const bar = $("toefl-tabs");
  bar.replaceChildren();
  for (const t of TABS) {
    const link = el("a", "chip", `${t.label} (${overview[t.kind].fresh})`);
    link.href = `#/toefl/${t.kind}`;
    link.dataset.active = String(t.kind === kind);
    bar.append(link);
  }

  const list = $("toefl-rows");
  list.replaceChildren();
  for (const p of data.patterns) {
    const count = p.tries ? `${p.misses} de ${p.tries} mal` : "sin intentos";
    const li = row(p.label, count);
    if (p.key === data.focus) li.querySelector(".name").append(el("span", "tag", " · foco"));
    list.append(li);
  }
}

// ── El banco vacío ────────────────────────────────────────────────────

function paintEmpty(message) {
  const focus = overview[kind].focus;
  $("toefl-title").textContent = "No quedan ejercicios sin hacer";
  $("toefl-meta").textContent = "";
  const body = $("toefl-body");
  body.replaceChildren(el("p", "panel-note",
    message || `Genero ${tab().batch} nuevos con claude -p (unos 25 s). ` +
    (focus ? "Van cargados hacia tu punto débil." : "Van mezclando todos los patrones.")));
  $("toefl-result").replaceChildren();

  const actions = $("toefl-actions");
  const button = el("button", "", `Generar ${tab().batch}`);
  button.type = "button";
  button.addEventListener("click", () => refill(button, focus));
  actions.replaceChildren(button);
}

async function refill(button, focus) {
  working(button, true);
  const stop = waiting($("toefl-body"), REFILL_ESTIMATE_MS);
  try {
    const out = await getJSON("/api/toefl/refill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, focus }),
    });
    stop(true);
    await load();
    if (out.rejected) {
      $("toefl-meta").textContent = `${out.added} nuevos · ${out.rejected} descartados por mal formados`;
    }
  } catch (error) {
    stop(false);
    working(button, false);
    if (!(error instanceof ApiError)) throw error;
    paintEmpty(`No se pudo generar: ${error.message}`);
  }
}

// ── Build a Sentence ──────────────────────────────────────────────────

function paintSentence(item) {
  $("toefl-title").textContent = "Ordená las piezas para responder";
  const placed = [];   // índices de item.chunks, en el orden elegido
  const body = $("toefl-body");
  body.replaceChildren();

  body.append(el("p", "toefl-context", item.context));
  const line = el("p", "toefl-sentence");
  const pool = el("div", "toefl-pool");
  body.append(line, pool);

  const check = el("button", "", "Comprobar");
  check.type = "button";
  check.addEventListener("click", () => grade(placed.map((i) => item.chunks[i])));

  const paint = () => {
    line.replaceChildren();
    if (item.before) line.append(el("span", "toefl-fixed", item.before));
    placed.forEach((index, position) => {
      const chip = el("button", "toefl-chunk", item.chunks[index]);
      chip.type = "button";
      chip.addEventListener("click", () => { placed.splice(position, 1); paint(); });
      line.append(chip);
    });
    for (let i = placed.length; i < item.chunks.length; i++) line.append(el("span", "toefl-slot", " "));
    if (item.after) line.append(el("span", "toefl-fixed", item.after));

    pool.replaceChildren();
    item.chunks.forEach((chunk, index) => {
      if (placed.includes(index)) return;
      const chip = el("button", "chip", chunk);
      chip.type = "button";
      chip.addEventListener("click", () => { placed.push(index); paint(); });
      pool.append(chip);
    });
    check.disabled = placed.length !== item.chunks.length;
  };

  paint();
  $("toefl-actions").replaceChildren(check);
}

function sentenceResult(out) {
  const box = $("toefl-result");
  box.replaceChildren();
  box.append(el("p", out.correct ? "toefl-verdict" : "toefl-verdict toefl-wrong",
    out.correct ? "Correcto" : "No era así"));
  box.append(el("p", "toefl-answer", out.sentence));
  if (!out.correct) box.append(tipCard(out.tip));
}

// ── Complete the Words ────────────────────────────────────────────────

function paintWords(item) {
  $("toefl-title").textContent = "Completá las letras que faltan";
  const body = $("toefl-body");
  const paragraph = el("p", "toefl-paragraph");
  const inputs = [];

  item.gaps.forEach((gap, index) => {
    paragraph.append(document.createTextNode(item.parts[index]));
    const word = el("span", "toefl-gap");
    word.append(el("span", "toefl-shown", gap.shown));
    const input = el("input");
    input.type = "text";
    input.maxLength = gap.length;
    // Ancho en ch de la fuente mono: el hueco mide lo que va a caber en él.
    input.style.width = `${gap.length + 0.6}ch`;
    input.placeholder = "_".repeat(gap.length);
    input.autocomplete = "off";
    input.spellcheck = false;
    // Enter salta al siguiente hueco; en el último, comprueba.
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" || event.isComposing) return;
      event.preventDefault();
      const next = inputs[index + 1];
      if (next) next.focus();
      else check.click();
    });
    inputs.push(input);
    word.append(input);
    paragraph.append(word);
  });
  paragraph.append(document.createTextNode(item.parts[item.parts.length - 1]));
  body.replaceChildren(paragraph);

  const check = el("button", "", "Comprobar");
  check.type = "button";
  check.addEventListener("click", () => grade(inputs.map((i) => i.value), inputs));
  $("toefl-actions").replaceChildren(check);
  inputs[0]?.focus();
}

function wordsResult(out, inputs) {
  out.results.forEach((result, index) => {
    const input = inputs[index];
    input.disabled = true;
    input.closest(".toefl-gap").dataset.state = result.correct ? "right" : "wrong";
    if (!result.correct) input.after(el("span", "toefl-fix", result.missing));
  });
  const box = $("toefl-result");
  box.replaceChildren(el("p", out.score === out.total ? "toefl-verdict" : "toefl-verdict toefl-wrong",
    `${out.score} de ${out.total}`));
  for (const tip of out.tips) box.append(tipCard(tip));
}

// ── Común ─────────────────────────────────────────────────────────────

function tipCard(tip) {
  const card = el("div", "toefl-tip");
  card.append(el("span", "tag", tip.label), el("p", "", tip.tip), el("p", "toefl-example", tip.example));
  return card;
}

async function grade(answer, inputs) {
  const check = $("toefl-actions").querySelector("button");
  working(check, true);
  let out;
  try {
    out = await getJSON("/api/toefl/grade", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, item_id: current.id, answer }),
    });
  } catch (error) {
    working(check, false);
    if (!(error instanceof ApiError)) throw error;
    $("toefl-result").replaceChildren(el("p", "foot-msg", error.message));
    return;
  }
  if (kind === "sentence") {
    for (const chip of $("toefl-body").querySelectorAll("button")) chip.disabled = true;
    sentenceResult(out);
  } else {
    wordsResult(out, inputs);
  }

  const next = el("button", "", "Siguiente");
  next.type = "button";
  next.addEventListener("click", load);
  $("toefl-actions").replaceChildren(next);
  next.focus();

  // El intento ya cuenta: la cabecera y los patrones lo muestran sin esperar
  // al siguiente ejercicio. Si esta lectura falla, el resultado ya está en
  // pantalla y la próxima carga lo arregla.
  try {
    overview = await getJSON("/api/toefl/overview");
    paintHeader();
    $("toefl-meta").textContent = `quedan ${overview[kind].fresh} sin hacer`;
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
  }
}

async function load() {
  overview = await getJSON("/api/toefl/overview");
  paintHeader();
  $("toefl-result").replaceChildren();
  if (!overview[kind].fresh) {
    paintEmpty();
    return;
  }
  const out = await getJSON(`/api/toefl/next/${kind}`);
  current = out.item;
  $("toefl-meta").textContent = `quedan ${out.fresh} sin hacer`;
  if (kind === "sentence") paintSentence(current);
  else paintWords(current);
}

export async function render(root, params) {
  kind = TABS.some((t) => t.kind === params[0]) ? params[0] : "sentence";
  root.innerHTML = MARKUP;
  current = null;
  if (!overview) $("toefl-rows").append(emptyRow("Leyendo tus intentos…"));
  await load();
}
