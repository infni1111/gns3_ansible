#!/usr/bin/env python3
# cli/shell.py
# Interface ligne de commande principale — GNS3 Automation Lab
# Style inspiré des grandes CLIs (AWS, Firebase, Vercel...)

import sys
import os
import json
import time

# Permet l'import depuis la racine du projet
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gns3 import GNS3Client
from gns3.project import GNS3Project
from gns3.deploy import GNS3Deployer, PREFIX_TO_TEMPLATE
from gns3.inventory import AnsibleInventory
from gns3.exceptions import GNS3NotFoundError, GNS3ConnectionError
from gns3.topology_builder import Topology, Link, Endpoint

# ------------------------------------------------------------------
# Couleurs ANSI
# ------------------------------------------------------------------
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    WHITE   = "\033[97m"
    GRAY    = "\033[90m"

def c(color, text):
    return f"{color}{text}{C.RESET}"

# ------------------------------------------------------------------
# Composants UI
# ------------------------------------------------------------------

def clear():
    os.system("clear")

def banner():
    print()
    print(c(C.CYAN, "  ╔══════════════════════════════════════════════════╗"))
    print(c(C.CYAN, "  ║") + c(C.BOLD + C.WHITE, "         GNS3 Automation Lab  ◆  CLI v1.0        ") + c(C.CYAN, "║"))
    print(c(C.CYAN, "  ║") + c(C.GRAY,  "         Network Topology Builder & Deployer      ") + c(C.CYAN, "║"))
    print(c(C.CYAN, "  ╚══════════════════════════════════════════════════╝"))
    print()

def divider(title=""):
    if title:
        pad = 48 - len(title) - 2
        print(c(C.GRAY, f"  ── {title} " + "─" * pad))
    else:
        print(c(C.GRAY, "  " + "─" * 50))

def ok(msg):    print(c(C.GREEN,  f"  ✔  {msg}"))
def err(msg):   print(c(C.RED,    f"  ✘  {msg}"))
def info(msg):  print(c(C.CYAN,   f"  ◆  {msg}"))
def warn(msg):  print(c(C.YELLOW, f"  ⚠  {msg}"))
def step(msg):  print(c(C.BOLD,   f"\n  →  {msg}"))

def prompt(label, default=None):
    hint = f" [{c(C.GRAY, default)}]" if default else ""
    try:
        val = input(f"  {c(C.CYAN, '?')} {label}{hint} : ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise KeyboardInterrupt
    if not val and default:
        return default
    return val

def prompt_choice(label, choices):
    """Affiche un menu numéroté et retourne l'index choisi (0-based)."""
    print()
    for i, ch in enumerate(choices, 1):
        icon = ch.get("icon", "◦")
        print(f"  {c(C.CYAN, str(i))}  {icon}  {c(C.BOLD, ch['label'])}")
        if ch.get("desc"):
            print(c(C.GRAY, f"        {ch['desc']}"))
    print()
    while True:
        try:
            val = input(f"  {c(C.CYAN, '?')} {label} (1-{len(choices)}) : ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raise KeyboardInterrupt
        if val.isdigit() and 1 <= int(val) <= len(choices):
            return int(val) - 1
        err(f"Choix invalide. Entrez un nombre entre 1 et {len(choices)}.")

def spinner(msg, duration=0.8):
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    end_time = time.time() + duration
    i = 0
    while time.time() < end_time:
        print(f"\r  {c(C.CYAN, frames[i % len(frames)])}  {msg}", end="", flush=True)
        time.sleep(0.08)
        i += 1
    print(f"\r  {c(C.GREEN, '✔')}  {msg}        ")

# ------------------------------------------------------------------
# Connexion GNS3
# ------------------------------------------------------------------

def connect_client() -> GNS3Client:
    try:
        client = GNS3Client(host="http://localhost:3080")
        result = client.ping()
        ok(f"GNS3 Server v{result['version']} connecté")
        return client
    except GNS3ConnectionError:
        err("Impossible de joindre GNS3 sur localhost:3080")
        err("Vérifiez que le container GNS3 est démarré.")
        sys.exit(1)

# ------------------------------------------------------------------
# PREFIX → template
# ------------------------------------------------------------------

PREFIX_LABELS = {
    "r": ("Router",   "MikroTik CHR 7.22.1",  "🔴"),
    "s": ("Switch",   "Ethernet switch",        "🔵"),
    "f": ("Firewall", "FortiGate VM 7.6.6",    "🟠"),
    "g": ("Guest",    "VPCS",                   "🟢"),
    "c": ("Cloud",    "Cloud",                  "☁️ "),
}

def prefix_menu():
    print()
    for k, (label, tmpl, icon) in PREFIX_LABELS.items():
        print(f"  {c(C.CYAN, k)}  {icon}  {c(C.BOLD, label):20}  {c(C.GRAY, tmpl)}")
    print()

# ------------------------------------------------------------------
# Affichage d'un projet (nœuds + liens)
# ------------------------------------------------------------------

def display_project_state(state: dict):
    nodes = state.get("nodes", [])
    links = state.get("links", [])

    divider("Nœuds")
    if nodes:
        for n in nodes:
            print(f"    {c(C.CYAN, n['user_id']):15} {c(C.GRAY, '→')} {n['template']:25} pos=({n['x']},{n['y']})")
    else:
        print(c(C.GRAY, "    (aucun nœud)"))

    divider("Liens")
    if links:
        for l in links:
            src = l["source"]
            dst = l["destination"]
            print(f"    {c(C.CYAN, src['node_id'])}_{src['adapter']}{src['port']}  {c(C.GRAY, '↔')}  {c(C.CYAN, dst['node_id'])}_{dst['adapter']}{dst['port']}")
    else:
        print(c(C.GRAY, "    (aucun lien)"))
    print()

# ------------------------------------------------------------------
# Session : créer un projet
# ------------------------------------------------------------------

def session_nodes(state: dict) -> dict:
    """Collecte les nœuds interactivement."""
    step("Création des nœuds")
    info("Préfixes disponibles :")
    prefix_menu()
    info("Tapez 'done' quand tous les nœuds sont saisis.")
    print()

    while True:
        raw = prompt("Préfixe + numéro du nœud  (ex: r1, s2, g3, c1)")
        if raw.lower() == "done":
            break
        if not raw or raw[0].lower() not in PREFIX_LABELS or not raw[1:].isdigit():
            err(f"Format invalide. Ex: r1  s3  g2  c1")
            continue

        user_id = raw.lower()
        prefix  = user_id[0]
        label, tmpl, icon = PREFIX_LABELS[prefix]

        ok(f"{icon}  {user_id}  →  {label} ({tmpl})")

        # Position X
        raw_x = prompt("Position X sur le canvas", default="0")
        x = int(raw_x) if raw_x.lstrip("-").isdigit() else 0

        # Position Y
        raw_y = prompt("Position Y sur le canvas", default="0")
        y = int(raw_y) if raw_y.lstrip("-").isdigit() else 0

        state["nodes"].append({
            "user_id":  user_id,
            "prefix":   prefix,
            "template": tmpl,
            "x": x,
            "y": y,
        })
        ok(f"Nœud {user_id} ajouté  pos=({x},{y})")
        print()

    return state


def session_links(state: dict) -> dict:
    """Collecte les liens interactivement."""
    if not state["nodes"]:
        warn("Aucun nœud créé — impossible d'ajouter des liens.")
        return state

    step("Création des liens")
    node_ids = [n["user_id"] for n in state["nodes"]]
    info(f"Nœuds disponibles : {c(C.CYAN, '  '.join(node_ids))}")
    info("Adaptateurs : e = Ethernet  |  w = WiFi")
    info("Tapez 'done' quand tous les liens sont saisis.")
    print()

    while True:
        divider("Nouveau lien")

        # Source
        src_node = prompt("Nœud source  (ex: r1)")
        if src_node.lower() == "done":
            break
        if src_node not in node_ids:
            err(f"Nœud '{src_node}' inconnu. Nœuds disponibles : {node_ids}")
            continue

        src_adapter = prompt("Adaptateur source  (e/w)", default="e").lower()
        if src_adapter not in ("e", "w"):
            src_adapter = "e"

        src_port_raw = prompt("Port source  (ex: 0)", default="0")
        src_port = int(src_port_raw) if src_port_raw.isdigit() else 0

        # Destination
        dst_node = prompt("Nœud destination  (ex: s1)")
        if dst_node not in node_ids:
            err(f"Nœud '{dst_node}' inconnu. Nœuds disponibles : {node_ids}")
            continue

        dst_adapter = prompt("Adaptateur destination  (e/w)", default="e").lower()
        if dst_adapter not in ("e", "w"):
            dst_adapter = "e"

        dst_port_raw = prompt("Port destination  (ex: 0)", default="0")
        dst_port = int(dst_port_raw) if dst_port_raw.isdigit() else 0

        state["links"].append({
            "source":      {"node_id": src_node, "adapter": src_adapter, "port": src_port},
            "destination": {"node_id": dst_node, "adapter": dst_adapter, "port": dst_port},
        })
        ok(f"Lien : {src_node}_{src_adapter}{src_port}  ↔  {dst_node}_{dst_adapter}{dst_port}")
        print()

    return state


def state_to_topology(state: dict) -> Topology:
    """Convertit le state dict en objet Topology."""
    topo = Topology()
    for lk in state["links"]:
        src = lk["source"]
        dst = lk["destination"]
        ep_src = Endpoint(src["node_id"], src["adapter"], src["port"])
        ep_dst = Endpoint(dst["node_id"], dst["adapter"], dst["port"])
        topo.add_link(src["node_id"], Link(ep_src, ep_dst))
    return topo


def session_create_project(client: GNS3Client):
    clear()
    banner()
    divider("Nouveau projet")
    print()

    # Nom du projet
    name = prompt("Nom du projet")
    if not name:
        err("Nom invalide.")
        return

    # Vérifier si existe déjà
    p = GNS3Project(client)
    try:
        p.load_by_name(name)
        warn(f"Un projet '{name}' existe déjà sur le serveur.")
        choice = prompt("Écraser ? (o/n)", default="n").lower()
        if choice != "o":
            info("Opération annulée.")
            return
        p.delete()
        ok("Ancien projet supprimé.")
    except GNS3NotFoundError:
        pass

    state = {"name": name, "nodes": [], "links": []}

    # Nœuds
    state = session_nodes(state)

    if not state["nodes"]:
        warn("Aucun nœud saisi. Projet annulé.")
        return

    # Liens
    state = session_links(state)

    # Résumé avant déploiement
    clear()
    banner()
    divider(f"Résumé — {name}")
    display_project_state(state)

    confirm = prompt("Déployer sur GNS3 ? (o/n)", default="o").lower()
    if confirm != "o":
        info("Déploiement annulé.")
        return

    # Déploiement
    print()
    spinner("Connexion au serveur GNS3...", 0.5)
    topo = state_to_topology(state)

    deployer = GNS3Deployer(client, project_name=name)
    result   = deployer.deploy(topo)

    print()
    result.summary()

    # Générer l'inventaire Ansible à partir des nœuds réellement créés
    if result.nodes_ok:
        inv_path = AnsibleInventory(result).write("inventory/gns3_dynamic.yml")
        info(f"Inventaire Ansible généré : {inv_path}")

    if not result.nodes_fail and not result.links_fail:
        ok(f"Projet '{name}' déployé avec succès !")
    else:
        warn("Déploiement partiel — voir le rapport ci-dessus.")

    input(c(C.GRAY, "\n  Appuyez sur Entrée pour revenir à l'accueil..."))

# ------------------------------------------------------------------
# Session : continuer un projet
# ------------------------------------------------------------------

def session_open_project(client: GNS3Client):
    clear()
    banner()
    divider("Projets existants")
    print()

    p = GNS3Project(client)
    projects = p.list_all()

    if not projects:
        warn("Aucun projet sur le serveur.")
        input(c(C.GRAY, "\n  Appuyez sur Entrée..."))
        return

    for i, proj in enumerate(projects, 1):
        status_color = C.GREEN if proj.get("status") == "opened" else C.GRAY
        print(f"  {c(C.CYAN, str(i))}  {c(C.BOLD, proj['name']):30}  {c(status_color, proj.get('status','?'))}")

    print()
    name = prompt("Nom du projet à ouvrir")
    if not name:
        return

    try:
        p.load_by_name(name)
    except GNS3NotFoundError:
        err(f"Projet '{name}' introuvable.")
        input(c(C.GRAY, "\n  Appuyez sur Entrée..."))
        return

    clear()
    banner()
    divider(f"Projet : {p.name}")
    print()
    info(f"ID     : {c(C.GRAY, p.id)}")
    info(f"Statut : {c(C.GREEN if p.status == 'opened' else C.GRAY, p.status)}")
    info(f"Chemin : {c(C.GRAY, p.path)}")
    print()

    # Afficher les nœuds et liens du projet
    from gns3.node import GNS3Node
    from gns3.link import GNS3Link

    node_helper = GNS3Node(client, p.id)
    link_helper = GNS3Link(client, p.id)

    nodes = node_helper.list_all()
    links = link_helper.list_all()

    divider("Nœuds")
    if nodes:
        for n in nodes:
            print(f"    {c(C.CYAN, n['name']):15}  {c(C.GRAY, n['node_type']):20}  status={n.get('status','?')}")
    else:
        print(c(C.GRAY, "    (aucun nœud)"))

    divider("Liens")
    if links:
        for l in links:
            eps = l.get("nodes", [])
            if len(eps) >= 2:
                a, b = eps[0], eps[1]
                print(f"    node:{a['node_id'][:8]}… port={a['port_number']}  ↔  node:{b['node_id'][:8]}… port={b['port_number']}")
    else:
        print(c(C.GRAY, "    (aucun lien)"))

    print()
    input(c(C.GRAY, "  Appuyez sur Entrée pour revenir à l'accueil..."))

# ------------------------------------------------------------------
# Session : supprimer un projet
# ------------------------------------------------------------------

def session_delete_project(client: GNS3Client):
    clear()
    banner()
    divider("Supprimer un projet")
    print()

    p = GNS3Project(client)
    projects = p.list_all()

    if not projects:
        warn("Aucun projet sur le serveur.")
        input(c(C.GRAY, "\n  Appuyez sur Entrée..."))
        return

    for i, proj in enumerate(projects, 1):
        print(f"  {c(C.CYAN, str(i))}  {c(C.BOLD, proj['name'])}")

    print()
    name = prompt("Nom du projet à supprimer")
    if not name:
        return

    try:
        p.load_by_name(name)
    except GNS3NotFoundError:
        err(f"Projet '{name}' introuvable.")
        input(c(C.GRAY, "\n  Appuyez sur Entrée..."))
        return

    warn(f"Vous allez supprimer définitivement '{name}'.")
    confirm = prompt("Confirmer ? (o/n)", default="n").lower()
    if confirm != "o":
        info("Annulé.")
        input(c(C.GRAY, "\n  Appuyez sur Entrée..."))
        return

    spinner(f"Suppression de '{name}'...", 0.6)
    p.delete()
    ok(f"Projet '{name}' supprimé.")
    input(c(C.GRAY, "\n  Appuyez sur Entrée pour revenir à l'accueil..."))

# ------------------------------------------------------------------
# Accueil principal
# ------------------------------------------------------------------

def home(client: GNS3Client):
    while True:
        clear()
        banner()

        divider("Accueil")
        print()

        idx = prompt_choice("Que voulez-vous faire ?", [
            {"icon": "✦", "label": "Créer un projet",    "desc": "Nouveau projet + nœuds + liens → déploiement GNS3"},
            {"icon": "◈", "label": "Ouvrir un projet",   "desc": "Voir les nœuds et liens d'un projet existant"},
            {"icon": "✕", "label": "Supprimer un projet", "desc": "Supprime définitivement un projet du serveur"},
            {"icon": "⏻", "label": "Quitter",             "desc": ""},
        ])

        if idx == 0:
            session_create_project(client)
        elif idx == 1:
            session_open_project(client)
        elif idx == 2:
            session_delete_project(client)
        elif idx == 3:
            clear()
            banner()
            print(c(C.GRAY, "  À bientôt.\n"))
            break

# ------------------------------------------------------------------
# Point d'entrée
# ------------------------------------------------------------------

def main():
    clear()
    banner()
    divider("Connexion")
    print()
    client = connect_client()
    print()
    time.sleep(0.4)
    home(client)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(c(C.GRAY, "\n\n  Session interrompue. À bientôt.\n"))
        sys.exit(0)
