"""FastAPI backend. Serves the API and the static front end."""
import shutil
from datetime import date, datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

import analysis
import anki
import coach
import generate
import llm
import practice
import repair
import snapshot
import state
# Con alias: `syllabus` es el nombre de la mitad del app —el endpoint, la
# pantalla, el archivo— y el módulo se lee dentro de las funciones que lo
# sirven. Sin alias, cualquier nombre local lo taparía.
import syllabus as syllabus_store

app = FastAPI(title="claude-fluent")

# The Atascos screen is the whole ranking, not the head of it that Today shows.
STUCK_LIMIT = 50

# How many stuck cards the model is shown when asked what to study next. It
# needs the shape of the problem, not the whole list.
STUCK_FOR_PROMPT = 10

# How many existing cards of a level the model is shown before proposing more
# for it. Enough to see what is there, not so many that the prompt is a deck.
FRONTS_FOR_PROMPT = 60

# A ceiling on one write. Ten terms of three candidates is thirty cards, and
# anything far above that is a bug in the client rather than a real approval.
MAX_CARDS_PER_WRITE = 60

# El nivel al que se conversa cuando la pantalla no manda uno. **No se lee del
# catálogo.** `current_level` para Writing dice A1, pero por ausencia y no por
# diagnóstico: la caminata A1→C1 se detiene en el primer nivel que no se
# sostiene, y un nivel vacío tampoco se sostiene, así que con Writing en cero
# tarjetas siempre va a decir A1. B1 es i+1 sobre lo que la colección sí
# muestra — Grammar en A1/A2 contra Reading y Speaking en B2.
PRACTICE_LEVEL = "B1"


@app.middleware("http")
async def no_stale_assets(request, call_next):
    """Serve the static files fresh.

    StaticFiles sends ETag and Last-Modified but no Cache-Control, so browsers
    fall back to heuristic caching and happily keep serving a stylesheet you
    edited minutes ago. During development that is indistinguishable from the
    change not having worked.
    """
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


def _window_start_ms(days: int = analysis.CALENDAR_DAYS) -> int:
    """Midnight local time, `days` back. Reviews are fetched from here."""
    start = datetime.combine(date.today() - timedelta(days=days - 1), datetime.min.time())
    return int(start.timestamp() * 1000)


@app.get("/api/settings")
def settings() -> dict:
    """Lo que decide el app y Anki no sabe. Hoy: la meta diaria."""
    return state.read()


@app.post("/api/settings")
def save_settings(payload: dict) -> dict:
    try:
        return state.write(payload or {})
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/health")
def health() -> dict:
    """Checked first because every failure in this system is silent: Anki
    closed or claude without a session both leave the app looking normal
    while it lies to you."""
    return {
        "anki": anki.is_alive(),
        "claude": shutil.which("claude") is not None,
        "last_sync": state.read().get("last_sync"),
    }


@app.get("/api/today")
def today() -> dict:
    if not anki.is_alive():
        raise HTTPException(503, "AnkiConnect is not answering — is Anki running?")

    reviews = anki.reviews_since(_window_start_ms())
    deck_counts = anki.due_counts()
    summary = analysis.summary(reviews, deck_counts, date.today())
    summary["goal"] = state.read()["daily_goal"]

    # analysis.py stays pure, so the card text is looked up here and merged in.
    details = anki.card_summaries([c["card_id"] for c in summary["struggling"]])
    for card in summary["struggling"]:
        found = details.get(card["card_id"], {})
        card["front"] = found.get("front", "")
        card["note_id"] = found.get("note_id")

    return summary


@app.get("/api/catalog")
def catalog() -> dict:
    """The deck catalogue, skill -> level -> decks.

    The classification comes from the deck name every time it is read; there is
    nothing stored to keep in sync. Renaming a deck in Anki is the whole
    editing interface.
    """
    if not anki.is_alive():
        raise HTTPException(503, "AnkiConnect is not answering — is Anki running?")

    return analysis.catalog(anki.deck_card_stats(), anki.due_counts())


@app.get("/api/stuck")
def stuck() -> dict:
    """The full list of cards you keep failing, with severity and the minutes
    they cost. The Today screen shows the head of this same ranking."""
    if not anki.is_alive():
        raise HTTPException(503, "AnkiConnect is not answering — is Anki running?")

    reviews = analysis.english_only(anki.reviews_since(_window_start_ms()))
    cards = analysis.struggling(reviews, limit=STUCK_LIMIT)

    # analysis.py stays pure, so the card text is looked up here and merged in.
    details = anki.card_summaries([c["card_id"] for c in cards])
    for card in cards:
        found = details.get(card["card_id"], {})
        card["front"] = found.get("front", "")
        card["note_id"] = found.get("note_id")
        card["severity"] = analysis.severity(card)

    total_cards = sum(d["total"] for d in anki.deck_card_stats()
                      if analysis.in_scope(d["deck"]))
    total_seconds = sum(r.duration_ms for r in reviews) / 1000.0
    return {
        "cards": cards,
        "impact": analysis.impact(cards, total_cards, total_seconds),
        "window": {"days": analysis.CALENDAR_DAYS, "reviews": len(reviews)},
    }


@app.post("/api/study")
def study(deck: str | None = None) -> dict:
    """Hand the session over to Anki, on the deck that actually has work.

    Reviewing is Anki's job; this app only decides where to start. With no
    `deck` the busiest one wins; the Progreso screen passes the one it named,
    so the button does what the sentence above it just promised.
    """
    if not anki.is_alive():
        raise HTTPException(503, "AnkiConnect is not answering — is Anki running?")

    due = analysis.due_by_deck(anki.due_counts())
    if deck is None:
        target = next((d for d in due["decks"] if d["due"] > 0), None)
    else:
        # Never forward an unchecked name to guiDeckReview: a deck that does
        # not exist opens the reviewer on nothing and looks like a hang.
        target = next(
            (d for d in due["decks"] if d["deck"] == deck and d["due"] > 0), None
        )
    if target is None:
        raise HTTPException(409, "No hay tarjetas pendientes hoy.")

    anki.open_deck_review(target["deck"])
    return {"ok": True, "deck": target["deck"], "due": target["due"]}


@app.post("/api/add-cards")
def add_cards() -> dict:
    """Open Anki's Add dialog. Generation with the model comes later."""
    if not anki.is_alive():
        raise HTTPException(503, "AnkiConnect is not answering — is Anki running?")
    anki.open_add_cards()
    return {"ok": True}


def _catalog() -> dict:
    return analysis.catalog(anki.deck_card_stats(), anki.due_counts())


def _stuck_with_text(limit: int) -> list[dict]:
    """The stuck ranking with each card's front text merged in.

    analysis.py stays pure, so the text is looked up here — the model needs to
    read the cards, not their ids.
    """
    cards = analysis.struggling(
        analysis.english_only(anki.reviews_since(_window_start_ms())), limit=limit)
    details = anki.card_summaries([c["card_id"] for c in cards])
    for card in cards:
        card["front"] = details.get(card["card_id"], {}).get("front", "")
    return cards


def _decks_at(catalog: dict, focus: dict) -> list[str]:
    """The decks of one skill and level, by full name.

    The catalogue is a tree and both the term proposal and the syllabus need
    the same branch of it; walking it twice by hand is how the two drift.
    """
    for skill in catalog["skills"]:
        if skill["skill"] != focus["skill"]:
            continue
        for level in skill["levels"]:
            if level["level"] == focus["level"]:
                return [d["deck"] for d in level["decks"]]
    return []


@app.post("/api/generate/terms")
def generate_terms(payload: dict | None = None) -> dict:
    """What is worth making cards for, read off the failures and the holes.
    Proposes only: nothing is written and no card exists yet.

    An optional `{skill, level}` narrows the question to one hole — the screen
    sends it when you arrived from a level with no deck at all. An optional
    `{topic}` is whatever was typed in the box: a subject to open into its
    terms rather than something to ignore.
    """
    if not anki.is_alive():
        raise HTTPException(503, "AnkiConnect is not answering — is Anki running?")

    focus = generate.focus_for(
        (payload or {}).get("skill", ""), (payload or {}).get("level", ""))

    catalog = _catalog()

    # Lo que ese nivel ya tiene, para que "enriquecer" no proponga lo que ya
    # estudiás. Sólo se lee cuando hay foco: sin él la pregunta es la colección
    # entera y la lista no cabría en el prompt.
    have: list[str] = []
    if focus:
        for deck in _decks_at(catalog, focus):
            have += anki.deck_fronts(deck, limit=FRONTS_FOR_PROMPT)

    try:
        return generate.propose_terms(
            _stuck_with_text(STUCK_FOR_PROMPT), catalog, focus,
            topic=(payload or {}).get("topic", ""), have=have)
    except llm.LLMError as e:
        raise HTTPException(502, f"claude -p failed: {e}") from e


def _syllabus_body(stored: dict, points: list[dict] | None = None) -> dict:
    """La forma que devuelven las tres llamadas del temario.

    Leer, congelar y cubrir hablan del mismo objeto y la pantalla lo dibuja con
    el mismo código; que una devuelva una clave distinta es exactamente cómo se
    rompe. `covered` es `None` mientras la cobertura no se derivó — no es cero,
    que querría decir "ningún punto cubierto", que es otra cosa.
    """
    skill, level = stored["skill"], stored["level"]
    return {
        "skill": skill,
        "level": level,
        "frozen": True,
        "points": points if points is not None else stored["points"],
        "covered": (sum(1 for p in points if p["covered_by"])
                    if points is not None else None),
        "total": len(stored["points"]),
        "drafts": stored.get("drafts"),
        "generated": stored.get("generated"),
        "edited": stored.get("edited", False),
        "path": str(syllabus_store.path_for(skill, level)),
    }


@app.get("/api/syllabus")
def syllabus_frozen(skill: str = "", level: str = "") -> dict:
    """El temario congelado de un nivel. Sin cobertura, sin modelo, sin Anki.

    Es la mitad estable y está en disco, así que se sirve en milisegundos: la
    pantalla pinta los puntos al instante y pide la cobertura después, que es
    la que tarda. Antes las dos mitades viajaban en la misma llamada y un nivel
    ya congelado se veía igual que uno generándose desde cero — cuarenta
    segundos en blanco bajo un cartel que decía "la primera vez tarda un par de
    minutos".

    Un nivel sin temario contesta `frozen: false`, que no es un error: es la
    primera vez, y quien pregunta necesita distinguirlas.
    """
    focus = generate.focus_for(skill, level)
    if not focus:
        raise HTTPException(400, "unknown skill or level")

    stored = syllabus_store.load(focus["skill"], focus["level"])
    if stored is None:
        return {
            "skill": focus["skill"],
            "level": focus["level"],
            "frozen": False,
            "points": [],
            "covered": None,
            "total": 0,
            "drafts": None,
            "generated": None,
            "edited": False,
            "path": str(syllabus_store.path_for(focus["skill"], focus["level"])),
        }
    return _syllabus_body(stored)


@app.post("/api/syllabus")
def syllabus_freeze(payload: dict | None = None) -> dict:
    """Congelar el temario de un nivel: tres borradores y una fusión, ~100 s.

    Sólo llama al modelo si ese nivel todavía no tiene temario, o si pediste
    `{regenerate: true}`. Con uno congelado devuelve el que hay y no gasta una
    llamada: la mitad estable se genera una vez en la vida del nivel.

    No toca Anki. Qué enseña un A1 es un hecho externo y no depende de tu
    colección, así que esto funciona con Anki cerrado. **No escribe en Anki.**
    """
    focus = generate.focus_for(
        (payload or {}).get("skill", ""), (payload or {}).get("level", ""))
    if not focus:
        raise HTTPException(400, "unknown skill or level")

    skill, level = focus["skill"], focus["level"]
    regenerate = bool((payload or {}).get("regenerate"))

    stored = None if regenerate else syllabus_store.load(skill, level)
    if stored is not None:
        return _syllabus_body(stored)

    try:
        built = generate.build_syllabus(skill, level)
    except llm.LLMError as e:
        raise HTTPException(502, f"claude -p failed: {e}") from e
    if not built["points"]:
        raise HTTPException(502, "el modelo no devolvió ningún punto")

    stored = syllabus_store.save(
        skill, level, built["points"], built["drafts"],
        datetime.now().isoformat(timespec="seconds"))
    return _syllabus_body({**stored, "edited": False})


@app.post("/api/syllabus/coverage")
def syllabus_coverage(payload: dict | None = None) -> dict:
    """Qué mazo de los tuyos cubre cada punto del temario. ~40 s.

    Ésta es la mitad que sí se deriva en cada lectura: es un hecho sobre la
    colección y cambia con cada tarjeta que escribís.

    Los puntos se leen del disco y no del cuerpo del pedido. `generate.cover`
    recorre la lista **congelada** para que un punto inventado quede fuera y
    uno saltado aparezca igual, sin cubrir; esa garantía no vale nada si la
    lista la manda quien llama. **No escribe nada.**
    """
    focus = generate.focus_for(
        (payload or {}).get("skill", ""), (payload or {}).get("level", ""))
    if not focus:
        raise HTTPException(400, "unknown skill or level")

    if not anki.is_alive():
        raise HTTPException(503, "AnkiConnect is not answering — is Anki running?")

    skill, level = focus["skill"], focus["level"]
    stored = syllabus_store.load(skill, level)
    if stored is None:
        raise HTTPException(409, "ese nivel todavía no tiene temario congelado")

    decks = _decks_at(_catalog(), focus)

    # Repartida entre los mazos y no por mazo: siete mazos a sesenta frentes
    # serían cuatrocientas líneas de prompt, y un tope por mazo dejaría al
    # último sin una sola tarjeta a la vista — invisible es indistinguible de
    # vacío, y se marcaría como no cubierto.
    per_deck = max(4, FRONTS_FOR_PROMPT // max(1, len(decks)))
    have: list[str] = []
    for deck in decks:
        topic = deck.split("::")[-1]
        have += [f"{topic}: {front}"
                 for front in anki.deck_fronts(deck, limit=per_deck)]

    try:
        points = generate.cover(
            skill, level, stored["points"],
            [d.split("::")[-1] for d in decks], have)
    except llm.LLMError as e:
        raise HTTPException(502, f"claude -p failed: {e}") from e

    return _syllabus_body(stored, points)


@app.post("/api/generate/cards")
def generate_cards(payload: dict) -> dict:
    """Candidate cards for one term, and the deck they belong in.

    One term per request on purpose: each is its own `claude -p` call of 8-15s,
    so the screen fills in as they land instead of staring at one long spinner,
    and a term that fails costs only itself.

    An optional `{skill, level}` — the one Agregar was opened on — is where the
    cards get filed, instead of the level the model judges the term to belong
    to. Coming from a hole and being handed a deck of another level is losing
    the reason you came.
    """
    if not anki.is_alive():
        raise HTTPException(503, "AnkiConnect is not answering — is Anki running?")

    term = str(payload.get("term", "")).strip()
    if not term:
        raise HTTPException(400, "no term")
    if len(term) > 80:
        raise HTTPException(400, "term too long")

    focus = generate.focus_for(
        payload.get("skill", ""), payload.get("level", ""))

    try:
        return generate.propose_cards(term, _catalog(), focus=focus)
    except llm.LLMError as e:
        raise HTTPException(502, f"claude -p failed: {e}") from e


def _clean_deck_name(value: str) -> str:
    """A deck name is a path in the collection, so it is checked rather than
    trusted: no empty components, no stray separators, no runaway length."""
    parts = [p.strip() for p in str(value or "").split("::")]
    if not parts or any(not p for p in parts) or len(value) > 200:
        raise HTTPException(400, f"invalid deck name: {value!r}")
    return "::".join(parts)


@app.post("/api/notes")
def add_notes(payload: dict) -> dict:
    """Create the approved cards. The one write path for generation.

    The model proposes and you approve: this endpoint only ever receives cards
    that were ticked on the screen. It creates the note type if it is missing —
    with its own record, since AnkiConnect cannot delete one — and then writes
    each deck's cards through snapshot.add_notes, which leaves a creation
    record so exactly these notes can be removed again.
    """
    if not anki.is_alive():
        raise HTTPException(503, "AnkiConnect is not answering — is Anki running?")

    cards = payload.get("cards")
    if not isinstance(cards, list) or not cards:
        raise HTTPException(400, "no cards to add")
    if len(cards) > MAX_CARDS_PER_WRITE:
        raise HTTPException(400, f"more than {MAX_CARDS_PER_WRITE} cards in one write")

    by_deck: dict[str, list[dict]] = {}
    for card in cards:
        if not isinstance(card, dict):
            raise HTTPException(400, "malformed card")
        front = str(card.get("front", "")).strip()
        back = str(card.get("back", "")).strip()
        if not front or not back:
            raise HTTPException(400, "a card needs both a front and a back")
        deck = _clean_deck_name(card.get("deck"))
        by_deck.setdefault(deck, []).append({
            "model": generate.MODEL_NAME,
            "tags": ["claude-fluent"],
            # The client sends plain text; Anki stores HTML.
            "fields": {
                "Front": anki.to_field_html(front),
                "Back": anki.to_field_html(back),
                "Ejemplo": anki.to_field_html(str(card.get("example", "")).strip()),
            },
        })

    model_record = snapshot.ensure_model(
        generate.MODEL_NAME, generate.MODEL_FIELDS,
        generate.MODEL_TEMPLATES, generate.MODEL_CSS,
    )

    written = []
    for deck, notes in by_deck.items():
        ids, record, refused = snapshot.add_notes(deck, notes)
        # Read the result back from Anki rather than trusting the response of
        # the call that wrote it: addNotes once returned eight ids for notes
        # that were gone a minute later.
        alive = [n for n in anki.call("notesInfo", notes=ids) if n] if ids else []
        written.append({
            "deck": deck,
            "asked": len(notes),
            "created": len(ids),
            "verified": len(alive),
            "refused": refused,
            "record": str(record),
        })

    return {
        "ok": True,
        "added": sum(w["verified"] for w in written),
        "refused": [r for w in written for r in w["refused"]],
        "decks": written,
        "model_created": str(model_record) if model_record else None,
    }


@app.post("/api/repair/{note_id}")
def propose_repair(note_id: int) -> dict:
    """Ask the model for a better version of a note. Writes nothing."""
    if not anki.is_alive():
        raise HTTPException(503, "AnkiConnect is not answering — is Anki running?")

    try:
        note = anki.note_info(note_id)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e

    try:
        return repair.propose(note)
    except llm.LLMError as e:
        raise HTTPException(502, f"claude -p failed: {e}") from e


@app.post("/api/apply/{note_id}")
def apply_repair(note_id: int, payload: dict) -> dict:
    """Write the approved fields back. Snapshot first, always."""
    if not anki.is_alive():
        raise HTTPException(503, "AnkiConnect is not answering — is Anki running?")

    fields = payload.get("fields")
    if not isinstance(fields, dict) or not fields:
        raise HTTPException(400, "no fields to apply")

    try:
        note = anki.note_info(note_id)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e

    # The client does not get to invent field names either.
    known = set(anki.note_fields(note))
    unknown = sorted(set(fields) - known)
    if unknown:
        raise HTTPException(400, f"unknown fields for this note: {', '.join(unknown)}")

    # The client sends plain text; Anki stores HTML.
    encoded = {name: anki.to_field_html(str(value)) for name, value in fields.items()}

    try:
        path = snapshot.update_note_fields(note_id, encoded)
    except anki.WriteWithoutSnapshot as e:  # cannot happen; loud if it ever does
        raise HTTPException(500, str(e)) from e

    written = anki.note_fields(anki.note_info(note_id))
    return {
        "ok": True,
        "note_id": note_id,
        "snapshot": str(path),
        "fields": {name: anki.to_plain_text(value) for name, value in written.items()},
    }


# ── La práctica de escritura ──────────────────────────────────────────────
# Ninguno de estos seis toca Anki, así que ninguno lleva el guardia de 503. Es
# deliberado y hay que sostenerlo: conversar en inglés no necesita la colección
# para nada, y heredar el guardia por copiar y pegar mataría la pantalla entera
# cada vez que Anki está cerrado, sin ninguna razón.


def _practice_level(value) -> str:
    """El nivel que manda la pantalla, contra la tupla cerrada de siempre."""
    wanted = str(value or "").strip().lower()
    for level in analysis.LEVELS:
        if level.lower() == wanted:
            return level
    return PRACTICE_LEVEL


def _open_or_404(session_id) -> dict:
    """La sesión que el cliente nombró, abierta y escribible, o el error."""
    try:
        practice._valid_id(session_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    session = practice.load(str(session_id))
    if session is None:
        raise HTTPException(404, "esa sesión no existe")
    if session["closed"]:
        raise HTTPException(409, "esa sesión ya está cerrada")
    return session


@app.get("/api/practice/session")
def practice_session() -> dict:
    """La sesión abierta, y la última cerrada. Lee disco: sin modelo.

    `last` viaja entera para que releer el análisis no cueste una segunda
    petición: es un archivo local y una sesión completa son unos pocos kilobytes.
    """
    return {
        "session": practice.open_session(),
        "last": practice.last_closed(),
        "topics": practice.recent_topics(),
    }


@app.post("/api/practice/session")
def practice_start(payload: dict | None = None) -> dict:
    """Abrir una sesión sobre un tema.

    No llama al modelo: el saludo lo compone el app. Quince segundos de espera
    antes de poder escribir la primera palabra es exactamente donde se abandona,
    y para decir "hablemos de anime" no hace falta un `claude -p`.
    """
    body = payload or {}
    topic = " ".join(str(body.get("topic", "")).split())[:60]
    if not topic:
        raise HTTPException(400, "elegí un tema para conversar")

    level = _practice_level(body.get("level"))

    current = practice.open_session()
    if current and not body.get("restart"):
        raise HTTPException(409, "ya tenés una sesión abierta")
    if current:
        current["closed"] = True
        current["abandoned"] = True
        current["closed_at"] = datetime.now().isoformat(timespec="seconds")
        practice.save(current)

    session = practice.new_session(topic, level)
    return {
        "session": session,
        "opening": f"Let's talk about {topic}. What's on your mind?",
    }


@app.post("/api/practice/turn")
def practice_turn(payload: dict) -> dict:
    """Responder un mensaje y corregir lo que estorbó. Una llamada, 13-21 s.

    El turno se persiste dos veces: tu texto primero, la respuesta después. Sin
    ese primer write, recargar a los cinco segundos borra lo que escribiste.
    """
    session = _open_or_404(payload.get("session_id"))

    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(400, "no escribiste nada")
    if len(text) > coach.MAX_TEXT_CHARS:
        raise HTTPException(400, "el mensaje es demasiado largo")
    # Reintentar reescribe el turno que falló; mandar uno nuevo lo agrega.
    retry = payload.get("retry_index")
    if retry is None:
        if len(session["turns"]) >= practice.MAX_TURNS:
            raise HTTPException(
                409, f"esta sesión ya llegó a {practice.MAX_TURNS} turnos: cerrala y analizala")
        turn = practice.append_turn(session, text)
    else:
        try:
            turn = practice.retry_turn(session, int(retry), text)
        except (TypeError, ValueError, IndexError) as e:
            raise HTTPException(400, f"no se puede reintentar ese turno: {e}") from e
    try:
        answer = coach.turn(session["topic"], session["level"],
                            session["turns"][:turn["index"]], text)
    except llm.LLMError as e:
        # El turno queda visible y reintentable: cuesta ese turno y nada más.
        practice.finish_turn(session, turn["index"], None, str(e))
        raise HTTPException(502, f"claude -p failed: {e}") from e

    return {
        "turn": practice.finish_turn(session, turn["index"], answer),
        "total": len(session["turns"]),
    }


@app.post("/api/practice/close")
def practice_close(payload: dict) -> dict:
    """Leer la sesión entera de una vez y contar los patrones. ~20-40 s.

    El único endpoint que escribe `patterns.json`. Se cuenta acá y no en cada
    turno porque el mismo error se corregiría dos veces —una en el turno, otra
    en el análisis— y porque el cierre es lo único que ve la sesión completa y
    sabe qué se repitió, que es la pregunta que el contador responde.
    """
    session = _open_or_404(payload.get("session_id"))
    done = [t for t in session["turns"] if t["state"] == "done"]

    analysis_result = None
    if done:
        try:
            analysis_result = coach.close(session["topic"], session["level"],
                                          session["turns"])
        except llm.LLMError as e:
            raise HTTPException(502, f"claude -p failed: {e}") from e

    session["analysis"] = analysis_result
    session["closed"] = True
    session["closed_at"] = datetime.now().isoformat(timespec="seconds")
    practice.save(session)

    if analysis_result is None:
        return {"session": session, "counted": [], "ready": []}

    stored = practice.count(practice.read_patterns(), analysis_result["areas"],
                            analysis_result["unmatched"], session["id"])
    practice.write_patterns(stored)

    counted = {a["pattern"] for a in analysis_result["areas"] if a["pattern"]}
    rows = practice.listing(stored)
    return {
        "session": session,
        "counted": [r for r in rows if r["key"] in counted],
        "ready": [r for r in rows if r["ready"]],
        "threshold": practice.PATTERN_THRESHOLD,
    }


@app.get("/api/practice/patterns")
def practice_patterns() -> dict:
    """El conteo entero. `unmatched` no es un contador: es lo que le falta al
    catálogo, que es tuyo para ampliar."""
    stored = practice.read_patterns()
    return {
        "patterns": practice.listing(stored),
        "unmatched": stored["unmatched"],
        "threshold": practice.PATTERN_THRESHOLD,
    }


@app.post("/api/practice/patterns")
def practice_mark(payload: dict) -> dict:
    """`carded` cuando ya escribiste la tarjeta, `reset` cuando no te importa.

    Sin esto la fila te reclama la misma tarjeta para siempre.
    """
    try:
        stored = practice.mark(practice.read_patterns(),
                               str(payload.get("key", "")),
                               str(payload.get("action", "")),
                               practice.stamp())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    practice.write_patterns(stored)
    return {"patterns": practice.listing(stored),
            "threshold": practice.PATTERN_THRESHOLD}


# Must go last: mounted at the root, it swallows the /api routes above it.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
