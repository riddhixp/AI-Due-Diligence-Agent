"""Application offline workflows must not require the repository's tests package."""
import subprocess
import sys
import unittest


class OfflineRuntimeImportTests(unittest.TestCase):
    def test_application_imports_without_tests_package(self):
        script = '''
import importlib.abc
import sys
class BlockTests(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "tests" or fullname.startswith("tests."):
            raise ImportError("Application attempted to import tests")
sys.meta_path.insert(0, BlockTests())
import offline_demo
import offline_interruption_demo
import sdk_offline_approval_demo
import full_financial_resume_demo
from scripted_offline_model import ScriptedOfflineModel
from sdk_resume_gate import checked_resume_mode
from types import SimpleNamespace
assert checked_resume_mode({}, b"pdf", SimpleNamespace(get_interruptions=lambda: []),
                           ScriptedOfflineModel()) == "OFFLINE_SDK_RESUME"
'''
        result = subprocess.run([sys.executable, '-c', script],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_engine_and_orchestrator_do_not_import_streamlit_page(self):
        script = """
import importlib.abc
import sys
class BlockUI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in ('app', 'streamlit') or fullname.startswith('streamlit.'):
            raise ImportError('Investigation engine imported UI')
sys.meta_path.insert(0, BlockUI())
import due_diligence_engine
import financial_approval_resume
import offline_correction_workflow
"""
        result = subprocess.run([sys.executable, '-c', script],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
