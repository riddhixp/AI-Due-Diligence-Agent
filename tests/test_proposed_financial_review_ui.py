"""Proposal evidence verdict must be visible without opening the details."""
import unittest
from unittest.mock import MagicMock, patch

from proposed_financial_review_ui import render_proposed_financial_review


class ProposedFinancialReviewUITests(unittest.TestCase):
    def setUp(self):
        self.st = MagicMock()
        self.expected = "abcd1234"
        self.state = object()
        self.pages = ["synthetic source"]

    def render(self, result):
        with patch("proposed_financial_review_ui.review_proposed_financial_request",
                   return_value=result) as review:
            render_proposed_financial_review(
                self.st, self.state, self.pages, self.expected)
        review.assert_called_once_with(self.state, self.pages)

    def test_pass_verdict_appears_before_detail_expander(self):
        self.render({
            "request_sha256": self.expected,
            "status": "PRELIMINARY_CHECKS_PASSED",
            "arithmetic": {"growth": {"status": "PASS"}},
            "statement_checks": [{"status": "ROW_YEAR_MATCH"}],
        })
        self.st.info.assert_called_once()
        self.assertIn("not been accepted or executed", self.st.info.call_args.args[0])
        self.assertLess(
            next(i for i, call in enumerate(self.st.mock_calls)
                 if str(call).startswith('call.info(')),
            next(i for i, call in enumerate(self.st.mock_calls)
                 if str(call).startswith("call.expander(")),
        )
        self.st.dataframe.assert_called_once()
        self.st.warning.assert_not_called()

    def test_incorrect_proposal_is_flagged_before_details(self):
        self.render({
            "request_sha256": self.expected,
            "status": "NEEDS_REVIEW",
            "citation_issues": ["source page mismatch"],
        })
        self.st.info.assert_not_called()
        self.assertIn("need review", self.st.warning.call_args_list[0].args[0])
        self.assertLess(
            next(i for i, call in enumerate(self.st.mock_calls)
                 if str(call).startswith("call.warning(")),
            next(i for i, call in enumerate(self.st.mock_calls)
                 if str(call).startswith("call.expander(")),
        )
        self.st.warning.assert_any_call("source page mismatch")

    def test_attention_summary_precedes_expandable_details(self):
        self.render({
            "request_sha256": self.expected, "status": "NEEDS_REVIEW",
            "arithmetic": {"growth": {"status": "FAIL"}},
            "sources": [{"Result": "NOT_FOUND"}],
            "statement_checks": [
                {"status": "NEEDS_REVIEW"}, {"status": "ROW_YEAR_MATCH"}],
            "metadata_issues": ["private company text"],
            "optional_issues": ["unsupported cash flow"],
            "citation_issues": ["missing page"],
        })
        summaries = [call.args[0] for call in self.st.caption.call_args_list]
        self.assertIn("Arithmetic discrepancies: 1", summaries)
        self.assertIn("Source-number concerns: 1", summaries)
        self.assertIn("Statement row/year concerns: 1", summaries)
        self.assertIn("Financial metadata concerns: 1", summaries)
        self.assertIn("Optional metric concerns: 1", summaries)
        self.assertIn("Citation concerns: 1", summaries)
        self.assertFalse(any("private company text" in line for line in summaries))
        first_caption = next(i for i, call in enumerate(self.st.mock_calls)
                             if str(call).startswith("call.caption("))
        expander = next(i for i, call in enumerate(self.st.mock_calls)
                        if str(call).startswith("call.expander("))
        self.assertLess(first_caption, expander)

    def test_attention_summary_skips_malformed_or_large_details(self):
        from proposed_financial_review_ui import _review_attention_summary
        summary = _review_attention_summary({
            "arithmetic": "invalid",
            "statement_checks": [{}] * 101,
            "sources": None,
            "metadata_issues": "not a list",
            "citation_issues": [object()] * 101,
            "optional_issues": ["one"],
        })
        self.assertEqual(summary, ["Optional metric concerns: 1"])

    def test_stale_request_never_claims_preliminary_pass(self):
        self.render({"request_sha256": "stale", "status": "PRELIMINARY_CHECKS_PASSED"})
        self.st.info.assert_not_called()
        self.st.expander.assert_not_called()
        self.st.warning.assert_called_once_with(
            "Local checks are unavailable. Inspect the PDF evidence before recording a decision.")

    def test_unavailable_proposal_shows_visible_warning(self):
        self.render({"request_sha256": self.expected, "status": "REVIEW_UNAVAILABLE"})
        self.st.info.assert_not_called()
        self.st.warning.assert_called_once_with(
            "Local checks are unavailable: the proposal is incomplete.")

    def test_review_errors_never_look_like_pass(self):
        with patch("proposed_financial_review_ui.review_proposed_financial_request",
                   side_effect=ValueError("private PDF contents")):
            render_proposed_financial_review(
                self.st, self.state, self.pages, self.expected)
        self.st.info.assert_not_called()
        self.st.expander.assert_not_called()
        self.assertNotIn("private PDF contents", str(self.st.warning.call_args))


if __name__ == "__main__":
    unittest.main()
