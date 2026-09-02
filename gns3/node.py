from .client import GNS3Client
from .exceptions import GNS3NotFoundError


class GNS3Node:
    """
    Gère les nœuds (routeurs, switches, VPCs, etc.) dans un projet GNS3.

    Usage :
        client = GNS3Client()
        node = GNS3Node(client, project_id="xxx-yyy-zzz")
        node.create(name="R1", template_id="abc-123", x=100, y=200)
        node.start()
    """

    def __init__(self, client: GNS3Client, project_id: str):
        self.client = client
        self.project_id = project_id

        # Attributs remplis après create() ou load_by_*()
        self.id: str | None = None
        self.name: str | None = None
        self.node_type: str | None = None
        self.status: str | None = None
        self.console: int | None = None
        self.console_type: str | None = None
        self.x: int = 0
        self.y: int = 0
        self._raw: dict = {}

    # ------------------------------------------------------------------
    # Création
    # ------------------------------------------------------------------

    def create(
        self,
        name: str,
        template_id: str,
        x: int = 0,
        y: int = 0,
        compute_id: str = "local",
    ) -> "GNS3Node":
        """
        Crée un nœud dans le projet à partir d'un template.

        Args:
            name        : Nom du nœud (ex: "R1", "SW1")
            template_id : UUID du template GNS3 à utiliser
            x, y        : Position sur le canvas GNS3
            compute_id  : Moteur de calcul (généralement "local")

        Returns:
            self
        """
        body = {"name": name, "x": x, "y": y, "compute_id": compute_id}
        data = self.client.post(f"/projects/{self.project_id}/templates/{template_id}", body=body)
        self._populate(data)
        return self

    def create_from_type(
        self,
        name: str,
        node_type: str,
        x: int = 0,
        y: int = 0,
        compute_id: str = "local",
        **kwargs,
    ) -> "GNS3Node":
        """
        Crée un nœud en spécifiant directement le type (sans template).
        Utile pour des nœuds simples comme 'ethernet_switch', 'cloud', 'vpcs'.

        Args:
            node_type : Type du nœud (ex: 'vpcs', 'ethernet_switch', 'cloud')
            kwargs    : Paramètres supplémentaires (properties, etc.)
        """
        body = {
            "name": name,
            "node_type": node_type,
            "x": x,
            "y": y,
            "compute_id": compute_id,
            **kwargs,
        }
        data = self.client.post(f"/projects/{self.project_id}/nodes", body=body)
        self._populate(data)
        return self

    # ------------------------------------------------------------------
    # Chargement
    # ------------------------------------------------------------------

    def load_by_id(self, node_id: str) -> "GNS3Node":
        """Charge un nœud existant par son UUID."""
        data = self.client.get(f"/projects/{self.project_id}/nodes/{node_id}")
        self._populate(data)
        return self

    def load_by_name(self, name: str) -> "GNS3Node":
        """Charge un nœud existant par son nom."""
        nodes = self.list_all()
        for n in nodes:
            if n["name"] == name:
                return self.load_by_id(n["node_id"])
        raise GNS3NotFoundError(resource="Nœud", identifier=name)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def start(self) -> "GNS3Node":
        """Démarre le nœud."""
        data = self.client.post(f"/projects/{self.project_id}/nodes/{self.id}/start")
        self._populate(data)
        return self

    def stop(self) -> "GNS3Node":
        """Arrête le nœud."""
        data = self.client.post(f"/projects/{self.project_id}/nodes/{self.id}/stop")
        self._populate(data)
        return self

    def reload(self) -> "GNS3Node":
        """Redémarre le nœud."""
        data = self.client.post(f"/projects/{self.project_id}/nodes/{self.id}/reload")
        self._populate(data)
        return self

    def suspend(self) -> "GNS3Node":
        """Suspend le nœud."""
        data = self.client.post(f"/projects/{self.project_id}/nodes/{self.id}/suspend")
        self._populate(data)
        return self

    def delete(self) -> None:
        """Supprime le nœud du projet."""
        self.client.delete(f"/projects/{self.project_id}/nodes/{self.id}")
        self.id = None
        self.name = None

    def update(self, **kwargs) -> "GNS3Node":
        """
        Met à jour les propriétés du nœud.
        Ex: node.update(x=200, y=300, name="R1_updated")
        """
        data = self.client.put(f"/projects/{self.project_id}/nodes/{self.id}", body=kwargs)
        self._populate(data)
        return self

    # ------------------------------------------------------------------
    # Informations
    # ------------------------------------------------------------------

    def list_all(self) -> list[dict]:
        """Retourne tous les nœuds du projet."""
        return self.client.get(f"/projects/{self.project_id}/nodes")

    def get_links(self) -> list[dict]:
        """Retourne les liens connectés à ce nœud."""
        return self.client.get(f"/projects/{self.project_id}/nodes/{self.id}/links")

    def get_console_info(self) -> dict:
        """Retourne les infos de console (port, type) pour se connecter."""
        return {
            "host": "localhost",
            "port": self.console,
            "type": self.console_type,
            "command": f"telnet localhost {self.console}" if self.console_type == "telnet" else f"ssh localhost -p {self.console}",
        }

    # ------------------------------------------------------------------
    # Représentation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<GNS3Node name='{self.name}' id='{self.id}' type='{self.node_type}' status='{self.status}'>"

    def summary(self) -> None:
        """Affiche un résumé lisible du nœud."""
        print("=" * 50)
        print(f"  Nœud    : {self.name}")
        print(f"  ID      : {self.id}")
        print(f"  Type    : {self.node_type}")
        print(f"  Statut  : {self.status}")
        print(f"  Console : {self.console_type}://localhost:{self.console}")
        print(f"  Position: x={self.x}, y={self.y}")
        print("=" * 50)

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _populate(self, data: dict) -> None:
        """Remplit les attributs depuis la réponse API."""
        self._raw = data
        self.id = data.get("node_id")
        self.name = data.get("name")
        self.node_type = data.get("node_type")
        self.status = data.get("status")
        self.console = data.get("console")
        self.console_type = data.get("console_type", "telnet")
        self.x = data.get("x", 0)
        self.y = data.get("y", 0)
