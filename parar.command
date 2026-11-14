#!/bin/bash
# Stops the studio and the ComfyUI that EasyComfee started (macOS).
# It finds who is listening on each port and ends that process.
achou=0
for porta in 8600 8188 8189; do
  for pid in $(lsof -nP -iTCP:"$porta" -sTCP:LISTEN -t 2>/dev/null); do
    echo "Stopping process $pid on port $porta ..."
    kill "$pid" 2>/dev/null
    achou=1
  done
done
if [ "$achou" = "0" ]; then
  echo "Nothing was running on ports 8600, 8188 and 8189."
else
  echo
  echo "Stopped."
fi
echo
read -r -p "Press Enter to close this window..." _
