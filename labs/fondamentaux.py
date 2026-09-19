#!/usr/bin/env python3
# labs/fondamentaux.py — labo "protocoles fondamentaux" : crée les nœuds, les
# câble, les démarre et génère l'inventaire Ansible. Idempotent (relançable).
#
#                         c1 (Cloud → bridge virbr0 = réseau de management)
#                        /  |  \          192.168.100.0/24, hors-bande
#                  ether1  ether1  ether1
#                     r1    sw1    sw2
#
#   Plan de données :
#                  r1  (routeur : inter-VLAN "router-on-a-stick" + DHCP)
#                   │ ether2  — trunk 802.1Q (VLAN 10, 20)
#                  sw1 (racine STP)
#            ether3 │  │ ether4   — 2 trunks en parallèle : boucle volontaire,
#            ether2 │  │ ether3     RSTP doit en bloquer un
#                  sw2
#   sw1 ether5 ─ pc1 (VLAN 10)        sw2 ether4 ─ pc3 (VLAN 10)
#   sw1 ether6 ─ pc2 (VLAN 20)        sw2 ether5 ─ pc4 (VLAN 20)
#
# Côté utilisateur une interface s'écrit eN (N à partir de 0) :
# sur un CHR, eN = ether(N+1)  →  r1_e1 = ether2 de r1.
#
# Usage :
#   python3 labs/fondamentaux.py
#   GNS3_CONSOLE_HOST=172.17.0.2 python3 labs/fondamentaux.py   # consoles non publiées sur l'hôte

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gns3 import GNS3Client
from gns3.deploy import GNS3Deployer
from gns3.inventory import AnsibleInventory
from gns3.node import GNS3Node
from gns3.project import GNS3Project
from gns3.exceptions import GNS3NotFoundError
from gns3.topology_builder import Topology, Link, Endpoint

PROJECT_NAME  = "lab_fondamentaux"
MGMT_BRIDGE   = "virbr0"            # créé par tools/mgmt_net.sh
MGMT_NODES    = ["r1", "sw1", "sw2"]  # un port de Cloud par équipement manageable
INVENTORY     = "inventory/gns3_dynamic.yml"
CONSOLE_HOST  = os.environ.get("GNS3_CONSOLE_HOST", "localhost")

# Câblage : (nœud, interface eN) ↔ (nœud, interface eN)
CABLES = [
    # management hors-bande : port N du Cloud ↔ ether1 de chaque équipement
    *[(("c1", i), (node, 0)) for i, node in enumerate(MGMT_NODES)],
    (("r1", 1),  ("sw1", 1)),   # r1 ether2  ↔ sw1 ether2  (trunk)
    (("sw1", 2), ("sw2", 1)),   # sw1 ether3 ↔ sw2 ether2  (trunk)
    (("sw1", 3), ("sw2", 2)),   # sw1 ether4 ↔ sw2 ether3  (trunk redondant → STP)
    (("sw1", 4), ("pc1", 0)),   # sw1 ether5 ↔ pc1         (accès VLAN 10)
    (("sw1", 5), ("pc2", 0)),   # sw1 ether6 ↔ pc2         (accès VLAN 20)
    (("sw2", 3), ("pc3", 0)),   # sw2 ether4 ↔ pc3         (accès VLAN 10)
    (("sw2", 4), ("pc4", 0)),   # sw2 ether5 ↔ pc4         (accès VLAN 20)
]

# Disposition sur le canevas GNS3 (purement visuel)
LAYOUT = {
    "c1": (0, -300),
    "r1": (0, -150),
    "sw1": (-150, 0), "sw2": (150, 0),
    "pc1": (-300, 150), "pc2": (-100, 150), "pc3": (100, 150), "pc4": (300, 150),
}


def build_topology() -> Topology:
    topo = Topology()
    for (a, pa), (b, pb) in CABLES:
        topo.add_link(a, Link(Endpoint(a, "e", pa), Endpoint(b, "e", pb)))
    return topo


def ensure_mgmt_cloud(client, project_id):
    """
    Crée le Cloud c1 AVANT le déploiement : ses ports doivent être définis
    avant qu'on y branche un câble (GNS3 refuse de modifier un Cloud connecté).
    Le déployeur le retrouvera ensuite par son nom et le réutilisera.
    """
    node = GNS3Node(client, project_id)
    try:
        return node.load_by_name("c1")
    except GNS3NotFoundError:
        pass
    template_id = next(t["template_id"] for t in client.get("/templates") if t["name"] == "Cloud")
    node.create(name="c1", template_id=template_id)
    ports = [
        {"name": f"mgmt-{n}", "port_number": i, "type": "ethernet", "interface": MGMT_BRIDGE}
        for i, n in enumerate(MGMT_NODES)
    ]
    node.update(properties={"ports_mapping": ports})
    print(f"  [cloud]  c1 : {len(ports)} ports sur le bridge {MGMT_BRIDGE}")
    return node


def main():
    client = GNS3Client("http://localhost:3080")
    print("Serveur GNS3 :", client.ping()["version"])

    project = GNS3Project(client)
    try:
        project.load_by_name(PROJECT_NAME)
    except GNS3NotFoundError:
        project.create(PROJECT_NAME)
    ensure_mgmt_cloud(client, project.id)

    result = GNS3Deployer(client, PROJECT_NAME).deploy(build_topology())
    result.summary()
    if result.nodes_fail or result.links_fail:
        sys.exit("Déploiement incomplet — voir le rapport ci-dessus.")

    for uid, node in result.nodes_ok.items():
        if uid in LAYOUT:
            x, y = LAYOUT[uid]
            node.update(x=x, y=y)
        if node.status != "started":
            node.start()
    print("Tous les nœuds sont démarrés.")

    path = AnsibleInventory(result, console_host=CONSOLE_HOST).write(INVENTORY)
    print(f"Inventaire Ansible : {path}  (consoles sur {CONSOLE_HOST})")


if __name__ == "__main__":
    main()
