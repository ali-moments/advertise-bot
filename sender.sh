#!/usr/bin/bash

tmux has-session -t sender 2>/dev/null && tmux kill-session -t sender; \
tmux new-session -d -s sender -c "$PWD" 'bash -c "source ./venv/bin/activate && python cli/run.py"'

echo "cli panel is getting started, you can access the menu using 'tmux a -t sender' command!"
