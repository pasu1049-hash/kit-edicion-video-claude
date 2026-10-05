#!/usr/bin/env bash
# Instalador del kit de edicion de video (Mac / Linux).  Uso:  bash instalar.sh
set -e
KIT="$(cd "$(dirname "$0")" && pwd)"
SK="$HOME/.claude/skills"; AG="$HOME/.claude/agents"
mkdir -p "$SK" "$AG"

for p in git node npm python3; do
  command -v $p >/dev/null || { echo "Falta $p. En Mac: brew install git node python ffmpeg"; exit 1; }
done
command -v ffmpeg >/dev/null || echo "Aviso: falta FFmpeg (brew install ffmpeg)"

echo "== 1/4 Skills oficiales de HyperFrames =="
npx -y skills add heygen-com/hyperframes -g -a claude-code -s '*' -y --copy

echo "== 2/4 Skill editor-videos-1porciento + agente editor =="
DEST="$SK/editor-videos-1porciento"
[ -f "$DEST/MARCA.md" ] && cp "$DEST/MARCA.md" /tmp/marca_bak.md
cp -R "$KIT/skills/editor-videos-1porciento" "$SK/"
[ -f /tmp/marca_bak.md ] && mv /tmp/marca_bak.md "$DEST/MARCA.md"
[ -f "$AG/editor.md" ] && cp "$AG/editor.md" "$AG/editor.md.bak"
cp "$KIT/agents/editor.md" "$AG/"

echo "== 3/4 Librerias de Python =="
python3 -m pip install -r "$DEST/scripts/requirements.txt"

echo "== 4/4 Kit de video de Nate Herk =="
NATE="$HOME/Documents/hyperframes-student-kit"
[ -d "$NATE" ] || git clone https://github.com/nateherkai/hyperframes-student-kit.git "$NATE"
(cd "$NATE" && npm ci && npm run setup)

echo; echo "LISTO. Cerra y volve a abrir Claude para que cargue los skills."
echo "Primer paso: decile a Claude 'completa mi MARCA.md del skill editor-videos-1porciento'."
