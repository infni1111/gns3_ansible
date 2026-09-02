class GNS3Error(Exception):
    """Erreur de base pour toutes les exceptions GNS3."""
    pass


class GNS3ConnectionError(GNS3Error):
    """Impossible de joindre le serveur GNS3."""
    def __init__(self, host: str, original: Exception = None):
        self.host = host
        self.original = original
        super().__init__(
            f"Impossible de se connecter au serveur GNS3 sur '{host}'. "
            f"Vérifiez que le container GNS3 est démarré.\n"
            f"Détail : {original}"
        )


class GNS3APIError(GNS3Error):
    """Le serveur GNS3 a retourné une erreur HTTP inattendue."""
    def __init__(self, method: str, url: str, status_code: int, message: str = ""):
        self.method = method
        self.url = url
        self.status_code = status_code
        self.message = message
        super().__init__(
            f"[{method}] {url} → HTTP {status_code}"
            + (f" : {message}" if message else "")
        )


class GNS3NotFoundError(GNS3Error):
    """Ressource GNS3 introuvable (HTTP 404)."""
    def __init__(self, resource: str, identifier: str):
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} '{identifier}' introuvable sur le serveur GNS3.")


class GNS3AlreadyExistsError(GNS3Error):
    """La ressource existe déjà (HTTP 409)."""
    def __init__(self, resource: str, name: str):
        self.resource = resource
        self.name = name
        super().__init__(f"{resource} '{name}' existe déjà.")