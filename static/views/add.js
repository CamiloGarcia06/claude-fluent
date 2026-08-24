// Agregar tarjetas — Pantallas 5A y 5B del wireframe.
//
// Es la única puerta para crear tarjetas o mazos: todos los botones de
// "Agregar tarjetas" de la app llegan acá en vez de abrir el diálogo de Anki,
// porque un mazo se crea escribiéndole la primera tarjeta y esa decisión es
// esta pantalla.
//
// El modelo propone y yo apruebo, que es la regla de todo el proyecto: nada
// viene tildado. Cada tarjeta exige una decisión antes de existir en Anki.
//
// Un término, una llamada a `claude -p`, y en serie. En paralelo serían diez
// procesos claude a la vez por una corrida; en un solo pedido no habría nada
// que mirar durante dos minutos y un término malo se llevaría la respuesta
// entera. En serie cada término aterriza solo y el que falla cuesta sólo él.

import {
  $, el, plural, getJSON, catalog, ApiError,
} from "/ui.js";

// Medido: 15 s por término. La barra corre hacia el 90 % en ese tiempo y salta
// al final cuando la respuesta llega — nunca al revés, porque una barra que se
// planta en 100 % y sigue esperando es peor que ninguna.
const TERM_ESTIMATE_MS = 15000;

const MAX_TERMS = 10;

// La opción del selector que abre un mazo nuevo. Un valor imposible como
// nombre de mazo, porque "::" no sobrevive a la validación del servidor.
const NEW_DECK = "::nuevo::";

const MARKUP = `
<div id="add">

  <section class="hero">
    <p class="date">Colección</p>
    <h1>Agregar tarjetas</h1>
    <p class="hint" id="add-hint" hidden></p>
  </section>

  <section class="panel">
    <div class="panel-head">
      <h2>Términos</h2>
      <span class="sub">uno por línea o separados por coma · máximo ${MAX_TERMS} por corrida</span>
    </div>
    <p class="sub-note">Escribí los términos, o un tema como “verbos modales” y
      pedile a Claude que lo abra. Con el campo vacío propone desde tus fallos
      y tus huecos.</p>
    <textarea id="terms" class="termbox" rows="3" spellcheck="false"
              placeholder="put up with, thorough, nevertheless — o un tema: verbos modales"></textarea>
    <div class="actions">
      <button id="generate" type="button">Generar</button>
      <button id="suggest" type="button" class="ghost">Proponer términos</button>
    </div>
    <div id="reasons" class="reasons" hidden></div>
  </section>

  <section class="panel" id="progress-panel" hidden>
    <div class="panel-head">
      <h2 id="progress-title"></h2>
      <button id="cancel" type="button" class="ghost">Cancelar</button>
    </div>
    <div id="progress" class="gen-progress"></div>
  </section>

  <div id="notes" hidden></div>

  <section class="panel" id="results-panel" hidden>
    <div class="panel-head">
      <h2>Candidatas</h2>
      <span class="sub" id="results-sub"></span>
    </div>
    <div id="cands" class="cands"></div>
  </section>

  <p class="sub-note" id="manual" hidden>
    ¿Preferís escribirlas vos? <button id="open-anki" type="button" class="linkish">Abrí
    el diálogo de Anki</button> — esta pantalla no es la única forma.
  </p>

  <div id="foot" class="gen-foot" hidden>
    <span id="foot-count" class="stat-meta"></span>
    <!-- El resultado se lee donde apretaste. Arriba, en el hero, quedaba a una
         pantalla de scroll del botón: un error ahí es un error invisible. -->
    <span id="foot-msg" class="foot-msg" hidden></span>
    <button id="add-selected" type="button">Agregar</button>
  </div>

</div>
`;

// Estado de la corrida. Vive aquí y no en el DOM: la selección y las ediciones
// tienen que sobrevivir a que se repinte la tabla.
let decks = [];        // mazos que ya existen, para el selector
let skills = [];       // las cinco skills con sus niveles, para el mazo nuevo
let levels = [];
let results = [];      // { term, deck, deck_exists, rationale, candidates }
let notes = [];        // lo que el modelo devolvió sin tarjetas, y por qué
let cancelled = false;
let focus = null;      // { skill, level } cuando venís de un hueco de Progreso

// ── Los términos ──────────────────────────────────────────────────────

function parseTerms(raw) {
  const parts = raw.split(/[\n,]+/).map((t) => t.trim()).filter(Boolean);
  const seen = new Set();
  const unique = [];
  for (const term of parts) {
    const key = term.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(term);
  }
  return unique.slice(0, MAX_TERMS);
}

function hint(text) {
  const node = $("add-hint");
  node.textContent = text;
  node.hidden = !text;
}

// Lo que haya en el campo manda. Escribir "verbos modales" y que la app
// proponga desde tus fallos es ignorarte: un tema escrito ahí es la pregunta,
// y lo que se abre son los términos que lo componen — can, could, must — no
// una tarjeta cuyo frente diga "verbos modales".
async function suggestTerms() {
  const button = $("suggest");
  const topic = $("terms").value.trim();

  button.disabled = true;
  if (topic) {
    hint(`Abriendo “${topic}” en términos…`);
  } else {
    hint(focus
      ? `Buscando qué poner en ${focus.skill} ${focus.level}…`
      : "Leyendo tus atascos y los huecos del catálogo… puede tardar unos segundos.");
  }

  try {
    const data = await getJSON("/api/generate/terms", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...(focus || {}), topic }),
    });
    if (!data.terms.length) {
      hint(topic
        ? `El modelo no sacó términos de “${topic}”. Probá con otras palabras.`
        : "No hay de dónde: ninguna tarjeta atascada y ningún nivel vacío.");
      return;
    }
    $("terms").value = data.terms.map((t) => t.term).join(", ");
    renderReasons(data.terms);

    hint(`${plural(data.terms.length, "término propuesto", "términos propuestos")}` +
         (topic ? ` a partir de “${topic}”` : "") +
         ". Borrá los que no quieras y dale a Generar.");
  } catch (error) {
    hint(error.message);
  } finally {
    button.disabled = false;
  }
}

// El porqué de cada término, que es lo que permite borrar los que no querés
// antes de gastar quince segundos en cada uno. Fila propia y no `.rows`: ahí
// la segunda columna es una cifra mono que no parte, y una frase entera metida
// en ella aplastaba el término a un carácter por línea.
function renderReasons(terms) {
  const list = $("reasons");
  list.replaceChildren();
  for (const item of terms) {
    const row = el("div", "reason-row");
    row.append(el("span", "reason-term", item.term),
               el("span", "reason-why", item.reason));
    list.append(row);
  }
  list.hidden = false;
}

// ── Mientras genera — Pantalla 5B ─────────────────────────────────────

function renderProgress(terms) {
  $("progress-title").textContent = `Generando ${plural(terms.length, "término", "términos")}`;
  const box = $("progress");
  box.replaceChildren();

  for (const [index, term] of terms.entries()) {
    const row = el("div", "gen-row");
    row.dataset.state = "pending";
    row.id = `gen-${index}`;
    row.append(el("span", "gen-term", term));

    const track = el("span", "gen-track");
    track.append(el("span", "gen-bar"));
    row.append(track, el("span", "gen-note", "en cola"));
    box.append(row);
  }
  $("progress-panel").hidden = false;
}

function markProgress(index, state, note) {
  const row = $(`gen-${index}`);
  if (!row) return;
  row.dataset.state = state;
  row.querySelector(".gen-note").textContent = note;

  const bar = row.querySelector(".gen-bar");
  if (state === "running") {
    // scaleX y no width: la barra no puede reflowar la fila en cada cuadro.
    bar.style.transition = `transform ${TERM_ESTIMATE_MS}ms linear`;
    requestAnimationFrame(() => { bar.style.transform = "scaleX(0.9)"; });
  } else if (state === "done") {
    bar.style.transition = "transform 200ms ease-out";
    bar.style.transform = "scaleX(1)";
  } else if (state === "error") {
    bar.style.transition = "none";
    bar.style.transform = "scaleX(0)";
  }
}

// ── El mazo de cada término ───────────────────────────────────────────
// Uno por término y no uno por corrida: `put up with` es Grammar B1 y
// `nevertheless` es Writing B2, y meterlos juntos rompe la convención de la
// que cuelga todo lo demás. El selector lleva el que propuso el modelo, los
// que ya existen, y la puerta para abrir uno nuevo.

function setDeck(result, name) {
  result.deck = name;
  for (const candidate of result.candidates) candidate.deck = name;
  refreshFoot();
}

function newDeckControls(result) {
  const box = el("div", "deck-new");

  const skillPick = el("select", "deck-pick");
  for (const name of skills) {
    const option = el("option", null, name);
    option.value = name;
    skillPick.append(option);
  }
  const levelPick = el("select", "deck-pick");
  for (const name of levels) {
    const option = el("option", null, name);
    option.value = name;
    levelPick.append(option);
  }
  const topic = el("input", "cand-input");
  topic.type = "text";
  topic.placeholder = "Tema: Phrasal verbs";

  // El nombre se arma delante tuyo. La convención Skill::Level::Topic es la
  // base de todos los niveles de la app, así que el mazo nuevo se construye
  // con ella en vez de dejarte escribir una ruta que después no clasifica.
  const preview = el("span", "deck-preview");
  const sync = () => {
    const name = topic.value.trim()
      ? `${skillPick.value}::${levelPick.value}::${topic.value.trim()}`
      : "";
    preview.textContent = name || "escribí un tema";
    setDeck(result, name);
  };
  for (const control of [skillPick, levelPick]) control.addEventListener("change", sync);
  topic.addEventListener("input", sync);

  if (focus) {
    skillPick.value = focus.skill;
    levelPick.value = focus.level;
  }

  box.append(skillPick, levelPick, topic, preview);
  sync();
  return box;
}

function deckPicker(result, group) {
  const select = el("select", "deck-pick");

  // El mazo que propuso el modelo va primero y marcado como nuevo si no
  // existe: crear un mazo es una decisión, no un efecto secundario.
  if (result.suggested) {
    const option = el("option", null,
      result.deck_exists ? result.suggested : `${result.suggested} · nuevo`);
    option.value = result.suggested;
    select.append(option);
  }
  for (const name of decks) {
    if (name === result.suggested) continue;
    const option = el("option", null, name);
    option.value = name;
    select.append(option);
  }
  const other = el("option", null, "Mazo nuevo…");
  other.value = NEW_DECK;
  select.append(other);

  // Sin mazo válido no hay dónde escribir: el modelo nombró una skill o un
  // nivel que este app no conoce, así que la decisión vuelve a vos.
  if (!result.suggested) {
    const option = el("option", null, "— elegí un mazo —");
    option.value = "";
    select.prepend(option);
  }
  select.value = result.deck || (result.suggested ? result.suggested : "");

  select.addEventListener("change", () => {
    group.querySelector(".deck-new")?.remove();
    if (select.value === NEW_DECK) {
      group.append(newDeckControls(result));
    } else {
      setDeck(result, select.value);
    }
  });
  return select;
}

// ── La tabla — Pantalla 5A ────────────────────────────────────────────
// Una sola tabla con una cabecera, no un panel por término: el encabezado
// FRONT · BACK · EJEMPLO se lee una vez y los términos son grupos dentro.

function editRow(row, candidate) {
  row.dataset.editing = "true";
  for (const field of ["front", "back", "example"]) {
    const cell = row.querySelector(`.cand-${field}`);
    cell.replaceChildren();
    const input = el("input", "cand-input");
    input.type = "text";
    input.value = candidate[field] || "";
    input.addEventListener("input", () => { candidate[field] = input.value.trim(); });
    cell.append(input);
  }
  row.querySelector(".cand-edit").textContent = "listo";
}

function showRow(row, candidate) {
  row.dataset.editing = "false";
  const front = row.querySelector(".cand-front");
  front.replaceChildren(el("span", "cand-text", candidate.front));
  if (candidate.label) front.append(el("span", "rail-chip", candidate.label));

  row.querySelector(".cand-back").replaceChildren(el("span", "cand-text", candidate.back));
  row.querySelector(".cand-example").replaceChildren(
    el("span", "cand-text", candidate.example));
  const edit = row.querySelector(".cand-edit");
  if (edit) edit.textContent = "editar";
}

function candidateRow(candidate) {
  const row = el("div", "cand-row");
  row.dataset.dup = String(Boolean(candidate.duplicate_in));

  const box = el("input");
  box.type = "checkbox";
  box.className = "cand-box";
  box.checked = Boolean(candidate.selected);   // nada viene tildado de fábrica
  box.disabled = Boolean(candidate.duplicate_in);
  box.addEventListener("change", () => {
    candidate.selected = box.checked;
    refreshFoot();
  });

  row.append(box, el("div", "cand-front"), el("div", "cand-back"),
             el("div", "cand-example"));

  if (candidate.duplicate_in) {
    row.append(el("span", "tag", `ya la tenés · ${candidate.duplicate_in}`));
  } else {
    const edit = el("button", "cand-edit", "editar");
    edit.type = "button";
    edit.addEventListener("click", () => {
      if (row.dataset.editing === "true") showRow(row, candidate);
      else editRow(row, candidate);
    });
    row.append(edit);
  }

  showRow(row, candidate);
  return row;
}

function groupRow(result) {
  const group = el("div", "cand-group");

  const title = el("span", "cand-term", result.term);
  const count = el("span", "rail-chip",
    plural(result.candidates.length, "candidata", "candidatas"));

  const head = el("div", "cand-group-head");
  head.append(title, count, deckPicker(result, group));
  group.append(head);

  if (result.deck_rationale) {
    group.append(el("p", "sub-note", result.deck_rationale));
  }
  return group;
}

function renderNotes() {
  const box = $("notes");
  box.replaceChildren();
  box.hidden = notes.length === 0;
  for (const note of notes) box.append(el("p", "sub-note", note));
}

function paintResults() {
  const table = $("cands");
  table.replaceChildren();

  const live = results.filter((r) => r.candidates.length);
  $("results-panel").hidden = live.length === 0;
  if (!live.length) { refreshFoot(); return; }

  const header = el("div", "cand-row cand-head");
  header.append(el("span"), el("div", "cand-front", "FRONT"),
                el("div", "cand-back", "BACK"), el("div", "cand-example", "EJEMPLO"),
                el("span"));
  table.append(header);

  for (const result of live) {
    table.append(groupRow(result));
    for (const candidate of result.candidates) table.append(candidateRow(candidate));
  }

  const total = live.reduce((n, r) => n + r.candidates.length, 0);
  const dupes = live.reduce(
    (n, r) => n + r.candidates.filter((c) => c.duplicate_in).length, 0);
  $("results-sub").textContent =
    `${plural(live.length, "término", "términos")} · ${plural(total, "candidata", "candidatas")}` +
    (dupes ? ` · ${dupes} que ya tenés` : "");

  refreshFoot();
}

// ── El pie: lo seleccionado y el botón que escribe ────────────────────

function selected() {
  return results.flatMap((r) => r.candidates.filter((c) => c.selected && c.deck));
}

function refreshFoot() {
  const total = results.reduce((n, r) => n + r.candidates.length, 0);
  const chosen = selected();
  $("foot").hidden = total === 0;
  $("foot-count").textContent = `${chosen.length} de ${total} seleccionadas`;
  if (chosen.length) footMessage("");

  // Tildada pero sin mazo no cuenta, y quedarse mirando un contador que no se
  // mueve no explica nada: pasa cuando el modelo nombró una skill o un nivel
  // que este app no conoce, o cuando el mazo nuevo todavía no tiene tema.
  const orphans = results.filter(
    (r) => !r.deck && r.candidates.some((c) => c.selected));
  if (orphans.length) {
    hint(`Elegí un mazo para ${orphans.map((r) => r.term).join(", ")}: ` +
         `sin mazo no hay dónde escribir.`);
  }

  $("add-selected").disabled = chosen.length === 0;
  $("add-selected").textContent = chosen.length
    ? `Agregar ${plural(chosen.length, "tarjeta", "tarjetas")}`
    : "Agregar";
}

function footMessage(text, ok = true) {
  const node = $("foot-msg");
  node.textContent = text;
  node.dataset.ok = String(ok);
  node.hidden = !text;
}

async function writeSelected() {
  const cards = selected();
  const button = $("add-selected");
  button.disabled = true;
  footMessage("Escribiendo en Anki…");
  hint("");

  try {
    const data = await getJSON("/api/notes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cards: cards.map((c) => ({
          front: c.front, back: c.back, example: c.example, deck: c.deck,
        })),
      }),
    });

    const lines = data.decks
      .map((d) => `${d.deck}: ${d.verified} de ${d.asked}`)
      .join(" · ");
    footMessage(`Agregaste ${plural(data.added, "tarjeta", "tarjetas")}.`);
    hint(`Agregaste ${plural(data.added, "tarjeta", "tarjetas")}. ${lines}. ` +
         `Podés deshacerlo desde el registro de creación en data/snapshots/.`);

    // Lo que Anki no aceptó se dice, con su motivo. Callarlo dejaría un
    // contador que no cuadra y ninguna forma de saber cuál faltó.
    if (data.refused.length) {
      notes.push(...data.refused.map(
        (r) => `Anki no aceptó “${r.front}”: ${r.error}`));
      renderNotes();
    }

    // Lo escrito ya no es una propuesta: sale de la tabla para que un segundo
    // clic no lo duplique. Los mazos nuevos ya existen, así que entran al
    // selector de los términos que quedan.
    for (const result of results) {
      result.candidates = result.candidates.filter((c) => !c.selected);
    }
    for (const written of data.decks) {
      if (!decks.includes(written.deck)) decks.push(written.deck);
    }
    decks.sort((a, b) => a.localeCompare(b));
    paintResults();
  } catch (error) {
    footMessage(error.message, false);
    hint(error.message);
  } finally {
    button.disabled = false;
    refreshFoot();
  }
}

// ── La corrida ────────────────────────────────────────────────────────

async function run() {
  const terms = parseTerms($("terms").value);
  if (!terms.length) {
    hint("Escribí al menos un término, o pedile al modelo que los proponga.");
    return;
  }

  cancelled = false;
  results = [];
  notes = [];
  renderNotes();
  paintResults();
  $("reasons").hidden = true;
  $("generate").disabled = true;
  hint("");
  renderProgress(terms);

  for (const [index, term] of terms.entries()) {
    if (cancelled) {
      markProgress(index, "pending", "cancelado");
      continue;
    }
    markProgress(index, "running", "generando…");
    try {
      const data = await getJSON("/api/generate/cards", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ term }),
      });

      // Un tema no es un término: el modelo lo dice y la nota explica qué
      // botón era el correcto, en vez de dejar una tarjeta que no enseña nada.
      if (data.not_a_term) {
        markProgress(index, "error", "es un tema");
        notes.push(data.note ||
          `“${term}” parece un tema, no un término. Escribilo solo en el campo ` +
          `y usá "Proponer términos" para abrirlo.`);
        renderNotes();
        continue;
      }

      // `suggested` es lo que propuso el modelo y no cambia; `deck` es lo que
      // vas a escribir, y eso sí lo movés vos.
      data.suggested = data.deck;
      for (const candidate of data.candidates) {
        candidate.selected = false;
        candidate.deck = data.deck || "";
      }
      results.push(data);
      markProgress(index, "done",
        `${plural(data.candidates.length, "candidata", "candidatas")} · ${Math.round(data.duration_ms / 1000)}s`);
      paintResults();
    } catch (error) {
      // Un término que falla cuesta sólo ese término: la corrida sigue.
      markProgress(index, "error",
        error instanceof ApiError ? error.message : "falló");
    }
  }

  $("generate").disabled = false;
  // El panel de progreso desaparece sólo si todo salió bien: si un término
  // falló, su línea es lo único que lo dice.
  $("progress-panel").hidden = results.length === terms.length && results.length > 0;
  // Con una nota abajo, "ningún término devolvió tarjetas" sería la segunda
  // vez que se dice lo mismo y la menos útil de las dos.
  if (!results.length && !notes.length) hint("Ningún término devolvió tarjetas.");
}

export async function render(root, params = []) {
  root.innerHTML = MARKUP;
  results = [];
  cancelled = false;
  focus = null;

  const tree = await catalog();
  skills = tree.skills.map((s) => s.skill);
  levels = tree.skills[0].levels.map((l) => l.level);
  decks = [
    ...tree.skills.flatMap((s) => s.levels.flatMap((l) => l.decks.map((d) => d.deck))),
    ...tree.unclassified.decks.map((d) => d.deck),
  ].sort((a, b) => a.localeCompare(b));

  // #/agregar/Grammar/A1 — venís de un hueco, y el modelo propone para ese
  // hueco en vez de para la colección entera. Un tercer tramo,
  // #/agregar/Grammar/A1/Art%C3%ADculos%20a%20%2F%20an, es un punto del
  // temario: llega escrito en la caja, que es de donde sale la pregunta.
  const [rawSkill, rawLevel, rawTopic] = params;
  const skill = skills.find((s) => s.toLowerCase() === String(rawSkill).toLowerCase());
  const level = levels.find((l) => l.toLowerCase() === String(rawLevel).toLowerCase());
  if (skill && level) {
    focus = { skill, level };
    const topic = rawTopic ? decodeURIComponent(rawTopic).trim() : "";
    if (topic) {
      $("terms").value = topic;
      hint(`Vas a cubrir “${topic}” en ${skill} ${level}. ` +
           `"Proponer términos" lo abre en los términos que lo componen.`);
    } else {
      hint(`Vas a llenar ${skill} ${level}. "Proponer desde mis fallos" busca términos para ese nivel.`);
    }
  }

  $("generate").addEventListener("click", run);
  $("suggest").addEventListener("click", suggestTerms);
  $("cancel").addEventListener("click", () => {
    cancelled = true;
    hint("Cancelado. Los términos que ya habían terminado siguen abajo.");
  });
  $("add-selected").addEventListener("click", writeSelected);

  // La escotilla: Anki sigue siendo el editor, y a veces una tarjeta se
  // escribe más rápido a mano que explicándosela al modelo.
  $("manual").hidden = false;
  $("open-anki").addEventListener("click", async () => {
    try {
      await getJSON("/api/add-cards", { method: "POST" });
      hint("Anki abrió el diálogo de añadir. Si la ventana no saltó al frente, cambiá a ella.");
    } catch (error) {
      hint(error.message);
    }
  });
}
