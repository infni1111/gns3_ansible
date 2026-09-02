from .client import GNS3Client
from .exceptions import GNS3NotFoundError


class GNS3Project:
    """
    Gère les projets GNS3 via l'API REST.

    Usage — créer un projet :
        client = GNS3Client()
        project = GNS3Project(client)
        project.create("mon_labo")
        print(project.id)

    Usage — charger un projet existant par nom :
        project = GNS3Project(client)
        project.load_by_name("mon_labo")
        print(project.id)
    """

    def __init__(self, client: GNS3Client):

        self.client = client
        # Attributs remplis après create() ou load_by_*()
        self.id: str | None = None
        self.name: str | None = None
        self.status: str | None = None
        self.path: str | None = None
        self._raw: dict = {}

    # ------------------------------------------------------------------
    # Création
    # ------------------------------------------------------------------

    def create(self, name: str, auto_open: bool = True, auto_start: bool = False) -> "GNS3Project":
        """
        Crée un nouveau projet GNS3.

        Args:
            name       : Nom du projet
            auto_open  : Ouvrir le projet automatiquement après création
            auto_start : Démarrer les nœuds automatiquement

        Returns:
            self (pour chaîner les appels)
        """
        body = {
            "name": name,
            "auto_open": auto_open,
            "auto_start": auto_start,
        }
        data = self.client.post("/projects", body=body)
        self._populate(data)
        return self

    # ------------------------------------------------------------------
    # Chargement
    # ------------------------------------------------------------------

    def load_by_id(self, project_id: str) -> "GNS3Project":
        """Charge un projet existant par son UUID."""
        data = self.client.get(f"/projects/{project_id}")
        self._populate(data)
        return self

    def load_by_name(self, name: str) -> "GNS3Project":
        """
        Charge un projet existant par son nom.
        Lève GNS3NotFoundError si aucun projet ne correspond.
        """
        projects = self.list_all()
        for p in projects:
            if p["name"] == name:
                return self.load_by_id(p["project_id"])
        raise GNS3NotFoundError(resource="Projet", identifier=name)

    # ------------------------------------------------------------------
    # Actions sur le projet
    # ------------------------------------------------------------------

    def open(self) -> "GNS3Project":
        """Ouvre le projet (nécessaire pour pouvoir le modifier)."""
        data = self.client.post(f"/projects/{self.id}/open")
        self._populate(data)
        return self

    def close(self) -> "GNS3Project":
        """Ferme le projet."""
        data = self.client.post(f"/projects/{self.id}/close")
        self._populate(data)
        return self

    def delete(self) -> None:
        """Supprime définitivement le projet."""
        self.client.delete(f"/projects/{self.id}")
        self.id = None
        self.name = None
        self.status = None

    def duplicate(self, new_name: str) -> "GNS3Project":
        """Duplique le projet avec un nouveau nom."""
        data = self.client.post(f"/projects/{self.id}/duplicate", body={"name": new_name})
        new_project = GNS3Project(self.client)
        new_project._populate(data)
        return new_project

    # ------------------------------------------------------------------
    # Informations
    # ------------------------------------------------------------------

    def get_info(self) -> dict:
        """Retourne les informations brutes du projet depuis l'API."""
        data = self.client.get(f"/projects/{self.id}")
        self._populate(data)
        return self._raw

    def list_all(self) -> list[dict]:
        """Retourne la liste de tous les projets du serveur GNS3."""
        return self.client.get("/projects")

    def get_stats(self) -> dict:
        """Retourne les statistiques du projet (nœuds, liens, etc.)."""
        return self.client.get(f"/projects/{self.id}/stats")

    # ------------------------------------------------------------------
    # Représentation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<GNS3Project name='{self.name}' id='{self.id}' status='{self.status}'>"

    def summary(self) -> None:
        """Affiche un résumé lisible du projet."""
        print("=" * 50)
        print(f"  Projet  : {self.name}")
        print(f"  ID      : {self.id}")
        print(f"  Statut  : {self.status}")
        print(f"  Chemin  : {self.path}")
        print("=" * 50)

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _populate(self, data: dict) -> None:
        """Remplit les attributs depuis la réponse API."""
        self._raw = data
        self.id = data.get("project_id")
        self.name = data.get("name")
        self.status = data.get("status")
        self.path = data.get("path")
