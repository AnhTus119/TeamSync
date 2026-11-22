from pathlib import Path
from xml.sax.saxutils import escape
from flask import current_app


def render_pdf(out,data,headers,values):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4,landscape
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    font=Path(current_app.config.get('REPORT_FONT','app/static/fonts/DejaVuSans.ttf'))
    if not font.exists():
        from ..academic.core import need
        need(False,'REPORT_FONT_MISSING','Cần cài font Unicode để xuất PDF',503)
    pdfmetrics.registerFont(TTFont('TeamSync',str(font)))
    styles=getSampleStyleSheet()
    for k in ('Title','BodyText'):styles[k].fontName='TeamSync'
    rows=[[Paragraph(escape(str(c if c is not None else '—')),styles['BodyText']) for c in row] for row in [headers]+values]
    doc=SimpleDocTemplate(out,pagesize=landscape(A4),leftMargin=28,rightMargin=28)
    table=Table(rows,colWidths=[100,74,78,72,88,74,90,145],repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#fae8ec')),
        ('GRID',(0,0),(-1,-1),.4,colors.HexColor('#d8d5e3')),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
    doc.build([Paragraph('TeamSync · '+escape(data['project']['name']),styles['Title']),Spacer(1,12),table,Spacer(1,14),
        Paragraph('Chỉ số hỗ trợ phản hồi; không tự động quy đổi thành điểm học phần. Dữ liệu tạm tính khi dưới 3 công việc.',styles['BodyText'])])
