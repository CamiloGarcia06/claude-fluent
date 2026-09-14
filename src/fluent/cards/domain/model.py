"""El tipo de nota que escribe este app. Un hecho del dominio: qué campos
tiene una tarjeta y cómo se ve."""

# The note type this app writes. Stock Basic has no room for an example
# sentence, and the example is what makes a vocabulary card usable instead of
# a word pair you can recite without understanding.
MODEL_NAME = "claude-fluent"
MODEL_FIELDS = ["Front", "Back", "Ejemplo"]

# One card per note, English -> Spanish. The reverse direction is a different
# skill and deserves its own deck rather than a second template that doubles
# every count silently.
MODEL_TEMPLATES = [
    {
        "Name": "Reconocer",
        "Front": "{{Front}}",
        "Back": "{{FrontSide}}\n<hr id=answer>\n{{Back}}\n"
        '{{#Ejemplo}}<div class="ejemplo">{{Ejemplo}}</div>{{/Ejemplo}}',
    }
]

# La ficha de cartón, en Anki: papel frío, tinta grafito, sin sombras. La regla
# impresa separa la pregunta de la respuesta y el ejemplo va en gris, un paso
# por detrás de la traducción.
MODEL_CSS = """.card {
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size: 22px;
  line-height: 1.5;
  color: #1b1d20;
  background: #fbfbfa;
  text-align: center;
  padding: 24px 16px;
}
hr#answer {
  border: 0;
  border-top: 1px solid rgba(27, 29, 32, 0.13);
  margin: 20px auto;
  max-width: 32ch;
}
.ejemplo {
  margin-top: 16px;
  font-size: 17px;
  font-style: italic;
  color: #7c8188;
}
.card.nightMode, .nightMode .card {
  color: #e9eaec;
  background: #17181b;
}
.nightMode hr#answer { border-top-color: rgba(255, 255, 255, 0.13); }
.nightMode .ejemplo { color: #858b93; }
"""
