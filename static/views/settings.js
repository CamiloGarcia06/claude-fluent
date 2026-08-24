// Ajustes — the state of the connections, and the dials.
//
// Every failure in this system is silent: Anki closed, `claude` without a
// session. This screen says so out loud, which is the whole reason /api/health
// exists and is the first thing to check when anything looks wrong.
//
// La meta diaria ya se escribe: vive en data/state.json y es lo único que este
// app decide sobre sí mismo. El resto de los dials siguen siendo de lectura —
// el umbral de madurez es una constante del análisis, no una preferencia.

import { $, el, plural, percent, getJSON, catalog } from "/ui.js";

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
        <h2>Meta diaria</h2>
        <span class="sub">lo que te proponés hoy</span>
      </div>
      <div class="goal-set">
        <input id="goal-input" class="goal-input" type="number" min="5" max="300" step="5">
        <span class="goal-unit">tarjetas por día</span>
        <button id="goal-save" type="button" class="ghost">Guardar</button>
      </div>
      <p class="sub-note" id="goal-msg">El atraso no la mueve: la meta es lo que
        entra en tu rato de hoy, no lo que se acumuló.</p>

      <div class="panel-head" style="margin-top: var(--s6)">
        <h2>Dials</h2>
        <span class="sub">de lectura</span>
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

async function saveGoal() {
  const button = $("goal-save");
  button.disabled = true;
  try {
    const saved = await getJSON("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ daily_goal: Number($("goal-input").value) }),
    });
    $("goal-input").value = saved.daily_goal;
    $("goal-msg").textContent =
      `Guardado: ${plural(saved.daily_goal, "tarjeta", "tarjetas")} por día. ` +
      `Hoy lo va a medir contra esto.`;
  } catch (error) {
    $("goal-msg").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

export async function render(root) {
  root.innerHTML = MARKUP;

  // La meta se lee aunque Anki esté cerrado: no sale de la colección.
  const current = await getJSON("/api/settings");
  $("goal-input").value = current.daily_goal;
  $("goal-save").addEventListener("click", saveGoal);

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
    row("Términos por corrida", "10",
        "cada uno es una llamada aparte a claude -p, de unos 15 s"),
    row("Candidatas por término", "3",
        "sentidos distintos de la palabra, nunca la misma dicha de otro modo"),
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
