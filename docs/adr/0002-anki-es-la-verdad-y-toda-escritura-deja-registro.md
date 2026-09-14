# 0002 — Anki es la verdad y toda escritura deja registro

**Contexto.** Editar notas en Anki no tiene deshacer. Ocho notas se perdieron
una vez por un `--undo` accidental y se recuperaron solo porque había copias
en disco. Además, el modelo propone tarjetas y reparaciones cuya salida no es
de fiar.

**Decisión.** Tres reglas, ahora en el código:

1. **Anki es la fuente de verdad.** El app no guarda nada que Anki sepa; lo
   único propio es la meta diaria (`settings`) y lo que Anki no puede saber
   (temarios, sesiones de práctica, patrones).
2. **Sin registro no hay escritura.** `anki.domain.policy.WRITE_ACTIONS` lista
   las 49 acciones que mutan la colección; `client.call()` las rechaza con
   `WriteWithoutSnapshot` salvo dentro de `write_unlocked(evidencia)`, que solo
   abre `anki/infrastructure/snapshots.py` después de escribir la evidencia en
   `data/snapshots/`: snapshot para sobrescribir o borrar, registro de creación
   para crear, registro de modelo para un tipo de nota.
3. **Proponer, aprobar, escribir.** El modelo propone (`cards.Proposer`), la
   persona aprueba en pantalla, y solo `WriteNotes`/`ApplyRepair` escriben, y
   solo lo aprobado. Todo lo que llega del modelo o de la pantalla se valida en
   el dominio (`cards.domain.decks`, `cards.domain.text`).

**Porqué.** La regla 2 es estructural y no una convención: olvidarla lanza en
vez de escribir en silencio. La 3 separa en tres peticiones lo que un solo
endpoint mezclaría, y hace que una escritura sea siempre una decisión humana.

**Descartado.** Confiar en el deshacer de Anki (no existe por AnkiConnect);
escribir directamente lo que propone el modelo.

**Consecuencias.** `data/snapshots/` crece con cada escritura y es lo que
permite restaurar (`snapshots.restore`, `undo_creation`, `undo_move`). Los
adaptadores de `cards` reciben el cliente y los snapshots inyectados, así que
un test puede sustituirlos por fakes sin tocar la regla.
