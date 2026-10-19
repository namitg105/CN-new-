#!/bin/bash
# usage: ./client.sh c1
# Sends one request to the server every half second and prints what happened.
NAME="${1:-client}"
while true; do
    CODE=$(curl -s -m 1 -o /dev/null -w "%{http_code}" http://10.0.0.100:5000/health)
    if [ "$CODE" = "200" ]; then STATE="OK"; else STATE="FAILED"; fi
    echo "$(date +%H:%M:%S.%3N) $NAME request $STATE (HTTP $CODE)"
    sleep 0.5
done
