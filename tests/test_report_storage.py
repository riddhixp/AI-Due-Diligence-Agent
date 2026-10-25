
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import report_storage


class TestReportStorage(unittest.TestCase):

    def setUp(self):
        # Use a temporary folder, not real saved reports.
        self.temp_dir = tempfile.TemporaryDirectory()
        self.reports_dir = Path(self.temp_dir.name)

        self.patcher = patch.object(
            report_storage,
            "REPORTS_DIR",
            self.reports_dir,
        )
        self.patcher.start()

        self.addCleanup(self.patcher.stop)
        self.addCleanup(self.temp_dir.cleanup)

        self.pdf_bytes = b"sample-company-pdf"

    def test_save_and_reload(self):
        report_storage.save_report(
            self.pdf_bytes,
            "Example due diligence report",
            {"revenue_growth": {"status": "PASS"}},
            {"company": "Example Company"},
        )

        saved = report_storage.load_report(self.pdf_bytes)

        self.assertEqual(
            saved["report"],
            "Example due diligence report",
        )
        self.assertEqual(
            saved["financial_data"]["company"],
            "Example Company",
        )

    def test_unknown_pdf_returns_none(self):
        saved = report_storage.load_report(
            b"pdf-that-has-not-been-analysed"
        )
        self.assertIsNone(saved)

    def test_different_pdfs_have_different_ids(self):
        first = report_storage.get_report_id(b"company-a")
        second = report_storage.get_report_id(b"company-b")

        self.assertNotEqual(first, second)

    def test_saved_reports_are_separate(self):
        report_storage.save_report(
            b"company-a",
            "Report A",
            {},
            {},
        )

        report_storage.save_report(
            b"company-b",
            "Report B",
            {},
            {},
        )

        first = report_storage.load_report(b"company-a")
        second = report_storage.load_report(b"company-b")

        self.assertEqual(first["report"], "Report A")
        self.assertEqual(second["report"], "Report B")

    def test_concurrent_saves_publish_complete_independent_payloads(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        barrier = Barrier(8)
        replace = Path.replace
        def synchronized_replace(source, target):
            barrier.wait(timeout=10)
            return replace(source, target)
        def save(index):
            report_storage.save_report(self.pdf_bytes, f'Report {index}',
                                       {'index': index}, {'index': index})
        with patch.object(Path, 'replace', synchronized_replace):
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(save, range(8)))
        saved = report_storage.load_report(self.pdf_bytes)
        index = saved['financial_data']['index']
        self.assertEqual(saved['report'], f'Report {index}')
        self.assertEqual(saved['validation']['index'], index)
        self.assertEqual(len(list(self.reports_dir.iterdir())), 1)

    def test_failed_publish_preserves_old_report_and_removes_temporary_file(self):
        report_storage.save_report(self.pdf_bytes, 'Original', {}, {})
        with patch.object(Path, 'replace', side_effect=OSError('Simulated storage failure')):
            with self.assertRaises(OSError):
                report_storage.save_report(self.pdf_bytes, 'Replacement', {}, {})
        self.assertEqual(report_storage.load_report(self.pdf_bytes)['report'], 'Original')
        self.assertEqual(len(list(self.reports_dir.iterdir())), 1)

    def test_nonfinite_save_does_not_replace_existing_report(self):
        report_storage.save_report(self.pdf_bytes, 'Original', {}, {})
        for value in [float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                report_storage.save_report(self.pdf_bytes, 'Invalid', {}, {'revenue': value})
        self.assertEqual(report_storage.load_report(self.pdf_bytes)['report'], 'Original')
        self.assertEqual(len(list(self.reports_dir.iterdir())), 1)

    def test_ambiguous_or_nonfinite_saved_json_is_rejected_without_rewriting(self):
        path = self.reports_dir / (report_storage.get_report_id(self.pdf_bytes) + '.json')
        for text in ['{"report":"A","report":"B"}', '{"value":NaN}',
                     '{"value":Infinity}', '{"value":1e400}', '[]', 'not JSON']:
            with self.subTest(text=text):
                path.write_text(text, encoding='utf-8')
                with self.assertRaises(ValueError):
                    report_storage.load_report(self.pdf_bytes)
                self.assertEqual(path.read_text(encoding='utf-8'), text)

    def test_excessively_nested_cache_is_rejected_without_rewriting(self):
        path = self.reports_dir / (report_storage.get_report_id(self.pdf_bytes) + '.json')
        payload = '{"report":"Findings","nested":' + '[' * 10000 + '0' + ']' * 10000 + '}'
        path.write_text(payload, encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'SAVED_REPORT_NESTING_TOO_DEEP'):
            report_storage.load_report(self.pdf_bytes)
        self.assertEqual(path.read_text(encoding='utf-8'), payload)


if __name__ == "__main__":
    unittest.main()
