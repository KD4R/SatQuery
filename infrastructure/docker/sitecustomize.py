# ─── Runtime support: hyphenated package alias (P6 containerisation) ──────────
# Installed into site-packages of the satquery image. Python auto-imports
# `sitecustomize` at interpreter startup, so EVERY process in the container
# (uvicorn, celery, shells, scripts) gets this alias — not just pytest, which
# is the only place conftest.py's equivalent finder runs.
#
# Why: services/agent imports `services.eo_data`, but the physical directory
# is `services/eo-data/` (hyphen), which Python cannot resolve as a module
# path. This finder transparently maps the canonical underscore name onto the
# physical hyphenated directory. Remove this file when the directory is
# renamed to services/eo_data/ (the proper long-term fix).

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import os
import sys

_repo_root = os.environ.get("SATQUERY_REPO_ROOT", "/app")

_HYPHEN_ALIASES = {
    "services.eo_data": os.path.join(_repo_root, "services", "eo-data"),
}


class _HyphenServiceFinder(importlib.abc.MetaPathFinder):
    """Resolves `services.eo_data.*` -> `services/eo-data/*` at import time."""

    def find_spec(self, fullname, path, target=None):
        for alias_prefix, physical_dir in _HYPHEN_ALIASES.items():
            if fullname == alias_prefix:
                init_path = os.path.join(physical_dir, "__init__.py")
                if os.path.exists(init_path):
                    spec = importlib.util.spec_from_file_location(
                        fullname,
                        init_path,
                        submodule_search_locations=[physical_dir],
                    )
                else:
                    spec = importlib.machinery.ModuleSpec(fullname, None, is_package=True)
                    spec.submodule_search_locations = [physical_dir]
                return spec
            if fullname.startswith(alias_prefix + "."):
                subpath = fullname[len(alias_prefix) + 1 :].replace(".", os.sep)
                for candidate in (
                    os.path.join(physical_dir, subpath + ".py"),
                    os.path.join(physical_dir, subpath, "__init__.py"),
                ):
                    if os.path.exists(candidate):
                        search_locs = (
                            [os.path.join(physical_dir, subpath)]
                            if candidate.endswith("__init__.py")
                            else None
                        )
                        return importlib.util.spec_from_file_location(
                            fullname,
                            candidate,
                            submodule_search_locations=search_locs,
                        )
        return None


sys.meta_path.insert(0, _HyphenServiceFinder())
