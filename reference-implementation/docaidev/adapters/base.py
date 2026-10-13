class AdapterError(Exception):
    pass


class Adapter:
    """Every tracker implements these two methods; nothing else is required."""
    name = "base"

    def __init__(self, settings):
        self.settings = settings

    def test_connection(self):
        """Return (ok: bool, message: str). Used by setup and pre-flight."""
        raise NotImplementedError

    def fetch(self, key):
        """Return a schema.WorkItem for the given key."""
        raise NotImplementedError
