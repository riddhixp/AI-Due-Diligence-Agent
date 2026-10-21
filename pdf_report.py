"""Client-facing preliminary due diligence PDF export (v6).

Builds a PDF locally from saved report text and structured financial results.
No AI requests, uploaded-document changes or external calls.
"""
import re
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

NAVY = colors.HexColor('#18314F')
INK = colors.HexColor('#283748')
MUTED = colors.HexColor('#62758A')
PALE = colors.HexColor('#EFF4F8')
LINE = colors.HexColor('#DFE7EE')
ACCENT = colors.HexColor('#27849C')

# Recognize headings even when the model emits unmarked plain text.
MAIN_SECTIONS = (
    'executive assessment', 'executive summary',
    'financial and commercial assessment', 'financial performance',
    'business model and revenue quality',
    'technology and operational assessment', 'technology and operational risks',
    'market position and competitive dynamics',
    'growth opportunities and key risks', 'growth and value-creation opportunities',
    'growth and value creation opportunities',
    'priority diligence workplan', 'management diligence questions',
    'evidence and limitations', 'sources and limitations',
    'concluding recommendation', 'preliminary conclusion',
)
SECONDARY_SECTIONS = (
    'three headline points', 'three important findings',
    'facts supported by the filing', 'calculations based on those facts',
    'analyst inferences that require validation',
    'information materially unavailable in the filing',
    'key uncertainties that could change the assessment',
    'commercial implications', 'further diligence', 'execution challenges',
)


def _safe(text):
    text = str(text if text is not None else '')
    for old, new in {
        '\u2014': '-', '\u2013': '-', '\u2011': '-', '\u2010': '-',
        '\u2212': '-', '\u00a0': ' ', '\u2265': '>=', '\u2264': '<=',
        '\u2248': '~', '\u2192': '->', '\u2019': "'", '\u2018': "'",
        '\u201c': '"', '\u201d': '"', '\u25a0': '-', '\u2012': '-',
        '\u00b7': '-', '\u202f': ' ',
    }.items():
        text = text.replace(old, new)
    return text


def _inline_md(text):
    text = escape(_safe(text))
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', text)
    return text


def _page_chrome(canvas, doc):
    canvas.saveState()
    width, height = doc.pagesize
    canvas.setStrokeColor(LINE)
    canvas.line(19 * mm, height - 18 * mm, width - 19 * mm, height - 18 * mm)
    canvas.setFont('Helvetica-Bold', 8)
    canvas.setFillColor(NAVY)
    canvas.drawString(19 * mm, height - 15 * mm, 'FINANCIAL & TECHNOLOGY DUE DILIGENCE')
    canvas.setFont('Helvetica', 7.6)
    canvas.setFillColor(MUTED)
    canvas.drawString(19 * mm, 13 * mm, 'PRELIMINARY  |  Public-document review  |  Human verification required')
    canvas.drawRightString(width - 19 * mm, 13 * mm, f'Page {doc.page}')
    canvas.restoreState()


def _styles():
    result = getSampleStyleSheet()
    result.add(ParagraphStyle(name='DTitle', parent=result['Title'], fontName='Helvetica-Bold',
                              fontSize=25, leading=31, textColor=NAVY, alignment=TA_LEFT, spaceAfter=7))
    result.add(ParagraphStyle(name='DSub', parent=result['Normal'], fontSize=10, leading=14,
                              textColor=MUTED, spaceAfter=12))

    result.add(ParagraphStyle(name='DH1', parent=result['Heading1'], fontSize=14, leading=19,
                              textColor=NAVY, spaceBefore=11, spaceAfter=6, keepWithNext=True))
    result.add(ParagraphStyle(name='DH2', parent=result['Heading2'], fontSize=10.8, leading=15,
                              textColor=NAVY, spaceBefore=8, spaceAfter=4, keepWithNext=True))
    result.add(ParagraphStyle(name='DBody', parent=result['Normal'], fontSize=9.3, leading=14.5,
                              textColor=INK, spaceAfter=4, allowWidows=0, allowOrphans=0))
    result.add(ParagraphStyle(name='DBullet', parent=result['DBody'], leftIndent=12,
                              firstLineIndent=-8, spaceAfter=3))

    result.add(ParagraphStyle(name='DFoot', parent=result['DBody'], fontSize=8.2,
                              leading=12, textColor=MUTED))
    result.add(ParagraphStyle(name='DKpiLabel', parent=result['DBody'], fontSize=8,
                              leading=11, textColor=MUTED, spaceAfter=4))
    result.add(ParagraphStyle(name='DKpiValue', parent=result['DBody'], fontName='Helvetica-Bold',
                              fontSize=16, leading=20, textColor=NAVY, spaceAfter=0))
    result.add(ParagraphStyle(name='DEyebrow', parent=result['DBody'], fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=ACCENT, spaceAfter=7))
    result.add(ParagraphStyle(name='DLead', parent=result['DBody'], fontSize=10.3, leading=16, spaceAfter=11))
    result.add(ParagraphStyle(name='DCardTitle', parent=result['DBody'], fontName='Helvetica-Bold', fontSize=9.3, leading=13.5, textColor=NAVY, spaceAfter=4))

    result.add(ParagraphStyle(
        name='DFindingTitle',
        parent=result['DH2'],
        fontName='Helvetica-Bold',
        fontSize=10.2,
        leading=14.5,
        spaceBefore=11,
        spaceAfter=5,
        textColor=NAVY,
        keepWithNext=True,
    ))

    result.add(ParagraphStyle(name='DCardText', parent=result['DBody'], fontSize=8.6, leading=12.6, spaceAfter=0))
    result.add(ParagraphStyle(name='DTableHead', parent=result['DBody'], fontName='Helvetica-Bold',
                              fontSize=8.5, leading=11, textColor=colors.white, spaceAfter=0))
    result.add(ParagraphStyle(name='DTableText', parent=result['DBody'],
                              fontSize=8.5, leading=12, spaceAfter=0))
    return result


def _money(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'{value:,.0f}'
    return 'Not supplied'


def _percentage(validation, key):
    value = ((validation or {}).get(key) or {}).get('calculated')
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'{value:.2f}%'
    return 'Not checked'


def _section_kind(text):
    label = re.sub(r'\s*\([^)]*\)\s*$', '', text.strip()).strip().lower()
    if any(label == s or label.startswith(s + ' -') or label.startswith(s + ' —')
           for s in MAIN_SECTIONS):
        return 1
    if label in SECONDARY_SECTIONS:
        return 2
    return 0


def _clean_lines(report):
    """Convert report to blocks; do not change substantive content."""
    blocks = []
    for raw in str(report or '').splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.fullmatch(r'[-_*]{3,}', line):
            continue
        if re.match(r'(?i)^(if you want, i can|let me know which|would you like me to)', line):
            continue
        md_heading = re.match(r'^(#{1,6})\s+(.+)$', line)
        if md_heading:
            blocks.append(('h1' if len(md_heading.group(1)) == 1 else 'h2', md_heading.group(2)))
            continue
        kind = _section_kind(line)
        if kind:
            if kind == 1 and ' - ' in line:
                lead, conclusion = line.split(' - ', 1)
                if _section_kind(lead) == 1 and conclusion.strip():
                    blocks.append(('h1', lead))
                    blocks.append(('text', conclusion.strip()))
                    continue
            blocks.append(('h1' if kind == 1 else 'h2', line))
            continue
        number = re.match(r'^(\d+)[.)]\s+(.+)', line)
        bullet = re.match(r'^[-*]\s+(.+)', line)
        if number:
            blocks.append(('number', number.group(1) + '. ' + number.group(2)))
        elif bullet:
            blocks.append(('bullet', bullet.group(1)))
        else:
            blocks.append(('text', line))
    return blocks


def _block_flow(kind, value, styles):
    if kind == 'h1':
        return Paragraph(_inline_md(value), styles['DH1'])

    if kind == 'h2':
        return Paragraph(
            _inline_md(value),
            styles['DFindingTitle']
        )

    if kind == 'bullet':
        return Paragraph('&#8226;  ' + _inline_md(value), styles['DBullet'])

    if kind == 'number':
        match = re.match(r'^(\d+)\.\s+(.+)$', value)

        if match:
            number, content = match.groups()
            label, separator, detail = content.partition(':')

            if separator and len(label) < 120:
                formatted = (
                    f'<font color="#27849C"><b>{number.zfill(2)}</b></font>'
                    f'&#160;&#160;<b>{_inline_md(label)}:</b>'
                    f'{_inline_md(detail)}'
                )
            else:
                formatted = (
                    f'<font color="#27849C"><b>{number.zfill(2)}</b></font>'
                    f'&#160;&#160;{_inline_md(content)}'
                )

            return Paragraph(formatted, styles['DBody'])

        return Paragraph(_inline_md(value), styles['DBody'])

    return Paragraph(_inline_md(value), styles['DBody'])


def _executive_and_body(report):
    """Lift the existing executive assessment into the opening page.

    Only reorders report text. Does not generate claims or imply verification.
    The complete remainder of the report is preserved for supporting detail.
    """
    blocks = _clean_lines(report)
    start = next((i for i, (kind, title) in enumerate(blocks)
                  if kind == 'h1' and title.lower().startswith(('executive assessment', 'executive summary'))), None)
    if start is None:
        return '', [], report
    end = next((i for i in range(start + 1, len(blocks))
                if blocks[i][0] == 'h1'), len(blocks))
    section = blocks[start + 1:end]
    lead_parts = []
    for kind, text in section:
        if kind in ('number', 'h2', 'bullet'):
            break
        if kind == 'text':
            lead_parts.append(text)
    lead = ' '.join(lead_parts).strip()
    # Preserve an executive conclusion written on the heading line.
    heading_text = blocks[start][1]

    heading_parts = re.split(
        r"\s+[—–-]\s+",
        heading_text,
        maxsplit=1,
    )

    if len(heading_parts) == 2:
        heading_lead = heading_parts[1].strip()
        lead = " ".join(
            part for part in (heading_lead, lead) if part
        )

    # Extract up to three findings and their first supporting evidence paragraph.
    # Do not invent commercial conclusions or replace the underlying wording.
    takeaways = []
    for index, (kind, text) in enumerate(section):
        if kind != 'number':
            continue
        title = re.sub(r'^\d+[.)]\s*', '', text)

        title = re.sub(
            r"(?i)^\s*finding\s*[-:–—]\s*",
            "",
            title,
        ).strip().rstrip(".")

        evidence = ''
        for subsequent_kind, subsequent_text in section[index + 1:]:
            if subsequent_kind in ('number', 'h1', 'h2'):
                break
            if subsequent_kind in ('text', 'bullet'):
                candidate = re.sub(
                    r'(?i)^\s*(?:evidence|supporting evidence)\s*:\s*',
                    '',
                    subsequent_text,
                ).strip()
                if candidate:
                    evidence = candidate
                    break

        if title:
            takeaways.append((title, evidence))
        if len(takeaways) == 3:
            break
    if not takeaways:
        for kind, text in section:
            if kind == 'bullet':
                label, separator, rest = text.partition(':')
                takeaways.append((label.strip(), rest.strip() if separator else ''))
            if len(takeaways) == 3:
                break
    # Keep the underlying numbered findings and evidence in the detailed
    # assessment. Never silently discard the supporting disclosure text.

    # The executive assessment has already been presented
    # on page 1. Continue with the remaining report sections.
    remainder = blocks[:start] + blocks[end:]

    return lead, takeaways, remainder



def _report_story_from_blocks(blocks, styles):
    """Convert already parsed blocks using existing flow and heading logic."""
    # Pass through the existing formatter's underlying block structure by
    # emitting canonical Markdown. Content isn't rewritten.
    lines = []
    for kind, value in blocks:
        prefix = {'h1': '# ', 'h2': '## ', 'bullet': '- ', 'number': ''}.get(kind, '')
        lines.append(prefix + value)
    return _story_from_report('\n'.join(lines), styles)


def _takeaway_table(takeaways, styles):
    """Client-facing finding title followed by its supporting filing evidence."""

    cells = []

    for i, (title, evidence) in enumerate(takeaways[:3], 1):
        title = re.sub(
            r"(?i)^\s*(?:\d+[.)]\s*)?finding\s*[-:–]\s*",
            "",
            title,
        ).strip()

        text = [Paragraph(_inline_md(title), styles['DCardTitle'])]
        if evidence:
            text.append(Paragraph(_inline_md(evidence), styles['DCardText']))
        cells.append([Paragraph(f'{i:02d}', styles['DEyebrow']), text])
    table = Table(cells, colWidths=[14 * mm, 158 * mm], hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PALE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, -2), 1, colors.white),
        ('TOPPADDING', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
        ('LEFTPADDING', (0, 0), (-1, -1), 11),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    return table


def _story_from_report(report, styles):
    """Lay out findings as coherent units without forcing entire sections onto a page.

    Short numbered findings stay with their associated evidence bullets. Long
    findings remain splittable to avoid a LayoutError on exceptionally long text.
    """
    blocks = _clean_lines(report)
    story = []
    i = 0
    while i < len(blocks):
        kind, content = blocks[i]

        if kind == 'number':
            # A numbered diligence finding often has multiple supporting bullets.
            # Group those bullets with its title when the unit fits on one page.
            group = [_block_flow(kind, content, styles)]
            j = i + 1
            while j < len(blocks) and blocks[j][0] == 'bullet':
                group.append(_block_flow(*blocks[j], styles))
                j += 1
            if len(group) > 1:
                # Cap grouping so very long findings can still flow naturally.
                # The first bullet remains linked to its numbered heading.
                if len(group) <= 5 and sum(len(blocks[k][1]) for k in range(i, j)) <= 1100:
                    story.append(KeepTogether(group))
                else:
                    story.append(KeepTogether(group[:2]))
                    story.extend(group[2:])
            else:
                story.append(group[0])
            i = j
            continue

        if kind in ('h1', 'h2'):
            # Group multiple adjacent headings plus the opening text, ensuring
            # no heading is abandoned at the bottom of a page.
            group = [_block_flow(kind, content, styles)]
            j = i + 1
            while j < len(blocks) and blocks[j][0] in ('h1', 'h2'):
                group.append(_block_flow(*blocks[j], styles))
                j += 1
            if j < len(blocks):
                group.append(_block_flow(*blocks[j], styles))
                j += 1
            story.append(KeepTogether(group) if len(group) > 1 else group[0])
            i = j
            continue

        story.append(_block_flow(kind, content, styles))
        i += 1
    return story


def _financial_insights_story(data, styles):
    """Format evidence-aware financial diligence insights."""
    if not data:
        return []

    from financial_summary import generate_financial_summary

    insights = generate_financial_summary(data)
    story = []

    if not insights:
        return story

    story.append(Paragraph(
        'Financial diligence | Investment implications',
        styles['DH2']
    ))

    for insight in insights:
        story.append(Paragraph(
            _inline_md(insight['title']),
            styles['DCardTitle']
        ))


        if insight.get("priority") == "Cash-flow and capital allocation":
            story.append(Paragraph(
                _inline_md(insight["finding"]),
                styles["DTableText"]
            ))


        story.append(Paragraph(
            '<b>Investment implication:</b> '
            + _inline_md(insight['implication']),
            styles['DTableText']
        ))

        story.append(Paragraph(
            '<b>Next diligence action:</b> '
            + _inline_md(insight['next_step']),
            styles['DTableText']
        ))


        source_pages = insight.get('source_pages') or []
        if source_pages:
            refs = ', '.join(
                str(page) for page in source_pages
            )
            story.append(Paragraph(
                'Structured extraction references: PDF page '
                + escape(refs),
                styles['DFoot']
            ))

        story.append(Spacer(1, 3 * mm))

    return story


def _financial_table(data, year, currency, units, styles):
    """Display reported financial data and derived diligence metrics."""

    labels = [
        ('FY revenue', 'revenue_current'),
        ('Prior-year revenue', 'revenue_previous'),
        ('Gross profit', 'gross_profit'),
        ('Operating income', 'operating_income'),
        ('Net income', 'net_income'),
        ('Operating cash flow', 'operating_cash_flow'),
        ('Capital expenditure', 'capital_expenditure'),
        ('Subscription revenue', 'subscription_revenue'),
    ]

    rows = [[
        Paragraph('Metric', styles['DTableHead']),
        Paragraph(
            f'FY{escape(str(year))} / comparison '
            f'({escape(currency)} {escape(units)})',
            styles['DTableHead']
        ),
    ]]

    def add_row(label, value):
        rows.append([
            Paragraph(escape(label), styles['DTableText']),
            Paragraph(escape(str(value)), styles['DTableText']),
        ])

    def is_number(value):
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
        )

    optional = {
        'operating_income',
        'operating_cash_flow',
        'capital_expenditure',
        'subscription_revenue',
    }

    for label, key in labels:
        value = data.get(key)
        if key in optional and value is None:
            continue
        add_row(label, _money(value))

    revenue = data.get('revenue_current')
    operating_income = data.get('operating_income')
    net_income = data.get('net_income')
    operating_cash_flow = data.get('operating_cash_flow')
    capex = data.get('capital_expenditure')
    subscription = data.get('subscription_revenue')

    if (
        is_number(revenue) and revenue > 0
        and is_number(operating_income)
    ):
        add_row(
            'Operating margin (derived)',
            f'{operating_income / revenue * 100:.2f}%'
        )

    if (
        is_number(operating_cash_flow)
        and is_number(capex) and capex >= 0
    ):
        free_cash_flow = operating_cash_flow - capex
        add_row(
            'Indicative free cash flow (derived)',
            _money(free_cash_flow)
        )

        if is_number(revenue) and revenue > 0:
            add_row(
                'Indicative FCF margin (derived)',
                f'{free_cash_flow / revenue * 100:.2f}%'
            )

    if (
        is_number(operating_cash_flow)
        and is_number(net_income) and net_income > 0
    ):
        add_row(
            'Operating cash flow / net income',
            f'{operating_cash_flow / net_income:.2f}x'
        )

    if (
        is_number(subscription)
        and is_number(revenue) and revenue > 0
    ):
        add_row(
            'Subscription revenue share (derived)',
            f'{subscription / revenue * 100:.2f}%'
        )

    table = Table(
        rows,
        colWidths=[70 * mm, 102 * mm],
        repeatRows=1,
        hAlign='LEFT'
    )

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.white, PALE]),
        ('LINEBELOW', (0, -1), (-1, -1), 0.5, LINE),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
    ]))

    return table


def generate_pdf_report(report, financial_data=None, validation=None, source_checks=None):
    """Produce PDF bytes. Existing Streamlit arguments remain compatible."""
    data = financial_data or {}
    validation = validation or {}
    styles = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=(210 * mm, 297 * mm),
        leftMargin=19 * mm, rightMargin=19 * mm,
        topMargin=21 * mm, bottomMargin=19 * mm,
        title='Preliminary Due Diligence Assessment',
        author='AI Due Diligence Agent',
    )
    story = []
    company = _safe(data.get('company') or 'Company Analysis')
    year = data.get('fiscal_year') or 'Not specified'
    currency = _safe(data.get('currency') or 'Currency unspecified')
    units = _safe(data.get('units') or 'units unspecified')

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(escape(company), styles['DTitle']))
    story.append(Paragraph(f'Preliminary financial &amp; technology due diligence | FY{escape(str(year))}', styles['DSub']))
    story.append(HRFlowable(width='100%', thickness=1.5, color=NAVY, spaceAfter=8 * mm))

    if data:
        kpis = [
            [Paragraph(f'Revenue ({escape(currency)} {escape(units)})', styles['DKpiLabel']),
             Paragraph(_money(data.get('revenue_current')), styles['DKpiValue'])],
            [Paragraph('Revenue growth', styles['DKpiLabel']),
             Paragraph(_percentage(validation, 'revenue_growth'), styles['DKpiValue'])],
            [Paragraph('Gross margin', styles['DKpiLabel']),
             Paragraph(_percentage(validation, 'gross_margin'), styles['DKpiValue'])],
        ]
        table = Table([kpis], colWidths=[57 * mm] * 3, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), PALE),
            ('BOX', (0, 0), (-1, -1), 0.5, LINE),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.white),
            ('TOPPADDING', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 11),
            ('LEFTPADDING', (0, 0), (-1, -1), 9),
            ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ]))
        story.append(table)
        story.append(Spacer(1, 5 * mm))

    # Executive page: summary and takeaway titles are extracted, not invented.
    lead, takeaways, remainder = _executive_and_body(report)
    if lead or takeaways:
        story.append(Paragraph('EXECUTIVE PERSPECTIVE', styles['DEyebrow']))
        story.append(Paragraph('Executive assessment', styles['DH1']))
        if lead:
            story.append(Paragraph(_inline_md(lead), styles['DLead']))
        if takeaways:
            story.append(Paragraph('Three priority findings', styles['DH2']))
            story.append(_takeaway_table(takeaways, styles))
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(
            'Preliminary desk-based assessment. Supporting evidence, alternative interpretations '
            'and diligence questions follow; findings require human verification.', styles['DFoot']))
        story.append(PageBreak())
        story.append(Paragraph('Detailed diligence assessment', styles['DH1']))


        # Insert structured financial insights beneath the
        # financial assessment heading, preserving source content.
        inserted_financial_insights = False


        for index, (kind, content) in enumerate(remainder):
            if (
                kind == 'h1'
                and content.strip().lower().startswith(
                    'financial and commercial assessment'
                )
                and not inserted_financial_insights
            ):
                story.append(_block_flow(kind, content, styles))
                story.extend(_financial_insights_story(data, styles))
                inserted_financial_insights = True
                continue

            story.append(_block_flow(kind, content, styles))


    else:
        story.append(Paragraph('Detailed diligence assessment', styles['DH1']))
        story.extend(_story_from_report(report, styles))

    # Present source/evidence mechanics in a dedicated appendix.
    if data or validation or source_checks:
        story.append(PageBreak())
        story.append(Paragraph('Appendix | Financial data and verification', styles['DH1']))
        story.append(Paragraph(
            'Figures below are taken from structured AI output. Arithmetic checks confirm calculations, '
            'not the accuracy of the source figures or citations.', styles['DFoot']))
        if data:
            story.append(Paragraph('Financial data', styles['DH2']))
            story.append(_financial_table(data, year, currency, units, styles))
            story.append(Spacer(1, 5 * mm))

            story.append(Paragraph(
                'Investment interpretation',
                styles['DH2']
            ))
            story.append(Paragraph(
                'Operating margin measures reported operating '
                'profitability, not adjusted EBITDA. Indicative '
                'free cash flow, where calculated, equals operating '
                'cash flow less cash purchases of property and '
                'equipment; it is not normalised transaction cash '
                'flow. Cash conversion may be affected by working '
                'capital and non-recurring items. Further '
                'diligence should test earnings adjustments, '
                'cash flow sustainability, customer cohorts and '
                'technology-related investment requirements.',
                styles['DFoot']
            ))
            story.append(Spacer(1, 4 * mm))
        if validation:
            story.append(Paragraph('Arithmetic validation', styles['DH2']))
            validation_rows = [[Paragraph('Metric', styles['DTableHead']),
                                Paragraph('Status', styles['DTableHead']),
                                Paragraph('Calculated', styles['DTableHead'])]]
            for key, item in validation.items():
                item = item or {}
                calc = item.get('calculated')
                pct = f'{calc:.2f}%' if isinstance(calc, (int, float)) and not isinstance(calc, bool) else '-'
                validation_rows.append([
                    Paragraph(escape(key.replace('_', ' ').title()), styles['DTableText']),
                    Paragraph(escape(str(item.get('status') or 'NOT CHECKED')), styles['DTableText']),
                    Paragraph(pct, styles['DTableText']),
                ])
            vtable = Table(validation_rows, colWidths=[72 * mm, 48 * mm, 52 * mm], hAlign='LEFT', repeatRows=1)
            vtable.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), NAVY),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PALE]),
                ('TOPPADDING', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(vtable)
        if source_checks:
            story.append(Paragraph('Source evidence checks', styles['DH2']))
            for row in source_checks:
                if not isinstance(row, dict):
                    continue
                label = row.get('Metric') or row.get('Financial figure') or 'Figure'
                status = row.get('Result') or row.get('status') or 'NEEDS_REVIEW'
                page = row.get('PDF page') or row.get('page') or 'Not supplied'
                story.append(Paragraph(
                    escape(f'{label} | PDF page {page} | {status}'), styles['DFoot']))
            story.append(Paragraph(
                'These automated checks provide preliminary supporting evidence, not independent audit assurance.',
                styles['DFoot']))


    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        'Limitations: This AI-assisted report is based on supplied documents only. '
        'Material figures, citations, interpretations and conclusions require human verification. '
        'This is not an audit, a technical security assessment or an investment recommendation.',
        styles['DFoot']))


    doc.build(story, onFirstPage=_page_chrome, onLaterPages=_page_chrome)
    return buffer.getvalue()
