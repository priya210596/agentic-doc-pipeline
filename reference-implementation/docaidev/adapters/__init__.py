from .base import Adapter, AdapterError
from .github import GitHubAdapter
from .jira import JiraAdapter
from .paste import PasteAdapter

REGISTRY = {"github": GitHubAdapter, "jira": JiraAdapter, "paste": PasteAdapter}


def get_adapter(name, settings=None):
    if name not in REGISTRY:
        raise AdapterError("Unknown tracker '%s'. Available: %s" % (name, ", ".join(sorted(REGISTRY))))
    return REGISTRY[name](settings or {})
