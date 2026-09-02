from .client import GNS3Client
from .exceptions import GNS3NotFoundError


class GNS3Link:
    """
    Gère les liens (câbles) entre les nœuds dans un projet GNS3.

    Un lien relie deux ports de deux nœuds différents.
    Chaque extrémité est un dict : { node_id, adapter_number, port_number }

    Usage :
        client = GNS3Client()
        link = GNS3Link(client, project_id="xxx-yyy-zzz")
        link.create(
            node_a_id="id-routeur1", adapter_a=0, port_a=0,
            node_b_id="id-routeur2", adapter_b=0, port_b=0,
        )
    """

    def __init__(self, client: GNS3Client, project_id: str):
        self.client = client
        self.project_id = project_id

        # Attributs remplis après create() ou load_by_id()
        self.id: str | None = None
        self.link_type: str | None = None
        self.nodes: list[dict] = []
        self._raw: dict = {}

    # ------------------------------------------------------------------
    # Création
    # ------------------------------------------------------------------

    def create(
        self,
        node_a_id: str,
        adapter_a: int,
        port_a: int,
        node_b_id: str,
        adapter_b: int,
        port_b: int,
    ) -> "GNS3Link":
        """
        Crée un lien (câble) entre deux ports de deux nœuds.

        Args:
            node_a_id  : UUID du premier nœud
            adapter_a  : Numéro d'adaptateur du premier nœud (généralement 0)
            port_a     : Numéro de port du premier nœud
            node_b_id  : UUID du deuxième nœud
            adapter_b  : Numéro d'adaptateur du deuxième nœud
            port_b     : Numéro de port du deuxième nœud

        Returns:
            self
        """
        body = {
            "nodes": [
                {"node_id": node_a_id, "adapter_number": adapter_a, "port_number": port_a},
                {"node_id": node_b_id, "adapter_number": adapter_b, "port_number": port_b},
            ]
        }
        data = self.client.post(f"/projects/{self.project_id}/links", body=body)
        self._populate(data)
        return self

    # ------------------------------------------------------------------
    # Chargement
    # ------------------------------------------------------------------

    def load_by_id(self, link_id: str) -> "GNS3Link":
        """Charge un lien existant par son UUID."""
        data = self.client.get(f"/projects/{self.project_id}/links/{link_id}")
        self._populate(data)
        return self

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def delete(self) -> None:
        """Supprime le lien (déconnecte les deux nœuds)."""
        self.client.delete(f"/projects/{self.project_id}/links/{self.id}")
        self.id = None
        self.nodes = []

    def start_capture(self, data_link_type: str = "DLT_EN10MB") -> dict:
        """
        Démarre une capture Wireshark sur ce lien.

        Args:
            data_link_type : Type de lien (DLT_EN10MB pour Ethernet, DLT_PPP_SERIAL pour PPP)
        """
        body = {"data_link_type": data_link_type}
        return self.client.post(
            f"/projects/{self.project_id}/links/{self.id}/start_capture",
            body=body,
        )

    def stop_capture(self) -> None:
        """Arrête la capture Wireshark."""
        self.client.post(f"/projects/{self.project_id}/links/{self.id}/stop_capture")

    # ------------------------------------------------------------------
    # Informations
    # ------------------------------------------------------------------

    def list_all(self) -> list[dict]:
        """Retourne tous les liens du projet."""
        return self.client.get(f"/projects/{self.project_id}/links")

    def get_endpoints(self) -> dict:
        """
        Retourne les deux extrémités du lien de façon lisible.
        """
        if len(self.nodes) < 2:
            return {}
        a, b = self.nodes[0], self.nodes[1]
        return {
            "endpoint_a": {
                "node_id": a.get("node_id"),
                "adapter": a.get("adapter_number"),
                "port": a.get("port_number"),
            },
            "endpoint_b": {
                "node_id": b.get("node_id"),
                "adapter": b.get("adapter_number"),
                "port": b.get("port_number"),
            },
        }

    # ------------------------------------------------------------------
    # Représentation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        endpoints = self.get_endpoints()
        a = endpoints.get("endpoint_a", {})
        b = endpoints.get("endpoint_b", {})
        return (
            f"<GNS3Link id='{self.id}' "
            f"{a.get('node_id', '?')}:{a.get('adapter', '?')}/{a.get('port', '?')} "
            f"↔ "
            f"{b.get('node_id', '?')}:{b.get('adapter', '?')}/{b.get('port', '?')}>"
        )

    def summary(self) -> None:
        """Affiche un résumé lisible du lien."""
        endpoints = self.get_endpoints()
        a = endpoints.get("endpoint_a", {})
        b = endpoints.get("endpoint_b", {})
        print("=" * 50)
        print(f"  Lien ID : {self.id}")
        print(f"  Type    : {self.link_type}")
        print(f"  De      : node={a.get('node_id')} adapter={a.get('adapter')} port={a.get('port')}")
        print(f"  Vers    : node={b.get('node_id')} adapter={b.get('adapter')} port={b.get('port')}")
        print("=" * 50)

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _populate(self, data: dict) -> None:
        """Remplit les attributs depuis la réponse API."""
        self._raw = data
        self.id = data.get("link_id")
        self.link_type = data.get("link_type")
        self.nodes = data.get("nodes", [])
