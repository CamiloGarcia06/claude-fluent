"""Spike 1: can we read the review log out of Anki through AnkiConnect?"""
import httpx


def call(action, **params):
    response = httpx.post(
        "http://127.0.0.1:8765",
        json={"action": action, "version": 6, "params": params},
    )
    data = response.json()
    if data["error"]:
        raise RuntimeError(f"{action}: {data['error']}")
    return data["result"]


decks = call("deckNames")
print("decks:", decks)

deck = decks[0]
since = call("getLatestReviewID", deck=deck) - 30 * 86400 * 1000
reviews = call("cardReviews", deck=deck, startID=since)
print(len(reviews), "reviews in", deck)
print(reviews[:3])
