from dataclasses import dataclass

from fastapi import Request

from fluent.collection.application.build_catalog import BuildCatalog
from fluent.collection.application.build_stuck import BuildStuck
from fluent.collection.application.build_today import BuildToday
from fluent.collection.application.open_add_cards import OpenAddCards
from fluent.collection.application.open_review import OpenReview


@dataclass(frozen=True)
class CollectionUseCases:
    today: BuildToday
    catalog: BuildCatalog
    stuck: BuildStuck
    open_review: OpenReview
    open_add_cards: OpenAddCards
    daily_goal: object  # callable () -> int, cableado por main


def get_collection(request: Request) -> CollectionUseCases:
    return request.app.state.collection
