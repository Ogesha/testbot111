import re
from typing import List
from .config import CategoryConf

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())

def pick_category_name(title: str, cat_confs: List[CategoryConf]) -> str | None:
    t = _norm(title)
    for c in cat_confs:
        for kw in c.keywords:
            if _norm(kw) in t:
                return c.name
    return None
