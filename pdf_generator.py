# pdf_generator.py

import os
from reportlab.lib.pagesizes import LETTER, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def create_pdf(text: str, output_path: str, page_size: str = 'LETTER'):
    """
    Generate a PDF file from a block of text.

    Args:
        text (str): The full text to render in the PDF. You can include newlines to separate paragraphs.
        output_path (str): The filesystem path where the PDF should be saved (including .pdf extension).
                           Any missing parent directories will be created automatically.
        page_size (str): Either 'LETTER' or 'A4'. Defaults to 'LETTER'.

    Usage:
        create_pdf(summary_text, '/path/to/static/uploads/summaries/summary_PAT0001_1234567890.pdf')
    """
    # 1. Choose page size
    if page_size.upper() == 'A4':
        PAGE_SIZE = A4
    else:
        PAGE_SIZE = LETTER

    # 2. Ensure the output directory exists
    directory = os.path.dirname(output_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    # 3. Set up a SimpleDocTemplate
    #    - left/right/top/bottom margins of 1 inch
    doc = SimpleDocTemplate(
        output_path,
        pagesize=PAGE_SIZE,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )

    # 4. Acquire a default stylesheet and customize styles as needed
    styles = getSampleStyleSheet()
    # Title style
    title_style = ParagraphStyle(
        name='Title',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        alignment=1,  # centered
        spaceAfter=20
    )
    # Body style
    body_style = ParagraphStyle(
        name='BodyText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=14,   # line spacing
        spaceAfter=12,
    )

    # 5. Build the story (a list of Flowables)
    story = []

    # Add the title at the top
    story.append(Paragraph("Patient Medical Summary", title_style))

    # Split the input text into paragraphs.
    # We treat each double‐newline block as a separate paragraph. Then, if a single blank line appears, we insert a Spacer.
    # This approach preserves paragraph breaks while avoiding runaway single‐line splits.
    paragraphs = text.strip().split('\n\n')
    for block in paragraphs:
        # Within each block, there may be single newlines that we want to treat as line breaks.
        # ReportLab's Paragraph will automatically wrap text. We replace single newlines with <br/> tags.
        # But we do not want to collapse multiple newlines (which were our paragraph separators) into <br/>.
        lines = block.split('\n')
        joined = '<br/>'.join(line.strip() for line in lines if line.strip() != '')
        # Create a Paragraph for this block
        p = Paragraph(joined, body_style)
        story.append(p)
        # Add a bit more space after each paragraph‐block
        story.append(Spacer(1, 12))  # 12 points = 1/6 inch

    # 6. Build the PDF
    try:
        doc.build(story)
    except Exception as e:
        # Re‐raise with a clearer message
        raise RuntimeError(f"Failed to generate PDF at {output_path}: {e}")

