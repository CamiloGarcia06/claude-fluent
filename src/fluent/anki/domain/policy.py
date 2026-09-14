"""La regla de la conexión con Anki: editar no tiene deshacer, así que ninguna
escritura ocurre sin haber dejado antes su registro en disco. Puro."""

from fluent.shared.errors import Conflict

# Every AnkiConnect action that mutates the collection. Editing notes has no
# undo, so `call` refuses these outright unless a snapshot has been written
# first. The guarantee lives here rather than in the callers: relying on each
# call site to remember is exactly how a write slips through.
WRITE_ACTIONS = frozenset(
    {
        # Notes and cards
        "addNote",
        "addNotes",
        "updateNote",
        "updateNoteFields",
        "updateNoteModel",
        "updateNoteTags",
        "addTags",
        "removeTags",
        "replaceTags",
        "replaceTagsInAllNotes",
        "clearUnusedTags",
        "deleteNotes",
        "removeNotes",
        "removeEmptyNotes",
        "createDeck",
        "deleteDecks",
        "changeDeck",
        "moveCardsToDeck",
        "setDueDate",
        "forgetCards",
        "relearnCards",
        "suspend",
        "unsuspend",
        "setSpecificValueOfCard",
        "setEaseFactors",
        "answerCards",
        "insertReviews",
        "storeMediaFile",
        "deleteMediaFile",
        "importPackage",
        # Note types. A card template is shared by every note that uses it, so a
        # bad edit here is not one broken card but every card of that type at once
        # — and AnkiConnect has no deleteModel, so a note type created by mistake
        # can only be removed from Anki's own GUI. These were missing while nothing
        # wrote note types; card generation is what writes them, so the list grew
        # before that landed rather than after.
        "createModel",
        "updateModelTemplates",
        "updateModelStyling",
        "modelFieldAdd",
        "modelFieldRemove",
        "modelFieldRename",
        "modelFieldReposition",
        "modelFieldSetDescription",
        "modelFieldSetFont",
        "modelFieldSetFontSize",
        "modelTemplateAdd",
        "modelTemplateRemove",
        "modelTemplateRename",
        "modelTemplateReposition",
        "findAndReplaceInModels",
        # Deck options. Changing a preset re-schedules every deck that uses it.
        "saveDeckConfig",
        "setDeckConfigId",
        "cloneDeckConfigId",
        "removeDeckConfigId",
    }
)


class WriteWithoutSnapshot(Conflict):
    """Raised when a write is attempted outside snapshot.guarded()."""

    code = "write_without_snapshot"
