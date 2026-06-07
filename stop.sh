set -e  
  
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"  
RUN_DIR="$ROOT_DIR/run"  
  
stop_service() {  
	  local name=$1  
	    local pid_file="$RUN_DIR/$name.pid"  
	      
	      if [ -f "$pid_file" ]; then  
		          PID=$(cat "$pid_file")  
			      if ps -p "$PID" > /dev/null 2>&1; then  
				            echo "Ì†ΩÌªë Stopping $name (PID: $PID)..."  
					          kill "$PID"  
						      else  
							            echo "‚ö†Ô∏è $name pid file exists but process not running"  
								        fi  
									    rm -f "$pid_file"  
									      else  
										          echo "‚ÑπÔ∏è $name is not running"  
											    fi  
										    }  
										      
										    stop_service backend  
										    stop_service frontend  
										      
										    echo "‚úÖ Done"
