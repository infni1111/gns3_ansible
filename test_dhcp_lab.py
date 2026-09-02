#!/usr/bin/env python3
# test_dhcp_lab.py — déploie un mini-labo pour tester l'attribution d'IP par DHCP :
#   r1 (MikroTik CHR)  <-- ether1/eth0 -->  kali1 (Kali Docker, futur serveur DHCP)
# Étape 1 du plan DHCP. Réversible : relancer supprime/recrée le projet.

import sys
from gns3 import GNS3Client, GNS3Project, GNS3Node, GNS3Link
from gns3.exceptions import GNS3NotFoundError

PROJECT_NAME = "lab_dhcp_test"
CHR_TEMPLATE  = "a6dd11d7-45de-4cce-b2df-b5af444a76c8"   # MikroTik CHR 7.22.1 (qemu)
KALI_TEMPLATE = "5b8262fe-4426-4daa-ad82-c4ca9171b5e0"   # Kali Linux (docker)

client = GNS3Client("http://localhost:3080")
print("Serveur GNS3 :", client.ping())

# Projet neuf (on repart propre)
project = GNS3Project(client)
try:
    project.load_by_name(PROJECT_NAME)
    print(f"Projet existant '{PROJECT_NAME}' → suppression pour repartir propre")
    project.delete()
except GNS3NotFoundError:
    pass
project = GNS3Project(client).create(PROJECT_NAME)
print(f"Projet créé : {project.name} ({project.id})")

# Nœuds
r1 = GNS3Node(client, project.id).create(name="r1", template_id=CHR_TEMPLATE, x=-200, y=0)
print(f"Nœud r1 (CHR)  : id={r1.id}  console={r1.console_type}:{r1.console}")
kali1 = GNS3Node(client, project.id).create(name="kali1", template_id=KALI_TEMPLATE, x=200, y=0)
print(f"Nœud kali1     : id={kali1.id}  console={kali1.console_type}:{kali1.console}")

# Lien direct : r1 ether1 (adapter 0, port 0)  <->  kali1 eth0 (adapter 0, port 0)
link = GNS3Link(client, project.id).create(
    node_a_id=r1.id,    adapter_a=0, port_a=0,
    node_b_id=kali1.id, adapter_b=0, port_b=0,
)
print(f"Lien créé : r1 ether1 <-> kali1 eth0  (id={link.id})")

print("\nOK — étape 1 terminée. Consoles :")
print(f"  r1    : telnet localhost {r1.console}")
print(f"  kali1 : telnet localhost {kali1.console}")
