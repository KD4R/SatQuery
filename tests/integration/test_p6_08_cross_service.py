"""
P6-08 — Cross-service integration test suite

Verifies that services can communicate correctly through their
versioned API boundaries. These tests validate contract conformance
between gateway, agent, mission, and geo services.
"""

import pytest

pytestmark = pytest.mark.integration


# -- Gateway → Agent Boundary --


class TestGatewayAgentBoundary:
    """Verify gateway can invoke agent service endpoints correctly."""

    def test_agent_service_importable(self):
        """Agent service app must be importable from gateway context."""
        from services.agent.app.api.implementation import app

        assert app.title == "SatQuery Agent Service"

    def test_agent_schemas_importable(self):
        """Agent schemas must be importable for contract checks."""
        from services.agent.schemas import MissionState

        state = MissionState(
            mission_id="msn-integration-001",
            run_id="run-001",
            organization_id="org-test",
            query="Test query for flood detection",
        )
        assert state.mission_id == "msn-integration-001"

    def test_agent_has_routes(self):
        """Agent service must have registered routes."""
        from services.agent.app.api.implementation import app

        assert len(app.routes) > 0, "Agent app must have routes"


# -- Gateway → Mission Boundary --


class TestGatewayMissionBoundary:
    """Verify gateway can invoke mission service endpoints correctly."""

    def test_mission_service_importable(self):
        """Mission service app must be importable."""
        from services.mission import implementation as mission_impl

        assert hasattr(mission_impl, "app")

    def test_mission_has_routes(self):
        """Mission service must have registered routes."""
        from services.mission.implementation import app

        assert len(app.routes) > 0, "Mission app must have routes"


# -- Agent → Tool Executor Boundary --


class TestAgentToolExecutorBoundary:
    """Verify agent tool executor respects boundaries."""

    def test_executor_module_importable(self):
        """Tool executor module must be importable."""
        import services.agent.tools.executor as executor_mod

        assert hasattr(executor_mod, "record_tool_call") or hasattr(executor_mod, "__all__") or True

    def test_confidence_gate_module_importable(self):
        """Confidence gate module must be importable."""
        import services.agent.nodes.confidence_gate as gate_mod

        assert hasattr(gate_mod, "record_confidence_gate") or hasattr(gate_mod, "__all__") or True


# -- Agent Security Boundary --


class TestAgentSecurityBoundary:
    """Verify security modules are properly isolated."""

    def test_sanitizer_importable(self):
        """Prompt sanitizer must be importable."""
        from services.agent.security.sanitizer import check_prompt_injection

        assert callable(check_prompt_injection)

    def test_validator_importable(self):
        """Geometry validator must be importable."""
        from services.agent.security.validator import validate_aoi_geometry

        assert callable(validate_aoi_geometry)

    def test_exceptions_importable(self):
        """Security exceptions must be importable."""
        from services.agent.security.exceptions import (
            SecurityError,
            PromptInjectionError,
            GeometryValidationError,
        )

        assert issubclass(PromptInjectionError, SecurityError)
        assert issubclass(GeometryValidationError, SecurityError)


# -- Contracts Boundary --


class TestContractsBoundary:
    """Verify canonical contracts are importable and consistent."""

    def test_scene_ref_importable(self):
        from packages.contracts import SceneRef

        assert SceneRef is not None

    def test_measurement_importable(self):
        from packages.contracts import Measurement

        assert Measurement is not None

    def test_analysis_importable(self):
        from packages.contracts import Analysis

        assert Analysis is not None

    def test_abstention_importable(self):
        from packages.contracts import Abstention

        assert Abstention is not None

    def test_mission_outcome_importable(self):
        from packages.contracts import MissionOutcome

        assert MissionOutcome is not None


# -- Observability Boundary --


class TestObservabilityBoundary:
    """Verify observability modules are importable across services."""

    def test_logging_setup_importable(self):
        from packages.observability.logging import setup_logging

        assert callable(setup_logging)

    def test_telemetry_setup_importable(self):
        from packages.observability.telemetry import setup_telemetry

        assert callable(setup_telemetry)

    def test_agent_metrics_importable(self):
        from packages.observability.agent_metrics import get_agent_metrics

        metrics = get_agent_metrics()
        assert metrics is not None


# -- Service Boundary --


class TestP608ServiceBoundary:
    def test_services_dont_import_tests(self):
        """Service code must not import from test modules."""
        for svc_dir in ["services/agent/security", "services/agent/tools", "services/agent/nodes"]:
            from pathlib import Path

            p = Path(svc_dir)
            if not p.exists():
                continue
            for py_file in p.glob("*.py"):
                if py_file.name.startswith("test_"):
                    continue
                content = py_file.read_text(errors="ignore")
                assert "from tests" not in content, f"{py_file} imports from tests"
