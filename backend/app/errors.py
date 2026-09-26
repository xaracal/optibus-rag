class StoreUnavailableError(Exception):
    """Redis is unreachable or the index has not been built yet."""


class ModelError(Exception):
    """The OpenAI embedding or chat call failed."""


class DatasetError(Exception):
    """The ingest source is missing or malformed."""
