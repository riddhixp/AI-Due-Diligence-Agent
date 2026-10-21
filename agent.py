
from pathlib import Path
import os
import re
import sys

from dotenv import load_dotenv
from pypdf import PdfReader
from agents import (
    Agent,
    Runner,
    function_tool,
    set_tracing_disabled,
)

load_dotenv()
set_tracing_disabled(True)

# Files are located beside this Python script
FOLDER = Path(__file__).resolve().parent
PDF_FILE = FOLDER / "company_report.pdf"
OUTPUT_FILE = FOLDER / "due_diligence_report.md"

if not PDF_FILE.exists():
    raise SystemExit("Missing company_report.pdf")

# Load every page into a searchable local index
reader = PdfReader(str(PDF_FILE))
pages = [
    (page.extract_text() or "").replace("\x00", "")
    for page in reader.pages
]

print(f"Loaded {len(pages)} PDF pages.")


def search_pages(query: str) -> str:
    """Search all PDF pages and return relevant excerpts."""

    words = re.findall(r"[a-z0-9]+", query.lower())
    words = [w for w in words if len(w) > 2]

    if not words:
        return "Enter a more specific search query."

    matches = []

    for page_num, content in enumerate(pages, start=1):
        lower = content.lower()

        score = sum(lower.count(w) for w in words)

        if score == 0:
            continue

        # Find an occurrence of a search term
        positions = [lower.find(w) for w in words]
        positions = [p for p in positions if p >= 0]

        position = min(positions)

        # Retrieve a relevant excerpt, not the whole page
        start = max(0, position - 400)
        end = min(len(content), position + 1600)

        excerpt = content[start:end]

        matches.append((score, page_num, excerpt))

    matches.sort(reverse=True)

    if not matches:
        return f"No matching text found for: {query}"

    result = []

    for score, page_num, excerpt in matches[:5]:
        result.append(
            f"\nPDF PAGE {page_num}\n"
            f"Search score: {score}\n"
            f"{excerpt}\n"
        )

    return "\n---\n".join(result)


@function_tool
def search_report(query: str) -> str:
    """Search the annual report for financial, business or
    risk information. Query is a short keyword phrase.
    Returns page-numbered excerpts from matching pages.
    """
    return search_pages(query)


@function_tool
def read_page(page_number: int) -> str:
    """Read one PDF page using its 1-based PDF page number.
    Use this to verify figures or obtain more context.
    """
    if page_number < 1 or page_number > len(pages):
        return "Invalid page number."

    content = pages[page_number - 1]

    return (
        f"PDF PAGE {page_number}\n"
        + content[:12000]
    )


@function_tool
def calculate_growth(
    current: float,
    previous: float
) -> str:
    """Calculate percentage growth from a previous
    period to a current period. Both values must use
    the same currency and units.
    """
    if previous == 0:
        return "Cannot calculate growth: previous is zero."

    growth = ((current - previous) / abs(previous)) * 100

    return f"Growth: {growth:.2f}%"


@function_tool
def calculate_margin(
    profit: float,
    revenue: float
) -> str:
    """Calculate a profit margin percentage.
    Profit and revenue must use the same units
    and reporting period.
    """
    if revenue == 0:
        return "Cannot calculate margin: revenue is zero."

    margin = (profit / revenue) * 100

    return f"Margin: {margin:.2f}%"


agent = Agent(
    name="Financial and Technology Due Diligence Agent",
    model="gpt-5-mini",
    tools=[
        search_report,
        read_page,
        calculate_growth,
        calculate_margin,
    ],
    instructions="""
You are a careful due diligence analyst working
for a private equity investment team.

Analyse the PDF report using your available tools.

First search the report to locate:
- The company business model
- Revenue and financial performance
- Financial statements
- Risk factors and cybersecurity
- Growth strategy and competitive position

Then read relevant pages to verify important figures.

Use the financial calculator tools when the
necessary reported figures are available.

Generate a structured report with:

1. Executive summary
2. Company overview and business model
3. Financial performance
   - Current and prior-year revenue
   - Revenue growth
   - Profitability and margins
   - Cash flow, if available
4. Technology and operational risks
5. Market position and competition
6. Growth opportunities
7. Top five due diligence questions
8. Preliminary investment assessment

Strict requirements:
- Do not invent financial numbers.
- Clearly state currency, units and fiscal years.
- Cite the actual PDF page number for claims.
- Separate reported facts from analysis.
- If data is missing, say "Not verified".
- Do not treat keyword matches as verified evidence.
- Read the relevant page for financial calculations.
- Do not guess about confidential technology architecture.
- Report limitations and unanswered questions.
- Do not give a definitive buy/sell recommendation.

This is preliminary desk-based diligence,
not a replacement for a full professional review.
"""
)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("\nTesting document search (no API call)...")
        print(search_pages("total net revenue")[:1800])
        return

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Missing OPENAI_API_KEY in .env")

    print("Starting Session 2 AI Due Diligence Agent...")

    result = Runner.run_sync(
        agent,
        (
            "Perform preliminary due diligence on the "
            "uploaded annual report. Use the tools to "
            "locate and verify financial data, calculate "
            "revenue growth and margins where possible, "
            "and produce an evidence-backed report."
        ),
        max_turns=20,
    )

    report = str(result.final_output)

    OUTPUT_FILE.write_text(
        report,
        encoding="utf-8"
    )

    print("\n" + report)
    print(f"\nReport saved: {OUTPUT_FILE.name}")


if __name__ == "__main__":
    main()
