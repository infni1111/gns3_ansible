# gns3/deploy.py
# Pont entre la topologie utilisateur (topology_builder.py) et le serveur GNS3.
# Lit une instance Topology et :
#   1. Crée les nœuds GNS3 à partir des préfixes utilisateur → templates réels
#   2. Crée les liens GNS3 entre les nœuds
#   3. Retourne un rapport de déploiement

from .client import GNS3Client
from .project import GNS3Project
from .node import GNS3Node
from .link import GNS3Link
from .exceptions import GNS3NotFoundError, GNS3AlreadyExistsError


# ------------------------------------------------------------------
# Mapping préfixe utilisateur → nom de template GNS3 réel
# Modifie ici si tu changes de templates sur le serveur.
# Les préfixes peuvent faire plusieurs lettres : c'est le plus LONG préfixe
# correspondant qui gagne (sw1 → "sw", s1 → "s").
# ------------------------------------------------------------------
PREFIX_TO_TEMPLATE = {
    "r": "MikroTik CHR 7.22.1",
    "s": "Ethernet switch",
    "sw": "MikroTik CHR 7.22.1",   # switch MANAGEABLE (CHR en mode bridge) — pilotable par Ansible
    "f": "FortiGate VM 7.6.6",
    "g": "VPCS",
    "pc": "VPCS",                  # terminal
    "c":"Cloud"
}

# Types de nœuds GNS3 à UN adaptateur multi-ports : l'interface eN est le
# port N de l'adaptateur 0. Pour tous les autres (qemu, docker, vpcs…),
# chaque interface est un adaptateur distinct : eN = adaptateur N, port 0.
SINGLE_ADAPTER_TYPES = {
    "ethernet_switch", "ethernet_hub", "cloud", "nat",
    "frame_relay_switch", "atm_switch",
}


def split_prefix(user_id: str) -> str:
    """Préfixe d'un identifiant utilisateur (plus long préfixe connu : sw1 → sw)."""
    letters = user_id.rstrip("0123456789")
    for n in range(len(letters), 0, -1):
        if letters[:n] in PREFIX_TO_TEMPLATE:
            return letters[:n]
    return letters

# Espacement automatique des nœuds sur le canvas GNS3
CANVAS_X_START  = 0
CANVAS_Y_START  = 0
CANVAS_X_STEP   = 200
CANVAS_Y_STEP   = 150
NODES_PER_ROW   = 5


class DeployResult:
    """Rapport de déploiement — ce qui a été créé, ce qui a échoué."""

    def __init__(self):
        self.project_id   = None
        self.project_name = None
        self.nodes_ok     = {}   # node_id_user (ex: r1) → GNS3Node (créé OU réutilisé)
        self.nodes_fail   = {}   # node_id_user → message d'erreur
        self.links_ok     = []   # liste de GNS3Link (créés OU réutilisés)
        self.links_fail   = []   # liste de dict {link_repr, error}
        # Idempotence : ce qui existait déjà et a été réutilisé tel quel
        self.nodes_existing = set()   # node_id_user
        self.links_existing = 0

    def summary(self):
        print("\n╔══════════════════════════════════════════╗")
        print("║          RAPPORT DE DÉPLOIEMENT          ║")
        print("╚══════════════════════════════════════════╝")
        print(f"  Projet  : {self.project_name}  (id={self.project_id})")
        print(f"\n  Nœuds          : {len(self.nodes_ok)}  (dont {len(self.nodes_existing)} déjà existants)")
        for uid, node in self.nodes_ok.items():
            tag = "=" if uid in self.nodes_existing else "✔"
            print(f"    {tag}  {uid:5}  →  {node.name:30}  id={node.id}")
        if self.nodes_fail:
            print(f"\n  Nœuds en erreur : {len(self.nodes_fail)}")
            for uid, err in self.nodes_fail.items():
                print(f"    ✘  {uid:5}  →  {err}")
        print(f"\n  Liens          : {len(self.links_ok)}  (dont {self.links_existing} déjà existants)")
        for lnk in self.links_ok:
            print(f"    ✔  {lnk}")
        if self.links_fail:
            print(f"\n  Liens en erreur : {len(self.links_fail)}")
            for item in self.links_fail:
                print(f"    ✘  {item['link']}  →  {item['error']}")
        print("═" * 44 + "\n")


class GNS3Deployer:
    """
    Déploie une Topology sur un serveur GNS3.

    Usage :
        deployer = GNS3Deployer(client, project_name="mon_labo")
        result   = deployer.deploy(topology)
        result.summary()
    """

    def __init__(self, client: GNS3Client, project_name: str):
        self.client       = client
        self.project_name = project_name
        self._project     = None
        self._template_cache = {}   # name → template_id

    # ------------------------------------------------------------------
    # Point d'entrée principal
    # ------------------------------------------------------------------

    def deploy(self, topology) -> DeployResult:
        """
        Déploie la topologie complète.
        Étapes : projet → nœuds → liens.
        """
        result = DeployResult()

        # 1. Créer ou récupérer le projet
        self._project = self._get_or_create_project()
        result.project_id   = self._project.id
        result.project_name = self._project.name

        # 2. Collecter tous les node_id uniques présents dans la topologie
        unique_node_ids = self._collect_node_ids(topology)

        # 3. Créer les nœuds — ou réutiliser ceux qui portent déjà ce nom.
        #    Sans ça, GNS3 renomme le doublon (r1 → r2) et chaque redéploiement
        #    empile une copie de la topologie.
        existing_nodes = {n["name"]: n["node_id"] for n in GNS3Node(self.client, self._project.id).list_all()}
        node_map = {}   # node_id_user → GNS3Node (pour les liens)
        for idx, uid in enumerate(sorted(unique_node_ids)):
            try:
                if uid in existing_nodes:
                    gns3_node = GNS3Node(self.client, self._project.id).load_by_id(existing_nodes[uid])
                    result.nodes_existing.add(uid)
                    print(f"  [nœud]   Existant : {uid:5} (réutilisé)")
                else:
                    gns3_node = self._create_node(uid, idx)
                node_map[uid]         = gns3_node
                result.nodes_ok[uid]  = gns3_node
            except Exception as e:
                result.nodes_fail[uid] = str(e)

        # Ports déjà câblés : (node_id, adapter, port) → link_id
        existing_ports = {}
        for lnk in GNS3Link(self.client, self._project.id).list_all():
            for end in lnk["nodes"]:
                existing_ports[(end["node_id"], end["adapter_number"], end["port_number"])] = lnk["link_id"]

        # 4. Créer les liens
        seen_links = set()   # évite les doublons (A-B == B-A)
        for node_topo in topology.nodes:
            for link in node_topo.links:
                src = link.source
                dst = link.destination

                # Clé canonique pour déduplication
                key = tuple(sorted([
                    (src.node_id, src.adapter, src.port),
                    (dst.node_id, dst.adapter, dst.port),
                ]))
                if key in seen_links:
                    continue
                seen_links.add(key)

                link_repr = f"{src} ↔ {dst}"

                # Vérifier que les deux nœuds ont été créés
                if src.node_id not in node_map:
                    result.links_fail.append({
                        "link": link_repr,
                        "error": f"Nœud source '{src.node_id}' non créé"
                    })
                    continue
                if dst.node_id not in node_map:
                    result.links_fail.append({
                        "link": link_repr,
                        "error": f"Nœud destination '{dst.node_id}' non créé"
                    })
                    continue

                try:
                    end_a = (node_map[src.node_id].id, *self._gns3_port(node_map[src.node_id], src.adapter, src.port))
                    end_b = (node_map[dst.node_id].id, *self._gns3_port(node_map[dst.node_id], dst.adapter, dst.port))
                    id_a, id_b = existing_ports.get(end_a), existing_ports.get(end_b)
                    if id_a and id_a == id_b:
                        # Ce câble existe déjà exactement : rien à faire.
                        result.links_ok.append(GNS3Link(self.client, self._project.id).load_by_id(id_a))
                        result.links_existing += 1
                        print(f"  [lien]   Existant : {link_repr} (réutilisé)")
                        continue
                    if id_a or id_b:
                        # Un des deux ports est déjà pris par un AUTRE câble : on ne
                        # débranche rien en silence, on signale le conflit.
                        raise RuntimeError("port déjà câblé vers une autre extrémité")
                    gns3_link = self._create_link(
                        node_map[src.node_id], src.adapter, src.port,
                        node_map[dst.node_id], dst.adapter, dst.port,
                    )
                    result.links_ok.append(gns3_link)
                except Exception as e:
                    result.links_fail.append({"link": link_repr, "error": str(e)})

        return result

    # ------------------------------------------------------------------
    # Méthodes internes
    # ------------------------------------------------------------------

    def _get_or_create_project(self) -> GNS3Project:
        project = GNS3Project(self.client)
        try:
            project.load_by_name(self.project_name)
            print(f"  [projet] Projet existant chargé : '{self.project_name}'")
        except GNS3NotFoundError:
            project.create(self.project_name)
            print(f"  [projet] Nouveau projet créé    : '{self.project_name}'")
        return project

    def _resolve_template_id(self, prefix: str) -> str:
        """Résout un préfixe utilisateur (r, s, sw, f, g, pc, c) en template_id GNS3."""
        template_name = PREFIX_TO_TEMPLATE.get(prefix)
        if template_name is None:
            raise ValueError(
                f"Préfixe '{prefix}' inconnu. "
                f"Préfixes supportés : {list(PREFIX_TO_TEMPLATE.keys())}"
            )

        # Cache pour éviter des appels API répétés
        if template_name in self._template_cache:
            return self._template_cache[template_name]

        # Chercher le template par nom sur le serveur
        templates = self.client.get("/templates")
        for t in templates:
            if t.get("name") == template_name:
                tid = t["template_id"]
                self._template_cache[template_name] = tid
                return tid

        raise GNS3NotFoundError(resource="Template", identifier=template_name)

    def _create_node(self, user_id: str, index: int) -> GNS3Node:
        """Crée un nœud GNS3 à partir d'un identifiant utilisateur (ex: r1, s2)."""
        prefix = split_prefix(user_id)
        template_id = self._resolve_template_id(prefix)

        # Position automatique sur le canvas
        col = index % NODES_PER_ROW
        row = index // NODES_PER_ROW
        x   = CANVAS_X_START + col * CANVAS_X_STEP
        y   = CANVAS_Y_START + row * CANVAS_Y_STEP

        node = GNS3Node(self.client, self._project.id)
        node.create(name=user_id, template_id=template_id, x=x, y=y)
        print(f"  [nœud]   Créé : {user_id:5} → template='{PREFIX_TO_TEMPLATE[prefix]}'  pos=({x},{y})")
        return node

    def _create_link(
        self,
        node_a: GNS3Node, adapter_a: str, port_a: int,
        node_b: GNS3Node, adapter_b: str, port_b: int,
    ) -> GNS3Link:
        """
        Crée un lien GNS3 entre deux interfaces utilisateur (ex: r1_e1 ↔ sw1_e1).
        """
        adp_a, prt_a = self._gns3_port(node_a, adapter_a, port_a)
        adp_b, prt_b = self._gns3_port(node_b, adapter_b, port_b)

        link = GNS3Link(self.client, self._project.id)
        link.create(
            node_a_id=node_a.id, adapter_a=adp_a, port_a=prt_a,
            node_b_id=node_b.id, adapter_b=adp_b, port_b=prt_b,
        )
        print(f"  [lien]   Créé : {node_a.name}_{adapter_a}{port_a} ↔ {node_b.name}_{adapter_b}{port_b}")
        return link

    @staticmethod
    def _gns3_port(node: GNS3Node, adapter: str, port: int) -> tuple:
        """
        Interface utilisateur (e, N) → (adapter_number, port_number) GNS3.
          - switch/hub/cloud GNS3 : un seul adaptateur multi-ports → (0, N)
          - qemu (CHR), docker, vpcs… : un adaptateur par interface → (N, 0)
            (sur un CHR : e0 = ether1, e1 = ether2…)
        Le type 'w' (WiFi) n'a pas de sens côté GNS3 : traité comme Ethernet.
        """
        if node.node_type in SINGLE_ADAPTER_TYPES:
            return 0, port
        return port, 0

    def _collect_node_ids(self, topology) -> set:
        """Collecte tous les node_id uniques présents dans la topologie."""
        ids = set()
        for node_topo in topology.nodes:
            ids.add(node_topo.node_id)
            for link in node_topo.links:
                ids.add(link.source.node_id)
                ids.add(link.destination.node_id)
        return ids
