# topology_builder.py

class Endpoint:
    """Niveau 3 — une extrémité : nœud + adaptateur + port"""
    def __init__(self, node_id: str, adapter: str, port: int):
        self.node_id = node_id      # ex: r1, s4, f1, g2
        self.adapter = adapter      # ex: e, w
        self.port = port            # ex: 5, 9, 0

    def __repr__(self):
        return f"{self.node_id}_{self.adapter}{self.port}"


class Link:
    """Niveau 2 — un lien : tuple de deux extrémités"""
    def __init__(self, source: Endpoint, destination: Endpoint):
        self.source = source
        self.destination = destination

    def __repr__(self):
        return f"({self.source}, {self.destination})"


class NodeTopology:
    """Niveau 1 — un nœud et tous ses liens"""
    def __init__(self, node_id: str):
        self.node_id = node_id      # ID utilisateur ex: r1, s4
        self.links = []             # liste de Link (niveau 2)

    def add_link(self, link: Link):
        self.links.append(link)

    def __repr__(self):
        return f"{self.node_id}: {self.links}"


class Topology:
    """Niveau 0 — la topologie complète"""
    def __init__(self):
        self.nodes = []             # liste de NodeTopology (niveau 1)
        self._index = {}            # node_id → NodeTopology pour accès rapide

    def get_or_create_node(self, node_id: str) -> NodeTopology:
        if node_id in self._index:
            return self._index[node_id]
        node = NodeTopology(node_id)
        self.nodes.append(node)
        self._index[node_id] = node
        return node

    def add_link(self, node_id: str, link: Link):
        node = self.get_or_create_node(node_id)
        node.add_link(link)

    def summary(self):
        print("\n=== TOPOLOGIE ===")
        for node in self.nodes:
            print(f"\n  Nœud : {node.node_id}")
            for link in node.links:
                print(f"    └── {link}")
        print("=================\n")


# ------------------------------------------------------------------
# Shell de saisie
# ------------------------------------------------------------------

ADAPTER_TYPES = {"e": "Ethernet", "w": "WiFi"}
NODE_TYPES    = {"r": "router", "s": "switch", "f": "firewall", "g": "guest"}
                
                
                
def get_endpoint(prompt_node: str) -> Endpoint:
    """Saisie verticale d'une extrémité — descend jusqu'au niveau 5."""
    print(f"\n    [Niveau 4] Adaptateur pour '{prompt_node}' ({'/'.join(ADAPTER_TYPES.keys())}) : ", end="")
    adapter = input().strip().lower()
    while adapter not in ADAPTER_TYPES:
        print(f"    Adaptateur invalide. Choix : {list(ADAPTER_TYPES.keys())} : ", end="")
        adapter = input().strip().lower()

    print(f"    [Niveau 5] Port ({adapter}) : ", end="")
    port = input().strip()
    while not port.isdigit():
        print(f"    Port invalide, entrez un nombre : ", end="")
        port = input().strip()

    return Endpoint(node_id=prompt_node, adapter=adapter, port=int(port))


def run_shell() -> Topology:
    topology = Topology()

    print("\n╔══════════════════════════════════╗")
    print("║     GNS3 Topology Builder        ║")
    print("╚══════════════════════════════════╝")
    print("  Préfixes nœuds :", {k: v for k, v in NODE_TYPES.items()})
    print("  Tapez 'done' pour terminer.\n")

    while True:
        print(f"\n[Niveau 1] Nœud source (ex: r1, s2, f1) : ", end="")
        node_input = input().strip().lower()

        if node_input == "done":
            break

        # Validation du préfixe
        prefix = node_input[0] if node_input else ""
        if prefix not in NODE_TYPES or not node_input[1:].isdigit():
            print(f"  Format invalide. Utilisez : préfixe({list(NODE_TYPES.keys())}) + numéro. Ex: r1, s3")
            continue

        print(f"\n  → Nœud source : '{node_input}' ({NODE_TYPES[prefix]})")

        # Saisie extrémité source — niveau 3 à 5
        source = get_endpoint(node_input)

        # Saisie nœud destination — niveau 1 (deuxième élément du tuple)
        print(f"\n[Niveau 1] Nœud destination : ", end="")
        dest_input = input().strip().lower()

        dest_prefix = dest_input[0] if dest_input else ""
        while dest_prefix not in NODE_TYPES or not dest_input[1:].isdigit():
            print(f"  Format invalide : ", end="")
            dest_input = input().strip().lower()
            dest_prefix = dest_input[0] if dest_input else ""

        print(f"\n  → Nœud destination : '{dest_input}' ({NODE_TYPES[dest_prefix]})")

        # Saisie extrémité destination — niveau 3 à 5
        destination = get_endpoint(dest_input)

        # Création du lien et ajout à la topologie
        link = Link(source=source, destination=destination)
        topology.add_link(node_input, link)

        print(f"\n  ✔ Lien ajouté : {link}")
        topology.summary()

    topology.summary()
    return topology


if __name__ == "__main__":
    topo = run_shell()
