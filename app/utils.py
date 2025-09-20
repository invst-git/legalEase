import fitz  # PyMuPDF
import os
from app.services import extract_text_with_ocr
import base64
import io
import zipfile
import xml.etree.ElementTree as ET
import re
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import pypdf
from datetime import datetime
import urllib.parse

# A simple heuristic: if a page has fewer than this many characters, it might be a scan.
MIN_CHARS_PER_PAGE = 50
# Treat a page as a scanned image if any single raster image block covers most of the page
# Chosen for typical Indian legal documents where scans have narrow margins
FULL_PAGE_IMAGE_THRESHOLD = 0.88  # 88% of page area (geometric coverage)
# If rawdict blocks are missing, approximate via XObject image pixel area vs. page pixel area at 200 DPI
FULL_PAGE_IMAGE_PIXEL_RATIO = 0.80  # 80% of page pixel area at 200 DPI

def _force_ocr_enabled() -> bool:
    v = (os.getenv("OCR_FORCE_SCAN", "") or "").strip().lower()
    return v in ("1", "true", "yes", "on")

def _has_near_full_image(page) -> bool:
    """Detect a near full-page raster image either via rawdict block coverage or XObject size.
    Fast, local, and avoids network calls.
    """
    try:
        raw = page.get_text("rawdict")
        blocks = raw.get("blocks", []) if isinstance(raw, dict) else []
    except Exception:
        blocks = []
    page_rect = page.rect
    page_area = float(page_rect.width * page_rect.height) if page_rect else 1.0
    # 1) Geometric coverage via rawdict blocks
    max_img_area = 0.0
    for b in blocks:
        if isinstance(b, dict) and int(b.get("type", -1)) == 1:  # image block
            bbox = b.get("bbox", None)
            if bbox and len(bbox) == 4:
                x0, y0, x1, y1 = bbox
                w = max(0.0, float(x1) - float(x0))
                h = max(0.0, float(y1) - float(y0))
                max_img_area = max(max_img_area, w * h)
    if page_area > 0 and (max_img_area / page_area) >= FULL_PAGE_IMAGE_THRESHOLD:
        return True
    # 2) Fallback via XObject intrinsic pixel size compared to page pixel size at 200 DPI
    try:
        imgs = page.get_images(full=True) or []
        if not imgs:
            return False
        # Evaluate coverage at typical scan DPIs to avoid under/over-estimation
        candidate_dpis = (150.0, 200.0, 300.0)
        for dpi in candidate_dpis:
            page_w_px = (page_rect.width / 72.0) * dpi if page_rect else 0.0
            page_h_px = (page_rect.height / 72.0) * dpi if page_rect else 0.0
            page_px_area = max(1.0, page_w_px * page_h_px)
            for img in imgs:
                # PyMuPDF tuple: (xref, smask, width, height, bpc, colorspace, ...)
                if len(img) >= 4:
                    w_px = float(img[2] or 0)
                    h_px = float(img[3] or 0)
                    if w_px <= 0 or h_px <= 0:
                        continue
                    if (w_px * h_px) / page_px_area >= FULL_PAGE_IMAGE_PIXEL_RATIO:
                        return True
    except Exception:
        return False
    return False

async def extract_text_from_document(file_bytes: bytes, mime_type: str) -> list[str]:
    """
    Orchestrates text extraction, returning a list of strings, where each string is a page's content.
    """
    # Handle plain text directly, returned as a single-element list
    if mime_type == "text/plain":
        return [file_bytes.decode("utf-8")]
    # Minimal support for common Office/text formats
    if mime_type in {"application/rtf", "text/rtf"}:
        # Naive RTF to text: strip control words and braces; preserve basic newlines
        try:
            text = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            text = file_bytes.decode("latin-1", errors="ignore")
        text = text.replace("\\line", "\n").replace("\\par", "\n").replace("\\tab", "\t")
        text = re.sub(r"\\'[0-9a-fA-F]{2}", "", text)  # remove hex escapes
        text = re.sub(r"\\[a-zA-Z]+-?\d*\s?", "", text)  # remove control words
        text = re.sub(r"[{}]", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return [text]
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        # DOCX: unzip and parse word/document.xml for w:t nodes
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                with zf.open("word/document.xml") as docxml:
                    tree = ET.parse(docxml)
                    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                    texts = [t.text or "" for t in tree.findall('.//w:t', ns)]
                    combined = "".join(texts)
                    return [combined]
        except Exception as e:
            raise ValueError(f"Failed to process DOCX. Details: {e}")
    if mime_type == "application/msword":
        # Legacy .doc not supported without external tools
        raise ValueError("Legacy .doc files are not supported. Please convert to PDF, DOCX, TXT, or RTF.")

    page_texts = []
    
    if mime_type == "application/pdf":
        try:
            pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
            # If forced via env, treat as scanned regardless of text presence
            if _force_ocr_enabled():
                image_bytes_list = [page.get_pixmap(dpi=300).tobytes("png") for page in pdf_document]
                ocr_texts = await extract_text_with_ocr(image_bytes_list)
                return ocr_texts
            is_likely_scanned = True
            scanned_by_full_image = False
            
            # Check for scanned PDF and extract text if not scanned
            for page in pdf_document:
                page_text = page.get_text()
                # Full-page image coverage heuristic has priority over text presence
                if _has_near_full_image(page):
                    scanned_by_full_image = True
                if len(page_text) > MIN_CHARS_PER_PAGE:
                    is_likely_scanned = False
                page_texts.append(page_text)

            # Prioritize image coverage heuristic: any near full-page image => treat as scanned
            if scanned_by_full_image:
                is_likely_scanned = True

            if not is_likely_scanned:
                # Stage 1: find ambiguous pages (cheap, local)
                ambiguous_indices: list[int] = []
                page_flags: dict[int, dict] = {}
                try:
                    for idx, page in enumerate(pdf_document):
                        try:
                            raw = page.get_text("rawdict")
                        except Exception:
                            raw = {"blocks": []}
                        blocks = raw.get("blocks", []) if isinstance(raw, dict) else []
                        page_rect = page.rect
                        page_area = float(page_rect.width * page_rect.height) if page_rect else 1.0
                        img_area = 0.0
                        has_large_image = False
                        img_blocks = 0
                        for b in blocks:
                            if not isinstance(b, dict):
                                continue
                            if int(b.get("type", -1)) == 1:  # image block
                                img_blocks += 1
                                bbox = b.get("bbox", None)
                                if bbox and len(bbox) == 4:
                                    x0, y0, x1, y1 = bbox
                                    w = max(0.0, float(x1) - float(x0))
                                    h = max(0.0, float(y1) - float(y0))
                                    area = w * h
                                    img_area += area
                                    if page_area > 0 and (w / (page_rect.width or 1) >= 0.3 or h / (page_rect.height or 1) >= 0.3):
                                        has_large_image = True
                        ratio = (img_area / page_area) if page_area > 0 else 0.0
                        text = page_texts[idx] if idx < len(page_texts) else ""
                        if text:
                            total = len(text)
                            alnum = sum(ch.isalnum() for ch in text)
                            non_alnum_ratio = 1.0 - (alnum / total) if total > 0 else 1.0
                        else:
                            non_alnum_ratio = 1.0
                        text_blocks = [b for b in blocks if isinstance(b, dict) and int(b.get("type", -1)) == 0]
                        fragmented = len(text_blocks) >= 50
                        # Ambiguity: digital text exists but layout suggests embedded image text
                        ambiguous = (
                            len(text) >= MIN_CHARS_PER_PAGE and (
                                ratio >= 0.25 or has_large_image or non_alnum_ratio >= 0.45 or fragmented or img_blocks >= 2
                            )
                        )
                        if ambiguous:
                            ambiguous_indices.append(idx)
                            page_flags[idx] = {
                                "ratio": ratio,
                                "fragmented": fragmented,
                                "non_alnum_ratio": non_alnum_ratio,
                                "digital_len": len(text),
                            }
                except Exception:
                    ambiguous_indices = []
                    page_flags = {}

                # Stage 2: AI detection on ambiguous pages (Vision probe)
                needs_ocr_indices: list[int] = []
                if ambiguous_indices:
                    try:
                        from google.cloud import vision as _vision
                        client = _vision.ImageAnnotatorClient()
                        for i in ambiguous_indices:
                            try:
                                # Low-res thumbnail for quick detection
                                pix = pdf_document.load_page(i).get_pixmap(dpi=150)
                                image = _vision.Image(content=pix.tobytes("png"))
                                resp = client.document_text_detection(image=image)
                                fta = getattr(resp, 'full_text_annotation', None)
                                vision_text = getattr(fta, 'text', '') or ''
                                vlen = len(vision_text)
                                flags = page_flags.get(i, {})
                                dlen = int(flags.get("digital_len", 0))
                                fragmented = bool(flags.get("fragmented", False))
                                # Decide OCR necessity: Vision finds much more, or digital is weak but Vision strong
                                if (vlen >= max(MIN_CHARS_PER_PAGE, int(dlen * 1.2)) and (vlen - dlen) >= 100) or (dlen < MIN_CHARS_PER_PAGE and vlen >= int(MIN_CHARS_PER_PAGE * 0.8)) or (fragmented and vlen > dlen + 50):
                                    needs_ocr_indices.append(i)
                            except Exception:
                                # If detection fails for a page, skip it (keep digital)
                                continue
                    except Exception:
                        # If Vision not available, skip AI detection (keep digital fast path)
                        needs_ocr_indices = []

                if needs_ocr_indices:
                    # OCR only AI-flagged pages and merge; keep others as-is
                    image_bytes_list = []
                    for i in needs_ocr_indices:
                        try:
                            pix = pdf_document.load_page(i).get_pixmap(dpi=300)
                            image_bytes_list.append(pix.tobytes("png"))
                        except Exception:
                            image_bytes_list.append(b"")
                    try:
                        ocr_texts = await extract_text_with_ocr(image_bytes_list)
                    except Exception:
                        ocr_texts = [""] * len(needs_ocr_indices)
                    for k, i in enumerate(needs_ocr_indices):
                        try:
                            page_texts[i] = ocr_texts[k] or page_texts[i]
                        except Exception:
                            pass
                # Return digital texts (possibly enriched with AI-selected OCR pages)
                return page_texts
            
            # If scanned, convert pages to images for OCR
            print("PDF is likely scanned. Converting pages to images for OCR.")
            image_bytes_list = [page.get_pixmap(dpi=300).tobytes("png") for page in pdf_document]
            
            # OCR per page: return list of page texts to preserve granularity
            ocr_texts = await extract_text_with_ocr(image_bytes_list)
            return ocr_texts

        except Exception as e:
            print(f"Error processing PDF: {e}")
            raise ValueError(f"Failed to process PDF. Details: {e}")
    
    # For single images, return OCR result as a single chunk
    else:
        # For any remaining types, attempt OCR only if it's an image; otherwise error
        # Heuristic: simple magic header checks for common image types
        is_png = file_bytes[:8] == b"\x89PNG\r\n\x1a\n"
        is_jpeg = file_bytes[:3] == b"\xff\xd8\xff"
        is_gif = file_bytes[:6] in {b"GIF87a", b"GIF89a"}
        if is_png or is_jpeg or is_gif:
            ocr_texts = await extract_text_with_ocr([file_bytes])
            return ocr_texts
        raise ValueError("Unsupported file type. Allowed: PDF, DOC, DOCX, TXT, RTF.")

async def get_page_images_if_scanned(file_bytes: bytes, mime_type: str) -> list[str]:
    """
    Returns a list of data URI PNGs if the PDF is likely scanned; otherwise returns an empty list.
    For non-PDF types, returns an empty list.
    """
    if mime_type != "application/pdf":
        return []
    try:
        pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
        # Forced scanned path via env
        if _force_ocr_enabled():
            images: list[str] = []
            for page in pdf_document:
                pix = page.get_pixmap(dpi=200)
                png_bytes = pix.tobytes("png")
                data_uri = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
                images.append(data_uri)
            return images
        is_likely_scanned = True
        scanned_by_full_image = False
        for page in pdf_document:
            # Full-page image coverage heuristic has priority over text presence
            if _has_near_full_image(page):
                scanned_by_full_image = True
            page_text = page.get_text()
            if len(page_text) > MIN_CHARS_PER_PAGE:
                is_likely_scanned = False
        # Prioritize image coverage heuristic: any near full-page image => treat as scanned
        if not is_likely_scanned and not scanned_by_full_image:
            return []
        images: list[str] = []
        for page in pdf_document:
            pix = page.get_pixmap(dpi=200)
            png_bytes = pix.tobytes("png")
            data_uri = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
            images.append(data_uri)
        return images
    except Exception:
        return []


def create_google_calendar_link(event: dict) -> str:
    """
    Creates a Google Calendar URL for an event.
    
    Args:
        event: Dictionary containing event data (date, label, description, kind)
    
    Returns:
        Google Calendar URL string or None if invalid
    """
    try:
        # Parse the event date
        event_date = datetime.strptime(event['date'], '%Y-%m-%d')
        
        # Get default times based on event kind
        def get_default_times(kind):
            times = {
                'payment_due': {'start': '09:00', 'end': '09:30'},
                'action_required': {'start': '10:00', 'end': '11:00'},
                'key_date': {'start': '09:00', 'end': '17:00'}
            }
            return times.get(kind, {'start': '09:00', 'end': '10:00'})
        
        times = get_default_times(event.get('kind', 'key_date'))
        
        # Format times for Google Calendar (YYYYMMDDTHHMMSSZ)
        start_time = event_date.strftime(f'%Y%m%dT{times["start"].replace(":", "")}00Z')
        end_time = event_date.strftime(f'%Y%m%dT{times["end"].replace(":", "")}00Z')
        
        # Create Google Calendar URL
        calendar_url = (
            f"https://www.google.com/calendar/render?action=TEMPLATE&"
            f"text={urllib.parse.quote(event['label'])}&"
            f"dates={start_time}/{end_time}&"
            f"details={urllib.parse.quote(event['description'])}&"
            f"location=Legal Document Reminder"
        )
        return calendar_url
    except Exception:
        return None


def create_analysis_pdf(analysis_data: dict, company_name: str = "Your Company") -> bytes:
    """
    Creates a branded PDF report for an analysis.
    
    Args:
        analysis_data: Dictionary containing analysis information
        company_name: Company name for branding (default: "Your Company")
    
    Returns:
        PDF bytes
    """
    buffer = io.BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Create custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        spaceBefore=20,
        textColor=colors.darkblue
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=14,
        spaceAfter=8,
        spaceBefore=12,
        textColor=colors.darkblue
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6
    )
    
    # Build content
    story = []
    
    # Cover page
    story.append(Paragraph("legalEase", title_style))
    story.append(Paragraph("Analysis Report", title_style))
    story.append(Spacer(1, 20))
    
    # Analysis details
    story.append(Paragraph(f"<b>Analysis ID:</b> {analysis_data.get('id', 'N/A')}", normal_style))
    story.append(Paragraph(f"<b>Document:</b> {analysis_data.get('filename', 'N/A')}", normal_style))
    story.append(Paragraph(f"<b>Date:</b> {analysis_data.get('created_at', 'N/A')}", normal_style))
    story.append(Paragraph(f"<b>Risk Level:</b> {analysis_data.get('risk_level', 'N/A')}", normal_style))
    story.append(Spacer(1, 20))
    
    # Risk summary
    if analysis_data.get('risk_reason'):
        story.append(Paragraph("Risk Summary", heading_style))
        story.append(Paragraph(analysis_data['risk_reason'], normal_style))
        story.append(Spacer(1, 20))
    
    # Assessment
    if analysis_data.get('assessment'):
        story.append(Paragraph("Assessment", heading_style))
        story.append(Paragraph(analysis_data['assessment'], normal_style))
        story.append(Spacer(1, 20))
    
    # Key Information
    if analysis_data.get('key_info'):
        story.append(Paragraph("Key Information", heading_style))
        
        # Create table for key info with better column widths and text wrapping
        table_data = [['Key', 'Value', 'Negotiable', 'Benchmarkable']]
        for item in analysis_data['key_info']:
            if isinstance(item, dict):
                key_text = item.get('key', '')
                value_text = item.get('value', '')
                negotiable = 'Yes' if item.get('is_negotiable', False) else 'No'
                benchmarkable = 'Yes' if item.get('is_benchmarkable', False) else 'No'
            else:
                # Handle Pydantic model
                key_text = getattr(item, 'key', '')
                value_text = getattr(item, 'value', '')
                negotiable = 'Yes' if getattr(item, 'is_negotiable', False) else 'No'
                benchmarkable = 'Yes' if getattr(item, 'is_benchmarkable', False) else 'No'
            
            # Wrap long text to prevent overflow
            table_data.append([
                Paragraph(key_text, normal_style),
                Paragraph(value_text, normal_style),
                Paragraph(negotiable, normal_style),
                Paragraph(benchmarkable, normal_style)
            ])
        
        # Better column widths to prevent text overlap
        table = Table(table_data, colWidths=[1.2*inch, 3.5*inch, 0.7*inch, 0.7*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.beige, colors.white]),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ]))
        
        story.append(table)
        story.append(Spacer(1, 20))
    
    # Identified Actions
    if analysis_data.get('identified_actions'):
        story.append(Paragraph("Identified Actions & Obligations", heading_style))
        
        for i, action in enumerate(analysis_data['identified_actions'], 1):
            if isinstance(action, dict):
                text = action.get('text', '')
                is_negotiable = action.get('is_negotiable', False)
                is_benchmarkable = action.get('is_benchmarkable', False)
            else:
                text = getattr(action, 'text', '')
                is_negotiable = getattr(action, 'is_negotiable', False)
                is_benchmarkable = getattr(action, 'is_benchmarkable', False)
            
            flags = []
            if is_negotiable:
                flags.append("Negotiable")
            if is_benchmarkable:
                flags.append("Benchmarkable")
            
            flag_text = f" ({', '.join(flags)})" if flags else ""
            story.append(Paragraph(f"{i}. {text}{flag_text}", normal_style))
        
        story.append(Spacer(1, 20))
    
    # Timeline Analysis
    if analysis_data.get('timeline'):
        story.append(Paragraph("Timeline Analysis", heading_style))
        
        # Lifecycle Summary
        if analysis_data['timeline'].get('lifecycle_summary'):
            story.append(Paragraph("Lifecycle Summary", subheading_style))
            story.append(Paragraph(analysis_data['timeline']['lifecycle_summary'], normal_style))
            story.append(Spacer(1, 12))
        
        # Timeline Events
        events = analysis_data['timeline'].get('events', [])
        if events:
            story.append(Paragraph("Key Events", subheading_style))
            
            # Create timeline events table with calendar links
            timeline_data = [['Date', 'Event', 'Type', 'Description', 'Add to Calendar']]
            for event in events:
                if isinstance(event, dict):
                    date = event.get('date', '')
                    label = event.get('label', '')
                    kind = event.get('kind', '')
                    description = event.get('description', '')
                else:
                    # Handle Pydantic model
                    date = getattr(event, 'date', '')
                    label = getattr(event, 'label', '')
                    kind = getattr(event, 'kind', '')
                    description = getattr(event, 'description', '')
                
                # Format the kind for better readability
                kind_formatted = kind.replace('_', ' ').title() if kind else ''
                
                # Create Google Calendar link
                event_dict = {
                    'date': date,
                    'label': label,
                    'kind': kind,
                    'description': description
                }
                calendar_url = create_google_calendar_link(event_dict)
                
                # Create clickable calendar link or empty cell
                if calendar_url:
                    calendar_link = Paragraph(f'<a href="{calendar_url}" color="blue">Add Reminder</a>', normal_style)
                else:
                    calendar_link = Paragraph('', normal_style)
                
                timeline_data.append([
                    Paragraph(date, normal_style),
                    Paragraph(label, normal_style),
                    Paragraph(kind_formatted, normal_style),
                    Paragraph(description, normal_style),
                    calendar_link
                ])
            
            # Timeline table with proper column widths (added column for calendar links)
            timeline_table = Table(timeline_data, colWidths=[1*inch, 1.8*inch, 0.8*inch, 2.2*inch, 1*inch])
            timeline_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.beige, colors.white]),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
            ]))
            
            story.append(timeline_table)
            story.append(Spacer(1, 20))
    
    # Notes section (placeholder for future features)
    story.append(Paragraph("Notes", heading_style))
    story.append(Paragraph("Additional notes and observations can be added here in future versions.", normal_style))
    
    # Build PDF
    doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes


def add_header_footer(canvas, doc):
    """
    Adds header and footer to each page.
    """
    company_name = os.getenv("COMPANY_NAME", "Your Company")
    
    # Header
    canvas.setFont("Helvetica-Bold", 10)
    
    # Footer
    canvas.setFont("Helvetica", 8)
    canvas.drawString(72, 50, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    canvas.drawRightString(522, 50, f"Page {doc.page}")


def merge_pdf_with_original(analysis_pdf_bytes: bytes, original_pdf_bytes: bytes) -> bytes:
    """
    Merges the analysis PDF with the original PDF document.
    
    Args:
        analysis_pdf_bytes: Bytes of the analysis PDF
        original_pdf_bytes: Bytes of the original PDF
    
    Returns:
        Merged PDF bytes
    """
    output_buffer = io.BytesIO()
    
    # Create PDF writer
    writer = pypdf.PdfWriter()
    
    # Add analysis PDF pages
    analysis_reader = pypdf.PdfReader(io.BytesIO(analysis_pdf_bytes))
    for page in analysis_reader.pages:
        writer.add_page(page)
    
    # Add original PDF pages
    try:
        original_reader = pypdf.PdfReader(io.BytesIO(original_pdf_bytes))
        for page in original_reader.pages:
            writer.add_page(page)
    except Exception as e:
        # If original PDF can't be read, add a notice page
        notice_pdf = create_original_unavailable_notice()
        notice_reader = pypdf.PdfReader(io.BytesIO(notice_pdf))
        for page in notice_reader.pages:
            writer.add_page(page)
    
    # Write merged PDF
    writer.write(output_buffer)
    merged_bytes = output_buffer.getvalue()
    output_buffer.close()
    
    return merged_bytes


def create_original_unavailable_notice() -> bytes:
    """
    Creates a PDF notice when the original document is unavailable.
    
    Returns:
        PDF bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'NoticeTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=colors.red
    )
    
    story = []
    story.append(Paragraph("Original Document Unavailable", title_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "The original document could not be retrieved or processed. "
        "Please refer to the analysis above for the extracted information.",
        styles['Normal']
    ))
    
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes


def attach_non_pdf_original(analysis_pdf_bytes: bytes, original_bytes: bytes, 
                          original_filename: str, original_mime_type: str) -> bytes:
    """
    Attaches a non-PDF original document as a file attachment to the analysis PDF.
    
    Args:
        analysis_pdf_bytes: Bytes of the analysis PDF
        original_bytes: Bytes of the original document
        original_filename: Original filename
        original_mime_type: Original MIME type
    
    Returns:
        PDF bytes with attachment
    """
    # Read the analysis PDF
    reader = pypdf.PdfReader(io.BytesIO(analysis_pdf_bytes))
    writer = pypdf.PdfWriter()
    
    # Copy all pages
    for page in reader.pages:
        writer.add_page(page)
    
    # Add attachment
    writer.add_attachment(
        filename=original_filename,
        data=original_bytes,
        mime_type=original_mime_type
    )
    
    # Write to buffer
    output_buffer = io.BytesIO()
    writer.write(output_buffer)
    pdf_bytes = output_buffer.getvalue()
    output_buffer.close()
    
    return pdf_bytes


def create_attachment_notice_page(original_filename: str) -> bytes:
    """
    Creates a notice page explaining where to find the attached original document.
    
    Args:
        original_filename: Name of the original file
    
    Returns:
        PDF bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'NoticeTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    story = []
    story.append(Paragraph("Original Document Attachment", title_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        f"The original document '{original_filename}' has been attached to this PDF. "
        "You can find it in the attachments section of your PDF viewer.",
        styles['Normal']
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "To access the attachment:",
        styles['Heading3']
    ))
    story.append(Paragraph("• In Adobe Acrobat: Go to View → Attachments", styles['Normal']))
    story.append(Paragraph("• In most PDF viewers: Look for a paperclip icon or attachments panel", styles['Normal']))
    
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
