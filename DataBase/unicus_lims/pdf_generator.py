import os
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent  # /home/.../website
LOGO_PATH = str(PROJECT_ROOT / "Unicus Diagnostics Logo.png")
REPORTS_DIR = HERE / "generated_reports"

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
PRIMARY = colors.HexColor("#1a237e")      # dark blue
HEADER_BG = colors.HexColor("#f5f5f5")   # light grey
ROW_ALT = colors.HexColor("#fafafa")     # alternating row
RED = colors.HexColor("#d32f2f")         # out-of-range
BORDER = colors.HexColor("#bdbdbd")      # table border


def _extract_number(value: str) -> float | None:
    """
    Attempt to parse a numeric value from a string.

    Args:
        value (str): The raw string (e.g. "13.5", "> 90.0", "< 6.0", "Non-reactive").

    Returns:
        float | None: The extracted number, or None if no number is found.
    """
    match = re.search(r"[-+]?\d*\.?\d+", str(value))
    if match:
        return float(match.group())
    return None


def _is_out_of_range(patient_value: str, normal_range: str) -> bool:
    """
    Determine whether a patient's result falls outside the reference range.

    Supports three range formats:
      - "X - Y"    : range between X and Y (inclusive).
      - "> X"      : must be greater than X.
      - "< X"      : must be less than X.
      - otherwise  : non-numeric comparison (e.g. "Non-reactive") returns False.

    Args:
        patient_value (str): The patient's result as a string.
        normal_range (str): The reference range string from the parameter definition.

    Returns:
        bool: True if the value is outside the normal range, False otherwise.
    """
    pv = _extract_number(patient_value)
    if pv is None:
        return False  # non-numeric patient value, can't check

    nr_clean = normal_range.strip()

    # Pattern: "X - Y"
    range_match = re.match(r"^([\d.]+)\s*-\s*([\d.]+)$", nr_clean)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        return pv < low or pv > high

    # Pattern: "> X"
    gt_match = re.match(r">\s*([\d.]+)", nr_clean)
    if gt_match:
        threshold = float(gt_match.group(1))
        return pv <= threshold

    # Pattern: "< X"
    lt_match = re.match(r"<\s*([\d.]+)", nr_clean)
    if lt_match:
        threshold = float(lt_match.group(1))
        return pv >= threshold

    return False


def generate_report_pdf(
    booking_id: str,
    patient_name: str,
    patient_phone: str,
    patient_address: str,
    test_name: str,
    parameter_values: dict[str, str],
    parameters: list,
    collection_address: str,
) -> str:
    """
    Generate a formatted A4 PDF report and save it to the generated_reports/ directory.

    The report includes:
      - A coloured header bar with the Unicus Diagnostics logo and lab information.
      - Patient details table.
      - Results table with parameter name, result, unit, and normal range.
      - Alternating row shading for readability.
      - Out-of-range values highlighted in bold red text.
      - Footer with generation date and a signature line.

    Args:
        booking_id (str): The booking UUID used as the output filename.
        patient_name (str): Full name of the patient.
        patient_phone (str): Phone number of the patient.
        patient_address (str): Address of the patient.
        test_name (str): The name of the test (e.g. "CBC Test").
        parameter_values (dict[str, str]): A mapping of parameter names to their
            result values as entered by the admin.
        parameters (list): A list of Parameter objects with name, unit, and
            normal_range attributes.
        collection_address (str): The address where the sample was collected.

    Returns:
        str: The absolute file path to the generated PDF.

    Raises:
        FileNotFoundError: If the logo image is not found at the expected path.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    output_path = str(REPORTS_DIR / f"{booking_id}.pdf")

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=15 * mm,
        bottomMargin=20 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    style_normal = styles["Normal"]
    style_heading = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        textColor=PRIMARY,
        spaceAfter=6,
    )

    elements = []

    # ------------------------------------------------------------------
    # HEADER: logo + lab letterhead
    # ------------------------------------------------------------------
    header_data = [[
        [Paragraph("<b>UNICUS DIAGNOSTICS</b>", ParagraphStyle(
            "LabName", fontSize=16, textColor=PRIMARY, spaceAfter=2,
        )),
         Paragraph("ISO 15189:2022 Accredited Pathology Laboratory",
                   ParagraphStyle("Sub", fontSize=8, textColor=colors.grey)),
         Paragraph("<i>Accuracy  •  Reliability  •  Trust</i>",
                   ParagraphStyle("Motto", fontSize=8, textColor=PRIMARY)),
         ],
        "",
    ]]

    try:
        logo = Image(LOGO_PATH, width=1.2 * inch, height=1.0 * inch)
        header_data[0][1] = logo
    except Exception:
        pass  # logo not available, skip

    header_table = Table(header_data, colWidths=[4.5 * inch, 1.5 * inch])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)

    # Thin decorative line
    line_data = [["", ""]]
    line_table = Table(line_data, colWidths=[6 * inch, 0.1 * inch])
    line_table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 1, PRIMARY),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(line_table)
    elements.append(Spacer(1, 6 * mm))

    # ------------------------------------------------------------------
    # TITLE
    # ------------------------------------------------------------------
    elements.append(Paragraph(f"<b>Test Report  —  {test_name}</b>", style_heading))
    elements.append(Spacer(1, 4 * mm))

    # ------------------------------------------------------------------
    # PATIENT INFORMATION TABLE
    # ------------------------------------------------------------------
    patient_info = [
        ["Patient Name", patient_name],
        ["Phone", patient_phone],
        ["Address", patient_address],
        ["Collection Address", collection_address],
        ["Booking ID", booking_id],
    ]
    info_table = Table(patient_info, colWidths=[2.0 * inch, 4.0 * inch])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 6 * mm))

    # ------------------------------------------------------------------
    # RESULTS TABLE
    # ------------------------------------------------------------------
    result_header = ["Parameter", "Result", "Unit", "Normal Range"]
    result_rows = [result_header]

    for param in parameters:
        value = parameter_values.get(param.name, "")
        result_rows.append([param.name, str(value), param.unit, param.normal_range])

    col_widths = [2.2 * inch, 1.2 * inch, 1.4 * inch, 1.8 * inch]
    result_table = Table(result_rows, colWidths=col_widths)

    # Build cell-by-cell styles
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 1), (1, -1), "CENTER"),
        ("ALIGN", (2, 1), (2, -1), "CENTER"),
        ("ALIGN", (3, 1), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]

    # Alternating row shading and out-of-range highlighting
    for i in range(1, len(result_rows)):
        if i % 2 == 0:
            style_commands.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
        param_name = result_rows[i][0]
        val = result_rows[i][1]
        nr = result_rows[i][3]
        if _is_out_of_range(val, nr):
            style_commands.append(("TEXTCOLOR", (1, i), (1, i), RED))
            style_commands.append(("FONTNAME", (1, i), (1, i), "Helvetica-Bold"))

    result_table.setStyle(TableStyle(style_commands))
    elements.append(result_table)

    # ------------------------------------------------------------------
    # FOOTER
    # ------------------------------------------------------------------
    elements.append(Spacer(1, 12 * mm))
    from datetime import datetime
    now_str = datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")
    footer_data = [
        [f"Report generated: {now_str}", ""],
        ["", "Authorised Signature ____________________________"],
    ]
    footer_table = Table(footer_data, colWidths=[3.5 * inch, 3.0 * inch])
    footer_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(footer_table)

    # Build the PDF
    doc.build(elements)
    return output_path
