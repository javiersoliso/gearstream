#!/data/data/com.termux/files/usr/bin/bash
# GearStream en el teléfono (Termux): servidor + puente al reloj, sin laptop.
#   bash start.sh              # busca el reloj en la red
#   bash start.sh <IP-del-reloj>
# Después abre http://localhost:8765 en el navegador del teléfono.
cd "$(dirname "$0")/.."
DEVICE="${1:-auto}"
termux-wake-lock || echo "(sin termux-wake-lock: Android puede dormir Termux con la pantalla apagada)"
python server/server.py &
SERVER=$!
trap 'kill $SERVER 2>/dev/null; termux-wake-unlock 2>/dev/null' EXIT
sleep 2
echo "Dashboard: http://localhost:8765"
echo "Ctrl+C detiene todo. Para escribir otros comandos mientras corre: desliza desde el borde izquierdo -> NEW SESSION"
# --batch 10: a phone hotspot has a ~60 ms round trip and sdb sends one packet per round trip,
# so the watch groups 10 samples per packet (adds <=100 ms but keeps the full 100 Hz).
python tools/sdb_bridge.py --device "$DEVICE" --batch 10
