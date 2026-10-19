#!/bin/bash
set -x

# 1. Clean previous state
echo 123456 | sudo -S mn -c

# 2. Start Ryu in background
/home/kalis/nettwin/ryu-env/bin/ryu-manager /home/kalis/nettwin/controller.py > /tmp/ryu.log 2>&1 &
RYU_PID=$!
sleep 2

# 3. Run the Mininet demo
echo 123456 | sudo -S python3 /home/kalis/nettwin/run_demo.py

# 4. Clean up
kill -9 $RYU_PID 2>/dev/null || true
echo 123456 | sudo -S mn -c
