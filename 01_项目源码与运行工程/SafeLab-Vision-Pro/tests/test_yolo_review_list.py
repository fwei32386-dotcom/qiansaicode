from __future__ import annotations

import unittest

from tools.generate_yolo_review_list import rank_review_rows


class YoloReviewListTest(unittest.TestCase):
    def test_rank_review_rows_prioritizes_problem_classes(self) -> None:
        report = {
            "rows": [
                {
                    "image": "ok.jpg",
                    "truth": ["person"],
                    "predictions": ["person"],
                    "missed_truth": [],
                    "false_positive": [],
                },
                {
                    "image": "fire_problem.jpg",
                    "truth": ["fire"],
                    "predictions": ["smoke", "helmet"],
                    "missed_truth": ["fire"],
                    "false_positive": ["smoke", "helmet"],
                },
                {
                    "image": "helmet_only.jpg",
                    "truth": ["helmet"],
                    "predictions": [],
                    "missed_truth": ["helmet"],
                    "false_positive": [],
                },
            ]
        }

        rows = rank_review_rows(report)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["image"], "fire_problem.jpg")
        self.assertEqual(rows[0]["priority_score"], 2)
        self.assertEqual(rows[0]["review_reason"], "fire:1, smoke:1")


if __name__ == "__main__":
    unittest.main()
