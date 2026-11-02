"""LangChain tools the worker may call. Which ones a role sees is decided per model call by
RoleToolsMiddleware (auth.allowed_tools); the tool gate re-checks every call."""
from .regulation import get_article, search_regulation  # noqa: F401
from .register import lookup_register  # noqa: F401
from .review import request_dpo_review  # noqa: F401

ALL_TOOLS = [search_regulation, get_article, lookup_register, request_dpo_review]
TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}
READ_TOOLS = [search_regulation, get_article, lookup_register]
