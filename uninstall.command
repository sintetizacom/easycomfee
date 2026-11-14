#!/bin/bash
# Removes EasyComfee (macOS): closes it, deletes its icons and this folder.
cd "$(dirname "$0")" || exit 1
RAIZ="$(pwd)"
# Development folder (has the private notes): never deleted by itself.
if [ -f AGENTS.md ]; then echo "This is the development folder: uninstall is disabled here."; exit 1; fi

echo "This will:"
echo "  - stop the studio and the ComfyUI that EasyComfee started"
echo "  - delete the EasyComfee app from your Desktop and ~/Applications"
echo "  - delete this whole folder: $RAIZ"
if [ -d "$RAIZ/ComfyUI" ]; then
  echo
  echo "Setup downloaded ComfyUI into this folder: ComfyUI, its models and everything you"
  echo "generated go with it. Copy what you want to keep first."
else
  echo "A ComfyUI you already had is never touched."
fi
echo "Python, Node.js and Git stay installed."
echo
read -r -p "Type YES to continue: " resposta
if [ "$resposta" != "YES" ]; then echo "Cancelled."; exit 1; fi

for porta in 8600 8188 8189; do
  for pid in $(lsof -nP -iTCP:"$porta" -sTCP:LISTEN -t 2>/dev/null); do kill "$pid" 2>/dev/null; done
done
rm -rf "$HOME/Desktop/EasyComfee.app" "$HOME/Applications/EasyComfee.app"
sleep 2
# Everything below is read before it runs, so deleting this very file is safe.
{
  cd "$HOME" || exit 1
  rm -rf "$RAIZ"
  if [ -d "$RAIZ" ]; then echo "Some files could not be deleted. Delete this folder by hand: $RAIZ"
  else echo "EasyComfee was removed."; fi
  read -r -p "Press Enter to close this window..." _
  exit 0
}
