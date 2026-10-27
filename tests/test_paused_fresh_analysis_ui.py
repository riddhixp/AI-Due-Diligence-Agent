"""Drive the real app with an uploaded fixture; never permit a provider run."""
from io import BytesIO
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from scripts.create_conflict_test_fixture import create_conflict_fixture
from offline_correction_workflow import start_offline_correction_workflow
from investigation_checkpoint import document_fingerprint


class PausedFreshAnalysisUITests(unittest.TestCase):
    def test_non_pdf_upload_clears_stale_report_without_model_call(self):
        upload = BytesIO(b'not a pdf at all')
        upload.name = 'renamed.pdf'
        app_path = Path(__file__).resolve().parents[1] / 'app.py'
        app = AppTest.from_file(str(app_path), default_timeout=20)
        app.session_state['file_id'] = ('prior.pdf', 123, 'old')
        app.session_state['report'] = 'CONFIDENTIAL_OLD_REPORT'
        with patch('streamlit.file_uploader', return_value=upload), \
             patch('due_diligence_engine.run_due_diligence',
                   side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model:
            app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('valid PDF' in entry.value for entry in app.error))
        self.assertNotIn('report', app.session_state)
        self.assertNotIn('file_id', app.session_state)
        model.assert_not_called()

    def test_empty_pdf_clears_old_report_without_paid_model(self):
        upload = BytesIO(b'%PDF-1.7')
        upload.name = 'empty.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        app.session_state['file_id'] = ('prior.pdf', 123, 'old')
        app.session_state['report'] = 'PREVIOUS_PRIVATE_REPORT'
        with patch('streamlit.file_uploader', return_value=upload), \
             patch('due_diligence_engine.extract_pages', return_value=[]), \
             patch('due_diligence_engine.run_due_diligence',
                   side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model:
            app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('No readable text' in item.value for item in app.error))
        self.assertNotIn('report', app.session_state)
        self.assertNotIn('file_id', app.session_state)
        model.assert_not_called()

    def test_pdf_parser_failure_clears_old_report_without_model(self):
        upload = BytesIO(b'%PDF-1.7')
        upload.name = 'broken.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        app.session_state['file_id'] = ('prior.pdf', 123, 'old')
        app.session_state['report'] = 'OLD_PRIVATE_REPORT'
        with (
            patch('streamlit.file_uploader', return_value=upload),
            patch('due_diligence_engine.extract_pages',
                  side_effect=ValueError('SECRET_DOCUMENT_ERROR')),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Could not read this PDF' in item.value
                            for item in app.error))
        self.assertFalse(any('SECRET_DOCUMENT_ERROR' in item.value
                             for item in app.error))
        self.assertNotIn('report', app.session_state)
        self.assertNotIn('file_id', app.session_state)
        model.assert_not_called()

    def test_malformed_parser_page_data_clears_session_without_paid_call(self):
        upload = BytesIO(b'%PDF-1.7')
        upload.name = 'malformed.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        app.session_state['file_id'] = ('prior.pdf', 123, 'old')
        app.session_state['report'] = 'STALE_REPORT'
        with (
            patch('streamlit.file_uploader', return_value=upload),
            patch('due_diligence_engine.extract_pages', return_value=['valid', None]),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Could not read PDF pages' in item.value
                            for item in app.error))
        self.assertNotIn('report', app.session_state)
        self.assertNotIn('file_id', app.session_state)
        model.assert_not_called()

    def test_oversized_pdf_clears_stale_state_before_copying_bytes(self):
        class OversizedUpload:
            size = 15 * 1024 * 1024 + 1
            name = 'oversized.pdf'
            def getvalue(self):
                raise AssertionError('OVERSIZED_FILE_WAS_COPIED')
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        app.session_state['file_id'] = ('prior.pdf', 123, 'old')
        app.session_state['report'] = 'STALE_REPORT'
        with (
            patch('streamlit.file_uploader', return_value=OversizedUpload()),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('smaller than 15 MB' in item.value for item in app.error))
        self.assertNotIn('report', app.session_state)
        self.assertNotIn('file_id', app.session_state)
        model.assert_not_called()

    def test_pdf_at_exact_size_limit_reaches_parser(self):
        # The 15 MB threshold is inclusive; size checks must not reject
        # an exactly-on-limit upload before invoking the PDF parser.
        class BoundaryUpload:
            size = 15 * 1024 * 1024
            name = 'boundary.pdf'
            def getvalue(self):
                return b'%PDF-1.7'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        with (
            patch('streamlit.file_uploader', return_value=BoundaryUpload()),
            patch('due_diligence_engine.extract_pages', return_value=[]) as parser,
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
        self.assertFalse(app.exception)
        parser.assert_called_once_with(b'%PDF-1.7')
        self.assertTrue(any('No readable text' in item.value for item in app.error))
        model.assert_not_called()

    def test_actual_bytes_over_limit_rejected_when_upload_size_underreported(self):
        class MisreportedUpload:
            size = 100
            name = 'misreported.pdf'
            def getvalue(self):
                return b'%PDF-' + b'X' * (15 * 1024 * 1024)
        upload = MisreportedUpload()
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        app.session_state['file_id'] = ('prior.pdf', 123, 'old')
        app.session_state['report'] = 'STALE_REPORT'
        with (
            patch('streamlit.file_uploader', return_value=upload),
            patch('due_diligence_engine.extract_pages',
                  side_effect=AssertionError('SHOULD_NOT_PARSE')) as parser,
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('smaller than 15 MB' in item.value for item in app.error))
        self.assertNotIn('report', app.session_state)
        parser.assert_not_called()
        model.assert_not_called()

    def test_empty_upload_rejected_before_parser_and_clears_state(self):
        upload = BytesIO(b'')
        upload.name = 'empty.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        app.session_state['file_id'] = ('prior.pdf', 123, 'old')
        app.session_state['report'] = 'OLD_REPORT'
        with (
            patch('streamlit.file_uploader', return_value=upload),
            patch('due_diligence_engine.extract_pages',
                  side_effect=AssertionError('SHOULD_NOT_PARSE')) as parser,
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('valid PDF' in item.value for item in app.error))
        self.assertNotIn('report', app.session_state)
        parser.assert_not_called()
        model.assert_not_called()

    def test_pdf_page_limit_rejects_excessive_parser_output(self):
        upload = BytesIO(b'%PDF-1.7')
        upload.name = 'many_pages.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        app.session_state['file_id'] = ('prior.pdf', 123, 'old')
        app.session_state['report'] = 'STALE_REPORT'
        with (
            patch('streamlit.file_uploader', return_value=upload),
            patch('due_diligence_engine.extract_pages', return_value=['page'] * 10001),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Could not read PDF pages' in item.value for item in app.error))
        self.assertNotIn('report', app.session_state)
        model.assert_not_called()

    def test_pdf_page_limit_accepts_exactly_10000_pages(self):
        upload = BytesIO(b'%PDF-1.7')
        upload.name = 'boundary_pages.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        with (
            patch('streamlit.file_uploader', return_value=upload),
            patch('due_diligence_engine.extract_pages', return_value=[''] * 10000),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('No readable text' in item.value for item in app.error))
        self.assertFalse(any('Could not read PDF pages' in item.value
                             for item in app.error))
        model.assert_not_called()

    def test_parser_non_sequence_result_is_rejected_without_model_call(self):
        upload = BytesIO(b'%PDF-1.7')
        upload.name = 'malformed_pages.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        app.session_state['file_id'] = ('prior.pdf', 123, 'old')
        app.session_state['report'] = 'PREVIOUS_REPORT'
        with (
            patch('streamlit.file_uploader', return_value=upload),
            patch('due_diligence_engine.extract_pages', return_value={'page': 'text'}),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Could not read PDF pages' in item.value for item in app.error))
        self.assertNotIn('report', app.session_state)
        model.assert_not_called()

    def test_parser_none_result_clears_state_without_paid_call(self):
        upload = BytesIO(b'%PDF-1.7')
        upload.name = 'none_pages.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        app.session_state['file_id'] = ('prior.pdf', 123, 'old')
        app.session_state['report'] = 'PREVIOUS_REPORT'
        with (
            patch('streamlit.file_uploader', return_value=upload),
            patch('due_diligence_engine.extract_pages', return_value=None),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Could not read PDF pages' in item.value for item in app.error))
        self.assertNotIn('report', app.session_state)
        model.assert_not_called()

    def test_pdf_parser_rejects_numeric_page_without_model_call(self):
        upload = BytesIO(b'%PDF-1.7')
        upload.name = 'numeric_page.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        app.session_state['file_id'] = ('prior.pdf', 123, 'old')
        app.session_state['report'] = 'PREVIOUS_REPORT'
        with (
            patch('streamlit.file_uploader', return_value=upload),
            patch('due_diligence_engine.extract_pages', return_value=['text', 42]),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Could not read PDF pages' in item.value for item in app.error))
        self.assertNotIn('report', app.session_state)
        model.assert_not_called()

    def test_pdf_parser_rejects_generator_output_without_model_call(self):
        upload = BytesIO(b'%PDF-1.7')
        upload.name = 'generator_pages.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        app.session_state['file_id'] = ('prior.pdf', 123, 'old')
        app.session_state['report'] = 'OLD_REPORT'
        with (
            patch('streamlit.file_uploader', return_value=upload),
            patch('due_diligence_engine.extract_pages',
                  return_value=(page for page in ['valid text'])),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Could not read PDF pages' in item.value for item in app.error))
        self.assertNotIn('report', app.session_state)
        model.assert_not_called()

    def test_free_approval_demo_button_creates_pending_queue_offline(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()
        upload = BytesIO(pdf)
        upload.name = 'fixture.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        with (
            patch('streamlit.file_uploader', return_value=upload),
            patch('report_storage.load_report', return_value=None),
            patch('socket.socket.connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
            self.assertFalse(app.exception)
            button = next(b for b in app.button
                          if b.label == 'Start FREE approval demo')
            button.click().run()
            self.assertFalse(app.exception)
            self.assertIn('offline_approval_queue', app.session_state)
            self.assertTrue(any(b.label == 'Approve demo submission'
                                for b in app.button))
            model.assert_not_called()

    def test_free_approval_demo_approve_records_decision_without_model(self):
        from approval_queue import approval_public_status
        with tempfile.TemporaryDirectory() as folder:
            pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()
        upload = BytesIO(pdf)
        upload.name = 'fixture.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        with (
            patch('streamlit.file_uploader', return_value=upload),
            patch('report_storage.load_report', return_value=None),
            patch('socket.socket.connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
            self.assertFalse(app.exception)
            next(b for b in app.button
                 if b.label == 'Start FREE approval demo').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(
                approval_public_status(app.session_state['offline_approval_queue'])['approvals'][0],
                'PENDING')
            next(b for b in app.button
                 if b.label == 'Approve demo submission').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(
                approval_public_status(app.session_state['offline_approval_queue'])['approvals'][0],
                'APPROVED')
            model.assert_not_called()

    def test_free_approval_demo_reject_records_decision_without_model(self):
        from approval_queue import approval_public_status
        with tempfile.TemporaryDirectory() as folder:
            pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()
        upload = BytesIO(pdf)
        upload.name = 'fixture.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        with (
            patch('streamlit.file_uploader', return_value=upload),
            patch('report_storage.load_report', return_value=None),
            patch('socket.socket.connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
            self.assertFalse(app.exception)
            next(b for b in app.button
                 if b.label == 'Start FREE approval demo').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(
                approval_public_status(app.session_state['offline_approval_queue'])['approvals'][0],
                'PENDING')
            next(b for b in app.button
                 if b.label == 'Reject demo submission').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(
                approval_public_status(app.session_state['offline_approval_queue'])['approvals'][0],
                'REJECTED')
            model.assert_not_called()

    def test_approved_free_queue_is_cleared_on_different_pdf_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()
        first = BytesIO(pdf)
        first.name = 'first.pdf'
        second = BytesIO(pdf + b'\n% Different PDF bytes')
        second.name = 'second.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        with (
            patch('streamlit.file_uploader', return_value=first) as uploader,
            patch('due_diligence_engine.extract_pages',
                  return_value=['Total revenue 120 million']),
            patch('report_storage.load_report', return_value=None),
            patch('socket.socket.connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
            self.assertFalse(app.exception)
            next(b for b in app.button
                 if b.label == 'Start FREE approval demo').click().run()
            self.assertFalse(app.exception)
            next(b for b in app.button
                 if b.label == 'Approve demo submission').click().run()
            self.assertFalse(app.exception)
            self.assertIn('offline_approval_queue', app.session_state)
            uploader.return_value = second
            app.run()
            self.assertFalse(app.exception)
            self.assertNotIn('offline_approval_queue', app.session_state)
            self.assertFalse(any(b.label == 'Approve demo submission'
                                 for b in app.button))
            model.assert_not_called()

    def test_pending_free_queue_is_cleared_on_pdf_removal(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()
        upload = BytesIO(pdf)
        upload.name = 'fixture.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        with (
            patch('streamlit.file_uploader', return_value=upload) as uploader,
            patch('report_storage.load_report', return_value=None),
            patch('socket.socket.connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
            self.assertFalse(app.exception)
            next(b for b in app.button
                 if b.label == 'Start FREE approval demo').click().run()
            self.assertFalse(app.exception)
            self.assertIn('offline_approval_queue', app.session_state)
            uploader.return_value = None
            app.run()
            self.assertFalse(app.exception)
            self.assertNotIn('offline_approval_queue', app.session_state)
            self.assertNotIn('file_id', app.session_state)
            uploader.return_value = upload
            app.run()
            self.assertFalse(app.exception)
            self.assertNotIn('offline_approval_queue', app.session_state)
            model.assert_not_called()

    def test_rejected_free_queue_is_cleared_on_different_pdf_upload(self):
        from approval_queue import approval_public_status
        with tempfile.TemporaryDirectory() as folder:
            pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()
        first = BytesIO(pdf)
        first.name = 'first.pdf'
        second = BytesIO(pdf + b'\n% document revision')
        second.name = 'revised.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        with (
            patch('streamlit.file_uploader', return_value=first) as uploader,
            patch('due_diligence_engine.extract_pages',
                  return_value=['Total revenue 120 million']),
            patch('report_storage.load_report', return_value=None),
            patch('socket.socket.connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
            self.assertFalse(app.exception)
            next(b for b in app.button
                 if b.label == 'Start FREE approval demo').click().run()
            self.assertFalse(app.exception)
            next(b for b in app.button
                 if b.label == 'Reject demo submission').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(
                approval_public_status(app.session_state['offline_approval_queue'])['approvals'][0],
                'REJECTED')
            uploader.return_value = second
            app.run()
            self.assertFalse(app.exception)
            self.assertNotIn('offline_approval_queue', app.session_state)
            model.assert_not_called()

    def test_pending_approval_is_cleared_when_pdf_bytes_change_same_name(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()
        original = BytesIO(pdf)
        original.name = 'same_name.pdf'
        revised = BytesIO(pdf + b'\n% revision with same filename')
        revised.name = 'same_name.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        with (
            patch('streamlit.file_uploader', return_value=original) as uploader,
            patch('due_diligence_engine.extract_pages',
                  return_value=['Total revenue 120 million']),
            patch('report_storage.load_report', return_value=None),
            patch('socket.socket.connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
            self.assertFalse(app.exception)
            next(b for b in app.button
                 if b.label == 'Start FREE approval demo').click().run()
            self.assertFalse(app.exception)
            self.assertIn('offline_approval_queue', app.session_state)
            uploader.return_value = revised
            app.run()
            self.assertFalse(app.exception)
            self.assertNotIn('offline_approval_queue', app.session_state)
            model.assert_not_called()

    def test_approved_queue_is_cleared_on_content_change_same_filename(self):
        from approval_queue import approval_public_status
        with tempfile.TemporaryDirectory() as folder:
            pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()
        original = BytesIO(pdf)
        original.name = 'report.pdf'
        revised = BytesIO(pdf + b'\n% corrected report revision')
        revised.name = 'report.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        with (
            patch('streamlit.file_uploader', return_value=original) as uploader,
            patch('due_diligence_engine.extract_pages',
                  return_value=['Total revenue 120 million']),
            patch('report_storage.load_report', return_value=None),
            patch('socket.socket.connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
            self.assertFalse(app.exception)
            next(b for b in app.button
                 if b.label == 'Start FREE approval demo').click().run()
            next(b for b in app.button
                 if b.label == 'Approve demo submission').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(
                approval_public_status(app.session_state['offline_approval_queue'])['approvals'][0],
                'APPROVED')
            uploader.return_value = revised
            app.run()
            self.assertFalse(app.exception)
            self.assertNotIn('offline_approval_queue', app.session_state)
            model.assert_not_called()

    def test_rejected_queue_is_cleared_on_content_change_same_filename(self):
        from approval_queue import approval_public_status
        with tempfile.TemporaryDirectory() as folder:
            pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()
        original = BytesIO(pdf)
        original.name = 'report.pdf'
        revised = BytesIO(pdf + b'\n% revised financial notes')
        revised.name = 'report.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        with (
            patch('streamlit.file_uploader', return_value=original) as uploader,
            patch('due_diligence_engine.extract_pages',
                  return_value=['Total revenue 120 million']),
            patch('report_storage.load_report', return_value=None),
            patch('socket.socket.connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
            self.assertFalse(app.exception)
            next(b for b in app.button
                 if b.label == 'Start FREE approval demo').click().run()
            next(b for b in app.button
                 if b.label == 'Reject demo submission').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(
                approval_public_status(app.session_state['offline_approval_queue'])['approvals'][0],
                'REJECTED')
            uploader.return_value = revised
            app.run()
            self.assertFalse(app.exception)
            self.assertNotIn('offline_approval_queue', app.session_state)
            model.assert_not_called()

    def test_free_demo_decision_buttons_disappear_after_approval(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()
        upload = BytesIO(pdf)
        upload.name = 'fixture.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        with (
            patch('streamlit.file_uploader', return_value=upload),
            patch('report_storage.load_report', return_value=None),
            patch('socket.socket.connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
            self.assertFalse(app.exception)
            next(b for b in app.button
                 if b.label == 'Start FREE approval demo').click().run()
            next(b for b in app.button
                 if b.label == 'Approve demo submission').click().run()
            self.assertFalse(app.exception)
            app.run()
            self.assertFalse(app.exception)
            self.assertFalse(any(b.label in ('Approve demo submission',
                                             'Reject demo submission')
                                 for b in app.button))
            model.assert_not_called()

    def test_free_demo_decision_buttons_disappear_after_rejection(self):
        from approval_queue import approval_public_status
        with tempfile.TemporaryDirectory() as folder:
            pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()
        upload = BytesIO(pdf)
        upload.name = 'fixture.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        with (
            patch('streamlit.file_uploader', return_value=upload),
            patch('report_storage.load_report', return_value=None),
            patch('socket.socket.connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
            self.assertFalse(app.exception)
            next(b for b in app.button
                 if b.label == 'Start FREE approval demo').click().run()
            next(b for b in app.button
                 if b.label == 'Reject demo submission').click().run()
            self.assertFalse(app.exception)
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(
                approval_public_status(app.session_state['offline_approval_queue'])['approvals'][0],
                'REJECTED')
            self.assertFalse(any(b.label in ('Approve demo submission',
                                             'Reject demo submission')
                                 for b in app.button))
            model.assert_not_called()

    def test_new_free_approval_demo_starts_fresh_queue_after_rejection(self):
        from approval_queue import approval_public_status
        with tempfile.TemporaryDirectory() as folder:
            pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()
        upload = BytesIO(pdf)
        upload.name = 'fixture.pdf'
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / 'app.py'),
            default_timeout=20)
        with (
            patch('streamlit.file_uploader', return_value=upload),
            patch('report_storage.load_report', return_value=None),
            patch('socket.socket.connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')),
            patch('due_diligence_engine.run_due_diligence',
                  side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as model,
        ):
            app.run()
            self.assertFalse(app.exception)
            start = lambda: next(b for b in app.button
                                 if b.label == 'Start FREE approval demo')
            start().click().run()
            first_queue = app.session_state['offline_approval_queue']
            next(b for b in app.button
                 if b.label == 'Reject demo submission').click().run()
            self.assertEqual(
                approval_public_status(first_queue)['approvals'][0], 'REJECTED')
            start().click().run()
            self.assertFalse(app.exception)
            fresh_queue = app.session_state['offline_approval_queue']
            self.assertIsNot(fresh_queue, first_queue)
            self.assertEqual(
                approval_public_status(fresh_queue)['approvals'][0], 'PENDING')
            model.assert_not_called()

    def test_pause_blocks_analysis_until_discard_without_model_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = create_conflict_fixture(Path(folder) / 'fixture.pdf').read_bytes()
        with patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
            fixture = start_offline_correction_workflow(pdf)
            upload = BytesIO(pdf)
            upload.name = 'fixture.pdf'
            app_path = Path(__file__).resolve().parents[1] / 'app.py'
            app = AppTest.from_file(str(app_path), default_timeout=20)
            app.session_state['file_id'] = (upload.name, len(pdf), document_fingerprint(pdf))
            app.session_state['live_financial_pause'] = fixture['handoff']
            with patch('streamlit.file_uploader', return_value=upload) as uploader, \
                 patch('report_storage.load_report', return_value=None), \
                 patch('due_diligence_engine.run_due_diligence', side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as run:
                app.run()
                self.assertFalse(app.exception)
                self.assertTrue(app.button(key='analyse_company').disabled)
                # Simulate a dispatched event despite the disabled UI to exercise
                # the independent server-side check before provider/key lookup.
                import streamlit as st
                button = st.button
                def dispatched(*args, **kwargs):
                    result = button(*args, **kwargs)
                    return True if kwargs.get('key') == 'analyse_company' else result
                with patch('streamlit.button', side_effect=dispatched):
                    app.run()
                self.assertFalse(app.exception)
                self.assertTrue(any('Discard the paused investigation' in item.value for item in app.error))
                run.assert_not_called()
                self.assertEqual(fixture['model'].calls, 2)
                app.button(key='live_financial_approve').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(fixture['handoff']['status'], 'APPROVED')
                self.assertTrue(app.button(key='analyse_company').disabled)
                self.assertEqual(fixture['model'].calls, 2)
                discard = next(button for button in app.button if button.label == 'Discard paused investigation')
                discard.click().run()
                self.assertFalse(app.exception)
                self.assertNotIn('live_financial_pause', app.session_state)
                self.assertFalse(app.button(key='analyse_company').disabled)
                run.assert_not_called()

                # Removing and re-uploading identical bytes must not resurrect
                # an earlier report or SDK decision from transient session state.
                app.session_state['report'] = 'Earlier report'
                app.session_state['live_financial_pause'] = fixture['handoff']
                app.session_state['live_financial_displayed_request'] = {'old': True}
                uploader.return_value = None
                app.run()
                self.assertFalse(app.exception)
                for key in ['file_id', 'report', 'live_financial_pause', 'live_financial_displayed_request']:
                    self.assertNotIn(key, app.session_state)
                uploader.return_value = upload
                app.run()
                self.assertFalse(app.exception)
                self.assertNotIn('report', app.session_state)
                self.assertNotIn('live_financial_pause', app.session_state)
                self.assertFalse(app.button(key='analyse_company').disabled)
                run.assert_not_called()

    def test_corrupt_saved_analysis_warns_without_model_or_partial_session(self):
        import report_storage
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            pdf = create_conflict_fixture(directory / 'fixture.pdf').read_bytes()
            cache = directory / (report_storage.get_report_id(pdf) + '.json')
            payloads = [
                '{"report":["Invalid narrative"],"financial_data":{}}',
                '{"report":"Findings","nested":' + '[' * 10000 + '0' + ']' * 10000 + '}',
            ]
            for payload in payloads:
                with self.subTest(nested=len(payload) > 1000):
                    cache.write_text(payload, encoding='utf-8')
                    upload = BytesIO(pdf)
                    upload.name = 'fixture.pdf'
                    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'),
                                            default_timeout=20)
                    with patch('streamlit.file_uploader', return_value=upload), \
                         patch.object(report_storage, 'REPORTS_DIR', directory), \
                         patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
                         patch('due_diligence_engine.run_due_diligence',
                               side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as run:
                        app.run()
                    self.assertFalse(app.exception)
                    self.assertTrue(any('Saved analysis could not be loaded' in item.value
                                        for item in app.warning))
                    for key in ['report', 'financial_data', 'validation', 'agent_evaluation']:
                        self.assertNotIn(key, app.session_state)
                    run.assert_not_called()
                    self.assertEqual(cache.read_text(encoding='utf-8'), payload)

    def test_invalid_cached_figures_preserve_narrative_without_dashboard_crash(self):
        import report_storage
        from synthetic_financial_fixture import supported_submission
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            pdf = create_conflict_fixture(directory / 'fixture.pdf').read_bytes()
            for field, value in [('fiscal_year', 'not a year'),
                                 ('fiscal_year', True),
                                 ('operating_cash_flow', 'not a number'),
                                 ('currency', ['USD'])]:
                with self.subTest(field=field, value=value):
                    financial = supported_submission()
                    financial[field] = value
                    upload = BytesIO(pdf)
                    upload.name = 'fixture.pdf'
                    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'),
                                            default_timeout=20)
                    with patch('streamlit.file_uploader', return_value=upload), \
                         patch.object(report_storage, 'REPORTS_DIR', directory), \
                         patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
                         patch('due_diligence_engine.run_due_diligence',
                               side_effect=AssertionError('PAID_MODEL_FORBIDDEN')) as run:
                        report_storage.save_report(pdf, '# Retained cached narrative', {}, financial)
                        app.run()
                        saved = report_storage.load_report(pdf)
                    self.assertFalse(app.exception)
                    self.assertEqual(app.session_state['financial_data'], {})
                    self.assertIsNone(app.session_state['validation'])
                    self.assertTrue(app.session_state['report'].endswith('# Retained cached narrative'))
                    self.assertTrue(any('Financial evidence not fully verified' in item.value
                                        for item in app.markdown))
                    self.assertFalse(app.session_state['agent_evaluation']['final_eligible'])
                    self.assertEqual(saved['financial_data'], financial)
                    run.assert_not_called()
