#!/bin/bash
# TimecodeBridge Host — Start all services
# Run: ./start.sh

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "TimecodeBridge starting..."
echo ""

# Kill any existing instances
pkill -f "python.*server\.py" 2>/dev/null
pkill -f "python.*ltc_listener\.py" 2>/dev/null
pkill -f "python.*http\.server.*8080" 2>/dev/null
sleep 1

# Start WebSocket server
PYTHONUNBUFFERED=1 python server.py &
SERVER_PID=$!
echo "WebSocket server: PID $SERVER_PID (ws://0.0.0.0:9876)"

# Start LTC listener
PYTHONUNBUFFERED=1 python ltc_listener.py &
LTC_PID=$!
echo "LTC listener:    PID $LTC_PID"

# Start HTTP server for browser client
python -m http.server 8080 --directory "$DIR" &>/dev/null &
HTTP_PID=$!
echo "HTTP server:     PID $HTTP_PID (http://localhost:8080)"

echo ""
echo "All services running. Press Ctrl+C to stop all."
echo ""
echo "In Resolve Console (Workspace > Console > Py3), paste:"
echo "  exec(open(\"$DIR/resolve_console_script.py\").read())"
echo ""

# Wait for Ctrl+C, then clean up
trap "echo ''; echo 'Stopping...'; kill $SERVER_PID $LTC_PID $HTTP_PID 2>/dev/null; exit 0" INT TERM
wait
