"""
packages/observability/agent_metrics.py — Agent telemetry & Prometheus/OTel metrics.
"""

from typing import Any, Dict, List


class AgentMetrics:
    """
    In-memory and Prometheus-compatible metrics collector for P2 Agent subsystem.
    Exposes:
      - agent_node_duration_ms
      - agent_tool_calls_total
      - confidence_gate_total
      - prompt_injection_block_total
    """

    def __init__(self):
        self._node_durations: Dict[str, List[float]] = {}
        self._tool_calls: Dict[str, int] = {}
        self._confidence_gate: Dict[str, int] = {"passed": 0, "failed": 0}
        self._prompt_injection_blocks: int = 0

    def record_node_duration(self, node_name: str, duration_ms: float) -> None:
        if not node_name:
            raise ValueError("Node name cannot be empty")
        if duration_ms < 0.0:
            raise ValueError("Duration cannot be negative")
        self._node_durations.setdefault(node_name, []).append(duration_ms)

    def record_tool_call(self, tool_name: str, status: str = "success") -> None:
        if not tool_name:
            raise ValueError("Tool name cannot be empty")
        key = f"{tool_name}:{status}"
        self._tool_calls[key] = self._tool_calls.get(key, 0) + 1

    def record_confidence_gate(self, passed: bool, action: str = "PROCEED") -> None:
        key = "passed" if passed else "failed"
        self._confidence_gate[key] = self._confidence_gate.get(key, 0) + 1

    def record_prompt_injection_block(self) -> None:
        self._prompt_injection_blocks += 1

    def get_snapshot(self) -> Dict[str, Any]:
        return {
            "agent_node_duration_ms": {
                node: {
                    "count": len(durs),
                    "avg_ms": round(sum(durs) / len(durs), 2) if durs else 0.0,
                    "max_ms": round(max(durs), 2) if durs else 0.0,
                }
                for node, durs in self._node_durations.items()
            },
            "agent_tool_calls_total": dict(self._tool_calls),
            "confidence_gate_total": dict(self._confidence_gate),
            "prompt_injection_block_total": self._prompt_injection_blocks,
        }

    def reset(self) -> None:
        self._node_durations.clear()
        self._tool_calls.clear()
        self._confidence_gate = {"passed": 0, "failed": 0}
        self._prompt_injection_blocks = 0


_global_metrics = AgentMetrics()


def get_agent_metrics() -> AgentMetrics:
    return _global_metrics
