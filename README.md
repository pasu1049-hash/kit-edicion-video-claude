# Kit de edición de video con Claude

Los skills que usa **Matías "Pasu" Pasutti / 1% Fitness** para editar sus historias, reels y videos con Claude.

## Qué trae

| | Qué hace | De dónde sale |
|---|---|---|
| **editor-videos-1porciento** | La plantilla con la que se editan las historias y el feed: subtítulos grandes con palabras clave en color, corte automático de pausas, zoom dinámico, motion graphics que aparecen cuando decís una palabra (sellos, chips, números que golpean, calendario, badges de redes), música propia sin derechos de autor que baja sola cuando hablás, entrada y cierre de marca y portada. Historia 9:16 y feed 4:5, máxima calidad. | Este repo |
| **Agente `editor`** | Un "editor" que decide qué herramienta usar y aplica el estilo. | Este repo |
| **HyperFrames** (8 skills: `hyperframes`, `-core`, `-animation`, `-creative`, `-keyframes`, `-cli`, `-registry`, `media-use`) | Motion graphics, títulos animados, explicativos, intros, overlays hechos con HTML. | Oficial de HeyGen ([heygen-com/hyperframes](https://github.com/heygen-com/hyperframes)) |
| **Kit de video de Nate Herk** (`edit-video`, `cut-silences`, `cut-mistakes`, `short-form-edit`, `video-storytelling`, `motion-showreel`, `style-library`…) | Edición de videos largos, cortar errores y repeticiones, armar el storytelling, showreels. | [nateherkai/hyperframes-student-kit](https://github.com/nateherkai/hyperframes-student-kit) |

## Cómo instalarlo

### Opción fácil: que Claude lo instale
En Claude Code (app de escritorio, pestaña **Code**, o terminal), pegá:

> Instalá el kit de edición de video de este repo: **https://github.com/pasu1049-hash/kit-edicion-video-claude**. Cloná el repo y corré el instalador.

### Opción manual
1. Tener instalado: **Git, Node.js 22+, Python 3.10+ y FFmpeg**.
   En Windows (PowerShell): `winget install Git.Git OpenJS.NodeJS.LTS Python.Python.3.12 Gyan.FFmpeg`
   En Mac: `brew install git node python ffmpeg`
2. Descargar este repo (botón verde **Code → Download ZIP**, o `git clone`).
3. Dentro de la carpeta:
   - Windows: `powershell -ExecutionPolicy Bypass -File .\instalar.ps1`
   - Mac: `bash instalar.sh`
4. Cerrar y volver a abrir Claude.

El instalador copia los skills a `~/.claude/skills`, el agente a `~/.claude/agents`, instala las librerías de Python y clona el kit de Nate Herk en `Documentos/hyperframes-student-kit`.

## Primer uso
1. Decile a Claude: **"Completá mi MARCA.md del skill editor-videos-1porciento"** (nombre de marca, color, @usuario, tono).
2. Después: **"Editame este video: C:/ruta/video.mov. Hacelo historia y feed."**
   Claude transcribe, te muestra las palabras para corregir, corta las pausas, arma los motion graphics y renderiza.

Notas:
- La primera transcripción descarga el modelo Whisper (~1,5 GB). Todo corre en tu compu, sin costos de API.
- Para la entrada/cierre "cartel de neón" hace falta una foto de tu logo en neón (`logo_led` en el config). Sin eso se usa una placa animada del color de tu marca.
- Los skills de HyperFrames y del kit de Nate Herk se actualizan desde sus repos oficiales.
