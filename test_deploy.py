# test_deploy.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gns3 import GNS3Client
from gns3.deploy import GNS3Deployer, PREFIX_TO_TEMPLATE
from gns3.project import GNS3Project
from gns3.exceptions import GNS3NotFoundError
from gns3.topology_builder import Topology, Link, Endpoint

PROJECT_NAME = "_test_labo_v2"

def make_client():
    return GNS3Client(host="http://localhost:3080")

def clean_project(client):
    """Supprime le projet de test s'il existe."""
    p = GNS3Project(client)
    try:
        p.load_by_name(PROJECT_NAME)
        p.delete()
        print(f"  [clean] Projet '{PROJECT_NAME}' supprimé.")
    except GNS3NotFoundError:
        pass

def build_topology() -> Topology:
    """
    Topologie :
        Cloud1_e0  ↔  s1_e0
        s1_e1      ↔  r1_e0
        s1_e2      ↔  g1_e0   (VPCS)
    """
    topo = Topology()

    ep_cloud_e0 = Endpoint("c1", "e", 0)
    ep_s1_e0    = Endpoint("s1", "e", 0)
    ep_s1_e1    = Endpoint("s1", "e", 1)
    ep_s1_e2    = Endpoint("s1", "e", 2)
    ep_r1_e0    = Endpoint("r1", "e", 0)
    ep_g1_e0    = Endpoint("g1", "e", 0)

    topo.add_link("c1", Link(ep_cloud_e0, ep_s1_e0))
    topo.add_link("s1", Link(ep_s1_e1,    ep_r1_e0))
    topo.add_link("s1", Link(ep_s1_e2,    ep_g1_e0))

    return topo

# ------------------------------------------------------------------
# Tests unitaires
# ------------------------------------------------------------------

def test_prefix_mapping():
    print("\n[TEST] Mapping préfixes...")
    expected = {"r", "s", "f", "g", "c"}
    actual   = set(PREFIX_TO_TEMPLATE.keys())
    assert expected == actual, f"Mapping incomplet : {actual}"
    print("  ✔ Tous les préfixes présents.")

def test_topology_structure():
    print("\n[TEST] Structure topologie...")
    topo = build_topology()
    node_ids = {n.node_id for n in topo.nodes}
    assert "c1" in node_ids
    assert "s1" in node_ids
    total_links = sum(len(n.links) for n in topo.nodes)
    assert total_links == 3, f"Attendu 3 liens, obtenu {total_links}"
    print("  ✔ Structure correcte.")

def test_collect_node_ids():
    print("\n[TEST] Collecte node_ids...")
    client   = make_client()
    deployer = GNS3Deployer(client, project_name=PROJECT_NAME)
    ids      = deployer._collect_node_ids(build_topology())
    assert {"c1", "s1", "r1", "g1"} == ids, f"IDs incorrects : {ids}"
    print(f"  ✔ node_ids : {sorted(ids)}")

# ------------------------------------------------------------------
# Tests d'intégration
# ------------------------------------------------------------------

def test_ping():
    print("\n[TEST] Ping GNS3...")
    result = make_client().ping()
    assert "version" in result
    print(f"  ✔ GNS3 v{result['version']} accessible.")

def test_deploy():
    print("\n[TEST] Déploiement topologie...")
    client = make_client()
    clean_project(client)
    topo   = build_topology()
    topo.summary()

    deployer = GNS3Deployer(client, project_name=PROJECT_NAME)
    result   = deployer.deploy(topo)
    result.summary()

    assert len(result.nodes_fail) == 0, f"Nœuds en erreur : {result.nodes_fail}"
    assert len(result.links_fail) == 0, f"Liens en erreur  : {result.links_fail}"
    assert len(result.nodes_ok)   == 4, f"Attendu 4 nœuds, obtenu {len(result.nodes_ok)}"
    assert len(result.links_ok)   == 3, f"Attendu 3 liens, obtenu {len(result.links_ok)}"
    print("  ✔ Déploiement complet.")

def test_idempotent():
    print("\n[TEST] Idempotence...")
    client   = make_client()
    deployer = GNS3Deployer(client, project_name=PROJECT_NAME)
    result   = deployer.deploy(build_topology())
    result.summary()
    print("  ✔ Double déploiement sans crash.")

# ------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------

UNIT_TESTS        = [test_prefix_mapping, test_topology_structure, test_collect_node_ids]
INTEGRATION_TESTS = [test_ping, test_deploy, test_idempotent]

def run_all():
    print("\n╔══════════════════════════════════════════╗")
    print("║         TESTS — GNS3 Deployer v2         ║")
    print("╚══════════════════════════════════════════╝")

    print("\n── Tests unitaires ──")
    u = 0
    for t in UNIT_TESTS:
        try:    t(); u += 1
        except Exception as e: print(f"  ✘ {t.__name__} : {e}")
    print(f"\n  Résultat : {u}/{len(UNIT_TESTS)} passés")

    print("\n── Tests intégration ──")
    i = 0
    for t in INTEGRATION_TESTS:
        try:    t(); i += 1
        except Exception as e: print(f"  ✘ {t.__name__} : {e}")
    print(f"\n  Résultat : {i}/{len(INTEGRATION_TESTS)} passés")
    print("\n══════════════════════════════════════════\n")

if __name__ == "__main__":
    run_all()
