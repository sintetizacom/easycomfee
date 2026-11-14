#!/bin/bash
# Creates the "EasyComfee" app icon (macOS) on the Desktop and in ~/Applications (Launchpad/Spotlight).
# Clicking it starts the studio with no Terminal window and opens the browser; if it is already
# running, it only opens the browser. Called by install.command; can be run alone too.
cd "$(dirname "$0")" || exit 1
RAIZ="$(pwd)"
mkdir -p logs

criar() {
  local APP="$1/EasyComfee.app"
  rm -rf "$APP"
  mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
  cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>EasyComfee</string>
<key>CFBundleDisplayName</key><string>EasyComfee</string>
<key>CFBundleIdentifier</key><string>com.easycomfee.launcher</string>
<key>CFBundleExecutable</key><string>EasyComfee</string>
<key>CFBundleIconFile</key><string>easycomfee</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>LSUIElement</key><true/>
</dict></plist>
PLIST
  cat > "$APP/Contents/MacOS/EasyComfee" <<LAUNCH
#!/bin/bash
RAIZ="$RAIZ"
PORT=\$("\$RAIZ/backend/.venv/bin/python" -c "import sys; sys.path.insert(0, '\$RAIZ/backend'); import config; print(config.APP_PORTA)" 2>/dev/null)
PORT=\${PORT:-8600}
if curl -s -o /dev/null --max-time 2 "http://127.0.0.1:\$PORT"; then
  open "http://127.0.0.1:\$PORT"
else
  mkdir -p "\$RAIZ/logs"
  nohup "\$RAIZ/start.command" >> "\$RAIZ/logs/servidor.log" 2>&1 &
fi
LAUNCH
  chmod +x "$APP/Contents/MacOS/EasyComfee"
  # Icon: Pillow (already in the environment) turns the brand .ico into an .icns.
  backend/.venv/bin/python -c "
from PIL import Image
Image.open('frontend/public/brand/easycomfee.ico').save('$APP/Contents/Resources/easycomfee.icns')
" 2>/dev/null
  touch "$APP"
}

mkdir -p "$HOME/Applications"
criar "$HOME/Applications"
criar "$HOME/Desktop"
echo "Created the EasyComfee app on your Desktop and in ~/Applications."
