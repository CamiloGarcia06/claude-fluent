# claude-fluent

Entrenador de inglés hablado con seguimiento medible del progreso.

Grabas un monólogo de 3 minutos en el navegador, la app lo transcribe en local
con Whisper, lo corrige con `claude -p` y guarda métricas objetivas de tu
producción oral. Todo local, sin API keys, sin coste por token.

## Por qué

Hablar solo sin corrección fosiliza errores: repites la misma estructura mal
500 veces y se te queda. Este proyecto cierra el bucle de feedback:

```
hablas → se transcribe → se corrige → se mide → se convierte en práctica → hablas
```

La diferencia con una app de idiomas al uso es que aquí **el progreso se mide**,
y se distingue lo que controlas de lo que no:

- **Esfuerzo** — minutos, sesiones, racha, palabras habladas. Sube si te presentas.
- **Progreso** — palabras por minuto, riqueza léxica, complejidad sintáctica,
  errores por 100 palabras. Se mueve a saltos, con mesetas de semanas.

Verlos juntos es lo que evita abandonar en la meseta.

## Métricas

| Métrica | Qué mide |
|---|---|
| Palabras por minuto | fluidez |
| Errores por 100 palabras | precisión |
| Type-token ratio | riqueza léxica |
| Ratio de subordinadas | complejidad sintáctica (marca de B2→C1) |
| Pausas > 2s | búsqueda de palabra |

Fluidez, precisión y complejidad **compiten entre sí**: enfocarte solo en no
cometer errores te hace hablar lento. Por eso se miden las tres a la vez.

## Créditos

La arquitectura de seguimiento de este proyecto está directamente inspirada en
**[m98/fluent](https://github.com/m98/fluent)** (MIT), el kit de aprendizaje de
idiomas para Claude Code. De ahí vienen las ideas que aquí se reimplementan:

- El bucle **practicar → analizar → feedback → registrar → adaptar**
- El **registro de patrones de error** con frecuencia y ejemplos, en vez de
  guardar solo aciertos y fallos
- Programación de repasos con **SM-2**
- Niveles de dominio 0-5 y dificultad adaptativa apuntando a un 60-70% de acierto

`claude-fluent` no contiene código de Fluent: es una implementación propia,
orientada a producción **oral medida** en vez de práctica tecleada, y con la
persistencia en SQLite en lugar de JSON. Si lo que buscas es un tutor de idiomas
completo dentro de la terminal, usa Fluent directamente — es mejor en eso.

Otras referencias:

- **[raine/anki-llm](https://github.com/raine/anki-llm)** (MIT) — para exportar
  los errores registrados a mazos de Anki (previsto, aún no implementado).
- **[SM-2](https://www.supermemo.com/en/archives1990-2015/english/ol/sm2)** — el
  algoritmo de repetición espaciada.

## Requisitos

- Python 3.14 (nativo en CachyOS)
- GPU NVIDIA con driver reciente (opcional — funciona en CPU, solo más lento)
- Claude Code instalado y autenticado (`claude -p` es el motor de corrección)

## Instalación

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Uso

```bash
./scripts/run.sh
```

Abre http://localhost:8000 y pulsa grabar. El navegador pide permiso de
micrófono: `localhost` cuenta como contexto seguro, así que no hace falta HTTPS.

## El plan de estudio

La app trae un plan de 12 semanas que se deriva de la fecha de inicio (se fija
sola el primer día que la abres). No se pregeneran los 84 días: solo se guarda
lo que completas, así que cambiar el plan no invalida el historial.

| Semanas | Bloque | Qué se interioriza |
|---|---|---|
| 1-2 | Esqueleto narrativo | past simple vs. continuous, past perfect, conectores |
| 3-4 | Textura | relativas, participle clauses, reported speech |
| 5-6 | Matiz | modales de deducción, condicionales 2 y 3, wish |
| 7 | Consolidación | nada nuevo: repaso y test de nivel |
| 8-9 | Storytelling puro | la estructura de 5 frases |
| 10-11 | Artículos y preposiciones | solo por corrección de errores propios |
| 12 | Medición final | grabación de control contra el baseline |

Cada bloque de dos semanas recorre el mismo arco: **input** (días 1-2) →
**producción guiada** (3-7) → **producción libre** (8-11) → **medición** (día 12).
Lunes a viernes son ~30 min, martes y jueves +10 por el monólogo grabado. El
sábado es descanso y el domingo se revisan las métricas.

La semana 7 no enseña nada nuevo a propósito: los planes sin consolidación
acumulan material sin asentarlo.

Grabar marca su propia tarea al terminar — marcarla a mano sería trabajo doble.

## Lecciones

40 unidades de gramática de A1 a B2, agrupadas en 9 áreas: presente, pasado,
present perfect, futuro, preguntas y auxiliares, unir ideas, matiz,
estructuras frecuentes y detalle fino.

**No hay RAG, y es deliberado.** La gramática inglesa está entera en el modelo:
recuperar fragmentos de un libro no aportaría información que Claude no tenga.
Lo que sí hace falta —y es lo que aporta el currículo— es una secuencia, un
criterio de prioridad y un puente con tus errores reales.

La cola de estudio se ordena por tres señales, en este orden:

1. **Vencidas por SM-2** — lo que ya estudiaste y toca repasar.
2. **Tus errores reales** — si `missing_article` sale seis veces en tus
   grabaciones, la unidad de artículos sube al principio aunque en el orden
   teórico fuera la número treinta.
3. **Frecuencia de uso** — a igualdad de todo, primero lo que más se usa al hablar.

Cada unidad declara qué `pattern_id` ataca, y el emparejamiento es difuso: los
identificadores los inventa el modelo al corregir, así que `article_omission` y
`missing_article` se reconocen como el mismo fallo comparando tokens.

Cada unidad es un capítulo completo, con seis secciones en pestañas:

| Sección | Qué es |
|---|---|
| **Introducción** | Un diálogo natural donde la estructura aparece varias veces, y tres observaciones del tipo "fíjate en que…". Se ve en uso antes de explicar nada. |
| **Gramática** | La referencia a la que volver: tabla de formación (afirmativa, negativa, pregunta), reglas con ejemplos, errores típicos del hispanohablante y las palabras que anuncian la estructura. |
| **Práctica** | Ejercicios de hueco, transformación, corrección y traducción, corregidos uno a uno con explicación del porqué. |
| **Writing** | Una tarea real (un mensaje, un correo, una entrada de diario) con elementos obligatorios. Se corrige señalando cada error, y devuelve el texto como lo diría un nativo. |
| **Speaking** | Un tema para hablar, con frases útiles y consejos. Reutiliza el grabador: hablas, se transcribe y se corrige. |
| **Examen** | Test final más exigente que la práctica. Con un 80% la unidad queda dominada. |

Todo se genera al vuelo con `claude -p` y **se cachea en la base de datos**: sin
caché, pasearte por las pestañas costaría seis llamadas al modelo en vez de una
por sección. El botón *"Otros ejercicios"* fuerza material nuevo cuando quieras
repetir la práctica.

Si tienes errores registrados de esa estructura, la explicación y al menos dos
ejercicios se construyen sobre tus propias frases. Y los fallos que cometes por
escrito entran en la misma tabla que los hablados: un error de artículos es el
mismo error lo digas o lo escribas, así que también reordena la cola.

Al corregir, cada unidad se reprograma con SM-2: fallar la mitad la devuelve
mañana, dominarla la aleja semanas.

## Herramientas

```bash
./scripts/run.sh              # arranca el servidor en localhost:8000
./scripts/check.sh            # diagnóstico: venv, GPU, claude, micrófono, datos
./scripts/probar.sh 30        # graba 30s desde la terminal y los procesa
./scripts/probar.sh --file a.wav   # procesa un audio que ya tengas
```

Para que arranque solo al iniciar sesión, hay una unidad de systemd de usuario
en `scripts/claude-fluent.service` con las instrucciones dentro.

## Arquitectura

```
[navegador] MediaRecorder graba webm/opus
     ↓ POST /api/recordings
[FastAPI] responde 202 y lanza el trabajo en segundo plano
     ↓ el navegador escucha GET /api/recordings/{id}/events (SSE)
     ├─ transcribing   faster-whisper, en local
     ├─ correcting     claude -p --json-schema
     ├─ metrics        wpm, TTR, subordinadas, pausas
     └─ done
     ↓
[SQLite] data/app.db → el dashboard se repinta solo
```

Sin React ni bundler: HTML y JavaScript nativos. La API REST está separada del
front, así que cambiar de interfaz no obliga a tocar el backend.

## Licencia

MIT
