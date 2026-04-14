"""Instance Jinja2Templates partagée entre tous les modules web.

On désactive le cache Jinja2 (cache_size=0) pour éviter le bug
d'interaction Starlette/Jinja2 où env.globals (dict non-hashable)
est utilisé comme clé de cache LRU.
"""

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="web/templates", cache_size=0)
