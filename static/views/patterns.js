// Patrones — en qué venís fallando cuando escribís, y cuántas veces.
//
// Es la hermana de Atascos, y la diferencia es de dónde sale la evidencia:
// Atascos mira las tarjetas que ya tenés y no te acordás; esto mira lo que
// producís. Una tarjeta que fallás dice que algo no se fijó; un patrón que se
// repite dice que algo no lo aprendiste todavía.
//
// Cuenta **sesiones**, no veces: escribir el mismo error tres veces en un
// párrafo es un hábito, no tres errores. Y sin color, por lo mismo que Atascos
// — el orden ya dice cuál duele más, y estos son el trabajo, no un veredicto.

import {
  $, el, emptyRow, plural, getJSON, formatLongDate, ApiError,
  loadMotion, staggerStep, DURATION_MS,
} from "/ui.js";

const MARKUP = `
<div id="patterns">
  <section class="hero">
    <p id="date" class="date">Patrones</p>
    <h1 id="patterns-headline"></h1>
    <p class="hero-note" id="patterns-sub"></p>
    <div class="actions">
      <a class="primary" href="#/practica/writing">Practicar escritura</a>
    </div>
  </section>

  <section class="panel" id="patterns-panel">
    <div class="panel-head">
      <h2>En cuántas sesiones apareció cada uno</h2>
      <span class="sub" id="patterns-meta"></span>
    </div>
    <ul id="pattern-rows" class="rows"></ul>
  </section>

  <section class="panel" id="gaps-panel" hidden>
    <div class="panel-head"><h2>Sin nombre todavía</h2></div>
    <p class="panel-note">Estos hábitos aparecieron en tus análisis y el
      catálogo no supo nombrarlos, así que no cuentan para tarjeta. Es la lista
      de lo que le falta al catálogo, y de acá salen las entradas nuevas.</p>
    <ul id="gap-rows" class="rows"></ul>
  </section>
</div>
`;

let threshold = 3;

/** Qué hacer con este patrón, no cuánto suma.
 *
 *  El número de la derecha ya dice cuánto suma, y decirlo dos veces —cifra y
 *  frase— fue lo que volvió ilegibles a las dos.
 *
 *  Con `carded` puesto y el contador en cero, el patrón no volvió a aparecer
 *  desde entonces: es lo más cerca de "mejoraste" que estos datos pueden decir
 *  con honestidad, y no cuesta una consulta nueva. */
function progress(row) {
  // "Lo llevaste a Agregar" y no "hiciste la tarjeta": `carded` se marca al
  // hacer clic en el enlace, y si de ahí escribiste la tarjeta o no es algo que
  // este lado no sabe. Decir lo segundo sería afirmar de más.
  if (row.carded && row.count === 0) return "No volvió desde que lo llevaste a Agregar";
  if (row.carded) return `Volvió ${plural(row.count, "vez", "veces")} desde que lo llevaste a Agregar`;
  if (row.ready) return "Ya se puede hacer la tarjeta";
  const left = threshold - row.count;
  return left === 1
    ? "Una sesión más y se vuelve tarjeta"
    : `Faltan ${left} sesiones para que se vuelva tarjeta`;
}

function examples(row) {
  const list = el("ul", "area-examples");
  for (const item of row.examples) {
    const li = el("li");
    li.append(el("span", "ex-wrong", item.wrong));
    // Los guardados antes de que los ejemplos viajaran en pares no tienen la
    // mitad corregida. Se muestra lo que hay en vez de una línea vacía.
    if (item.right) li.append(el("span", "ex-right", item.right));
    list.append(li);
  }
  return list;
}

/** El riel de siempre, ahora contando sesiones hacia la tarjeta.
 *
 *  La cifra de la derecha dice cuánto falta y hasta ahora nada lo mostraba:
 *  siete bloques de idéntica textura y un "2/3" como única diferencia entre
 *  ellos. Un patrón que ya llevaste a Agregar y que no volvió queda en papel
 *  sin marcar — el mismo trato que un nivel que no empezaste, por el mismo
 *  motivo. */
function meter(row) {
  const share = threshold ? Math.min(1, row.count / threshold) : 0;
  const track = el("span", "meter pattern-meter");
  track.dataset.empty = String(share === 0);

  const fill = el("span", "meter-fill");
  fill.style.width = `${Math.round(share * 100)}%`;
  track.append(fill);
  return track;
}

function patternRow(row) {
  const li = el("li", "pattern");
  li.dataset.ready = String(row.ready);

  const head = el("div", "pattern-head");
  head.append(el("span", "name", row.label));

  // La cifra con su unidad al lado. Sola era un "2/3" que había que adivinar, y
  // la línea de abajo la repetía con palabras: dos formas de decir lo mismo y
  // ninguna que se entendiera. Ahora el número dice **cuánto** y la frase dice
  // **qué hacer**.
  const score = el("span", "count pattern-score");
  score.append(el("b", null, `${row.count}/${threshold}`),
               el("span", "score-unit", "sesiones"));
  score.title = `Apareció en ${plural(row.count, "sesión", "sesiones")}. `
    + `A las ${threshold} se ofrece como tarjeta.`;
  head.append(score);
  li.append(head);

  const meta = el("p", "pattern-meta");
  meta.append(el("span", null, progress(row)));
  if (row.last_seen) {
    meta.append(el("span", null,
      ` · última vez ${formatLongDate(row.last_seen).toLowerCase()}`));
  }
  li.append(meta, meter(row));

  if (row.examples.length) li.append(examples(row));

  const actions = el("div", "pattern-actions");

  // Deshacer el clic. "Hacer tarjeta" se marca al apretar el enlace —este lado
  // no sabe si después la escribiste— y eso era de ida: un clic, aunque no
  // hubieras escrito nada, y el patrón dejaba de reclamarte la tarjeta para
  // siempre. Quedaban temas que necesitaban tarjeta sin forma de volver a
  // pedirla. Es gratis porque limpiar nunca borró historia: mover la raya al
  // principio devuelve el conteo entero.
  if (!row.ready && row.carded) {
    const undo = el("button", "ghost", "Todavía no la hice");
    undo.type = "button";
    undo.title = "Vuelve a contar las sesiones anteriores, y el patrón te reclama la tarjeta otra vez.";
    undo.addEventListener("click", async () => {
      undo.disabled = true;
      try {
        paint(await mark(row.key, "uncard"));
      } catch {
        undo.disabled = false;
      }
    });
    actions.append(undo);
  }

  if (row.ready) {
    const path = [row.skill, row.level, row.seed].map(encodeURIComponent).join("/");
    const link = el("a", "ghost", `Hacer tarjeta en ${row.skill} ${row.level}`);
    link.href = `#/agregar/${path}`;
    // Se marca y después se navega: dejar el POST volando mientras cambia el
    // hash es una carrera que a veces se pierde, y perderla significa que el
    // patrón te sigue reclamando una tarjeta que ya fuiste a escribir.
    link.addEventListener("click", async (event) => {
      event.preventDefault();
      await mark(row.key, "carded").catch(() => {});
      location.hash = link.getAttribute("href");
    });

    const drop = el("button", "ghost", "No me interesa");
    drop.type = "button";
    drop.addEventListener("click", async () => {
      drop.disabled = true;
      try {
        paint(await mark(row.key, "reset"));
      } catch {
        drop.disabled = false;
      }
    });

    actions.append(link, drop);
  }

  if (actions.children.length) li.append(actions);
  return li;
}

const mark = (key, action) =>
  getJSON("/api/practice/patterns", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key, action }),
  });

function paint(data) {
  threshold = data.threshold || threshold;
  const rows = data.patterns || [];
  const ready = rows.filter((r) => r.ready).length;

  $("patterns-headline").textContent = rows.length
    ? plural(rows.length, "patrón", "patrones")
    : "Todavía no hay patrones";
  $("patterns-sub").textContent = rows.length
    ? (ready
        ? `${plural(ready, "llegó", "llegaron")} a ${threshold} sesiones y ya `
          + `${ready === 1 ? "puede ser tarjeta" : "pueden ser tarjeta"}.`
        : `Se cuentan por sesión, no por vez. A las ${threshold} se vuelven tarjeta.`)
    : "Cerrá una sesión de práctica y lo que falles aparece acá.";

  $("patterns-meta").textContent = rows.length
    ? `${plural(ready, "listo", "listos")} para tarjeta`
    : "";

  const list = $("pattern-rows");
  list.replaceChildren();
  if (!rows.length) {
    list.append(emptyRow("Sin patrones todavía — empezá por practicar."));
  } else {
    for (const row of rows) list.append(patternRow(row));
  }

  // Los huecos del catálogo. No es un contador tuyo: es trabajo pendiente del
  // app, y por eso vive en su propio panel y no mezclado con lo de arriba.
  const gaps = Object.entries(data.unmatched || {}).sort((a, b) => b[1] - a[1]);
  $("gaps-panel").hidden = !gaps.length;
  const gapList = $("gap-rows");
  gapList.replaceChildren();
  for (const [name, times] of gaps) {
    const li = el("li");
    li.append(el("span", "name", name),
              el("span", "count", plural(times, "vez", "veces")));
    gapList.append(li);
  }
}

// El mismo vocabulario del tablero y de Progreso: escala desde la izquierda,
// escalonado, y todo termina a los 300 ms.
function playEntrance() {
  loadMotion().then((motion) => {
    if (!motion) return;
    const { animate, stagger } = motion;

    const fills = document.querySelectorAll("#patterns .meter-fill");
    if (fills.length) {
      animate(fills, {
        scaleX: [0, 1],
        duration: DURATION_MS,
        delay: stagger(staggerStep(fills.length)),
        ease: "outQuad",
      });
    }

    const rows = document.querySelectorAll("#patterns .rows li");
    if (rows.length) {
      animate(rows, {
        opacity: [0, 1],
        y: [6, 0],
        duration: DURATION_MS,
        delay: stagger(staggerStep(rows.length)),
        ease: "outQuad",
      });
    }
  });
}

export async function render(root) {
  root.innerHTML = MARKUP;
  try {
    paint(await getJSON("/api/practice/patterns"));
    playEntrance();
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    // Contenido en la pantalla: este endpoint no toca Anki, así que un banner
    // de "Anki no responde" sería mentira.
    $("patterns-headline").textContent = "No se pudo leer el conteo";
    $("patterns-sub").textContent = error.message;
  }
}
