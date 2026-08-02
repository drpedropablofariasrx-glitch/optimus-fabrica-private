import json
import unittest

from test_fabrica_abdomen_characterization import load_app_copy


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path):
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class SftRevisionQueueMergeTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir, self.mod = load_app_copy()
        self.client = self.mod.app.test_client()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _general_case(self, **overrides):
        base = {
            "review_case_id": "general_case_1",
            "region": "abdomen_pelvis",
            "modality": "TC",
            "candidate_type": "structural_raw_final_pair_v2",
            "raw_input": "Datos clinicos ficticios de abdomen.",
            "final_report": "Informe final ficticio de abdomen.",
            "approval_status": "pending",
            "review_notes": "",
            "sft_eligible": False,
        }
        base.update(overrides)
        return base

    def _vuepacs_case(self, **overrides):
        base = {
            "review_case_id": "vuepacs_case_1",
            "region": "cabeza_cuello",
            "modality": "RM",
            "candidate_type": "historical_final_report_masked_impression",
            "raw_input": "Datos clinicos ficticios de craneo.",
            "final_report": "Informe final ficticio de craneo.",
            "approval_status": "candidate",
            "review_notes": "",
            "sft_eligible": False,
        }
        base.update(overrides)
        return base

    def test_cases_endpoint_merges_both_queues(self):
        _write_jsonl(self.mod.SFT_REVIEW_QUEUE, [self._general_case()])
        _write_jsonl(self.mod.VUEPACS_REVIEW_QUEUE, [self._vuepacs_case()])

        response = self.client.get("/sft_revision/cases?region=all&status=all")
        data = response.get_json()

        ids = {case["review_case_id"] for case in data["cases"]}
        self.assertEqual(ids, {"general_case_1", "vuepacs_case_1"})
        self.assertIn("cabeza_cuello", data["regions"])
        self.assertIn("abdomen_pelvis", data["regions"])
        self.assertIn("RM", data["modalities"])
        self.assertIn("TC", data["modalities"])

    def test_modality_filter_narrows_results(self):
        _write_jsonl(self.mod.SFT_REVIEW_QUEUE, [self._general_case()])
        _write_jsonl(self.mod.VUEPACS_REVIEW_QUEUE, [self._vuepacs_case()])

        response = self.client.get("/sft_revision/cases?region=all&modality=RM&status=all")
        data = response.get_json()

        ids = {case["review_case_id"] for case in data["cases"]}
        self.assertEqual(ids, {"vuepacs_case_1"})

    def test_origen_filter_isolates_vuepacs_cases(self):
        _write_jsonl(self.mod.SFT_REVIEW_QUEUE, [self._general_case()])
        _write_jsonl(
            self.mod.VUEPACS_REVIEW_QUEUE,
            [self._vuepacs_case(), self._vuepacs_case(review_case_id="vuepacs_case_2")],
        )

        response = self.client.get("/sft_revision/cases?origen=vuepacs&status=all")
        data = response.get_json()

        ids = {case["review_case_id"] for case in data["cases"]}
        self.assertEqual(ids, {"vuepacs_case_1", "vuepacs_case_2"})
        for case in data["cases"]:
            self.assertEqual(case["origen_cola"], "vuepacs")

    def test_origen_filter_general_excludes_vuepacs(self):
        _write_jsonl(self.mod.SFT_REVIEW_QUEUE, [self._general_case()])
        _write_jsonl(self.mod.VUEPACS_REVIEW_QUEUE, [self._vuepacs_case()])

        response = self.client.get("/sft_revision/cases?origen=general&status=all")
        data = response.get_json()

        ids = {case["review_case_id"] for case in data["cases"]}
        self.assertEqual(ids, {"general_case_1"})

    def test_update_writes_back_to_originating_queue_only(self):
        _write_jsonl(self.mod.SFT_REVIEW_QUEUE, [self._general_case()])
        _write_jsonl(self.mod.VUEPACS_REVIEW_QUEUE, [self._vuepacs_case()])

        response = self.client.put(
            "/sft_revision/cases/vuepacs_case_1",
            json={
                "raw_input": "Datos clinicos ficticios de craneo revisados.",
                "final_report": "Informe final ficticio de craneo revisado.",
                "review_notes": "ok",
                "approval_status": "approved",
            },
        )
        self.assertEqual(response.status_code, 200)

        general_rows = _read_jsonl(self.mod.SFT_REVIEW_QUEUE)
        self.assertEqual(len(general_rows), 1)
        self.assertEqual(general_rows[0]["review_case_id"], "general_case_1")
        self.assertEqual(general_rows[0]["approval_status"], "pending")

        vuepacs_rows = _read_jsonl(self.mod.VUEPACS_REVIEW_QUEUE)
        self.assertEqual(len(vuepacs_rows), 1)
        self.assertEqual(vuepacs_rows[0]["approval_status"], "approved")
        self.assertTrue(vuepacs_rows[0]["sft_eligible"])

    def test_update_rejects_missing_case(self):
        response = self.client.put(
            "/sft_revision/cases/does_not_exist",
            json={"approval_status": "approved", "raw_input": "x", "final_report": "y"},
        )
        self.assertEqual(response.status_code, 404)

    def test_approval_still_requires_both_fields_regardless_of_origin(self):
        _write_jsonl(self.mod.VUEPACS_REVIEW_QUEUE, [self._vuepacs_case()])

        response = self.client.put(
            "/sft_revision/cases/vuepacs_case_1",
            json={"approval_status": "approved", "raw_input": "", "final_report": "algo"},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
