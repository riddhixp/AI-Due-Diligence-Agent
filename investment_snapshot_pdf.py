"""One-page, preliminary PE/M&A briefing from an existing investment briefing.

Does not call an AI API, verify source figures or issue investment advice.
"""
from io import BytesIO
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import simpleSplit
from reportlab.platypus import Paragraph
from reportlab.pdfbase.pdfmetrics import stringWidth
from xml.sax.saxutils import escape

NAVY = colors.HexColor('#16263E')
INK = colors.HexColor('#263446')
MUTED = colors.HexColor('#586476')
LINE = colors.HexColor('#DCE3EB')
PALE = colors.HexColor('#F3F6FA')


def _plain(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def _excerpt(value, limit=210):
    text = _plain(value)
    if len(text) <= limit:
        return text
    return text[:limit - 3].rsplit(' ', 1)[0].rstrip(' ,.;:') + '...'


def generate_investment_snapshot_pdf(brief):
    """Return one-page PDF bytes, using existing structured analysis only."""
    buf = BytesIO()
    from reportlab.pdfgen.canvas import Canvas
    page_w, page_h = A4
    c = Canvas(buf, pagesize=A4)
    c.setTitle('Preliminary Investment Committee Snapshot')
    margin = 43
    usable = page_w - 2 * margin
    y = page_h - 43

    pstyle = ParagraphStyle('Body', fontName='Helvetica', fontSize=8.35,
        leading=11.7, textColor=INK, alignment=TA_LEFT)
    small = ParagraphStyle('Small', parent=pstyle, fontSize=7.5, leading=10.4)
    headline = ParagraphStyle('Headline', parent=pstyle, fontName='Helvetica-Bold',
        fontSize=9, leading=12.3, textColor=NAVY)

    def para(value, style=pstyle, after=5):
        nonlocal y
        p = Paragraph(escape(_plain(value)), style)
        _, height = p.wrap(usable, page_h)
        if y - height < 65:
            raise ValueError('Snapshot exceeds one page; shorten the source briefing.')
        p.drawOn(c, margin, y - height)
        y -= height + after

    def section(label):
        nonlocal y
        y -= 5
        c.setStrokeColor(LINE)
        c.line(margin, y, page_w - margin, y)
        y -= 16
        c.setFont('Helvetica-Bold', 9)
        c.setFillColor(NAVY)
        c.drawString(margin, y, label.upper())
        y -= 13

    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 18)
    c.drawString(margin, y, 'INVESTMENT COMMITTEE SNAPSHOT')
    y -= 22
    company = _excerpt(brief.get('company', 'Company'), 70)
    year = brief.get('fiscal_year') or 'Period not specified'
    c.setFont('Helvetica', 10)
    c.setFillColor(MUTED)
    c.drawString(margin, y, f'{company}  |  FY{year}  |  Preliminary public-document assessment')
    y -= 23

    c.setFillColor(PALE)
    c.roundRect(margin, y - 29, usable, 34, 5, fill=1, stroke=0)
    c.setFont('Helvetica-Bold', 9)
    c.setFillColor(NAVY)
    c.drawString(margin + 10, y - 8, 'STATUS: HUMAN REVIEW REQUIRED')
    c.setFont('Helvetica', 8)
    c.drawString(margin + 10, y - 21, 'Not an investment recommendation, audit or verified quality-of-earnings report.')
    y -= 42

    section('Financial investment considerations')
    priorities = brief.get('financial_priorities') or []
    for index, item in enumerate(priorities[:2], 1):
        para(f'{index}. {_excerpt(item.get("title"), 110)}', headline, 2)
        para(_excerpt(item.get('implication'), 220), pstyle, 2)
        para('NEXT ACTION: ' + _excerpt(item.get('next_step'), 170), small, 7)
        pages = [str(x) for x in item.get('source_pages', []) if type(x) is int]
        if pages:
            para('Submitted PDF page(s): ' + ', '.join(pages) + ' (not independently verified).', small, 5)

    section('Management information requests')
    # Exclude unresolved placeholders from the presentation, but never silently
    # repair them. The original stays available in the full underlying report.
    all_questions = brief.get('diligence_questions') or []
    placeholder = re.compile(r'(?i)(?:>\s*X\s*%|\bTBD\b|\[insert\b)')
    valid_questions = [q for q in all_questions if not placeholder.search(str(q))]
    excluded_count = len(all_questions) - len(valid_questions)
    for index, question in enumerate(valid_questions[:3], 1):
        para(f'{index}. {_excerpt(question, 190)}', small, 5)
    if len(valid_questions) > 3:
        para(f'{len(valid_questions) - 3} additional request(s) in the full diligence report.', small, 3)
    if excluded_count:
        para(f'{excluded_count} request(s) withheld from this snapshot: unresolved placeholder; edit the original report.', small, 4)

    section('Evidence and review requirements')
    gaps = brief.get('evidence_gaps') or []
    for gap in gaps[:1]:
        para(_excerpt(gap.get('finding'), 190), small, 4)
    issues = brief.get('quality_issues') or []
    para(f'Automated report-quality warnings: {len(issues)}. '
         'Read and resolve warnings in the dashboard before circulation.', small, 3)
    para('Source figures and page citations are model-submitted and require human verification. '
         'The diligence requests above are selected in source order, not ranked by deal impact.', small, 3)

    c.setStrokeColor(LINE)
    c.line(margin, 47, page_w - margin, 47)
    c.setFillColor(MUTED)
    c.setFont('Helvetica', 7.1)
    c.drawString(margin, 33, 'WORKING DRAFT  |  Investment case requires financial, commercial and technology diligence')
    c.showPage()
    c.save()
    return buf.getvalue()
