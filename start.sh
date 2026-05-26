set -e  

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
RUN_DIR="$ROOT_DIR/run"

mkdir -p "$LOG_DIR" "$RUN_DIR"

echo "Starting backend..."  
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt

nohup "$ROOT_DIR/.venv/bin/uvicorn" app.main:app --host 0.0.0.0 --port 11451 > "$LOG_DIR/backend.log" 2>&1 &
echo $! > "$RUN_DIR/backend.pid"
echo "Backend PID: $(cat "$RUN_DIR/backend.pid")"  

echo "Starting frontend..."  
cd "$ROOT_DIR/frontend"

npm install

nohup npm run dev -- --host 0.0.0.0 --port 19198 > "$LOG_DIR/frontend.log" 2>&1 &
echo $! > "$RUN_DIR/frontend.pid"
echo "Frontend PID: $(cat "$RUN_DIR/frontend.pid")"  

sleep 3

echo "Checking ports..."  
lsof -i:11451 || true
lsof -i:19198 || true
EOF

chmod +x start.sh