"""Instance Jinja2Templates partagée entre tous les modules web.

On désactive le cache Jinja2 en assignant None à env.cache,
pour éviter le bug Starlette/Jinja2 où env.globals (dict non-hashable)
est utilisé comme clé de cache LRU.
"""

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="web/templates")
templates.env.cache = None  # type: ignore[assignment]
