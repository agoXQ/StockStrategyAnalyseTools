set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$ROOT_DIR/run"

check_service() {
          local name=$1  
            local pid_file="$RUN_DIR/$name.pid"  

              if [ -f "$pid_file" ]; then
                          PID=$(cat "$pid_file")
                              if ps -p "$PID" > /dev/null 2>&1; then
                                            echo "✅ $name is running, PID: $PID"  
                                                else
                                                              echo "❌ $name pid file exists, but process is not running"  
                                                                  fi
                                                                    else
                                                                                echo "ℹ️ $name is not running"  
                                                                                  fi
                                                                          }

                                                                          check_service backend
                                                                          check_service frontend