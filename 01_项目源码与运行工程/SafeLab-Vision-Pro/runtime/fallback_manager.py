from __future__ import annotations

from dataclasses import dataclass

from runtime.interfaces import FallbackMode, HealthStatus


@dataclass(frozen=True)
class FallbackDecision:
    mode: FallbackMode
    can_run_pipeline: bool
    use_mock_detection: bool
    use_shell_tools: bool
    reasons: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "can_run_pipeline": self.can_run_pipeline,
            "use_mock_detection": self.use_mock_detection,
            "use_shell_tools": self.use_shell_tools,
            "reasons": self.reasons,
        }


class FallbackManager:
    def decide(self, health: HealthStatus) -> FallbackDecision:
        reasons: list[str] = []
        use_shell_tools = health.python == "missing"
        use_mock_detection = False

        if use_shell_tools:
            reasons.append("python runtime missing; use shell-only board checks")

        if health.camera == "missing":
            use_mock_detection = True
            reasons.append("camera device missing; use mock detection input")
        if health.ov13855 == "not_ready":
            use_mock_detection = True
            reasons.append("ov13855 sensor not ready; use mock detection input")
        if health.rknn_model == "missing":
            use_mock_detection = True
            reasons.append("rknn model missing; use mock detection input")

        mode: FallbackMode
        if use_shell_tools and use_mock_detection:
            mode = "shell_only+mock_detection"
        elif use_shell_tools:
            mode = "shell_only"
        elif use_mock_detection:
            mode = "mock_detection"
        else:
            mode = "none"

        return FallbackDecision(
            mode=mode,
            can_run_pipeline=True,
            use_mock_detection=use_mock_detection,
            use_shell_tools=use_shell_tools,
            reasons=reasons or ["all required runtime inputs are available"],
        )
