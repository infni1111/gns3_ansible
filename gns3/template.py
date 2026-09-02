from .client import GNS3Client
from .exceptions import GNS3NotFoundError


class GNS3Template:
    """
    Gère les templates GNS3 (modèles d'équipements disponibles sur le serveur).
    Un template est le modèle à partir duquel on crée des nœuds.

    Usage :
        client = GNS3Client()
        template = GNS3Template(client)
        templates = template.list_all()
        t = template.find_by_name("Cisco IOS")
        print(t["template_id"])
    """

    def __init__(self, client: GNS3Client):
        self.client = client

        # Attributs remplis après load_by_*()
        self.id: str | None = None
        self.name: str | None = None
        self.template_type: str | None = None
        self.category: str | None = None
        self._raw: dict = {}

    # ------------------------------------------------------------------
    # Chargement
    # ------------------------------------------------------------------

    def load_by_id(self, template_id: str) -> "GNS3Template":
        """Charge un template par son UUID."""
        data = self.client.get(f"/templates/{template_id}")
        self._populate(data)
        return self

    def find_by_name(self, name: str) -> dict:
        """
        Cherche un template par son nom (recherche exacte).
        Retourne le dict brut du template.
        Lève GNS3NotFoundError si introuvable.
        """
        templates = self.list_all()
        for t in templates:
            if t.get("name") == name:
                self._populate(t)
                return t
        raise GNS3NotFoundError(resource="Template", identifier=name)

    def search_by_name(self, keyword: str) -> list[dict]:
        """
        Cherche tous les templates dont le nom contient `keyword` (insensible à la casse).
        Utile pour explorer les templates disponibles.
        """
        keyword_lower = keyword.lower()
        templates = self.list_all()
        return [t for t in templates if keyword_lower in t.get("name", "").lower()]

    # ------------------------------------------------------------------
    # Informations
    # ------------------------------------------------------------------

    def list_all(self) -> list[dict]:
        """Retourne tous les templates disponibles sur le serveur GNS3."""
        return self.client.get("/templates")

    def list_by_category(self, category: str) -> list[dict]:
        """
        Filtre les templates par catégorie.
        Catégories communes : 'router', 'switch', 'guest', 'firewall'
        """
        templates = self.list_all()
        return [t for t in templates if t.get("category") == category]

    def print_all(self) -> None:
        """Affiche tous les templates disponibles de façon lisible."""
        templates = self.list_all()
        print(f"\n{'='*60}")
        print(f"  Templates disponibles ({len(templates)} trouvés)")
        print(f"{'='*60}")
        for t in templates:
            print(
                f"  [{t.get('category', '?'):10}] "
                f"{t.get('name', '?'):30} "
                f"id={t.get('template_id', '?')}"
            )
        print(f"{'='*60}\n")

    # ------------------------------------------------------------------
    # Représentation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<GNS3Template name='{self.name}' id='{self.id}' type='{self.template_type}'>"

    def summary(self) -> None:
        """Affiche un résumé lisible du template."""
        print("=" * 50)
        print(f"  Template  : {self.name}")
        print(f"  ID        : {self.id}")
        print(f"  Type      : {self.template_type}")
        print(f"  Catégorie : {self.category}")
        print("=" * 50)

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _populate(self, data: dict) -> None:
        """Remplit les attributs depuis la réponse API."""
        self._raw = data
        self.id = data.get("template_id")
        self.name = data.get("name")
        self.template_type = data.get("template_type")
        self.category = data.get("category")