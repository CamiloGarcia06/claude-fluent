// Conversar en inglés y que te corrijan mientras escribís.
//
// Nada de burbujas de chat: una burbuja no es una ficha de cartón. Cada
// intercambio es un bloque separado por una regla, con la etiqueta mono al
// costado, y la corrección se dibuja con el mismo par antes/después que el
// panel de reparación — porque es lo mismo, lo que hay contra lo que debería
// haber.
//
// La conversación vive en el servidor: `llm.generate` no tiene memoria, así que
// el historial viaja dentro del prompt en cada turno y tiene que sobrevivir al
// proceso igual. Acá sólo se espeja lo que el servidor devolvió, como `add.js`
// espeja sus candidatas.

import {
  $, el, getJSON, side, ApiError, plural, waiting, working,
  loadMotion, staggerStep, DURATION_MS,
} from "/ui.js";

// Medido contra la colección real: los turnos caen entre 13 y 21 s, y el
// cierre entre 30 y 35. La barra no llega nunca al 100 % esperando.
const TURN_ESTIMATE_MS = 18000;
const CLOSE_ESTIMATE_MS = 32000;

// A partir de acá el cierre tiene con qué. Nombra **hábitos**, no resbalones, y
// para distinguirlos necesita verte repetir algo: con dos intercambios cada
// hallazgo se apoya en un solo ejemplo. Por debajo el botón no se bloquea —
// cerrar siempre se puede— sólo deja de insistir.
const READY_AFTER = 5;

const LEVELS = ["A1", "A2", "B1", "B2", "C1"];

// El nivel no se lee del catálogo: para Writing dice A1 por ausencia y no por
// diagnóstico, porque la caminata se detiene en el primer nivel que no se
// sostiene y un nivel vacío tampoco se sostiene. Ver PRACTICE_LEVEL en app.py.
const DEFAULT_LEVEL = "B1";

// Concretos y con algo que contar. "Vocabulario" o "el trabajo" no arrancan una
// conversación; "qué hice hoy" sí.
const FALLBACK_TOPICS = ["qué hice hoy", "anime", "mi trabajo",
                         "una serie que estoy viendo", "el fin de semana",
                         "un problema que resolví"];

const MARKUP = `
  <div id="practice">
    <section class="hero">
      <p class="date" id="practice-kicker">Práctica de escritura</p>
      <h1 id="practice-title">Escribí en inglés y te corrijo</h1>
      <p class="hero-note" id="practice-sub"></p>
      <p class="hint" id="practice-hint" hidden></p>
    </section>

    <section class="panel" id="setup">
      <div class="panel-head"><h2>¿De qué querés hablar?</h2></div>
      <p class="panel-note">Elegí un tema y escribimos sobre eso. Te contesto en
        inglés y te corrijo sólo lo que estorba el mensaje.</p>
      <textarea id="topic" class="termbox" rows="2" spellcheck="false"
        placeholder="anime, mi trabajo con Odoo, el fin de semana…"></textarea>
      <div class="chips" id="topic-chips"></div>
      <div class="level-pick" id="level-pick"></div>
      <div class="actions">
        <button id="start" type="button">Empezar</button>
        <button id="see-last" type="button" class="ghost" hidden></button>
        <a class="ghost" href="#/patrones">Ver mis patrones</a>
      </div>
      <p class="foot-msg" id="setup-msg" hidden></p>
    </section>

    <section class="panel" id="thread-panel" hidden>
      <div class="panel-head">
        <h2 id="thread-topic"></h2>
      </div>
      <p class="sub-note" id="thread-meta"></p>
      <div id="thread"></div>

      <div class="composer" id="composer">
        <textarea id="message" class="termbox" rows="3" spellcheck="false"
          placeholder="Escribí tu respuesta en inglés…"></textarea>
        <!-- La pista de espera se inserta acá y se va cuando llega la
             respuesta. Vivía en el markup, siempre presente: un surco de 8 px
             bajo la caja que no significaba nada mientras no pasaba nada. -->
        <div id="turn-wait"></div>
        <div class="composer-foot">
          <span class="composer-tip">Enter envía · Shift+Enter salta de línea</span>
          <span class="foot-msg" id="send-msg" hidden></span>
          <span class="turn-count" id="turn-count"></span>
          <button id="finish" type="button" class="ghost">Cerrar y analizar</button>
          <button id="send" type="button">Enviar</button>
        </div>
      </div>
    </section>

    <section class="panel" id="close-panel" hidden>
      <div class="panel-head"><h2>Cómo te fue</h2></div>
      <p class="diagnosis" id="close-summary"></p>
      <h3 class="block-title" id="strengths-title" hidden>Lo que te salió bien</h3>
      <ul class="rows" id="close-strengths"></ul>
      <div id="close-areas"></div>
      <div id="close-turns"></div>
      <div class="actions">
        <button id="restart" type="button">Practicar de nuevo</button>
        <a class="ghost" href="#/patrones">Ver mis patrones</a>
      </div>
    </section>
  </div>
`;

let session = null;
let last = null;      // la última cerrada, para releer su análisis
let level = DEFAULT_LEVEL;
let busy = false;
let ticket = 0;

// ── Estado de la pantalla ─────────────────────────────────────────────

/** Un ticket por operación larga: mandar un turno y cerrar la sesión pueden
 *  pisarse, y la respuesta de la que perdió no puede repintar nada. */
function claim() {
  ticket += 1;
  const mine = ticket;
  return () => mine === ticket;
}

function hint(text) {
  const node = $("practice-hint");
  node.textContent = text || "";
  node.hidden = !text;
}

/** El mensaje va al lado del botón que apretaste. En el hero estaría a una
 *  pantalla de scroll del botón, o sea sería un error invisible. */
function message(id, text, ok = true) {
  const node = $(id);
  node.textContent = text || "";
  node.dataset.ok = String(ok);
  node.hidden = !text;
}

function setBusy(value, fired) {
  busy = value;
  $("send").disabled = value;
  $("finish").disabled = value;
  $("start").disabled = value;
  // Y el que apretaste lo dice: conserva su tinta en vez de irse al gris de
  // "no está disponible". Los otros dos sí quedan deshabilitados de verdad.
  // Se limpian los tres antes, o el atributo queda pegado al que disparó la
  // llamada anterior y vuelve a pintarse la próxima vez que se deshabilite.
  for (const id of ["send", "finish", "start"]) $(id).dataset.working = "false";
  working(fired, value);
  // El textarea NO se deshabilita: bloquear un campo de texto veinte segundos
  // se siente roto, y seguir escribiendo es la única forma de recuperar la
  // espera.
}

/** La espera del turno y la del cierre, que nunca se pisan: las dos llamadas
 *  se excluyen por `busy`. */
let stopBar = null;

const startBar = (estimate) => { stopBar = waiting($("turn-wait"), estimate); };
const endBar = (done) => { stopBar?.(done); stopBar = null; };

/** El bloque recién llegado entra; el resto del hilo no se toca.
 *
 *  Son diecisiete segundos de espera y después el bloque aparece de golpe a
 *  media pantalla: la entrada es lo que dice "esto es lo nuevo". Es la única
 *  animación de esta pantalla y ocurre una vez cada veinte segundos — nada que
 *  cruces cien veces, que es lo que el sistema deja sin animar. */
function enterLastTurn() {
  loadMotion().then((motion) => {
    const block = $("thread")?.lastElementChild;
    if (!motion || !block) return;
    motion.animate(block, {
      opacity: [0, 1],
      y: [8, 0],
      duration: DURATION_MS,
      ease: "outQuad",
    });
  });
}

/** El análisis llega después de medio minuto y es media pantalla de texto. La
 *  cascada corta la aparición de golpe y ordena por dónde empezar a leer; como
 *  en Hoy, todo termina dentro del mismo presupuesto. */
function enterClose() {
  loadMotion().then((motion) => {
    if (!motion) return;
    const blocks = document.querySelectorAll(
      "#close-strengths li, #close-areas .block-title, #close-areas .area, "
      + "#close-areas .rows li, #close-turns .block-title, #close-turns .field");
    if (!blocks.length) return;
    motion.animate(blocks, {
      opacity: [0, 1],
      y: [6, 0],
      duration: DURATION_MS,
      delay: motion.stagger(staggerStep(blocks.length)),
      ease: "outQuad",
    });
  });
}

// ── La conversación ───────────────────────────────────────────────────

// ── Marcar qué cambió ─────────────────────────────────────────────────
// Poner tu frase al lado de la corregida no alcanza si el idioma es el que
// estás aprendiendo: dos párrafos parecidos y tenés que encontrar la diferencia
// vos, adivinando. Así que se marca palabra por palabra — es la única forma de
// que el par antes/después se lea sin saber inglés.

const words = (text) => String(text || "").split(/\s+/).filter(Boolean);

/** Diff por palabras con la subsecuencia común más larga. Los mensajes son de
 *  decenas de palabras, así que la tabla cuadrática no cuesta nada y da el
 *  alineamiento mínimo — que es lo que hace que sólo se marque lo que cambió y
 *  no media frase corrida. */
function diffOps(a, b) {
  const n = a.length, m = b.length;
  const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j]
        ? dp[i + 1][j + 1] + 1
        : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const ops = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { ops.push(["same", a[i]]); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { ops.push(["del", a[i]]); i++; }
    else { ops.push(["ins", b[j]]); j++; }
  }
  while (i < n) ops.push(["del", a[i++]]);
  while (j < m) ops.push(["ins", b[j++]]);
  return ops;
}

/** Un lado del par: lo que se conserva en texto plano, lo que cambia marcado. */
function marked(ops, keep) {
  const frag = document.createDocumentFragment();
  let first = true;
  for (const [tag, word] of ops) {
    if (tag !== "same" && tag !== keep) continue;
    if (!first) frag.append(document.createTextNode(" "));
    first = false;
    frag.append(tag === keep ? el("span", "chg", word)
                             : document.createTextNode(word));
  }
  return frag;
}

/** El par antes/después con las dos caras marcadas contra la otra. */
function pair(wroteLabel, wrote, correctLabel, correct) {
  const ops = diffOps(words(wrote), words(correct));
  return [
    side(wroteLabel, marked(ops, "del"), false, "wrong"),
    side(correctLabel, marked(ops, "ins"), true, "right"),
  ];
}

function correction(item) {
  const block = el("div", "field");
  block.dataset.changed = "true";
  const tag = [item.category_es, item.severity_es].filter(Boolean).join(" · ");
  block.append(
    el("div", "field-name", tag),
    ...pair("Escribiste", item.wrote, "Correcto", item.correct),
  );
  if (item.why) block.append(el("p", "field-why", item.why));
  return block;
}

function turnBlock(turn) {
  const box = el("article", "turn");
  box.dataset.state = turn.state;

  const said = el("div", "turn-said");
  said.append(el("span", "turn-label", "Vos"), el("p", "turn-text", turn.text));
  box.append(said);

  if (turn.state === "pending") {
    box.append(el("p", "turn-note", "quedó sin respuesta — recargaste mientras pensaba"));
    box.append(retryButton(turn));
    return box;
  }
  if (turn.state === "failed") {
    box.append(el("p", "turn-note", turn.error || "el modelo falló en este turno"));
    box.append(retryButton(turn));
    return box;
  }

  const answer = el("div", "turn-reply");
  answer.append(el("span", "turn-label", "Claude"));
  if (turn.reply) answer.append(el("p", "turn-text", turn.reply));
  // La pregunta lleva el peso porque es lo que tenés que contestar. No lleva
  // el acento: en esta pantalla el acento ya está en Enviar, y sólo hay uno.
  if (turn.question) answer.append(el("p", "turn-question", turn.question));
  box.append(answer);

  if (turn.corrections.length) {
    const diff = el("div", "diff");
    for (const item of turn.corrections) diff.append(correction(item));
    box.append(diff);
  }

  if (turn.alternative) {
    const alt = el("div", "alt");
    alt.append(el("span", "turn-label", "Más natural"),
               el("p", "alt-text", turn.alternative));
    box.append(alt);
  }
  return box;
}

function retryButton(turn) {
  const button = el("button", "ghost", "Reintentar");
  button.type = "button";
  button.addEventListener("click", () => send(turn.text, turn.index));
  return button;
}

function paintThread() {
  const box = $("thread");
  box.replaceChildren();
  for (const turn of session.turns) box.append(turnBlock(turn));

  $("thread-topic").textContent = session.topic;
  const done = session.turns.filter((t) => t.state === "done").length;
  $("thread-meta").textContent = done
    ? `${session.level} · ${plural(done, "intercambio", "intercambios")}`
    : `${session.level} · empezá cuando quieras`;

  // El contador y el botón viven abajo, al lado de Enviar. Estaban en la
  // cabecera del panel: a los cinco intercambios el hilo ya los había empujado
  // fuera de pantalla, y cerrar es lo único que hace que la sesión cuente.
  $("turn-count").textContent = done
    ? plural(done, "intercambio", "intercambios") : "";
  const ready = done >= READY_AFTER;
  $("finish").dataset.ready = String(ready);
  $("finish").textContent = ready ? "Listo para analizar" : "Cerrar y analizar";
  $("finish").title = ready
    ? "Ya tenés material para que el análisis encuentre hábitos y no resbalones."
    : `El análisis distingue hábitos de resbalones: con ${READY_AFTER} intercambios tiene con qué.`;

  box.lastElementChild?.scrollIntoView({ block: "nearest" });
}

// ── Acciones ──────────────────────────────────────────────────────────

async function start() {
  const topic = $("topic").value.trim();
  if (!topic) {
    message("setup-msg", "Escribí un tema, o elegí uno de los de arriba.", false);
    $("topic").focus();
    return;
  }
  const mine = claim();
  setBusy(true, $("start"));
  message("setup-msg", "");

  try {
    // `restart` va siempre, y es seguro por cómo se llega acá: si había una
    // sesión abierta, `render` la retomó y este panel ni se ve. La única otra
    // puerta es "Practicar de nuevo", y ahí la anterior ya está cerrada.
    const data = await getJSON("/api/practice/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic, level, restart: true }),
    });
    if (!mine()) return;
    session = data.session;
    enterConversation(data.opening);
  } catch (error) {
    if (!mine()) return;
    message("setup-msg", error instanceof ApiError ? error.message : "No se pudo empezar.", false);
  } finally {
    if (mine()) setBusy(false);
  }
}

function enterConversation(opening) {
  $("setup").hidden = true;
  $("close-panel").hidden = true;
  $("thread-panel").hidden = false;
  hint(opening || "");
  paintThread();
  $("message").focus();
}

async function send(text, replaceIndex) {
  const value = (text ?? $("message").value).trim();
  if (!value || busy) return;

  const mine = claim();
  setBusy(true, $("send"));
  message("send-msg", "");
  startBar(TURN_ESTIMATE_MS);

  // El mensaje se vacía ya: el servidor lo persiste antes de llamar al modelo,
  // así que dejarlo en la caja invitaría a mandarlo dos veces.
  if (replaceIndex === undefined) $("message").value = "";

  try {
    const data = await getJSON("/api/practice/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: session.id, text: value,
        ...(replaceIndex === undefined ? {} : { retry_index: replaceIndex }),
      }),
    });
    if (!mine()) return;
    endBar(true);
    await refresh();
    enterLastTurn();
  } catch (error) {
    if (!mine()) return;
    endBar(false);
    // El texto vuelve a la caja: perder lo que escribiste porque el modelo se
    // cayó es el peor final posible para un turno.
    if (replaceIndex === undefined && !$("message").value.trim()) {
      $("message").value = value;
    }
    message("send-msg", error instanceof ApiError ? error.message : "El turno falló.", false);
    await refresh();
  } finally {
    if (mine()) setBusy(false);
  }
}

/** Releer la sesión del servidor en vez de parchear el objeto local. El
 *  archivo es la conversación; el navegador sólo la espeja. */
async function refresh() {
  try {
    const data = await getJSON("/api/practice/session");
    if (data.session) {
      session = data.session;
      paintThread();
    }
  } catch {
    // Si el refresco falla, lo que ya está pintado sigue siendo válido.
  }
}

async function finish() {
  if (busy) return;
  const done = session.turns.filter((t) => t.state === "done").length;
  if (done && !window.confirm(
        "Cerrar la sesión y analizarla. Tarda algo más de medio minuto. ¿Vamos?")) {
    return;
  }

  const mine = claim();
  setBusy(true, $("finish"));
  message("send-msg", "Leyendo toda la sesión… cerca de medio minuto.");
  startBar(CLOSE_ESTIMATE_MS);

  try {
    const data = await getJSON("/api/practice/close", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: session.id }),
    });
    if (!mine()) return;
    endBar(true);
    session = data.session;
    paintClose(data);
  } catch (error) {
    if (!mine()) return;
    endBar(false);
    message("send-msg", error instanceof ApiError ? error.message : "No se pudo cerrar.", false);
  } finally {
    if (mine()) setBusy(false);
  }
}

// ── El cierre ─────────────────────────────────────────────────────────

function areaBlock(area) {
  const box = el("section", "area");
  const tag = [area.area_es, area.severity_es].filter(Boolean).join(" · ");
  box.append(el("div", "field-name", tag), el("p", "area-finding", area.finding));

  // Un hallazgo sin patrón no suma para tarjeta, y se dibujaba idéntico a uno
  // que sí: un hábito crítico se leía como cualquier otro mientras el contador
  // lo ignoraba. Ahora lo dice.
  if (!area.pattern) {
    box.append(el("p", "area-uncounted",
      "Este hábito todavía no está en el catálogo de patrones, así que no suma "
      + "para tarjeta."));
  }

  // Cada caso va con su arreglo. Un `tink` suelto señala dónde te equivocaste
  // sin decir qué iba ahí, y para cuando leés el análisis la frase que lo
  // rodeaba quedó veinte minutos atrás.
  if (area.examples.length) {
    const list = el("ul", "area-examples");
    for (const case_ of area.examples) {
      const ops = diffOps(words(case_.wrong), words(case_.right));
      const item = el("li");
      const wrong = el("span", "ex-wrong");
      wrong.append(marked(ops, "del"));
      const right = el("span", "ex-right");
      right.append(marked(ops, "ins"));
      item.append(wrong, right);
      list.append(item);
    }
    box.append(list);
  }
  return box;
}

function readyRow(row) {
  const item = el("li");
  item.append(el("span", "name", row.label));
  const note = el("span", "count",
    `te pasó en ${plural(row.count, "sesión", "sesiones")}`);
  item.append(note);

  const link = el("a", "ghost", "Hacer tarjeta");
  const path = [row.skill, row.level, row.seed].map(encodeURIComponent).join("/");
  link.href = `#/agregar/${path}`;

  // Se marca y DESPUÉS se navega. Dejar el POST volando mientras el hash cambia
  // es una carrera que se pierde a veces, y perderla significa que el patrón te
  // sigue reclamando una tarjeta que ya fuiste a escribir.
  link.addEventListener("click", async (event) => {
    event.preventDefault();
    try {
      await getJSON("/api/practice/patterns", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: row.key, action: "carded" }),
      });
    } catch {
      // Que no se marque no puede impedirte ir a escribir la tarjeta.
    }
    location.hash = link.getAttribute("href");
  });
  item.append(link);
  return item;
}

/** Releer el análisis de la última sesión cerrada. No cuenta nada: el conteo
 *  ocurrió cuando se cerró, y esto sólo vuelve a dibujar lo que ya está en
 *  disco. Los patrones listos se piden aparte porque el umbral pudo haberse
 *  alcanzado —o apagado— después de aquel cierre. */
async function showLast() {
  session = last;
  $("setup").hidden = true;
  let ready = [];
  try {
    ready = (await getJSON("/api/practice/patterns")).patterns.filter((p) => p.ready);
  } catch {
    // Sin la lista sólo faltan los enlaces a Agregar; el análisis se lee igual.
  }
  paintClose({ ready });
}

function paintClose(data) {
  const analysis = session.analysis;
  $("thread-panel").hidden = true;
  $("close-panel").hidden = false;
  hint("");

  if (!analysis) {
    $("close-summary").textContent =
      "No llegaste a escribir nada, así que no hay nada que leer. Empezá de nuevo cuando quieras.";
    $("close-strengths").replaceChildren();
    $("close-areas").replaceChildren();
    $("close-turns").replaceChildren();
    return;
  }

  $("close-summary").textContent = analysis.summary;

  // Tres frases sueltas colgando del resumen, sin nada que dijera qué eran:
  // las otras dos mitades del cierre sí llevan título, y esta se leía como una
  // continuación del párrafo de arriba.
  const strengths = $("close-strengths");
  strengths.replaceChildren();
  $("strengths-title").hidden = analysis.strengths.length === 0;
  for (const item of analysis.strengths) {
    strengths.append(el("li", null, item));
  }

  const areas = $("close-areas");
  areas.replaceChildren();
  if (analysis.areas.length) {
    areas.append(el("h3", "block-title", "Para trabajar"));
    for (const area of analysis.areas) areas.append(areaBlock(area));
  }

  if (data.ready?.length) {
    areas.append(el("h3", "block-title", "Ya son tarjeta"));
    const list = el("ul", "rows");
    for (const row of data.ready) list.append(readyRow(row));
    areas.append(list);
  }

  const turns = $("close-turns");
  turns.replaceChildren();
  const changed = analysis.turns.filter((t) => t.rewritten);
  if (changed.length) {
    turns.append(el("h3", "block-title", "Tus mensajes, reescritos"));
    const diff = el("div", "diff");
    for (const item of changed) {
      const block = el("div", "field");
      block.dataset.changed = "true";
      block.append(
        el("div", "field-name", `Mensaje ${item.index + 1}`),
        ...pair("Escribiste", item.text, "Más natural", item.rewritten),
      );
      if (item.note) block.append(el("p", "field-why", item.note));
      diff.append(block);
    }
    turns.append(diff);
  }

  // Al final, con las tres mitades ya en el DOM: la cascada las ordena.
  enterClose();
}

// ── Arranque ──────────────────────────────────────────────────────────

function levelPicker() {
  const box = $("level-pick");
  box.replaceChildren(el("span", "pick-label", "Nivel"));
  for (const name of LEVELS) {
    const button = el("button", "chip", name);
    button.type = "button";
    button.dataset.active = String(name === level);
    button.addEventListener("click", () => {
      level = name;
      for (const other of box.querySelectorAll(".chip")) {
        other.dataset.active = String(other.textContent === name);
      }
    });
    box.append(button);
  }
}

/** Los temas que ya elegiste, y detrás los genéricos.
 *
 *  Salían de los mazos, y estaba mal: el tema de un mazo dice qué enseña, y en
 *  Grammar eso es una regla. La pantalla ofrecía «Negatives with any» y
 *  «Adverbs of frequency» como temas de conversación, que no son temas de
 *  conversación de nada. Un tema que ya elegiste vos está probado por
 *  definición: conversaste sobre él. */
function topicChips(mine = []) {
  const chips = $("topic-chips");
  const topics = [...new Set([...mine, ...FALLBACK_TOPICS])].slice(0, 7);

  chips.replaceChildren();
  for (const topic of topics) {
    const button = el("button", "chip", topic);
    button.type = "button";
    button.addEventListener("click", () => {
      $("topic").value = topic;
      $("topic").focus();
    });
    chips.append(button);
  }
}

export async function render(root, params) {
  root.innerHTML = MARKUP;
  session = null;
  last = null;
  level = DEFAULT_LEVEL;
  busy = false;
  ticket = 0;

  $("practice-sub").textContent =
    "Writing no tiene una sola tarjeta todavía. Esto es lo que la va a llenar: " +
    "lo que falles tres veces se vuelve tarjeta.";

  levelPicker();
  topicChips();   // los genéricos, hasta que llegue el GET

  $("start").addEventListener("click", start);
  $("restart").addEventListener("click", () => {
    $("close-panel").hidden = true;
    $("setup").hidden = false;
    session = null;
    $("topic").value = "";
    $("topic").focus();
  });
  $("send").addEventListener("click", () => send());
  $("finish").addEventListener("click", finish);

  // El primer listener de teclado de la app. Enter manda; Shift+Enter salta de
  // línea; `isComposing` deja en paz a los teclados con composición, donde
  // Enter confirma un caracter y no termina una frase.
  $("message").addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
    event.preventDefault();
    send();
  });

  try {
    const data = await getJSON("/api/practice/session");
    if (data.session) {
      session = data.session;
      level = session.level || DEFAULT_LEVEL;
      levelPicker();
      enterConversation(
        `Retomamos lo de «${session.topic}». Seguí donde lo dejaste.`);
      return;
    }

    // El análisis dejó de ser de un solo uso. Estaba entero en el disco y no
    // había forma de volver a mirarlo: cerrabas la sesión, cambiabas de
    // pantalla, y lo perdías aunque el archivo siguiera ahí.
    topicChips(data.topics || []);

    if (data.last?.analysis) {
      last = data.last;
      const button = $("see-last");
      button.textContent = `Ver el análisis de «${last.topic}»`;
      button.title = `Releer el análisis de la sesión sobre «${last.topic}». No cuenta nada: el conteo ocurrió al cerrarla.`;
      button.hidden = false;
      button.addEventListener("click", showLast);
    }
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    message("setup-msg", error.message, false);
  }
}
