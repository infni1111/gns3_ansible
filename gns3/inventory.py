# gns3/inventory.py
# Génère un inventaire Ansible à partir d'un déploiement GNS3 (DeployResult).
#
# C'est le pont entre le SDK (qui connaît les nœuds réels : id, console, type)
# et Ansible (qui a besoin d'un inventaire pour atteindre les équipements).
#
# Chaque nœud est rangé dans un groupe selon son préfixe utilisateur
# (r=routers, sw=switches, pc=terminals, …). On exporte pour
# chaque nœud ses infos de console GNS3 (host/port/type), seul point d'accès
# garanti dès la création — avant toute config réseau.
#
# Usage :
#   from gns3.inventory import AnsibleInventory
#   AnsibleInventory(result).write("inventory/gns3_dynamic.yml")

import yaml

from .deploy import split_prefix

# Préfixe utilisateur → (nom de groupe Ansible, variables de groupe par défaut)
# Les vars de connexion réelles vivent dans inventory/group_vars/<groupe>.yml ;
# ici on ne pose que ce qui dépend du type d'équipement.
PREFIX_TO_GROUP = {
    "r": "routers",         # MikroTik CHR (RouterOS)
    "sw": "switches",       # MikroTik CHR en mode switch (bridge) — manageable
    "s": "gns3_switches",   # switch Ethernet GNS3 intégré (non configurable)
    "f": "firewalls",       # FortiGate
    "g": "guests",          # VPCS / Linux
    "pc": "terminals",      # VPCS utilisé comme poste utilisateur
    "c": "clouds",          # nœud Cloud (pont vers l'hôte)
}

# Groupes parents par OS : c'est sur eux que s'accrochent les vars de
# connexion et la couche de traduction vendeur (inventory/group_vars/routeros.yml…).
OS_PARENT_GROUPS = {
    "routeros": ["routers", "switches"],
    "vpcs": ["guests", "terminals"],
}

# Console host : où GNS3 expose les consoles. Sur une install Docker locale
# c'est l'hôte qui publie les ports ; ajustable si le serveur est distant.
DEFAULT_CONSOLE_HOST = "localhost"


class AnsibleInventory:
    """Construit un inventaire Ansible (format YAML) depuis un DeployResult."""

    def __init__(self, deploy_result, console_host: str = DEFAULT_CONSOLE_HOST):
        self.result = deploy_result
        self.console_host = console_host

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def build(self) -> dict:
        """Retourne le dict d'inventaire Ansible (structure 'all/children')."""
        children: dict[str, dict] = {}

        for uid, node in self.result.nodes_ok.items():
            group = PREFIX_TO_GROUP.get(split_prefix(uid), "ungrouped")
            children.setdefault(group, {"hosts": {}})
            children[group]["hosts"][uid] = self._host_vars(uid, node)

        for parent, members in OS_PARENT_GROUPS.items():
            present = [g for g in members if g in children]
            if present:
                children[parent] = {"children": {g: {} for g in present}}

        return {
            "all": {
                "vars": {
                    "gns3_project_id": self.result.project_id,
                    "gns3_project_name": self.result.project_name,
                    "gns3_console_host": self.console_host,
                },
                "children": children,
            }
        }

    def _host_vars(self, uid: str, node) -> dict:
        """Variables par hôte : identité GNS3 + point d'accès console."""
        return {
            "gns3_node_id": node.id,
            "gns3_node_type": node.node_type,
            "gns3_console_host": self.console_host,
            "gns3_console_port": node.console,
            "gns3_console_type": node.console_type,
        }

    # ------------------------------------------------------------------
    # Sortie
    # ------------------------------------------------------------------

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            self.build(), default_flow_style=False, sort_keys=False, allow_unicode=True
        )

    def write(self, path: str) -> str:
        """Écrit l'inventaire sur disque et retourne le chemin."""
        with open(path, "w", encoding="utf-8") as f:
            f.write("# Inventaire GNS3 généré automatiquement — NE PAS éditer à la main.\n")
            f.write("# Régénéré à chaque déploiement par gns3/inventory.py\n")
            f.write(self.to_yaml())
        return path
