#!/usr/bin/env bash
# tools/mgmt_net.sh — réseau de MANAGEMENT hors-bande entre l'hôte Ansible et
# les équipements GNS3 (idempotent : relançable sans risque).
#
#   hôte (Ansible) ──route──► conteneur GNS3 ──► bridge virbr0 192.168.100.1/24
#                                                   ├─ gns3tap0-0 ─ Cloud c1 port 0 ─ r1  ether1
#                                                   ├─ gns3tap0-1 ─ Cloud c1 port 1 ─ sw1 ether1
#                                                   └─ gns3tap0-2 ─ Cloud c1 port 2 ─ sw2 ether1
#
# Pourquoi un bridge nommé "virbr0" ?
#   - GNS3 filtre les interfaces utilisables par un Cloud (allowed_interfaces
#     dans gns3_server.conf) et virbr0 y figure déjà : pas de config GNS3 à
#     modifier, pas de redémarrage du serveur.
#   - Quand un port de Cloud pointe sur un BRIDGE Linux, GNS3 crée tout seul un
#     TAP par port et l'y attache : un seul Cloud suffit pour tous les nœuds.
#
# Pourquoi du NAT (MASQUERADE) vers virbr0 ?
#   Les équipements n'ont pas de route vers le réseau de l'hôte (172.17.0.0/16) :
#   vus depuis eux, les paquets d'Ansible viennent de 192.168.100.1, sur leur
#   propre sous-réseau. Aucune route à poser côté équipement.
#
# ⚠️ Tout ce qui est fait DANS le conteneur est éphémère (perdu s'il est recréé) :
#    relancer ce script après chaque (re)création du conteneur.
#
# Usage : tools/mgmt_net.sh [nom_conteneur]      (défaut : gns3server)

set -euo pipefail

CT="${1:-gns3server}"
BR="virbr0"
GW="192.168.100.1/24"
NET="192.168.100.0/24"

ct() { docker exec "$CT" sh -c "$1"; }

# 1. Bridge de management dans le conteneur GNS3
ct "ip link show $BR >/dev/null 2>&1 || ip link add $BR type bridge"
ct "ip -4 addr show dev $BR | grep -q '${GW%/*}/' || ip addr add $GW dev $BR"
ct "ip link set $BR up"

# 2. Routage + NAT dans le conteneur. dockerd (interne au conteneur) met la
#    politique FORWARD à DROP : on autorise explicitement le trafic de/vers virbr0.
ct "sysctl -qw net.ipv4.ip_forward=1"
ct "iptables -C FORWARD -o $BR -j ACCEPT 2>/dev/null || iptables -I FORWARD -o $BR -j ACCEPT"
ct "iptables -C FORWARD -i $BR -j ACCEPT 2>/dev/null || iptables -I FORWARD -i $BR -j ACCEPT"
ct "iptables -t nat -C POSTROUTING -o $BR -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -o $BR -j MASQUERADE"

# 3. Route côté hôte vers le réseau de management, via l'IP du conteneur
CT_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$CT")
sudo ip route replace "$NET" via "$CT_IP"

echo "[mgmt_net] $NET joignable via $CT ($CT_IP), passerelle ${GW%/*} sur $BR"
