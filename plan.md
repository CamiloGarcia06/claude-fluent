# Plan del repo — versión simple

FastAPI + HTML/CSS/JS a mano + anime.js. Sin build, sin npm, sin bundler.
Anki es el motor; la app sincroniza, analiza y genera tarjetas con `claude -p`.

**Todo el código en inglés**: nombres de archivo, identificadores y comentarios.
La documentación y los commits, en español.

---

## Estructura

```
claude-fluent/
├── README.md
├── .gitignore
├── requirements.txt
├── app.py              ← FastAPI: rutas + sirve el front
├── anki.py             ← cliente AnkiConnect
├── llm.py              ← wrapper de `claude -p`
├── analysis.py         ← revlog → streak, due, struggling
├── snapshot.py         ← respaldo antes de escribir en Anki
├── spike_anki.py       ← prueba 1
├── spike_claude.py     ← prueba 2
├── static/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── anki_template/      ← HTML + CSS de la carta, para subir a Anki
├── docs/
│   ├── wireframes.excalidraw
│   └── decisions.md
└── data/               ← gitignored
    ├── state.json
    └── snapshots/
```

`.gitignore`:

```
__pycache__/
.venv/
data/
*.log
```

Arranque:

```bash
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn httpx
uvicorn app:app --reload      # http://localhost:8000
```

Sin paso de compilación: guardás un archivo, recargás el navegador.

---

## Fase 0 — Las dos pruebas

No escribas la app hasta que estas dos corran. Si alguna falla, la arquitectura cambia.

**`spike_anki.py`**

```python
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
```

Cada fila es `[timestamp, cardId, usn, button, newInterval, prevInterval, factor, durationMs, type]`.
Las columnas que te importan son `button` y `durationMs`.

**`spike_claude.py`**

```python
import json
import subprocess

SCHEMA = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "front": {"type": "string"},
                    "back": {"type": "string"},
                    "example": {"type": "string"},
                },
                "required": ["front", "back", "example"],
            },
        }
    },
    "required": ["cards"],
}

# No --bare: that mode ignores the subscription login and demands ANTHROPIC_API_KEY
proc = subprocess.run(
    [
        "claude", "-p",
        "Generate 3 English flashcards for 'to put up with'. Backs in Spanish.",
        "--output-format", "json",
        "--json-schema", json.dumps(SCHEMA),
    ],
    capture_output=True,
    text=True,
    timeout=180,
)

result = json.loads(proc.stdout)
if result.get("is_error"):  # failures arrive on stdout, not through the exit code
    raise RuntimeError(result["result"])

print(json.dumps(result["structured_output"]["cards"], indent=2, ensure_ascii=False))
print("duration:", result["duration_ms"], "ms")
```

Anotá esa duración. Define si la generación puede ser interactiva o va en lote.

---

## Fase 1 — Backend y pantalla Hoy

Un endpoint de salud y uno de datos. Nada más.

```python
# app.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import analysis
import anki

app = FastAPI()


@app.get("/api/health")
def health():
    return {"anki": anki.is_alive(), "last_sync": analysis.last_sync()}


@app.get("/api/today")
def today():
    return analysis.summary()  # streak, due counts, calendar, struggling cards


app.mount("/", StaticFiles(directory="static", html=True))  # must go last
```

El `mount` va al final: si lo ponés antes, se traga las rutas `/api`.

`/api/health` es el primer endpoint porque las fallas de este sistema son silenciosas
—Anki cerrado, `claude` sin sesión— y la app se ve normal mientras te miente.

El front es una función que pide `/api/today` y arma el HTML con plantillas de texto.
Sin framework: son cuatro bloques y no cambian de forma.

---

## anime.js: qué animar y qué no

Por CDN, sin instalar nada. La versión 4 cambió la API a exports con nombre:

```html
<script type="module">
  import { animate, stagger } from "https://cdn.jsdelivr.net/npm/animejs@4/+esm";

  // calendar squares cascading in
  animate(".day", {
    opacity: [0, 1],
    scale: [0.85, 1],
    delay: stagger(12),
    duration: 300,
    ease: "outQuad",
  });

  // streak counting up to its value
  const counter = { value: 0 };
  animate(counter, {
    value: streak,
    duration: 700,
    ease: "outExpo",
    onUpdate: () => {
      streakEl.textContent = `${Math.round(counter.value)} días`;
    },
  });
</script>
```

Pineá la versión mayor; si un día se rompe sin que hayas tocado nada, es eso.

**Dónde sí:** la carga de Hoy —calendario en cascada, racha contando, barras creciendo—.
Es una pantalla que abrís una vez al día y la animación la hace sentir viva.

**Dónde no:** en el flujo de repaso. Si cada tarjeta tarda 300 ms en aparecer, una sesión
de 48 se te va en 15 segundos de espera pura y empieza a molestar al tercer día. Ahí, nada
por encima de 120 ms, y que el teclado nunca espere a que la animación termine.

Regla corta: **animá lo que mirás, no lo que atravesás.**

---

## Fases siguientes

**2 · Usala dos semanas.** Sin agregar nada. Si no la abrís a diario, el problema no se
resuelve con más features, y te ahorrás las fases 3 y 4.

**3 · Generación.** Escribís un término, ves las candidatas, tildás las que entran,
`addNotes` a Anki. Tope de tarjetas por corrida y una sola llamada a la vez.

**4 · Reparación y template.** Tarjeta atascada → propuesta → antes/después → aceptás.
`snapshot.py` guarda el estado previo antes de cada escritura: modificar Anki no tiene
deshacer. Y el diseño de la carta, en `anki_template/`, subido como note type.

---

## La skill de diseño

```bash
npx skills add https://github.com/dammyjay93/interface-design --skill interface-design
```

Instalala ahora, usala en la fase 2 —cuando Hoy ya muestre datos reales de Anki—.
Pulir el aspecto de datos inventados es trabajo que se tira.

No te va a servir para la carta: esa es un template de Anki y el HTML y CSS
disponibles están limitados por cómo renderiza Anki.

---

## Las cuatro cosas que van en el README

1. **Anki abierto o no hay datos.** AnkiConnect vive dentro de Anki.
2. **Nunca `--bare`.** Ignora el login de la suscripción. Está anunciado como futuro
   default de `-p`: si todo deja de andar después de actualizar Claude Code, es esto.
3. **En macOS, desactivar App Nap**, o AnkiConnect deja de responder cuando Anki no
   está al frente.
4. **No editar notas con el navegador de Anki abierto** en esas mismas notas.

---

## Primer commit

```bash
git init
git add .
git commit -m "wireframes, decisiones y las dos pruebas de conexión"
```

Con `docs/` adentro desde el principio. En este diseño ya se descartaron dos rumbos
enteros —el planificador tipo Gantt y el motor de repaso propio— y en tres meses vas a
tener las mismas ideas de nuevo sin recordar por qué las dejaste. Cinco líneas por
decisión alcanzan.
