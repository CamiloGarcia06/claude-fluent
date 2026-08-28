// One skill's library: its decks grouped by level, with the maturity of each
// and the level you are standing on. Five routes, one view — only the filter
// changes.
//
// It is not a review screen. Studying happens in Anki; the rows here only
// decide which deck it opens on.

import {
  $, el, plural, percent, getJSON, catalog, waiting, working, formatLongDate,
  loadMotion, staggerStep, DURATION_MS,
} from "/ui.js";

// Las dos esperas más largas del app, medidas: el temario se congela una sola
// vez y tarda cerca de dos minutos —tres borradores y una fusión—, y la
// cobertura se deriva en cada lectura y tardó 27 s contra esta colección.
const SYLLABUS_ESTIMATE_MS = 110000;
const COVERAGE_ESTIMATE_MS = 30000;
import { rail, slug } from "/views/progress.js";

const topicOf = (deck) => deck.split("::").pop();

// Qué habilidades tienen práctica, y cuál. Un mapa y no un `if skill ===
// "Writing"`: cuando Speaking la tenga es una línea acá y ninguna rama nueva,
// y este módulo sirve a las cinco pantallas.
const PRACTICE = { Writing: "writing" };

const MARKUP = `
<div id="skill">
  <section class="hero">
    <p id="date" class="date">Habilidad</p>
    <h1 id="due-headline"></h1>
    <p id="start-hint" class="hint" hidden></p>
    <div class="hero-foot">
      <span id="skill-standing" class="streak"></span>
      <span id="skill-rail" class="rail-solo"></span>
    </div>
    <div class="actions" id="skill-actions" hidden></div>
  </section>
  <div id="levels"></div>
</div>
`;

function deckRow(deck) {
  // Tres columnas fijas y no una fila flex. Sólo la mitad de los mazos tiene
  // algo para hoy, así que sólo la mitad lleva "Estudiar" — y con flex eso
  // dejaba las cifras en dos verticales distintas según hubiera botón o no.
  // La celda de la acción existe siempre; vacía cuando no hay nada que abrir.
  const li = el("li", "level-row");
  li.append(el("span", "name", topicOf(deck.deck)));

  const counts = deck.due
    ? `${plural(deck.total, "tarjeta", "tarjetas")} · ${deck.due} para hoy`
    : `${plural(deck.total, "tarjeta", "tarjetas")} · al día`;
  li.append(el("span", "count", counts));

  if (deck.due > 0) {
    const study = el("button", "ghost", "Estudiar");
    study.type = "button";
    study.addEventListener("click", () => openInAnki(deck.deck, study));
    li.append(study);
  } else {
    li.append(el("span"));
  }
  return li;
}

// ── El temario ───────────────────────────────────────────────────────
// La madurez dice si te acordás de tus tarjetas. El temario dice si tus
// tarjetas cubren el nivel, que es otra pregunta: siete mazos de presente
// simple llegan al 60 % de maduras y dejan sin ver la mitad del programa.
//
// Se pide a mano y no al entrar: es la llamada más lenta del app, cerca de un
// minuto cuando el nivel ya tiene mazos, y nadie quiere esperarla para leer
// una lista de mazos.

// ── ¿La cobertura guardada todavía vale? ─────────────────────────────
// De lo que depende es de los mazos de ese nivel y de cuántas tarjetas tiene
// cada uno: un mazo nuevo, uno borrado o una tarjeta más y deja de valer. El
// servidor guarda ese mapa junto con la respuesta y acá se compara con el de
// ahora — dos mapas chicos, sin hash ni versión, así que las dos puntas no
// tienen que ponerse de acuerdo en ningún algoritmo.

const deckTotals = (level) =>
  Object.fromEntries(level.decks.map((d) => [d.deck, d.total]));

const cardsIn = (decks) =>
  Object.values(decks || {}).reduce((n, v) => n + v, 0);

function sameDecks(a, b) {
  const names = Object.keys(a || {});
  return names.length === Object.keys(b || {}).length
    && names.every((name) => a[name] === b[name]);
}

/** "calculada hoy" / "calculada el jueves 27 de agosto". */
function when(iso) {
  const day = String(iso || "").slice(0, 10);
  if (!day) return "calculada antes";
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`
              + `-${String(now.getDate()).padStart(2, "0")}`;
  return day === today
    ? "calculada hoy"
    : `calculada el ${formatLongDate(day).toLowerCase()}`;
}

function pointRow(point, data, skillName, levelName) {
  // `covered === null` es la cobertura todavía en vuelo. No es "no cubierto":
  // marcar el punto como hueco y ofrecer "generar" sería afirmar algo que
  // nadie miró aún, y cuarenta segundos después se desdice solo.
  const pending = data.covered === null;

  const li = el("li", "point");
  li.dataset.covered = pending ? "pending" : String(Boolean(point.covered_by));

  const name = el("span", "name");
  const title = el("span", "point-title", point.point);
  if (point.english) title.append(el("span", "point-en", point.english));

  // El acuerdo entre borradores es dónde mirar, no una nota: tres de tres es
  // el modelo seguro, uno de tres es el modelo dudando y ahí decidís vos. Un
  // punto que escribiste a mano no tiene acuerdo que mostrar, y es correcto:
  // no salió de ningún borrador.
  if (point.drafts && data.drafts) {
    const mark = el("span", "point-drafts");
    for (let i = 1; i <= data.drafts; i += 1) {
      const dot = el("span");
      dot.dataset.on = String(i <= point.drafts);
      mark.append(dot);
    }
    mark.title = `${point.drafts} de ${data.drafts} borradores nombraron este punto`;
    title.append(mark);
  }

  name.append(title);
  if (point.note) name.append(el("span", "point-note", point.note));
  li.append(name);

  if (pending) return li;

  if (point.covered_by) {
    li.append(el("span", "count", point.covered_by));
    return li;
  }

  // Un punto sin cubrir es lo próximo a generar, y llega escrito en la caja
  // de Agregar en vez de obligarte a recordarlo y teclearlo de nuevo.
  const fill = el("a", "count", "generar");
  fill.href = `#/agregar/${slug(skillName)}/${levelName}/` +
              encodeURIComponent(point.point);
  li.append(fill);
  return li;
}

function syllabusFoot(data, onRegenerate) {
  const foot = el("p", "syllabus-note");
  const when = (data.generated || "").slice(0, 10);
  foot.append(el("span", null, data.edited
    ? `Temario editado a mano. Generado el ${when} con ${data.drafts} borradores.`
    : `Temario congelado el ${when}, de ${data.drafts} borradores. ` +
      `Editalo en data/syllabus/.`));

  const again = el("button", "ghost syllabus-again", "Regenerar");
  again.type = "button";
  again.addEventListener("click", () => {
    // Regenerar pisa el archivo, y si lo editaste ese trabajo no vuelve. Es la
    // única acción destructiva de esta pantalla, así que pregunta — y sólo
    // cuando hay algo que perder.
    const lost = data.edited
      ? "Editaste este temario a mano. Regenerarlo pisa esos cambios y no hay vuelta atrás. ¿Seguimos?"
      : "Volver a generar el temario tarda un par de minutos. ¿Seguimos?";
    if (window.confirm(lost)) onRegenerate();
  });
  foot.append(again);
  return foot;
}

/** El archivo está ahí y el app no lo entiende. Se dice, con la ruta, y la
 *  decisión de pisarlo queda de tu lado.
 *
 *  Editar el **contenido** de un temario es seguro y es para lo que existe;
 *  lo que rompe es la **forma** — una coma de más al borrar un punto, un
 *  comentario `//`, los puntos escritos como texto suelto en vez de objetos.
 *  Por eso el mensaje nombra la forma y no te dice "está mal". */
function renderUnreadable(box, data, onRegenerate) {
  box.replaceChildren();

  const note = el("p", "syllabus-note");
  note.append(el("span", null,
    "El archivo de este temario existe pero el app no puede leerlo, así que no "
    + "lo ve. No lo regenero solo: si lo editaste a mano, generar lo pisa."));
  box.append(note);

  const where = el("p", "sub-note");
  where.append(el("span", null, "Está en "), el("span", "point-en", data.path),
               el("span", null, ". Suele ser la forma y no el contenido: una coma "
                 + "de más al borrar un punto, un comentario, o los puntos escritos "
                 + "como texto suelto en vez de objetos con la clave \u201cpoint\u201d."));
  box.append(where);

  const foot = el("p", "syllabus-note");
  foot.append(el("span", null, "Arreglalo y volvé a abrir el panel."));
  const anyway = el("button", "ghost syllabus-again", "Regenerar de todos modos");
  anyway.type = "button";
  anyway.addEventListener("click", () => {
    // La única acción destructiva de esta pantalla, y sobre el caso donde más
    // probable es que haya trabajo tuyo adentro: pregunta siempre. Queda un
    // `.json.bak` al lado igual, que es lo que faltaba el día que se perdió uno.
    if (window.confirm(
      "Este archivo puede tener ediciones tuyas que el app no logra leer. "
      + "Regenerarlo lo pisa — queda una copia .json.bak al lado. ¿Seguimos?")) {
      onRegenerate();
    }
  });
  foot.append(anyway);
  box.append(foot);
}

function renderSyllabus(box, data, skillName, levelName, onRegenerate, status) {
  box.replaceChildren();

  if (!data.points.length) {
    box.append(el("p", "syllabus-note", "El modelo no devolvió ningún punto para este nivel."));
    return;
  }

  // La primera línea dice qué estás viendo y **de cuándo es**. Sin la fecha,
  // una cobertura guardada y una recién calculada se leen igual, y la que
  // vale medio minuto es la segunda.
  const head = el("p", "syllabus-note");
  head.append(el("span", null, status?.text ?? (data.covered === null
    ? "Comparando el temario con tus mazos… cerca de un minuto."
    : `${data.covered} de ${data.total} puntos cubiertos por tus mazos.`)));
  if (status?.action) {
    const act = el("button", "ghost syllabus-again", status.action.label);
    act.type = "button";
    act.title = status.action.title || "";
    act.addEventListener("click", status.action.run);
    head.append(act);
  }
  box.append(head);

  const list = el("ul", "rows");
  for (const point of data.points) {
    list.append(pointRow(point, data, skillName, levelName));
  }
  box.append(list, syllabusFoot(data, onRegenerate));
}

async function loadSyllabus(button, box, skillName, levelName, decksNow, opts = {}) {
  const { regenerate = false, recompute = false } = opts;
  // Dos paneles pueden estar cargando a la vez y "Regenerar" puede pisar una
  // cobertura en vuelo, así que cada corrida deja su número en el panel y sólo
  // pinta si sigue siendo la última.
  const ticket = String(Number(box.dataset.run || 0) + 1);
  box.dataset.run = ticket;
  const mine = () => box.dataset.run === ticket;

  working(button, true);
  box.hidden = false;

  const again = () => loadSyllabus(button, box, skillName, levelName, decksNow, { regenerate: true });
  const update = () => loadSyllabus(button, box, skillName, levelName, decksNow, { recompute: true });
  const post = (path, extra) => getJSON(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ skill: skillName, level: levelName, ...extra }),
  });

  box.replaceChildren(el("p", "syllabus-note", regenerate
    ? "Generando el temario de nuevo: tres borradores y una fusión. Un par de minutos."
    : "Leyendo el temario…"));

  // La espera va donde va a aparecer el temario. Es la más larga del app —dos
  // minutos la primera vez de un nivel— y hasta ahora eran dos minutos de una
  // frase quieta bajo un botón gris.
  let stop = regenerate ? waiting(box, SYLLABUS_ESTIMATE_MS) : null;

  let painted = false;

  try {
    // El temario está congelado en disco: llega en milisegundos y se pinta
    // antes de pedir nada más. Al modelo sólo se lo llama si este nivel
    // todavía no tiene temario —una vez en su vida— o si pediste regenerarlo.
    let data = regenerate ? { frozen: false } : await getJSON(
      `/api/syllabus?skill=${encodeURIComponent(skillName)}` +
      `&level=${encodeURIComponent(levelName)}`);
    if (!mine()) return;

    // El archivo existe y no se puede leer. **No se regenera solo**: sobre un
    // nivel sin temario generar es correcto —es la primera vez, no hay nada que
    // perder—, pero sobre un archivo roto es pisar trabajo tuyo sin preguntar,
    // y la edición a mano es justamente para lo que este archivo se congeló.
    if (data.unreadable && !regenerate) {
      renderUnreadable(box, data, again);
      painted = true;
      return;
    }

    if (!data.frozen) {
      box.replaceChildren(el("p", "syllabus-note", regenerate
        ? "Generando el temario de nuevo: tres borradores y una fusión. Un par de minutos."
        : "Primera vez de este nivel: tres borradores y una fusión. Un par de minutos."));
      stop = waiting(box, SYLLABUS_ESTIMATE_MS);
      data = await post("/api/syllabus", { regenerate });
      if (!mine()) return;
    }
    stop?.();
    // ── La cobertura que ya se pagó ──────────────────────────────────
    // Sigue siendo un hecho derivado y sigue cambiando con cada tarjeta que
    // escribís. Lo que cambia es la frecuencia: eso justifica recalcularla
    // cuando algo cambió, no en cada lectura. Entre dos aperturas sin tocar
    // una tarjeta, esos treinta segundos no compran nada.
    const cached = data.coverage;
    const fresh = cached && sameDecks(cached.decks, decksNow);

    if (cached && !recompute) {
      renderSyllabus(box, data, skillName, levelName, again, fresh ? {
        text: `${data.covered} de ${data.total} puntos cubiertos por tus mazos · ${when(cached.computed)}`,
        action: { label: "Recalcular", run: update,
                  title: "Volver a preguntarle al modelo. Cerca de medio minuto." },
      } : {
        // Vieja, pero se pinta igual: son lo último que se supo, y borrar las
        // marcas para poner "todavía nadie miró" sería saber menos que hace un
        // rato. Lo que no se hace es recalcular sola — eso lo decidís vos.
        text: `${data.covered} de ${data.total} puntos, ${when(cached.computed)} `
            + `sobre ${plural(cardsIn(cached.decks), "tarjeta", "tarjetas")}. `
            + `Ahora este nivel tiene ${cardsIn(decksNow)}.`,
        action: { label: "Actualizar", run: update,
                  title: "Volver a comparar el temario con tus mazos de ahora. Cerca de medio minuto." },
      });
      return;
    }

    // Sin nada guardado —o pediste recalcular— hay que pagar la mitad lenta.
    // Con lo viejo en pantalla mientras tanto, si lo había.
    renderSyllabus(box, data, skillName, levelName, again, cached
      ? { text: "Actualizando la cobertura… cerca de medio minuto." }
      : undefined);
    painted = true;

    stop = waiting(box, COVERAGE_ESTIMATE_MS, box.children[1]);
    const covered = await post("/api/syllabus/coverage");
    if (!mine()) return;
    stop();
    stop = null;
    renderSyllabus(box, covered, skillName, levelName, again, {
      text: `${covered.covered} de ${covered.total} puntos cubiertos por tus mazos · calculada recién`,
      action: { label: "Recalcular", run: update,
                title: "Volver a preguntarle al modelo. Cerca de medio minuto." },
    });
  } catch (error) {
    // El temario es un extra sobre una pantalla que ya sirve, así que su fallo
    // se queda dentro de su propio panel: no se tira al router ni borra la
    // lista de mazos que está arriba. Y si los puntos ya están pintados, el
    // aviso se agrega debajo: que se caiga la cobertura no es razón para
    // borrar el temario, que se leyó bien.
    if (!mine()) return;
    stop?.(false);
    const note = el("p", "syllabus-note", error.message);
    if (painted) box.append(note); else box.replaceChildren(note);
  } finally {
    if (mine()) working(button, false);
  }
}

function levelPanel(level, skill, threshold) {
  const section = el("section", "panel");

  const head = el("div", "panel-head");
  const heading = el("h2", null, level.level);
  if (level.level === skill.current_level) {
    heading.append(el("span", "rail-chip", "estás acá"));
  }
  head.append(heading);

  const meta = el("span", "panel-meta");
  meta.append(el("span", "sub", level.total
    ? `${percent(level.maturity)} maduras${level.maturity >= threshold ? " · sostenido" : ""}`
    : "hueco"));
  head.append(meta);
  section.append(head);

  const list = el("ul", "rows");
  if (!level.decks.length) {
    // The hole is the finding, so it says what to do about it rather than
    // leaving a blank where a list should be — and the way out is one click,
    // carrying the level with it.
    const li = el("li", "empty");
    li.append(el("span", null, "Sin mazos en este nivel. "));
    const fill = el("a", null, "Generar las primeras tarjetas");
    fill.href = `#/agregar/${slug(skill.skill)}/${level.level}`;
    li.append(fill);
    list.append(li);
  } else {
    for (const deck of level.decks) list.append(deckRow(deck));
  }
  section.append(list);

  const button = el("button", "ghost syllabus-open", "Ver temario");
  button.type = "button";
  const box = el("div", "syllabus");
  box.hidden = true;
  // Los mazos de este nivel tal como están ahora: es contra esto que se juzga
  // si la cobertura guardada todavía vale.
  const decksNow = deckTotals(level);
  button.addEventListener("click", () =>
    loadSyllabus(button, box, skill.skill, level.level, decksNow));
  meta.append(button);
  section.append(box);

  return section;
}

function showHint(text) {
  $("start-hint").textContent = text;
  $("start-hint").hidden = false;
}

async function openInAnki(deck, button) {
  button.disabled = true;
  showHint("Abriendo Anki…");
  try {
    const data = await getJSON(`/api/study?deck=${encodeURIComponent(deck)}`,
                               { method: "POST" });
    showHint(`Anki está en “${data.deck}”, con ${plural(data.due, "tarjeta", "tarjetas")}. ` +
             `Si la ventana no saltó al frente, cambiá a ella.`);
  } catch (error) {
    showHint(error.message);
  } finally {
    button.disabled = false;
  }
}

export async function render(root, params) {
  root.innerHTML = MARKUP;
  const data = await catalog();

  const skill = data.skills.find((s) => slug(s.skill) === params[0]);
  if (!skill) {
    $("due-headline").textContent = "Esa habilidad no existe";
    $("skill-standing").textContent = "Las habilidades son Grammar, Writing, Speaking, Listening y Reading.";
    return;
  }

  $("due-headline").textContent = skill.skill;
  $("skill-standing").textContent = skill.total
    ? `Estás en ${skill.current_level} · ${percent(skill.maturity)} maduras`
    : "Sin ninguna tarjeta todavía";
  $("skill-rail").append(rail(skill, data.maturity_threshold));

  // La única acción primaria de esta pantalla, y sólo donde hay práctica. Un
  // `<a>` y no un `<button>`: es navegación, no una llamada.
  const practice = PRACTICE[skill.skill];
  if (practice) {
    const link = el("a", "primary", "Practicar escritura");
    link.href = `#/practica/${practice}`;
    const seen = el("a", "ghost", "Mis patrones de error");
    seen.href = "#/patrones";
    $("skill-actions").append(link, seen);
    $("skill-actions").hidden = false;
  }

  // Los cinco niveles en una columna, no en una rejilla de dos. A1 suele
  // llevar doce mazos y A2 dos, así que en dos columnas la segunda fila
  // esperaba a la primera y quedaba un agujero de ochocientos píxeles al lado
  // de A2. Y en una columna el orden vuelve a ser el que la pantalla cuenta:
  // A1 → C1, el mismo del riel de arriba.
  const levels = $("levels");
  for (const level of skill.levels) {
    levels.append(levelPanel(level, skill, data.maturity_threshold));
  }

  playEntrance();
}

// El riel entra con el vocabulario del tablero: escala desde la izquierda,
// escalonado, dentro del mismo presupuesto de 300 ms. Nunca `width`, que
// reflowaría la fila entera en cada cuadro.
function playEntrance() {
  loadMotion().then((motion) => {
    if (!motion) return;
    const { animate, stagger } = motion;
    const fills = document.querySelectorAll("#skill .seg-fill");
    if (!fills.length) return;
    animate(fills, {
      scaleX: [0, 1],
      duration: DURATION_MS,
      delay: stagger(staggerStep(fills.length)),
      ease: "outQuad",
    });
  });
}
