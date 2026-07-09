from __future__ import annotations

import unittest
from pathlib import Path

from actuator.alarm_manager import AlarmManager
from ai_engine.json_detection_loader import load_detections_from_json
from runtime.interfaces import Detection
from safety_brain.ppe_association import associate_ppe
from safety_brain.rule_dsl_engine import RuleDslEngine
from safety_brain.scene_graph import SceneGraph


ROOT = Path(__file__).resolve().parents[1]


def _detection(class_name: str, bbox: list[int]) -> Detection:
    x1, y1, x2, y2 = bbox
    return Detection(
        frame_id=1,
        source_type="mock",
        class_name=class_name,  # type: ignore[arg-type]
        confidence=0.9,
        bbox=bbox,
        center=[(x1 + x2) // 2, (y1 + y2) // 2],
        area=(x2 - x1) * (y2 - y1),
        model_name="unit_test",
        infer_time_ms=0.0,
    )


class RuleDslEngineTest(unittest.TestCase):
    def test_scene_graph_finds_zone(self) -> None:
        scene = SceneGraph.from_json(ROOT / "configs" / "semantic_map.json")

        self.assertEqual(scene.find_zone([240, 410]).zone_id, "danger_zone")  # type: ignore[union-attr]
        self.assertEqual(scene.find_zone([640, 410]).zone_id, "normal_zone")  # type: ignore[union-attr]

    def test_ppe_association_uses_person_regions(self) -> None:
        detections = load_detections_from_json(ROOT / "data" / "mock_scenarios" / "danger_zone_ppe.json")
        person_ppe = associate_ppe(detections)[0]

        self.assertFalse(person_ppe.has_helmet)
        self.assertTrue(person_ppe.has_vest)
        self.assertEqual(person_ppe.missing_ppe, ["helmet", "goggles", "gloves"])

    def test_ppe_association_is_per_person_not_global(self) -> None:
        detections = load_detections_from_json(
            ROOT / "data" / "mock_scenarios" / "two_person_ppe_association.json"
        )
        people = associate_ppe(detections)

        self.assertEqual(len(people), 2)
        self.assertFalse(people[0].has_helmet)
        self.assertTrue(people[1].has_helmet)

    def test_ppe_association_assigns_each_item_to_one_person(self) -> None:
        detections = [
            _detection("person", [100, 100, 340, 600]),
            _detection("person", [260, 100, 460, 600]),
            _detection("helmet", [290, 120, 350, 180]),
        ]

        people = associate_ppe(detections)

        self.assertEqual([person.has_helmet for person in people], [False, True])

    def test_dsl_triggers_high_risk_in_danger_zone(self) -> None:
        detections = load_detections_from_json(ROOT / "data" / "mock_scenarios" / "danger_zone_ppe.json")
        engine = RuleDslEngine.from_files(
            ROOT / "configs" / "semantic_map.json",
            ROOT / "configs" / "rule_dsl.json",
        )
        events = engine.evaluate(detections)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].risk_score, 82)
        self.assertEqual(events[0].risk_level, "high")
        self.assertEqual(events[0].rule_id, "R001")
        self.assertIn("zone=danger_zone", events[0].reasons)
        self.assertTrue(any("suppressed_rules=R003" in reason for reason in events[0].reasons))

    def test_dsl_triggers_goggles_rule_in_welding_zone(self) -> None:
        detections = load_detections_from_json(
            ROOT / "data" / "mock_scenarios" / "welding_zone_missing_goggles.json"
        )
        events = RuleDslEngine.from_files(
            ROOT / "configs" / "semantic_map.json",
            ROOT / "configs" / "rule_dsl.json",
        ).evaluate(detections)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].rule_id, "R004")
        self.assertEqual(events[0].risk_level, "high")

    def test_dsl_triggers_gloves_rule_in_operation_zone(self) -> None:
        detections = load_detections_from_json(
            ROOT / "data" / "mock_scenarios" / "operation_zone_missing_gloves.json"
        )
        events = RuleDslEngine.from_files(
            ROOT / "configs" / "semantic_map.json",
            ROOT / "configs" / "rule_dsl.json",
        ).evaluate(detections)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].rule_id, "R005")
        self.assertEqual(events[0].risk_level, "warning")

    def test_dsl_action_hint_drives_alarm_action(self) -> None:
        detections = load_detections_from_json(ROOT / "data" / "mock_scenarios" / "danger_zone_ppe.json")
        engine = RuleDslEngine.from_files(
            ROOT / "configs" / "semantic_map.json",
            ROOT / "configs" / "rule_dsl.json",
        )
        action = AlarmManager().build_action(engine.evaluate(detections)[0])

        self.assertEqual(action.voice_text, "Helmet missing in danger zone. Please correct immediately.")
        self.assertEqual(action.led_color, "red")
        self.assertTrue(action.buzzer)

    def test_dsl_does_not_trigger_danger_rule_in_normal_zone(self) -> None:
        detections = load_detections_from_json(ROOT / "data" / "mock_scenarios" / "normal_zone_no_ppe.json")
        engine = RuleDslEngine.from_files(
            ROOT / "configs" / "semantic_map.json",
            ROOT / "configs" / "rule_dsl.json",
        )
        events = engine.evaluate(detections)

        self.assertEqual(events, [])

    def test_construction_scene_checks_helmet_and_vest_anywhere(self) -> None:
        detections = [_detection("person", [500, 100, 760, 620])]
        events = RuleDslEngine.from_files(
            ROOT / "configs" / "semantic_map.json",
            ROOT / "configs" / "rule_dsl.json",
            scene_mode="construction",
        ).evaluate(detections)

        self.assertEqual(events[0].rule_id, "SCENE_CONSTRUCTION_HELMET")
        self.assertIn("scene_mode=construction", events[0].reasons)
        self.assertIn("missing_ppe=helmet, vest", events[0].reasons)

    def test_construction_scene_uses_ppe_items_when_person_is_missed(self) -> None:
        detections = [_detection("helmet", [168, 89, 269, 197])]
        events = RuleDslEngine.from_files(
            ROOT / "configs" / "semantic_map.json",
            ROOT / "configs" / "rule_dsl.json",
            scene_mode="construction",
        ).evaluate(detections)

        self.assertEqual(events[0].rule_id, "SCENE_CONSTRUCTION_VEST")
        self.assertIn("missing_ppe=vest", events[0].reasons)

    def test_construction_scene_does_not_alarm_when_inferred_person_has_required_ppe(self) -> None:
        detections = [
            _detection("helmet", [168, 89, 269, 197]),
            _detection("vest", [136, 192, 276, 393]),
        ]
        events = RuleDslEngine.from_files(
            ROOT / "configs" / "semantic_map.json",
            ROOT / "configs" / "rule_dsl.json",
            scene_mode="construction",
        ).evaluate(detections)

        self.assertEqual(events, [])

    def test_lab_scene_checks_goggles_and_gloves_and_ignores_vest(self) -> None:
        detections = [
            _detection("person", [500, 100, 760, 620]),
            _detection("helmet", [560, 120, 650, 190]),
            _detection("vest", [535, 300, 715, 560]),
        ]
        events = RuleDslEngine.from_files(
            ROOT / "configs" / "semantic_map.json",
            ROOT / "configs" / "rule_dsl.json",
            scene_mode="lab",
        ).evaluate(detections)

        self.assertEqual(events[0].rule_id, "SCENE_LAB_GOGGLES")
        self.assertIn("scene_mode=lab", events[0].reasons)
        self.assertIn("missing_ppe=goggles, gloves", events[0].reasons)
        self.assertNotIn("vest", events[0].rule_id.lower())

    def test_lab_scene_uses_ppe_items_when_person_is_missed(self) -> None:
        detections = [_detection("goggles", [560, 150, 650, 190])]
        events = RuleDslEngine.from_files(
            ROOT / "configs" / "semantic_map.json",
            ROOT / "configs" / "rule_dsl.json",
            scene_mode="lab",
        ).evaluate(detections)

        self.assertEqual(events[0].rule_id, "SCENE_LAB_GLOVES")
        self.assertIn("missing_ppe=gloves", events[0].reasons)

    def test_lab_scene_does_not_alarm_when_inferred_person_has_required_ppe(self) -> None:
        detections = [
            _detection("goggles", [560, 150, 650, 190]),
            _detection("gloves", [710, 360, 780, 450]),
        ]
        events = RuleDslEngine.from_files(
            ROOT / "configs" / "semantic_map.json",
            ROOT / "configs" / "rule_dsl.json",
            scene_mode="lab",
        ).evaluate(detections)

        self.assertEqual(events, [])

    def test_lab_scene_does_not_trigger_when_only_vest_is_missing(self) -> None:
        detections = [
            _detection("person", [500, 100, 760, 620]),
            _detection("goggles", [560, 150, 650, 190]),
            _detection("gloves", [710, 360, 780, 450]),
        ]
        events = RuleDslEngine.from_files(
            ROOT / "configs" / "semantic_map.json",
            ROOT / "configs" / "rule_dsl.json",
            scene_mode="lab",
        ).evaluate(detections)

        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
