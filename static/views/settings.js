// Ajustes — the state of the connections, and the dials.
//
// Every failure in this system is silent: Anki closed, `claude` without a
// session. This screen says so out loud, which is the whole reason /api/health
// exists and is the first thing to check when anything looks wrong.
//
// The dials are read-only for now. data/state.json is not written yet, so
// showing an editable field would be a control that quietly does nothing —
// worse than showing the value and saying it is not editable.

import { $, el, percent, getJSON, catalog } from "/ui.js";

const MARKUP = `
<div id="settings">
  <section class="hero">
    <p id="date" class="date">Ajustes</p>
    <h1 id="due-headline">Estado del sistema</h1>
  </section>

  <div class="columns">
    <section class="panel">
      <div class="panel-head">
        <h2>Conexiones</h2>
        <span class="sub">lo que falla en silencio</span>
      </div>
      <ul id="health" class="rows"></ul>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>Dials</h2>
        <span class="sub">todavía no editables</span>
      </div>
      <ul id="dials" class="rows"></ul>
    </section>
  </div>
</div>
`;

function statusRow(name, ok, okText, failText) {
  const li = el("li");
  li.append(el("span", "name", name));
  const state = el("span", "count", ok ? okText : failText);
  state.dataset.ok = String(ok);
  li.append(state);
  return li;
}

export async function render(root) {
  root.innerHTML = MARKUP;

  // /api/health is the one endpoint that must answer even when Anki does not,
  // so it is fetched on its own rather than through the shared catalogue.
  const health = await getJSON("/api/health");
  const list = $("health");
  list.append(
    statusRow("Anki y AnkiConnect", health.anki, "respondiendo", "sin respuesta"),
    statusRow("claude en el PATH", health.claude, "disponible", "no encontrado"),
    statusRow("Último sync", Boolean(health.last_sync),
              health.last_sync || "", "todavía sin registrar"),
  );

  const dials = $("dials");
  if (!health.anki) {
    dials.append(el("li", "empty", "Con Anki cerrado no hay colección que medir."));
    return;
  }

  const data = await catalog();
  dials.append(
    row("Umbral de madurez", percent(data.maturity_threshold),
        "un nivel se sostiene con esta proporción de tarjetas maduras"),
    row("Presupuesto diario", "sin definir", "va en data/state.json"),
    row("Tope por generación", "sin definir", "va en data/state.json"),
  );
}

// Local to this screen: a row with a sentence under the name, which no other
// list needs.
function row(name, value, note) {
  const li = el("li", "dial");
  const left = el("span", "name");
  left.append(el("span", null, name), el("span", "dial-note", note));
  li.append(left, el("span", "count", value));
  return li;
}
