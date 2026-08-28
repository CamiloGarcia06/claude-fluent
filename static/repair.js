// The model proposes, you approve. Nothing reaches Anki until you press
// Aceptar, and the server snapshots the note before it writes.
//
// Lives on its own because two screens open the same panel: the "Vengo
// fallando" block on Hoy and the Atascos screen. The markup keeps the ids it
// had when this was part of app.js, so styles.css did not have to change —
// only one view is mounted at a time, so the ids stay unique.

import { $, el, getJSON, side, waiting, working } from "/ui.js";

// Medido contra la colección real: 19 s la última vez, y la nota del proyecto
// dice 8–15. La barra corre hacia el 90 % en ese tiempo y espera ahí.
const REPAIR_ESTIMATE_MS = 16000;

const MARKUP = `
  <div class="panel-head">
    <h2 id="repair-title">Reparar tarjeta</h2>
    <span id="repair-status" class="sub"></span>
  </div>
  <p id="repair-diagnosis" class="diagnosis"></p>
  <div id="repair-diff" class="diff"></div>
  <p id="repair-rationale" class="rationale"></p>
  <div class="actions">
    <button id="repair-accept" type="button">Aceptar</button>
    <button id="repair-discard" type="button" class="ghost">Descartar</button>
  </div>
`;

let proposal = null;
let onApplied = null;

function renderDiff(data) {
  const diff = $("repair-diff");
  diff.replaceChildren();
  for (const name of Object.keys(data.current)) {
    const changed = data.changed.includes(name);
    const block = el("div", "field");
    block.dataset.changed = String(changed);
    block.append(
      el("div", "field-name", changed ? `${name} · cambia` : `${name} · igual`),
      side("Antes", data.current[name], changed),
      side("Después", data.proposal[name], changed),
    );
    diff.append(block);
  }
}

function setBusy(busy, message) {
  $("repair-status").textContent = message || "";
  $("repair-accept").disabled = busy || !proposal;
  document.querySelectorAll(".repair-open").forEach((b) => { b.disabled = busy; });
}

async function open(noteId, name, fired) {
  proposal = null;
  $("repair").hidden = false;
  $("repair-title").textContent = `Reparar “${name}”`;
  $("repair-diagnosis").textContent = "";
  $("repair-rationale").textContent = "";
  $("repair-diff").replaceChildren();
  setBusy(true, "Pensando… unos quince segundos.");
  working(fired, true);
  $("repair").scrollIntoView({ block: "nearest" });

  // La barra ocupa el hueco donde va a aparecer el antes/después. Hasta ahora
  // acá había una frase quieta durante veinte segundos y un botón en gris:
  // idéntico a una pantalla colgada.
  const stop = waiting($("repair-diff"), REPAIR_ESTIMATE_MS);

  try {
    proposal = await getJSON(`/api/repair/${noteId}`, { method: "POST" });
  } catch (error) {
    stop(false);
    working(fired, false);
    setBusy(false, error.message);
    return;
  }
  stop();
  working(fired, false);

  $("repair-diagnosis").textContent = proposal.diagnosis;
  $("repair-rationale").textContent = proposal.rationale;
  renderDiff(proposal);

  const changes = proposal.changed.length;
  setBusy(false, changes
    ? `${changes === 1 ? "1 campo cambia" : `${changes} campos cambian`} · ${Math.round(proposal.duration_ms / 1000)}s`
    : "El modelo no propone cambios.");
  $("repair-accept").disabled = changes === 0;
}

function close() {
  proposal = null;
  $("repair").hidden = true;
  setBusy(false, "");
}

async function accept() {
  if (!proposal) return;
  setBusy(true, "Guardando…");

  const noteId = proposal.note_id;
  const fields = proposal.proposal;
  try {
    await getJSON(`/api/apply/${noteId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fields }),
    });
  } catch (error) {
    setBusy(false, error.message);
    return;
  }

  close();
  if (onApplied) await onApplied();
}

/** Build the panel and hand back the element for the view to place. */
export function mount({ onApplied: applied } = {}) {
  onApplied = applied || null;
  proposal = null;

  const section = el("section", "panel repair");
  section.id = "repair";
  section.hidden = true;
  section.innerHTML = MARKUP;

  section.querySelector("#repair-accept").addEventListener("click", accept);
  section.querySelector("#repair-discard").addEventListener("click", close);
  return section;
}

/** A "Reparar" button for one card, or nothing when the card has no note. */
export function button(card, name) {
  if (!card.note_id) return null;
  const control = el("button", "ghost repair-open", "Reparar");
  control.type = "button";
  control.addEventListener("click", () => open(card.note_id, name, control));
  return control;
}
