from __future__ import annotations

import json
import logging
from pathlib import Path

from shiftbot.parsing.text_utils import clean_name, name_key

log = logging.getLogger(__name__)


# spellings are never merged automatically - "Саша" and "Александра" can be
# two different people on the same shift. only data/aliases.json merges them
class NameResolver:
    def __init__(self, aliases: dict[str, list[str]] | None = None):
        self._canonical: dict[str, str] = {}
        for canonical, variants in (aliases or {}).items():
            # a key starting with "_" is a comment in the json file
            if canonical.startswith("_") or not isinstance(variants, list):
                continue
            display = clean_name(canonical)
            self._canonical[name_key(display)] = display
            for variant in variants:
                if isinstance(variant, str):
                    self._canonical[name_key(variant)] = display

    @classmethod
    def load(cls, path: Path | None) -> NameResolver:
        if path is None or not Path(path).exists():
            return cls()
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            log.warning("Could not read alias file %s - continuing without it", path)
            return cls()
        return cls(data)

    def key(self, name: str) -> str:
        raw = name_key(name)
        canonical = self._canonical.get(raw)
        return name_key(canonical) if canonical else raw

    def canonical(self, name: str) -> str:
        return self._canonical.get(name_key(name), clean_name(name))

    def __len__(self) -> int:
        return len(self._canonical)
