"""Pure functions over a list of reviews. No I/O, no AnkiConnect, no clock:
every function takes the data and the reference date it should work against,
so the whole module is testable by handing it rows."""
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta

from anki import Review, interval_to_seconds

CALENDAR_DAYS = 30

# A card has to have been seen a few times AND actually failed before it counts
# as stuck. Ranking on time alone surfaces cards you simply read slowly, which
# is how "0 fallos de 3" ended up at the top of the list.
MIN_ATTEMPTS = 3
MIN_FAILURES = 1

# Weights for the struggling ranking. Failures dominate, time spent breaks
# ties, and a dropped interval is the scheduler's own vote that the card was
# forgotten.
W_FAILURE_RATE = 60.0
W_SECONDS_LOST = 1.0
W_INTERVAL_DROP = 8.0


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


def due_by_deck(deck_counts: list[dict]) -> dict:
    """Shape the per-deck due counts and total them. Due state is scheduling,
    not history, so it comes from Anki rather than from the revlog."""
    decks = sorted(deck_counts, key=lambda d: (-d["due"], d["deck"]))
    return {
        "total": sum(d["due"] for d in decks),
        "decks": decks,
    }


def struggling(reviews: list[Review], limit: int = 12) -> list[dict]:
    """Cards ranked by how much trouble they cause.

    Three signals combine, because none of them is enough alone: a card can be
    failed often, be slow every time without being failed, or keep having its
    interval pulled back by the scheduler.

    A card must clear both gates first: seen at least MIN_ATTEMPTS times, and
    failed at least MIN_FAILURES of them. Without the failure gate the ranking
    is really a slowest-cards list, and a card you have never once got wrong is
    not a card you are stuck on.
    """
    by_card: dict[int, list[Review]] = defaultdict(list)
    for r in reviews:
        by_card[r.card_id].append(r)

    ranked = []
    for card_id, rows in by_card.items():
        attempts = len(rows)
        failures = sum(1 for r in rows if r.failed)
        if attempts < MIN_ATTEMPTS or failures < MIN_FAILURES:
            continue

        drops = sum(1 for r in rows if r.interval_dropped)
        durations = [r.duration_ms for r in rows]
        seconds_lost = sum(durations) / 1000.0

        failure_rate = failures / attempts
        score = (
            W_FAILURE_RATE * failure_rate
            + W_SECONDS_LOST * seconds_lost
            + W_INTERVAL_DROP * drops
        )

        ranked.append({
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
            "score": round(score, 1),
        })

    ranked.sort(key=lambda c: -c["score"])
    return ranked[:limit]


def summary(reviews: list[Review], deck_counts: list[dict], today: date) -> dict:
    """Everything the Today screen needs, in one object."""
    total_seconds = sum(r.duration_ms for r in reviews) / 1000.0
    return {
        "date": today.isoformat(),
        "streak": streak(reviews, today),
        "due": due_by_deck(deck_counts),
        "calendar": calendar(reviews, today),
        "struggling": struggling(reviews),
        "window": {
            "days": CALENDAR_DAYS,
            "reviews": len(reviews),
            "seconds": round(total_seconds, 1),
        },
    }
