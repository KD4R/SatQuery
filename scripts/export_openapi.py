"""
scripts/export_openapi.py
Exports the OpenAPI JSON schemas for the Gateway and Mission services (P1-14, P1-16).
"""

import json
import os
import sys

# Ensure packages can be found if script is run from root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
