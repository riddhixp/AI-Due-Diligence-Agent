
import os
import re
from agent_financial_review import review_financial_evidence
from optional_financial_validation import validate_optional_financial_data
from investigation_control import submission_block_reason
from investigation_outcome import investigation_outcome
from investigation_guidance import investigation_next_actions
from tool_sequence_audit import assess_tool_sequence
from verification_notice import final_verification_notice
from report_verification import finalise_dd_report
from audit_appendix import append_audit_appendix
from agent_evaluation import evaluate_agent_run
from run_limits import permitted_turn_limit
from cache_policy import should_cache_report
from correction_changes import financial_correction_changes
from revenue_narrative_check import find_reversed_revenue_arrows
from fault_injection import inject_first_submission_error
from interrupted_report import interrupted_report
from resume_transcript import extract_resume_input, inspect_replay_boundary
from sdk_resume_policy import classify_run_boundary
from sdk_pause_capture import capture_approval_pause, pause_public_status
from tool_state_rebinding import prepare_tool_state
from sdk_resume_gate import checked_resume_mode
from sdk_resume_once import consume_sdk_resume_state
from live_financial_pause_handoff import make_financial_pause_handoff, SDKFinancialApprovalPaused
from live_financial_approval_decision import decide_live_financial_pause
from live_continuation_preflight import preflight_live_continuation
from latest_review_gate import trusted_latest_review
from completion_boundary import enforce_completion_boundary
from final_artifact_policy import final_report_eligible
from offline_demo import simulate_conflict_correction
from offline_interruption_demo import simulate_turn_limit
from offline_approval_demo import start_offline_approval, finish_offline_approval
from sdk_offline_approval_demo import start_sdk_offline_approval, decide_sdk_offline_approval, resume_sdk_offline_approval
from full_financial_resume_demo import start_financial_resume_demo, finish_financial_resume_demo
from pdf_report import generate_pdf_report
from report_quality import check_report_quality
from financial_metric_labels import verify_metric_automatically
from financial_labels import verify_revenue_automatically
from column_detector import verify_value_by_year
from source_verifier import (
    verify_financial_data,
    check_statement_row_and_year,
    verify_with_alternative_labels,
)
from source_verifier import (
    verify_financial_data,
    check_statement_row_and_year,
)
from io import BytesIO

import streamlit as st
from report_storage import save_report, load_report
from dotenv import load_dotenv
from pypdf import PdfReader
from financial_validator import FinancialData, validate_financials
from financial_insights import (
    ExtendedFinancialData,
    calculate_financial_insights,
)
from financial_summary import generate_financial_summary
from agents import (
    Agent,
    Runner,
    function_tool,
    set_tracing_disabled,
)

load_dotenv()
set_tracing_disabled(True)

st.set_page_config(
    page_title="AI Due Diligence Analyst",
    page_icon="📊",
    layout="wide",
)

st.title("📊 AI Due Diligence Analyst")
st.caption(
    "Automated financial and technology due diligence"
)

st.warning(
    "Prototype: AI findings require human verification. "
    "Do not upload confidential client documents."
)


# -----------------------------
# Document processing
# -----------------------------

from due_diligence_engine import extract_pages, find_evidence, run_due_diligence


# -----------------------------
# Streamlit dashboard
# -----------------------------

st.subheader("1. Upload company report")

uploaded_file = st.file_uploader(
    "Select a PDF annual report",
    type=["pdf"],
)

if uploaded_file is not None:

    pdf_bytes = uploaded_file.getvalue()

    # Clear the previous report if the file changes
    file_id = (
        uploaded_file.name,
        len(pdf_bytes),
        __import__("hashlib").sha256(
            pdf_bytes
        ).hexdigest()
    )


    if st.session_state.get("file_id") != file_id:
        st.session_state["file_id"] = file_id
        st.session_state.pop("report", None)
        st.session_state.pop("validation", None)
        st.session_state.pop("financial_data", None)
        st.session_state.pop("agent_evaluation", None)
        st.session_state.pop("offline_approval_queue", None)
        st.session_state.pop("sdk_offline_approval", None)
        st.session_state.pop("financial_resume_demo", None)
        st.session_state.pop("financial_resume_result", None)
        st.session_state.pop("offline_application_workflow", None)
        st.session_state.pop("paid_test_plan_preview", None)
        st.session_state.pop("offline_practice_suite", None)
        st.session_state.pop("live_financial_pause", None)
        st.session_state.pop("live_continuation_preflight", None)

    if len(pdf_bytes) > 15 * 1024 * 1024:
        st.error("Please upload a PDF smaller than 15 MB.")
        st.stop()

    try:
        pages = extract_pages(pdf_bytes)
    except Exception as error:
        st.error(f"Could not read PDF: {error}")
        st.stop()

    readable = sum(bool(page.strip()) for page in pages)

    col1, col2, col3 = st.columns(3)

    col1.metric("Total pages", len(pages))
    col2.metric("Readable pages", readable)
    col3.metric(
        "File size",
        f"{len(pdf_bytes) / 1024 / 1024:.2f} MB"
    )

    if readable == 0:
        st.error(
            "No readable text found. "
            "Scanned PDFs will need OCR support."
        )
        st.stop()

    # Cached reports are rechecked against this PDF with the current rules.
    # A cache does not establish the original model's tool/review history.
    if "report" not in st.session_state:
        from cached_analysis_review import recheck_cached_analysis
        try:
            saved = load_report(pdf_bytes)
            if saved:
                refreshed = recheck_cached_analysis(saved, pages)
                for name in ("report", "validation", "financial_data", "agent_evaluation"):
                    st.session_state[name] = refreshed[name]
                st.info("Saved analysis loaded and evidence rechecked locally. "
                        "Original investigation history is unavailable. No API call was made.")
        except (ValueError, OSError):
            st.warning("Saved analysis could not be loaded. No AI model was run.")

    st.subheader("2. Check source evidence")

    evidence = find_evidence(
        pages,
        "total revenue net income",
        limit=3,
    )

    with st.expander("Preview financial evidence"):
        if evidence:
            for _, number, excerpt in evidence:
                st.markdown(f"**PDF page {number}**")
                st.text(excerpt[:1100])
        else:
            st.info(
                "No matching financial excerpt found."
            )

    st.caption(
        "These are search results, not yet verified "
        "financial figures. The agent will examine "
        "supporting pages."
    )

    st.subheader("3. Run AI analysis")

    st.checkbox(
        "Controlled smoke test (8 agent turns; still uses paid API credits)",
        key="smoke_test_mode",
        help=(
            "Limits the agent's turns for a short evaluation. "
            "This is not a monetary spending cap or a guarantee "
            "that the diligence report will be complete."
        ),
    )

    st.checkbox(
        "Inject wrong first revenue submission (synthetic conflict PDF only)",
        key="inject_test_error",
        help=(
            "Only works on synthetic_conflict_test.pdf. "
            "The first accepted FY2025 revenue of 120 is changed to 130 "
            "to test whether the agent finds and fixes the error. "
            "Uses paid API credits when analysis runs."
        ),
    )

    st.checkbox(
        "Pause paid investigation for financial submission approval (experimental)",
        key="real_financial_approval_mode",
        help=(
            "Requires a paid AI analysis run. Captures genuine SDK approval and "
            "financial checkpoint in this session; real paid resumption is disabled."
        ),
    )

    live_handoff = st.session_state.get("live_financial_pause")
    if live_handoff is not None:
        from live_financial_pause_handoff import public_financial_pause_status
        public_pause = public_financial_pause_status(live_handoff)
        st.warning(
            "Real investigation paused for financial approval. "
            "No completed report was produced. Paid resume is disabled."
        )
        st.write("Pending approval checkpoint:", public_pause)
        if live_handoff.get("status") == "AWAITING_APPROVAL":
            st.caption(
                "This decision will be applied to the paused SDK state. "
                "It will not resume the AI model or use additional API credits."
            )
            approve_live, reject_live = st.columns(2)
            if approve_live.button("Approve paused financial submission"):
                try:
                    decide_live_financial_pause(live_handoff, pdf_bytes, True)
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
            if reject_live.button("Reject paused financial submission"):
                try:
                    decide_live_financial_pause(live_handoff, pdf_bytes, False)
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
        else:
            st.info(
                "Financial submission decision recorded: "
                f"{live_handoff['status']}. The model has not resumed."
            )
            if live_handoff["status"] == "APPROVED":
                if st.button("Check financial continuation readiness (FREE)"):
                    try:
                        st.session_state["live_continuation_preflight"] = (
                            preflight_live_continuation(live_handoff, pdf_bytes)
                        )
                    except ValueError as error:
                        st.error(str(error))
                ready = st.session_state.get("live_continuation_preflight")
                if ready is not None:
                    st.write("Continuation checks:", ready)
                    st.caption("No AI model resumed; paid continuation remains disabled.")
        if st.button("Discard paused investigation"):
            st.session_state.pop("live_financial_pause", None)
            st.rerun()

    st.subheader("FREE approval interface demo")
    st.caption(
        "Synthetic decision queue only. No AI, no API credits, "
        "and no resumed investigation."
    )
    if st.button("Start FREE approval demo"):
        st.session_state["offline_approval_queue"] = start_offline_approval(pdf_bytes)
    demo_queue = st.session_state.get("offline_approval_queue")
    if demo_queue is not None:
        from approval_queue import approval_public_status
        public_approval = approval_public_status(demo_queue)
        st.write("Approval status:", public_approval["approvals"][0])
        if public_approval["approvals"][0] == "PENDING":
            approve_col, reject_col = st.columns(2)
            if approve_col.button("Approve demo submission"):
                finish_offline_approval(demo_queue, pdf_bytes, True)
                st.success("Synthetic approval recorded. No tool or model was run.")
            if reject_col.button("Reject demo submission"):
                finish_offline_approval(demo_queue, pdf_bytes, False)
                st.info("Synthetic rejection recorded. No tool or model was run.")

    st.subheader("FREE real-SDK approval demo")
    st.caption(
        "A scripted local model creates a real SDK pause. "
        "Approval/rejection is applied to RunState, but the model is NOT resumed."
    )
    if st.button("Create FREE SDK approval pause"):
        st.session_state["sdk_offline_approval"] = start_sdk_offline_approval(pdf_bytes)
        st.success("SDK RunState paused. No external model calls.")
    sdk_demo = st.session_state.get("sdk_offline_approval")
    if sdk_demo is not None:
        from approval_queue import approval_public_status
        sdk_public = approval_public_status(sdk_demo)
        if sdk_demo.get("decisions_applied") and not sdk_demo.get("offline_resumed"):
            if st.button("Resume FREE scripted SDK demo"):
                result = resume_sdk_offline_approval(sdk_demo, pdf_bytes)
                st.success(
                    "Real SDK continuation completed using a scripted offline model. "
                    f"Executed synthetic submissions: {len(result['executed_submissions'])}. "
                    "No external API calls."
                )
                st.rerun()
        elif sdk_demo.get("offline_resumed"):
            st.success(
                "FREE scripted SDK resume completed. "
                f"Synthetic submissions executed: {len(sdk_demo['_offline_executed'])}. "
                "External API calls: 0."
            )
        if sdk_public["approvals"][0] == "PENDING":
            sdk_yes, sdk_no = st.columns(2)
            if sdk_yes.button("Approve SDK demo"):
                decide_sdk_offline_approval(sdk_demo, pdf_bytes, True)
                st.rerun()
            if sdk_no.button("Reject SDK demo"):
                decide_sdk_offline_approval(sdk_demo, pdf_bytes, False)
                st.rerun()
        elif sdk_public["approvals"][0] == "APPROVED":
            st.success("SDK financial submission approval: APPROVED. No model resumed or API call made.")
        elif sdk_public["approvals"][0] == "REJECTED":
            st.info("SDK financial submission approval: REJECTED. No financial tool executed.")

    from correction_workflow_ui import render_correction_workflow
    render_correction_workflow(st, pdf_bytes)
    from practice_scenarios_ui import render_practice_scenarios
    render_practice_scenarios(st, pdf_bytes)
    from paid_test_planning_ui import render_paid_test_planning
    render_paid_test_planning(st, pdf_bytes)

    if st.button("Run FREE interruption demo"):
        try:
            report, validation, financial_data, agent_evaluation = (
                simulate_turn_limit(pages)
            )
            st.session_state["report"] = report
            st.session_state["validation"] = validation
            st.session_state["financial_data"] = financial_data
            st.session_state["agent_evaluation"] = agent_evaluation
            st.info(
                "Interruption with an unreviewed financial submission "
                "simulated. No OpenAI API credits used."
            )
        except ValueError as error:
            st.error(str(error))

    if st.button("Run FREE offline correction demo"):
        try:
            report, validation, financial_data, agent_evaluation = (
                simulate_conflict_correction(pages)
            )
            st.session_state["report"] = report
            st.session_state["validation"] = validation
            st.session_state["financial_data"] = financial_data
            st.session_state["agent_evaluation"] = agent_evaluation
            st.success(
                "Scripted offline correction completed. No OpenAI API "
                "credits were used. This does not test autonomous AI."
            )
        except ValueError as error:
            st.error(str(error))

    if st.button(
        "Analyse Company",
        type="primary",
        width="stretch",
    ):
        if not os.getenv("OPENAI_API_KEY"):
            st.error(
                "OPENAI_API_KEY is missing from .env"
            )
        else:
            with st.spinner(
                "Analysing the company report..."
            ):
                

                try:
                    report, validation, financial_data, agent_evaluation = run_due_diligence(
                        pages,
                        max_turns=8 if st.session_state.get('smoke_test_mode') else None,
                        inject_test_error=bool(st.session_state.get("inject_test_error")),
                        financial_approval_required=bool(st.session_state.get("real_financial_approval_mode")),
                        pause_pdf_bytes=pdf_bytes,
                    )
                    st.session_state["report"] = report
                    st.session_state["validation"] = validation
                    st.session_state["financial_data"] = financial_data
                    st.session_state["agent_evaluation"] = agent_evaluation
                    if (should_cache_report(bool(st.session_state.get("smoke_test_mode")))
                            and final_report_eligible(agent_evaluation, st.session_state.get("live_financial_pause"))):
                        save_report(
                            pdf_bytes,
                            report,
                            validation,
                            financial_data,
                        )
                    else:
                        st.info(
                            "Smoke-test result is session-only. "
                            "It has not replaced the cached full report."
                        )
                except SDKFinancialApprovalPaused as paused:
                    st.session_state["live_financial_pause"] = paused.handoff
                    st.warning(
                        "Actual SDK approval pause captured. Financial progress "
                        "was preserved in this session. Paid resume is disabled. "
                        "No finished due diligence report was created."
                    )
                except Exception as error:
                    st.error(
                        "Analysis failed: "
                        f"{type(error).__name__}: {error}"
                    )

        


    if "report" in st.session_state:
        validation = st.session_state.get("validation")


        st.subheader("4. Due diligence findings")
        agent_evaluation = st.session_state.get("agent_evaluation")
        if agent_evaluation and agent_evaluation.get("simulation"):
            st.info(
                "OFFLINE SIMULATION — predetermined tool steps, "
                "not a real AI model run. No API calls made."
            )
        if agent_evaluation:
            st.subheader("Agent investigation evaluation")
            if agent_evaluation["evaluation"] == "INTERRUPTED_TURN_LIMIT":
                st.error(
                    "Investigation interrupted before a final AI report. "
                    "Submitted numbers may be unverified; this is not a pass."
                )
            elif agent_evaluation["evaluation"] == "PRELIMINARY_PASS":
                st.success(
                    "Financial evidence and tool sequencing passed "
                    "preliminary automated checks. Human validation "
                    "is still required."
                )
            else:
                st.warning(
                    "Outstanding investigation checks require review "
                    "before relying on the findings."
                )
            st.json(agent_evaluation)
            import json
            st.download_button(
                "Download investigation evaluation (JSON)",
                data=json.dumps(agent_evaluation, indent=2),
                file_name="agent_investigation_evaluation.json",
                mime="application/json",
            )
        else:
            st.caption(
                "No live tool-use evaluation is stored for this report. "
                "Cached analyses do not establish which tools were called."
            )

        current_financials = st.session_state.get("financial_data")
        current_review = (
            review_financial_evidence(pages, current_financials)
            if current_financials else None
        )
        notice_level, notice_message = final_verification_notice(
            current_financials, current_review
        )
        if notice_level == "warning":
            st.warning(notice_message)
        else:
            st.info(notice_message)
        st.markdown(st.session_state["report"])

    

        # Financial dashboard
        financial_data = st.session_state.get("financial_data")

        if financial_data and validation:
            year = int(financial_data["fiscal_year"])
            currency = financial_data["currency"]
            units = financial_data["units"]

            # Financial KPI cards
            st.subheader("Financial Overview")

            st.caption(
                f"FY{year} | {currency} | {units} | "
                "Arithmetic checks only"
            )

            col1, col2, col3, col4 = st.columns(4)

            col1.metric(
                "Revenue",
                f"{financial_data['revenue_current']:,.0f}"
            )

            col2.metric(
                "Revenue growth",
                f"{validation['revenue_growth']['calculated']:.2f}%"
            )

            col3.metric(
                "Gross margin",
                f"{validation['gross_margin']['calculated']:.2f}%"
            )

            col4.metric(
                "Net margin",
                f"{validation['net_margin']['calculated']:.2f}%"
            )

            # Revenue chart
            st.subheader("Revenue Comparison")

            revenue_chart = {
                f"FY{year - 1}": financial_data["revenue_previous"],
                f"FY{year}": financial_data["revenue_current"],
            }

            st.bar_chart(
                revenue_chart,
                x_label="Fiscal year",
                y_label=f"Revenue ({currency}, {units})",
            )

            # Additional financial diagnostics based on available inputs.
            extended_data = ExtendedFinancialData(
                revenue_current=financial_data["revenue_current"],
                revenue_previous=financial_data["revenue_previous"],
                gross_profit=financial_data["gross_profit"],
                net_income=financial_data["net_income"],
                operating_income=financial_data.get("operating_income"),
                operating_cash_flow=financial_data.get("operating_cash_flow"),
                capital_expenditure=financial_data.get("capital_expenditure"),
                subscription_revenue=financial_data.get("subscription_revenue"),
            )

            insights = calculate_financial_insights(extended_data)

            st.subheader("Financial Diagnostics")

            st.caption(
                "Calculated from the extracted financial inputs. "
                "Unavailable metrics indicate missing information, "
                "not zero values. Source accuracy requires separate "
                "verification."
            )

            diagnostic_labels = {
                "revenue_growth": "Revenue growth",
                "gross_margin": "Gross margin",
                "net_margin": "Net margin",
                "operating_margin": "Operating margin",
                "operating_cash_conversion": "Operating cash conversion",
                "subscription_revenue_share": "Subscription revenue share",
                "free_cash_flow": "Free cash flow",
            }

            diagnostic_rows = []

            for metric, label in diagnostic_labels.items():
                value = insights[metric]

                if value is None:
                    display_value = "Unavailable"
                    status = "Missing required input"
                elif metric == "free_cash_flow":
                    display_value = f"{value:,.2f} {currency} {units}"
                    status = "Calculated"
                else:
                    display_value = f"{value:.2f}%"
                    status = "Calculated"

                diagnostic_rows.append({
                    "Indicator": label,
                    "Result": display_value,
                    "Status": status,
                })

            st.dataframe(
                diagnostic_rows,
                width="stretch",
                hide_index=True,
            )

            # Evidence-aware financial insights for management review.
            management_insights = generate_financial_summary(
                financial_data
            )

            st.subheader("Management Financial Insights")

            st.caption(
                "Preliminary observations derived from extracted "
                "financial inputs. These do not independently "
                "verify source figures or establish investment merit."
            )

            for number, insight in enumerate(management_insights, 1):
                with st.container(border=True):
                    st.markdown(
                        f"**{number}. {insight['title']}**"
                    )
                    st.write(insight["finding"])

                    st.markdown("**Why it matters**")
                    st.write(insight["implication"])

                    st.markdown("**Management action**")
                    st.write(insight["next_step"])


        # Source verification for the uploaded company
        st.subheader("Source Evidence Checks")

        st.caption(
            "Checks whether submitted financial figures "
            "appear on the cited PDF page. "
            "A matching number does not prove the "
            "correct metric, year, or units."
        )

        if financial_data:
            source_results = verify_financial_data(
                pages,
                financial_data,
            )

            # Stronger verification for gross profit:
            # accept approved alternative statement labels.
            gross_value = financial_data.get("gross_profit")
            fiscal_year = financial_data.get("fiscal_year")
            source_pages = financial_data.get("source_pages") or {}
            gross_page = source_pages.get("gross_profit")

            if (
                isinstance(gross_value, (int, float))
                and not isinstance(gross_value, bool)
                and isinstance(fiscal_year, int)
                and not isinstance(fiscal_year, bool)
                and isinstance(gross_page, int)
                and not isinstance(gross_page, bool)
            ):
                gross_check = verify_with_alternative_labels(
                    pages=pages,
                    value=gross_value,
                    page_number=gross_page,
                    labels=["Gross profit", "Gross margin"],
                    fiscal_year=fiscal_year,
                    column_index=0,
                )


                for result in source_results:
                    if result.get("Financial figure") == "Gross profit":
                        result["Result"] = gross_check["status"]

                        explanation = gross_check.get("reason", "")
                        matched_label = gross_check.get("matched_label")

                        if matched_label:
                            explanation += f" | Statement label: {matched_label}"

                        result["Explanation"] = explanation


            if source_results:
                st.dataframe(
                    source_results,
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.warning(
                    "No financial figures available "
                    "for source verification."
                )
        else:
            st.warning(
                "No structured financial data available "
                "for source verification."
            )


        # Automatic financial statement year verification
        st.subheader("Financial Statement Row & Year Check")

        st.caption(
            "Checks revenue against fiscal-year headings "
            "and financial statement rows. "
            "Experimental: complex PDF layouts require manual review."
        )

        if financial_data:
            source_pages = financial_data.get("source_pages") or {}
            fiscal_year = int(financial_data["fiscal_year"])

            revenue_checks = [
                (
                    "Current-year revenue",
                    financial_data["revenue_current"],
                    source_pages.get("revenue_current"),
                    fiscal_year,
                ),
                (
                    "Previous-year revenue",
                    financial_data["revenue_previous"],
                    source_pages.get("revenue_previous"),
                    fiscal_year - 1,
                ),
            ]

            stronger_rows = []

            for label, value, page, year in revenue_checks:
                if (
                    not isinstance(page, int)
                    or not 1 <= page <= len(pages)
                ):
                    result = {
                        "status": "NEEDS_REVIEW",
                        "reason": "Missing or invalid PDF page.",
                    }

                else:
                    result = verify_revenue_automatically(
                        page_text=pages[page - 1],
                        fiscal_year=year,
                        expected_value=value,
                    )

                stronger_rows.append({
                    "Metric": label,
                    "Fiscal year": year,
                    "Value": value,
                    "PDF page": page,
                    "Result": result["status"],
                    "Explanation": result["reason"],
                })

            # Verify gross profit and net income
            additional_checks = [
                ("Gross profit", "gross_profit"),
                ("Net income", "net_income"),
            ]

            for label, metric in additional_checks:
                page = source_pages.get(metric)
                value = financial_data.get(metric)

                if (
                    not isinstance(page, int)
                    or not 1 <= page <= len(pages)
                    or value is None
                ):
                    result = {
                        "status": "NEEDS_REVIEW",
                        "reason": "Missing figure or valid source page.",
                    }
                else:
                    result = verify_metric_automatically(
                        page_text=pages[page - 1],
                        metric=metric,
                        fiscal_year=fiscal_year,
                        expected_value=value,
                    )

                stronger_rows.append({
                    "Metric": label,
                    "Fiscal year": fiscal_year,
                    "Value": value,
                    "PDF page": page,
                    "Result": result["status"],
                    "Explanation": result["reason"],
                })


            st.dataframe(
                stronger_rows,
                width="stretch",
                hide_index=True,
            )
        else:
            st.info(
                "Financial data unavailable for row-and-year checks."
            )

        st.subheader("Financial Validation Results")
        validation = st.session_state.get("validation")

        if validation:
            for metric, result in validation.items():
                status = result["status"]

                if status == "PASS":
                    st.success(
                        f"{metric}: PASS — "
                        f"Calculated {result['calculated']}%"
                    )
                elif status == "FAIL":
                    st.error(
                        f"{metric}: FAIL — "
                        f"AI reported {result['reported']}%, "
                        f"Python calculated "
                        f"{result['calculated']}%"
                    )
                else:
                    st.warning(f"{metric}: MISSING")
        else:
            if agent_evaluation and agent_evaluation["evaluation"] == "INTERRUPTED_TURN_LIMIT":
                st.warning(
                    "The investigation stopped before arithmetic validation "
                    "was completed. Submitted figures remain unverified."
                )
            else:
                st.warning(
                    "Structured financial data was not "
                    "submitted. Validation unavailable."
                )

        st.caption(
            "PASS confirms arithmetic agreement only. "
            "It does not independently verify the "
            "underlying figures or PDF citations."
        )
        # Check the report's writing quality before download.
        quality_issues = (
            []
            if agent_evaluation and agent_evaluation["evaluation"] == "INTERRUPTED_TURN_LIMIT"
            else check_report_quality(st.session_state["report"])
        )

        st.subheader("Report Quality Review")

        if agent_evaluation and agent_evaluation["evaluation"] == "INTERRUPTED_TURN_LIMIT":
            st.info(
                "Full-report quality checks are skipped for an interrupted "
                "investigation. This is a progress summary, not a final report."
            )
        elif quality_issues:
            st.warning(
                f"{len(quality_issues)} potential report quality "
                "issue(s) detected. Review these before using "
                "the report professionally."
            )

            with st.expander("View quality warnings", expanded=True):
                for issue in quality_issues:
                    st.write(f"• {issue}")
        else:
            st.success(
                "No issues detected by the automated writing "
                "and structure checks."
            )

        st.caption(
            "These checks flag possible writing and structural "
            "issues. They do not verify financial figures, "
            "source citations or analytical conclusions."
        )


        if final_report_eligible(agent_evaluation, st.session_state.get("live_financial_pause")):
            # Export the preliminary report only after verification checks.
            try:
                report_pdf_bytes = generate_pdf_report(
                    report=st.session_state["report"],
                    financial_data=st.session_state.get("financial_data"),
                    validation=st.session_state.get("validation"),
                )

                st.download_button(
                    label="Download Professional PDF Report",
                    data=report_pdf_bytes,
                    file_name="due_diligence_report.pdf",
                    mime="application/pdf",
                    width="stretch",
                )

            except Exception as exc:
                st.error(
                    f"PDF export unavailable: {exc}"
                )


            st.download_button(
                label="Download Due Diligence Report",
                data=st.session_state["report"],
                file_name="due_diligence_report.md",
                mime="text/markdown",
                width="stretch",
            )

        else:
            st.warning(
                "Final report exports are disabled because the investigation "
                "has not passed all financial evidence and sequence checks. "
                "The progress summary and evaluation remain visible."
            )

        st.info(
            "Before using this report, check important "
            "figures, calculations and citations "
            "against the uploaded PDF."
        )

else:
    st.info("Upload a company PDF to begin.")
