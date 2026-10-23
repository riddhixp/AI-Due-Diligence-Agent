"""Regression check: PDF report rendering must not overwrite uploaded document bytes."""
import ast
import unittest
from pathlib import Path


class PDFExportIsolationTests(unittest.TestCase):
    def test_report_export_has_separate_binary_variable(self):
        source = Path(__file__).resolve().parents[1].joinpath("app.py").read_text()
        tree = ast.parse(source)
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "generate_pdf_report"
        ]
        self.assertEqual(len(calls), 1)
        parents = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Assign) and node.value is calls[0]
        ]
        self.assertEqual(len(parents), 1)
        self.assertEqual(
            [target.id for target in parents[0].targets if isinstance(target, ast.Name)],
            ["report_pdf_bytes"],
        )


if __name__ == "__main__":
    unittest.main()
