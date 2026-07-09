from pathlib import Path

from actuator.backends import JsonlActuatorBackend


class MockActuator(JsonlActuatorBackend):
    def __init__(self, output_path: str | Path = "data/events/actuator_log.jsonl") -> None:
        super().__init__(Path(output_path))
