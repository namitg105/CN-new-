#!/bin/bash
# Environment setup for Main Server terminal
[ -f /etc/bash.bashrc ] && source /etc/bash.bashrc 2>/dev/null
[ -f ~/.bashrc ] && source ~/.bashrc 2>/dev/null

SRV_IP="10.0.0.100"
SRV_PORT="5000"

# Colors
GREEN='\033[1;32m'
BLUE='\033[1;34m'
YELLOW='\033[1;33m'
CYAN='\033[1;36m'
RED='\033[1;31m'
NC='\033[0m'

export PS1="\[\033[1;36m\]root@Main-Server (${SRV_IP})\[\033[0m\]:\[\033[1;34m\]\w\[\033[0m\]# "

echo -e "${CYAN}==================================================================${NC}"
echo -e "${CYAN}  MAIN SERVER TERMINAL: srv (IP: ${SRV_IP}:${SRV_PORT})${NC}"
echo -e "${CYAN}==================================================================${NC}"
echo -e "  Role: Central HTTP Application Server (Flask)"
echo -e "  Connected to: Switch s4 (Port 3)"
echo -e "${CYAN}------------------------------------------------------------------${NC}"
echo -e "  ${YELLOW}Quick Commands Available:${NC}"
echo -e "    ${GREEN}start-server${NC}   - Start Flask application server in background"
echo -e "    ${RED}stop-server${NC}    - Kill Flask server (Simulates Application Crash)"
echo -e "    ${GREEN}server-status${NC}  - Check if Flask server is listening on port 5000"
echo -e "    ${GREEN}show-logs${NC}      - Tail server HTTP access logs (/tmp/server.log)"
echo -e "    ${GREEN}ip a${NC}           - Inspect server network interfaces"
echo -e "${CYAN}==================================================================${NC}\n"

alias start-server="python3 -m nettwin.server.app > /tmp/server.log 2>&1 & echo '[+] Server started on port 5000'"
alias stop-server="pkill -f nettwin.server.app && echo '[-] Server stopped (CRASH SIMULATED)'"
alias server-status="ss -tlpn | grep 5000 || echo '[-] Server NOT running'"
alias show-logs="tail -f /tmp/server.log"
alias test-health="curl -s http://127.0.0.1:5000/health"
