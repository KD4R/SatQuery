"""
scripts/export_openapi.py
Exports the OpenAPI JSON schemas for the Gateway and Mission services (P1-14, P1-16).
"""

import json
import os
import sys

# Ensure packages can be found if script is run from root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import importlib
import importlib.abc
import importlib.machinery
import importlib.util

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_HYPHEN_ALIASES = {
    "services.eo_data": os.path.join(_repo_root, "services", "eo-data"),
    "services.geo": os.path.join(_repo_root, "services", "geo"),
}

class _HyphenServiceFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        for alias_prefix, physical_dir in _HYPHEN_ALIASES.items():
            if fullname == alias_prefix:
                init_path = os.path.join(physical_dir, "__init__.py")
                if os.path.exists(init_path):
                    return importlib.util.spec_from_file_location(fullname, init_path, submodule_search_locations=[physical_dir])
                spec = importlib.machinery.ModuleSpec(fullname, None, is_package=True)
                spec.submodule_search_locations = [physical_dir]
                return spec
            if fullname.startswith(alias_prefix + "."):
                subpath = fullname[len(alias_prefix) + 1 :].replace(".", os.sep)
                for candidate in [os.path.join(physical_dir, subpath + ".py"), os.path.join(physical_dir, subpath, "__init__.py")]:
                    if os.path.exists(candidate):
                        return importlib.util.spec_from_file_location(
                            fullname, candidate, submodule_search_locations=([os.path.join(physical_dir, subpath)] if candidate.endswith("__init__.py") else None)
                        )
        return None

sys.meta_path.insert(0, _HyphenServiceFinder())

from services.agent.app.api.implementation import app as agent_app  # noqa: E402
from services.gateway.implementation import app as gateway_app  # noqa: E402
from services.mission.implementation import app as mission_app  # noqa: E402


def export_openapi(app, output_path: str):
    schema = app.openapi()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(schema, f, indent=2)
    print(f"Exported OpenAPI schema to {output_path}")


if __name__ == "__main__":
    export_openapi(gateway_app, "docs/openapi/gateway.json")
    export_openapi(mission_app, "docs/openapi/mission.json")
    export_openapi(agent_app, "docs/openapi/agent.json")
