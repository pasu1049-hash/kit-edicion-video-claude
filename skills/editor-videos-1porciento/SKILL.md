---
name: editor-videos-1porciento
description: Edita videos de cámara (talking-head) para Instagram, TikTok y YouTube Shorts con la plantilla "1%": subtítulos de marca con palabras clave en color, cortes de silencios, zoom dinámico, motion graphics disparados por palabra, música propia con ducking, entrada y cierre de marca y portada. Formatos historia/reel 9:16 (1080x1920) y feed 4:5 (1080x1350). Usar cuando pidan "editame este video", "hacé la historia", "subtitulá este clip", "sacale las pausas", "pasalo a feed y a historia" o similar.
---

# Editor de videos — plantilla 1%

Pipeline en Python (sin programas de edición): el video crudo + un `config.json` → video final en máxima calidad + `_PORTADA.png`.
Los scripts están en `scripts/` de este skill. Las salidas y la carpeta `work/` se crean **en la carpeta desde donde se corre el comando** (usá una carpeta por proyecto).

## 0. Antes de empezar (una sola vez)
- Leé `MARCA.md` de este skill: color de acento, nombre de marca, handle, frases. Si está sin completar, preguntale al usuario esos datos y completalo.
- Dependencias: `pip install -r scripts/requirements.txt` (numpy, pillow, imageio-ffmpeg, faster-whisper). La primera transcripción descarga el modelo Whisper "medium" (~1,5 GB).

Atajo: en los comandos de abajo, `S` = ruta a `scripts/` de este skill (ej. `~/.claude/skills/editor-videos-1porciento/scripts`).

## 1. Flujo por video
1. **Config**: copiá `ejemplos/historia_ejemplo.json` (9:16) o `ejemplos/feed_ejemplo.json` (4:5) a la carpeta del proyecto y completá `video`, `words`, `salida`, `marca`, `acento`, `cierre`, `portada`.
   - `recorte`: área del video original a usar (x, y, w, h en píxeles del original). Debe tener la proporción del formato (9:16 historia, 4:5 feed). Medí el tamaño del original con ffprobe antes.
2. **Transcribir**: `python S/editar_video.py transcribir config.json` → genera el `words.json` con tiempo por palabra.
3. **Corregir el words.json a mano**: nombres propios, marcas, números ("1%"), modismos. Guardarlo como `*_words_ok.json` y apuntar el config ahí. Ponele en el config `"vocabulario"` con nombres que se repiten para que Whisper acierte.
4. **Silencios**: `python S/auto_cortes.py video.mov 0.12` → imprime la lista de `cortes` (medida por energía de audio, NO con los tiempos de Whisper). Pegala en `"cortes"`. Si un corte cae entre dos partes de la misma palabra, sacalo.
5. **Palabras clave** (`claves`): las palabras que se pintan con el color de acento en los subtítulos. Escribilas exactamente como están en el words.json (con la puntuación pegada, ej. `"tiempo."`).
6. **Motion graphics** (`motion`): usalos SIEMPRE por defecto, 3 a 6 por video, en los momentos fuertes del guion. Ver tabla abajo.
7. **Zoom** (`zoom`) y **música** (`musica`): activados por defecto.
8. **Revisar cuadros sueltos** antes del render largo: `python S/editar_video.py preview config.json 4.5` → `work/_prev_4.5.jpg` (segundo del video final). Mirá subtítulos, motion graphics y encuadre de la cara.
9. **Render**: `python S/editar_video.py render config.json` → `salida.mp4` + `salida_PORTADA.png`.
10. Mirá cuadros del resultado (ffmpeg select de 3-4 frames en una tira) antes de entregar. Al terminar, abrí la carpeta con los videos para el usuario.

Si el usuario pide historia y feed, hacé dos configs (mismo words.json, distinto `formato`/`recorte`/`subs_y`/posiciones). Se pueden renderizar 2 en paralelo con 8 GB de RAM.

## 2. Reglas que aprendimos (no saltear)
- **Transcribir sin VAD** (ya está así en el script): con VAD se pierde la primera frase.
- **Videos de iPhone HDR (HLG, 4K60)**: NO aplicar tonemap con zscale (mete artefactos). El crudo con el eq suave del script se ve bien.
- **Calidad máxima siempre**: H.264 crf 14 preset slow, audio AAC 320k, voz normalizada a -14 LUFS. No bajar calidad para que pese menos salvo que lo pidan.
- Posición de subtítulos: `subs_y` ~1300 en historia (zona segura de IG), ~1060 en feed. Los motion graphics van arriba, lejos de la cara y de los subtítulos.
- Textos en pantalla: cortos, en MAYÚSCULAS, directos. Nada de frases largas.

## 3. Referencia del config
| clave | qué hace |
|---|---|
| `formato` | `"historia"` (1080x1920) o sin poner = feed (1080x1350) |
| `video`, `words`, `salida` | rutas del crudo, del words.json y del mp4 final |
| `recorte` | `{x,y,w,h}` del original |
| `pre` / `post` | segundos de aire antes de la primera palabra / después de la última |
| `subs_y` | altura de los subtítulos |
| `claves` | palabras en color de acento |
| `cortes` | `[[ini, fin], ...]` en segundos del original, se eliminan |
| `acento` | color de marca `[R,G,B]` (default coral `[255,104,74]`) |
| `marca` | nombre de la marca (placa de entrada/cierre y portada) |
| `logo` | ruta a un PNG cuadrado del logo (portada, opcional) |
| `logo_led` | foto de un cartel de neón con el logo → entrada/cierre "LED". Sin esto se usa la placa de color |
| `placa` | entrada/cierre personalizados: `{"marca","color","kicker","filas":[...],"pie","size","entrada","cierre"}` |
| `sin_intro` | `true` = arranca directo con el video |
| `cierre` | `{"titulo":[...],"by","fecha","plataformas","handle"}` (cierre LED) — con placa se usan `by`, `fecha`, `handle` |
| `cierre_seg` | duración del cierre |
| `portada` | `{"segundo","kicker","titulo":[líneas],"size","fecha","pie"}` |
| `zoom` | `{"push":0.05,"cortes":0.08,"cara":[x,y],"punch":[{"palabra","hasta"|"dur","z":1.15}]}` — `cara` = centro de la cara en el cuadro final |
| `musica` | `{"bpm":92,"seed":3,"vol":0.2,"ducking":0.75}` — beat generado (sin derechos de autor), baja sola cuando hay voz. Cambiá `seed` para otra variación |
| `vocabulario` | texto con nombres propios para ayudar a Whisper |

### Motion graphics (`motion`: lista de eventos)
Cada evento: `{"tipo", "palabra", "hasta" o "dur", "extra", "txt", "pos":[x,y], "size", "rot", "anim", "escala", "offset"}`. `pos` = centro del elemento en el cuadro final.
Aparece cuando se dice `palabra` (si se repite, `"n": 2` = segunda vez) y se va con `hasta` (+`extra` s) o después de `dur` s. `anim`: `"pop"` (default), `"slide"` (con `"desde"` px), `"slam"`.

| tipo | qué es | campos propios |
|---|---|---|
| `texto` | texto grande con contorno | `txt`, `size`, `coral:true` = color acento |
| `chip` | etiqueta redondeada | `txt`, `size`, `claro` |
| `sello` | sello inclinado tipo estampa | `txt`, `size`, `rot` |
| `slam` | número/palabra gigante que golpea | `txt`, `size` |
| `calendario` | hoja de calendario | `txt` (día), `big` (número), `sub` |
| `envivo` | badge "EN VIVO" | `txt` |
| `plataforma` | badge de red social con su color (TIKTOK, YOUTUBE, KICK; otro texto = badge oscuro) | `txt` |
| `contador` | número que cuenta | ver `motion.py` |
| `misterio` | cartel de invitado con signo de pregunta | `lineas` |

Cada motion graphic trae su efecto de sonido automáticamente.

## 4. Showreel (clips sin voz al ritmo de la música)
`python S/showreel.py config.json` — config con `clips` (cada uno dura `beats` tiempos y puede tener `label`), `bpm`, `formato`, `etiqueta_y`, `textos`, `placa`, `seed`, `vol`. Antes de armar uno, leé `main()` en `showreel.py` para ver los campos exactos de cada clip.

## 5. Cuándo usar otra herramienta
- Animaciones/motion design más complejos (títulos animados, explicativos, intros 3D, gráficos): skill `hyperframes` (router oficial de HyperFrames).
- Edición larga para YouTube, cortar errores/repeticiones, storytelling: skills del kit de Nate Herk (`edit-video`, `cut-mistakes`, `short-form-edit`, `video-storytelling`), corriendo desde la carpeta del kit.
