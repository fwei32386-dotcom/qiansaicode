from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def validate_config(
    semantic_map_path: str | Path = ROOT / "configs" / "semantic_map.json",
    rule_dsl_path: str | Path = ROOT / "configs" / "rule_dsl.json",
) -> list[str]:
    errors: list[str] = []
    semantic = _read_json(semantic_map_path)
    rules = _read_json(rule_dsl_path)

    zones = semantic.get("zones", [])
    if not isinstance(zones, list) or not zones:
        errors.append("semantic_map.json: zones must be a non-empty list")
        zones = []

    zone_ids: set[str] = set()
    for index, zone in enumerate(zones):
        zone_id = str(zone.get("zone_id", "")).strip()
        if not zone_id:
            errors.append(f"semantic_map.json: zones[{index}] missing zone_id")
        elif zone_id in zone_ids:
            errors.append(f"semantic_map.json: duplicate zone_id {zone_id}")
        zone_ids.add(zone_id)

        polygon = zone.get("polygon", [])
        if not isinstance(polygon, list) or len(polygon) < 3:
            errors.append(f"semantic_map.json: zone {zone_id} polygon must contain at least 3 points")
        for point in polygon:
            if not _is_point(point):
                errors.append(f"semantic_map.json: zone {zone_id} has invalid point {point}")

    raw_rules = rules.get("rules", [])
    if not isinstance(raw_rules, list) or not raw_rules:
        errors.append("rule_dsl.json: rules must be a non-empty list")
        raw_rules = []

    rule_ids: set[str] = set()
    for index, rule in enumerate(raw_rules):
        rule_id = str(rule.get("id", "")).strip()
        if not rule_id:
            errors.append(f"rule_dsl.json: rules[{index}] missing id")
        elif rule_id in rule_ids:
            errors.append(f"rule_dsl.json: duplicate rule id {rule_id}")
        rule_ids.add(rule_id)

        zone_id = str(rule.get("zone", "")).strip()
        if zone_id not in zone_ids:
            errors.append(f"rule_dsl.json: rule {rule_id} references unknown zone {zone_id}")

        if "priority" not in rule or not isinstance(rule.get("priority"), int):
            errors.append(f"rule_dsl.json: rule {rule_id} priority must be an integer")

        risk = rule.get("risk")
        if not isinstance(risk, dict) or "score" not in risk or "level" not in risk:
            errors.append(f"rule_dsl.json: rule {rule_id} risk must contain score and level")

        actions = rule.get("actions")
        if not isinstance(actions, dict):
            errors.append(f"rule_dsl.json: rule {rule_id} actions must be an object")
        else:
            for key in ("voice", "led", "buzzer", "snapshot", "log"):
                if key not in actions:
                    errors.append(f"rule_dsl.json: rule {rule_id} actions missing {key}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SafeLab semantic map and rule DSL configs.")
    parser.add_argument("--semantic-map", default=str(ROOT / "configs" / "semantic_map.json"))
    parser.add_argument("--rule-dsl", default=str(ROOT / "configs" / "rule_dsl.json"))
    args = parser.parse_args()

    errors = validate_config(args.semantic_map, args.rule_dsl)
    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"status": "ok", "errors": []}, ensure_ascii=False, indent=2))
    return 0


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _is_point(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(item, int | float) for item in value)
    )


if __name__ == "__main__":
    raise SystemExit(main())

