#!/usr/bin/env bash
# tools/console_relay.sh — rend les consoles telnet des nœuds GNS3 joignables
# sur l'HÔTE (localhost:5000-5019), pour un client GNS3 distant (idempotent).
#
# Pourquoi ? Le conteneur GNS3 ne publie que 3080 (API) et 8080 (web UI). Les
# consoles (5000+) n'existent que sur son IP interne. Or le client GNS3 ouvre
# les consoles sur l'hôte qu'il utilise pour joindre l'API : via un tunnel
# (gh codespace ports forward), c'est 127.0.0.1 côté client → localhost du
# Codespace → il faut donc un relais localhost:500x → conteneur:500x.
#
# Alternative plus propre, mais qui oblige à recréer le conteneur :
#   docker run … -p 5000-5019:5000-5019 …
#
# Usage : tools/console_relay.sh [nom_conteneur] [premier_port] [dernier_port]

set -euo pipefail

CT="${1:-gns3server}"
FIRST="${2:-5000}"
LAST="${3:-5019}"

CT_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$CT")

for port in $(seq "$FIRST" "$LAST"); do
    if ss -ltn "sport = :$port" | grep -q LISTEN; then
        continue    # relais déjà en place (ou port pris)
    fi
    nohup socat "TCP-LISTEN:$port,fork,reuseaddr" "TCP:$CT_IP:$port" >/dev/null 2>&1 &
done

echo "[console_relay] localhost:$FIRST-$LAST → $CT ($CT_IP)"
