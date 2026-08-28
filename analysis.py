"""Pure functions over a list of reviews. No I/O, no AnkiConnect, no clock:
every function takes the data and the reference date it should work against,
so the whole module is testable by handing it rows."""
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta

from anki import Review, interval_to_seconds

CALENDAR_DAYS = 30

# The catalogue is derived from the deck name on every read, following the
# convention Skill::Level::Topic. Nothing is stored: renaming a deck in Anki
# reclassifies it, and there is no mapping on disk to drift out of date.
SKILLS = ("Grammar", "Writing", "Speaking", "Listening", "Reading")
LEVELS = ("A1", "A2", "B1", "B2", "C1")
UNCLASSIFIED = "Sin clasificar"

# A level counts as held once this share of its cards is mature — Anki's own
# definition, an interval of three weeks or more, applied by anki.deck_card_stats.
# Not 100%: waiting for every card to mature means never advancing, because new
# cards keep arriving at the level you are working on.
MATURITY_THRESHOLD = 0.60

# Severity bands for the stuck cards, on failure rate rather than on the ranking
# score. `score` has no ceiling — its weights are tuned for ordering, not for
# reading — so any threshold over it would be unexplainable. "You get this one
# wrong half the times you see it" is a sentence.
SEVERITY_CRITICAL = 0.50
SEVERITY_HIGH = 0.30

# How many stuck cards the Hoy screen lists. Atascos shows the whole ranking,
# and the Dashboard shows only how long that ranking is.
TODAY_STUCK_LIMIT = 12

# A card has to have been seen a few times AND actually failed before it counts
# as stuck. Ranking on time alone surfaces cards you simply read slowly, which
# is how "0 fallos de 3" ended up at the top of the list.
MIN_ATTEMPTS = 3
MIN_FAILURES = 1

# Dos preguntas distintas sobre las mismas tarjetas, y por eso dos ordenamientos.
#
#   ¿Qué me está costando tiempo?   → `struggling`, que es lo que pinta Atascos
#                                      bajo el titular "te están costando 83 min".
#   ¿Qué vengo fallando?            → `failing_now`, que es lo que pinta Hoy
#                                      bajo el titular "Vengo fallando".
#
# Eran el mismo ranking, y el que se llamaba "vengo fallando" estaba ordenado
# por tiempo: medido contra la colección real, **el 87 % del puntaje era tiempo
# y sólo el 9 % eran fallos**. La consecuencia se veía en pantalla: una tarjeta
# fallada 2 de 11 veces encabezaba la lista y otra fallada 9 de 11 quedaba
# duodécima, porque la primera es lenta y se repasó más veces. `seconds_lost`
# es una suma sobre todos los repasos, así que crece con la cantidad de
# repasos; la tasa de fallo, en cambio, tiene techo en 1.
W_FAILURE_RATE = 60.0
W_SECONDS_LOST = 1.0     # segundos **totales**: el costo, para Atascos
W_INTERVAL_DROP = 8.0

# Para "vengo fallando": los fallos mandan y el tiempo sólo desempata. Es el
# segundo **medio** por repaso y no el total, justamente para que ver una
# tarjeta muchas veces no la suba sola.
W_FAILURES = 6.0         # cuántas veces, no sólo en qué proporción
W_SECONDS_EACH = 0.5     # lo lenta que es cada vez, como desempate

# Y sólo lo que estás repasando ahora. Una tarjeta que no ves hace dos semanas
# no es algo que "vengas fallando": es de un mazo que dejaste. Medido: cinco de
# las doce que mostraba Hoy no se tocaban hacía quince días.
RECENT_DAYS = 7

# El aprendizaje inicial no cuenta como fallo. Un "Otra vez" mientras aprendés
# una tarjeta nueva es el método funcionando, no una tarjeta atascada — y se
# nota en los números: 7 % de fallos en los repasos de tipo aprendizaje contra
# 45 % en los de reaprendizaje, que son los que sí dicen que algo se te
# olvidó. (Tipos del revlog: 0 aprendiendo · 1 repaso · 2 reaprendiendo.)
LEARNING_TYPE = 0


def _day(timestamp_ms: int) -> date:
    return datetime.fromtimestamp(timestamp_ms / 1000).date()


def studied_days(reviews: list[Review]) -> set[date]:
    """The set of local dates on which at least one card was reviewed."""
    return {_day(r.timestamp_ms) for r in reviews}


def streak(reviews: list[Review], today: date, grace_per_month: int = 1) -> dict:
    """Consecutive days studied, counting back from today.

    One grace day per calendar month: missing a single day does not reset the
    streak, because breaking it is the moment of highest abandonment risk.
    Today not being studied yet never breaks the streak — the day is not over.
    The walk stops at the first day ever studied, so days before you started
    never consume grace.
    """
    days = studied_days(reviews)
    grace_left: dict[tuple[int, int], int] = defaultdict(lambda: grace_per_month)
    if not days:
        return {
            "days": 0,
            "grace_used": [],
            "grace_left_this_month": grace_per_month,
            "studied_today": False,
        }

    first_day = min(days)
    cursor = today
    if cursor not in days:
        cursor -= timedelta(days=1)  # today is still in progress

    count = 0
    used: list[str] = []
    while cursor >= first_day:
        if cursor in days:
            count += 1
        else:
            month = (cursor.year, cursor.month)
            if grace_left[month] <= 0:
                break
            grace_left[month] -= 1
            used.append(cursor.isoformat())
        cursor -= timedelta(days=1)

    month_now = (today.year, today.month)
    return {
        "days": count,
        "grace_used": used,
        "grace_left_this_month": max(grace_left[month_now], 0)
        if month_now in grace_left
        else grace_per_month,
        "studied_today": today in days,
    }


def calendar(reviews: list[Review], today: date, days: int = CALENDAR_DAYS) -> list[dict]:
    """One entry per day for the last `days`, oldest first."""
    counts: dict[date, int] = defaultdict(int)
    for r in reviews:
        counts[_day(r.timestamp_ms)] += 1

    # Days before the first review are days the app did not exist for. They are
    # not missed days and must not be drawn as if they were.
    first = min(counts) if counts else None

    start = today - timedelta(days=days - 1)
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        out.append({
            "date": d.isoformat(),
            "reviews": counts.get(d, 0),
            "studied": counts.get(d, 0) > 0,
            "before_start": first is not None and d < first,
        })
    return out


def in_scope(deck: str) -> bool:
    """¿Este mazo es de este app?

    Sí cuando cuelga de una de las cinco skills — `Reading`,
    `Reading::A1::Mil palabras` — y no en cualquier otro caso. La colección es
    de una persona, no de una app: al lado del inglés viven los mazos de una
    maestría, y sumarlos infla las pendientes, alarga la racha con días en que
    no tocaste inglés y mete tarjetas de otro idioma en el ranking de atascos.

    No hay lista que mantener ni ajuste que recordar: **el nombre del mazo es
    la base de datos**, acá también. Lo que el app crea nace dentro de la
    convención y entra solo; lo que no la sigue se queda afuera y se sigue
    viendo en Mazos, que es donde un mazo que el app no entiende importa.
    """
    head = deck.split("::")[0].strip().lower()
    return head in {skill.lower() for skill in SKILLS}


def english_only(reviews: list[Review]) -> list[Review]:
    """Los repasos de los mazos de este app."""
    return [r for r in reviews if in_scope(r.deck)]


def done_today(reviews: list[Review], today: date) -> dict:
    """Lo hecho hoy: tarjetas distintas y repasos.

    Las dos cifras porque no son la misma: fallar una tarjeta y volver a verla
    diez minutos después son dos repasos de una sola tarjeta, y una meta que
    contara repasos se cumpliría fallando.
    """
    rows = [r for r in reviews if _day(r.timestamp_ms) == today]
    return {"cards": len({r.card_id for r in rows}), "reviews": len(rows)}


def due_by_deck(deck_counts: list[dict]) -> dict:
    """Shape the per-deck due counts and total them. Due state is scheduling,
    not history, so it comes from Anki rather than from the revlog.

    **Anki rolls a deck's counts up into its parents.** Summing every row
    counts each card once per level of its name: with `Reading`,
    `Reading::A1` and `Reading::A1::Mil palabras` all reporting the same 206,
    a collection of 458 cards claimed 1147 waiting. Nothing was wrong with the
    data — the naming convention gave the decks parents for the first time,
    and the old flat collection had hidden the bug.

    So the total is the sum of the **roots**, which is exactly what Anki's own
    deck browser shows and exactly what a session will serve; and the list is
    the **leaves**, which are the decks you can actually pick. They do not add
    up, and that is Anki being honest: a parent's daily limit can be lower than
    the sum of its children — 206 + 119 under a parent that will serve 212.
    """
    rows = [d for d in deck_counts if in_scope(d["deck"])]
    names = {d["deck"] for d in rows}
    is_container = lambda name: any(o.startswith(f"{name}::") for o in names)

    roots = [d for d in rows if "::" not in d["deck"]]
    leaves = [d for d in rows if not is_container(d["deck"])]

    return {
        "total": sum(d["due"] for d in roots),
        "decks": sorted(leaves, key=lambda d: (-d["due"], d["deck"])),
    }


def card_stats(reviews: list[Review]) -> list[dict]:
    """Una fila por tarjeta, con los dos puntajes y sin ordenar.

    Las dos preguntas —qué te cuesta tiempo y qué venís fallando— se responden
    con los mismos números y se diferencian sólo en cómo se ordenan, así que se
    cuentan una vez sola. Contarlas dos veces es cómo las dos listas se van
    separando en cosas que no deberían.

    Las dos puertas valen para las dos: vista al menos MIN_ATTEMPTS veces y
    fallada al menos MIN_FAILURES. Sin la puerta de los fallos, cualquier
    ranking sobre tiempo es una lista de tarjetas lentas, y una tarjeta que
    nunca fallaste no es una en la que estés trabado.
    """
    by_card: dict[int, list[Review]] = defaultdict(list)
    for r in reviews:
        by_card[r.card_id].append(r)

    rows_out = []
    for card_id, rows in by_card.items():
        attempts = len(rows)
        failures = sum(1 for r in rows if r.failed)
        if attempts < MIN_ATTEMPTS or failures < MIN_FAILURES:
            continue

        drops = sum(1 for r in rows if r.interval_dropped)
        durations = [r.duration_ms for r in rows]
        seconds_lost = sum(durations) / 1000.0
        seconds_each = statistics.mean(durations) / 1000.0

        failure_rate = failures / attempts

        rows_out.append({
            "card_id": card_id,
            "deck": rows[-1].deck,
            "attempts": attempts,
            "failures": failures,
            "failure_rate": round(failure_rate, 2),
            "interval_drops": drops,
            "avg_duration_ms": round(statistics.mean(durations)),
            "seconds_lost": round(seconds_lost, 1),
            "last_seen": datetime.fromtimestamp(
                rows[-1].timestamp_ms / 1000
            ).isoformat(timespec="seconds"),
            "last_interval_s": interval_to_seconds(rows[-1].new_interval),
            # Lo que te cuesta: los segundos totales mandan, porque la pregunta
            # es cuántos minutos te comen.
            "score": round(
                W_FAILURE_RATE * failure_rate
                + W_SECONDS_LOST * seconds_lost
                + W_INTERVAL_DROP * drops, 1),
            # Lo que venís fallando: manda la proporción, la cantidad de fallos
            # la respalda, y el segundo medio sólo desempata. La caída de
            # intervalo dice casi lo mismo que un fallo —el programador la
            # aplica cuando fallás— y por eso refuerza en vez de aportar.
            "failing_score": round(
                W_FAILURE_RATE * failure_rate
                + W_FAILURES * failures
                + W_SECONDS_EACH * seconds_each
                + W_INTERVAL_DROP * drops, 1),
        })

    return rows_out


def struggling(reviews: list[Review], limit: int | None = 12) -> list[dict]:
    """Las tarjetas que más tiempo te cuestan. Es lo que ordena Atascos.

    Tres señales se combinan porque ninguna alcanza sola: una tarjeta puede
    fallarse seguido, ser lenta siempre sin fallarse, o que el programador le
    siga recortando el intervalo.
    """
    ranked = sorted(card_stats(reviews), key=lambda c: -c["score"])
    # `limit=None` returns the whole ranking, which is what the counters on the
    # dashboard need: with the list cut to twelve, "7 atascos" and "12 atascos"
    # would be the same screen.
    return ranked[:limit]


def failing_now(reviews: list[Review], today: date,
                limit: int | None = TODAY_STUCK_LIMIT,
                recent_days: int = RECENT_DAYS) -> list[dict]:
    """Lo que venís fallando **de lo que estás repasando**. Es lo de Hoy.

    Dos diferencias con `struggling`, y las dos salieron de mirar la lista real:

    Se ordena por fallos y no por tiempo. Con el puntaje del costo, el 87 % lo
    ponía el tiempo: una tarjeta fallada 2 de 11 veces encabezaba la lista y
    otra fallada 9 de 11 quedaba duodécima. El titular del panel dice "vengo
    fallando" desde el primer día; la lista recién ahora dice lo mismo.

    Y sólo entra lo repasado en los últimos `recent_days`. Una tarjeta que no
    ves hace quince días no es algo que vengas fallando: es un mazo que
    dejaste, y llenaba media pantalla de temas que no estás estudiando.

    El aprendizaje inicial no cuenta: un "Otra vez" mientras aprendés una
    tarjeta nueva es el método funcionando. Los repasos y los reaprendizajes sí
    — ahí un fallo quiere decir que algo que sabías se te olvidó.
    """
    seen = [r for r in reviews if r.review_type != LEARNING_TYPE]
    cutoff = today - timedelta(days=recent_days)

    fresh = [c for c in card_stats(seen)
             if datetime.fromisoformat(c["last_seen"]).date() >= cutoff]
    fresh.sort(key=lambda c: -c["failing_score"])
    return fresh[:limit]


def summary(reviews: list[Review], deck_counts: list[dict], today: date) -> dict:
    """Everything the Today screen needs, in one object.

    Todo lo que sale de acá mira sólo los mazos de este app: la racha cuenta
    días en que estudiaste **inglés**, no días en que abriste Anki.
    """
    reviews = english_only(reviews)
    total_seconds = sum(r.duration_ms for r in reviews) / 1000.0
    # El ranking del costo, entero, para que el Dashboard pueda contarlo: con
    # la lista cortada en doce, "7 atascos" y "40 atascos" serían la misma cifra.
    stuck = struggling(reviews, limit=None)
    return {
        "date": today.isoformat(),
        "done": done_today(reviews, today),
        "streak": streak(reviews, today),
        "due": due_by_deck(deck_counts),
        "calendar": calendar(reviews, today),
        # Dos listas y no una: Hoy pinta lo que venís fallando de lo que estás
        # repasando, y el Dashboard cuenta cuántas tarjetas te cuestan tiempo.
        # Son dos preguntas y hasta ahora las dos se contestaban con el
        # ranking del costo.
        "failing": failing_now(reviews, today, limit=TODAY_STUCK_LIMIT),
        "failing_window": {"days": RECENT_DAYS},
        "struggling_total": len(stuck),
        "window": {
            "days": CALENDAR_DAYS,
            "reviews": len(reviews),
            "seconds": round(total_seconds, 1),
        },
    }


def parse_deck_name(name: str) -> tuple[str, str, str] | None:
    """Skill::Level::Topic -> (skill, level, topic), or None if it does not
    follow the convention.

    Matching is case-insensitive but the canonical spelling is what comes back,
    so `grammar::b1::x` lands in the same group as `Grammar::B1::y` instead of
    quietly opening a second one. The topic keeps any remaining `::`, because a
    deeper subdeck is still a topic of that level.
    """
    parts = [p.strip() for p in name.split("::")]
    if len(parts) < 2:
        return None

    skill = next((s for s in SKILLS if s.lower() == parts[0].lower()), None)
    level = next((l for l in LEVELS if l.lower() == parts[1].lower()), None)
    if skill is None or level is None:
        return None

    return skill, level, "::".join(parts[2:])


def _totals(rows: list[dict]) -> dict:
    return {
        "total": sum(r["total"] for r in rows),
        "seen": sum(r["seen"] for r in rows),
        "mature": sum(r["mature"] for r in rows),
    }


def maturity(mature: int, total: int) -> float:
    """Share of cards that have reached Anki's three-week interval.

    Zero, not None, when the level holds no cards. A level you have not started
    sits at the bottom of the rail, which is exactly where it belongs; handing
    back None would leave every caller inventing its own fallback for a case
    that has an obvious answer.
    """
    return round(mature / total, 4) if total else 0.0


def current_level(levels: list[dict]) -> str:
    """The level you are standing on: walking A1 -> C1, the first one not held.

    An empty level is not held either, so the walk stops at the first gap. That
    is the honest answer — you are not at B2 because A2 has nothing in it, you
    are at A2 and it is empty. When all five are held there is nothing above
    C1, so C1 is where you stand.
    """
    for level in levels:
        if level["maturity"] < MATURITY_THRESHOLD:
            return level["level"]
    return LEVELS[-1]


def gaps(levels: list[dict]) -> list[str]:
    """Levels with no cards at all — the holes in the collection.

    A hole and a weak level need different actions: one you generate, the other
    you study. Keeping them apart is what turns this screen into the next batch
    to generate instead of another progress bar. A level whose deck exists but
    is empty counts as a hole, because there is still nothing to review.
    """
    return [level["level"] for level in levels if level["total"] == 0]


def next_up(skills: list[dict]) -> dict | None:
    """What to do next: study something due, or fill the lowest hole.

    Not a plan and not a date. In spaced repetition the scheduler owns *when*,
    so this only ever answers *what*, and only for right now.

    Cards due at the level you are standing on win over cards due anywhere
    else, because that is the level you are trying to move. With nothing due at
    all it falls through to the lowest empty level across every skill: you
    build A1 before B2, whichever skill it belongs to.
    """
    at_level, anywhere = [], []
    for skill in skills:
        for level in skill["levels"]:
            for deck in level["decks"]:
                if deck.get("due", 0) <= 0:
                    continue
                entry = {
                    "action": "study",
                    "skill": skill["skill"],
                    "level": level["level"],
                    "deck": deck["deck"],
                    "due": deck["due"],
                }
                anywhere.append(entry)
                if level["level"] == skill["current_level"]:
                    at_level.append(entry)

    pool = at_level or anywhere
    if pool:
        return max(pool, key=lambda e: e["due"])

    # Ordered by level first, so the lowest hole wins regardless of which skill
    # it is in; the skill order only breaks ties.
    holes = [
        (LEVELS.index(level), SKILLS.index(skill["skill"]), skill["skill"], level)
        for skill in skills
        for level in skill["gaps"]
    ]
    if holes:
        _, _, skill_name, level = min(holes)
        return {
            "action": "generate",
            "skill": skill_name,
            "level": level,
            "deck": None,
            "due": 0,
        }
    return None


def severity(card: dict) -> str:
    """How badly a stuck card is stuck. A label, never a colour: red is
    reserved for failures of the system, and these cards are the work."""
    rate = card["failure_rate"]
    if rate >= SEVERITY_CRITICAL:
        return "crítica"
    if rate >= SEVERITY_HIGH:
        return "alta"
    return "media"


def impact(stuck: list[dict], total_cards: int, total_seconds: float) -> dict:
    """The comparison that makes the stuck list actionable instead of shaming:
    a small share of the collection eating a large share of the time.

    Without it the screen is a list of your mistakes and reads as a reproach.
    With it, it is a place where a few edits buy back real minutes.
    """
    seconds = sum(c["seconds_lost"] for c in stuck)
    return {
        "cards": len(stuck),
        "total_cards": total_cards,
        "card_share": round(len(stuck) / total_cards, 4) if total_cards else 0.0,
        "seconds": round(seconds, 1),
        "total_seconds": round(total_seconds, 1),
        "time_share": round(seconds / total_seconds, 4) if total_seconds else 0.0,
    }


def catalog(deck_stats: list[dict], deck_counts: list[dict] | None = None) -> dict:
    """Deck rows -> the skill -> level -> decks tree, with the rail on top.

    Decks that do not follow the convention are grouped under "sin clasificar"
    rather than dropped: a deck the app cannot read is exactly the thing worth
    seeing. The one exception is an empty deck that only exists to hold
    subdecks — `Grammar` above `Grammar::B1::...` is scaffolding, not a deck
    that failed to classify.

    `deck_counts` is optional and only carries scheduling — how many cards each
    deck has due. Without it the tree still describes the collection; with it,
    it can also say what to do next.
    """
    names = {row["deck"] for row in deck_stats}
    due = {row["deck"]: row["due"] for row in deck_counts or []}

    classified: dict[str, dict[str, list[dict]]] = {
        skill: {level: [] for level in LEVELS} for skill in SKILLS
    }
    unclassified: list[dict] = []

    for row in sorted(deck_stats, key=lambda r: r["deck"]):
        name = row["deck"]
        parsed = parse_deck_name(name)
        card_counts = {k: row[k] for k in ("total", "seen", "mature")}
        card_counts["maturity"] = maturity(row["mature"], row["total"])
        card_counts["due"] = due.get(name, 0)

        # Un padre vacío que sólo sostiene subdecks es andamiaje, no un mazo:
        # `Reading::A1` sobre `Reading::A1::Mil palabras` lo crea Anki solo al
        # crear el hijo, y contarlo lo mete en Mazos con cero tarjetas y con
        # los pendientes del hijo prestados. Vale para los que la convención
        # entiende igual que para los que no.
        is_container = any(other.startswith(f"{name}::") for other in names)
        if row["total"] == 0 and is_container:
            continue

        if parsed is None:
            unclassified.append({"deck": name, **card_counts})
            continue

        skill, level, topic = parsed
        classified[skill][level].append({
            "deck": name,
            "topic": topic or level,  # a deck named exactly Skill::Level
            **card_counts,
        })

    skills = []
    for skill in SKILLS:
        levels = []
        # Iterated over LEVELS rather than over the dict, so the rail is always
        # five segments in A1 -> C1 order. current_level walks it in that order
        # and would be wrong the moment the insertion order drifted.
        for level in LEVELS:
            decks_at = classified[skill][level]
            totals = _totals(decks_at)
            levels.append({
                "level": level,
                "decks": decks_at,
                "due": sum(d["due"] for d in decks_at),
                "maturity": maturity(totals["mature"], totals["total"]),
                **totals,
            })

        totals = _totals([d for level in levels for d in level["decks"]])
        skills.append({
            "skill": skill,
            "levels": levels,
            "due": sum(level["due"] for level in levels),
            "maturity": maturity(totals["mature"], totals["total"]),
            "current_level": current_level(levels),
            "gaps": gaps(levels),
            **totals,
        })

    unclassified_totals = _totals(unclassified)
    return {
        "skills": skills,
        "unclassified": {
            "label": UNCLASSIFIED,
            "decks": unclassified,
            "due": sum(d["due"] for d in unclassified),
            "maturity": maturity(
                unclassified_totals["mature"], unclassified_totals["total"]
            ),
            **unclassified_totals,
        },
        "next_up": next_up(skills),
        "maturity_threshold": MATURITY_THRESHOLD,
        **_totals(deck_stats),
    }
