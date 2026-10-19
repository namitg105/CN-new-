#!/bin/bash
# Environment setup for System (Client Host) terminals
[ -f /etc/bash.bashrc ] && source /etc/bash.bashrc 2>/dev/null
[ -f ~/.bashrc ] && source ~/.bashrc 2>/dev/null

# Auto-detect IP and interface name directly from the namespace
DETECTED_IP=$(ip -4 -o addr show 2>/dev/null | grep -v '127.0.0.1' | awk '{print $4}' | cut -d/ -f1 | head -n1)
DETECTED_NAME=$(ip -4 -o addr show 2>/dev/null | grep -v '127.0.0.1' | awk '{print $2}' | cut -d- -f1 | head -n1)

SYS_NAME="${DETECTED_NAME:-${SYS_NAME:-${1:-c1}}}"
SYS_IP="${DETECTED_IP:-${SYS_IP:-${2:-10.0.0.1}}}"

# Colors
GREEN='\033[1;32m'
BLUE='\033[1;34m'
YELLOW='\033[1;33m'
CYAN='\033[1;36m'
NC='\033[0m'

export PS1="\[\033[1;32m\]root@${SYS_NAME} (${SYS_IP})\[\033[0m\]:\[\033[1;34m\]\w\[\033[0m\]# "

echo -e "${CYAN}==================================================================${NC}"
echo -e "${GREEN}  HOST SYSTEM TERMINAL: ${SYS_NAME} (IP: ${SYS_IP})${NC}"
echo -e "${CYAN}==================================================================${NC}"
echo -e "  Role: Virtual Client Host connected to Switch s1 (Router-1)"
echo -e "  Subnet: 10.0.0.0/24 | Target Server: 10.0.0.100:5000"
echo -e "${CYAN}------------------------------------------------------------------${NC}"
echo -e "  ${YELLOW}Quick Commands Available:${NC}"
echo -e "    ${GREEN}curl-srv${NC}      - Query Server health (curl http://10.0.0.100:5000/health)"
echo -e "    ${GREEN}start-traffic${NC} - Send recurring HTTP requests to server (client.sh)"
echo -e "    ${GREEN}fast-ping${NC}     - Send 100 fast pings (10ms interval) to test failover"
echo -e "    ${GREEN}ping-srv${NC}      - Standard ping to Server (10.0.0.100)"
echo -e "    ${GREEN}ip a${NC}          - Check interface configuration"
echo -e "${CYAN}==================================================================${NC}\n"

alias curl-srv="curl -s http://10.0.0.100:5000/health"
alias test-health="curl -s http://10.0.0.100:5000/health"
alias start-traffic="bash /home/kalis/nettwin/scripts/client.sh ${SYS_NAME}"
alias fast-ping="ping -i 0.01 -c 100 10.0.0.100"
alias ping-srv="ping -c 4 10.0.0.100"
