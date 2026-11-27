"""One report dataset, three export formats; no reviewer identities."""
from io import BytesIO
from pathlib import Path
from html import escape
from flask import send_file, render_template
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.chart import BarChart, Reference
from .core import need

LABEL={'todo':'Cần làm','in_progress':'Đang làm','review':'Chờ duyệt','done':'Hoàn thành','pending':'Chờ xử lý','approved':'Đã đồng ý','rejected':'Không đồng ý'}
def clean(v):
    s=str(v if v is not None else '')
    return "'"+s if s.startswith(('=','+','-','@','\t','\r')) else s

def tables(d):
    return [
      ('Đóng góp',['Thành viên','Khối lượng đã duyệt','Tỷ trọng %'],[[m['user']['full_name'],float(m['accepted_workload']),float(m['percent'])] for m in d['members']]),
      ('Công việc',['Công việc','Trạng thái','Khối lượng','Hạn','Phân bổ'],[[t['title'],LABEL.get(t['status'],t['status']),t['points'],t['due_at'],'; '.join(x['user']['full_name']+': '+x['percent']+'%' for x in t['shares'])] for t in d['tasks']]),
      ('Đánh giá chéo',['Đợt','Thành viên','Số phiếu','Hợp tác /10','Chất lượng /10','Trung bình /10'],[[r['title'],x['user']['full_name'],x['count'],x['attitude'],x['quality'],x['average']] for r in d['peer'] for x in r['items']]),
      ('Nhân sự',['Thành viên','Lý do','Trạng thái','Đồng ý','Ngưỡng','Người kế nhiệm'],[[x['user']['full_name'],x['reason'],LABEL.get(x['status'],x['status']),x['yes'],x['threshold'],(x['successor'] or {}).get('full_name','')] for x in d['departures']]),
      ('Điều chỉnh',['Công việc','Người quyết định','Lý do','Tỷ lệ mới'],[[next((t['title'] for t in d['tasks'] if t['id']==x['task_id']),str(x['task_id'])),x['decided_by_name'],x['reason'],'; '.join(next((m['user']['full_name'] for m in d['members'] if str(m['user']['id'])==uid),uid)+': '+str(v)+'%' for uid,v in x['shares'].items())] for x in d['allocation_history']]),
      ('Diễn biến',['Thời điểm','Sự kiện','Nội dung'],[[e['at'],{'task.created':'Tạo việc','task.started':'Bắt đầu','task.submitted':'Nộp bài','submission.accepted':'Duyệt hoàn thành','submission.returned':'Yêu cầu sửa'}.get(e['action'],e['action']),e['reason']] for e in d['timeline']]),
      ('Sản phẩm',['Tên bàn giao','Ngày nộp','Mã bài nộp'],[[x['title'],x['created_at'],', '.join(map(str,x['submission_ids']))] for x in d['deliveries']]),
      ('Tài liệu đề bài',['Tên tài liệu'],[[x['original_filename']] for x in d['documents']]),
      ('Minh chứng',['Tiêu chí','Bản đã duyệt','Bản chờ duyệt','Bản cần sửa'],[[e['title']+('' if e.get('is_active',True) else ' (đã ẩn)'),e['accepted'],e['pending'],e['returned']] for e in d.get('evidence',[])])]

def export_report(d,fmt):
    need(fmt in ('xlsx','pdf','html'));out=BytesIO();tabs=tables(d)
    if fmt=='html':return render_template('academic/report_v2.html',d=d,tabs=tabs)
    if fmt=='xlsx':
        wb=Workbook();ws=wb.active;ws.title='Tổng quan'
        for row in [['TEAMSYNC — BÁO CÁO NHÓM'],[d['course']['title'],d['course']['term']],[d['project']['name'],d['assignment']['title']],['Thời điểm xuất',d['generated_at']],['Cách tính',d['formula']],[],['Trạng thái','Số công việc']]:ws.append(row)
        for status in ('todo','in_progress','review','done'):ws.append([LABEL[status],sum(t['status']==status for t in d['tasks'])])
        chart=BarChart();chart.title='Trạng thái công việc';chart.add_data(Reference(ws,min_col=2,min_row=7,max_row=11),titles_from_data=True);chart.set_categories(Reference(ws,min_col=1,min_row=8,max_row=11));ws.add_chart(chart,'D7')
        for title,headers,rows in tabs:
            sheet=wb.create_sheet(title);sheet.append(headers)
            for row in rows:sheet.append([clean(x) if isinstance(x,str) else x for x in row])
        for sheet in wb:
            sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
            sheet.sheet_properties.pageSetUpPr.fitToPage=True
            sheet.page_setup.orientation='landscape';sheet.page_setup.paperSize=sheet.PAPERSIZE_A4;sheet.page_setup.fitToWidth=1;sheet.page_setup.fitToHeight=0
            sheet.print_title_rows='1:1'
            for cell in sheet[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='1768AE')
            for col in sheet.columns:
                sheet.column_dimensions[col[0].column_letter].width=min(55,max(18,max(len(str(c.value or '')) for c in col)+2))
            for row in sheet.iter_rows(min_row=2):
                for cell in row:
                    cell.alignment=Alignment(vertical='top',wrap_text=True)
                    if cell.row%2==0:cell.fill=PatternFill('solid',fgColor='EDF5FC')
        sh=wb['Đóng góp'];chart=BarChart();chart.title='Khối lượng ghi nhận';chart.add_data(Reference(sh,min_col=2,min_row=1,max_row=max(2,sh.max_row)),titles_from_data=True);chart.set_categories(Reference(sh,min_col=1,min_row=2,max_row=max(2,sh.max_row)));sh.add_chart(chart,'E2')
        wb.save(out);mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,PageBreak
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.pagesizes import A4,landscape
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics.charts.barcharts import VerticalBarChart
        from reportlab.lib import colors
        pdfmetrics.registerFont(TTFont('VN',str(Path(__file__).parents[1]/'static/fonts/DejaVuSans.ttf')))
        st=getSampleStyleSheet()
        for s in st.byName.values():s.fontName='VN'
        st['BodyText'].fontSize=9;st['BodyText'].leading=13
        p=lambda s:Paragraph(escape(str(s)),st['BodyText'])
        story=[Paragraph('BÁO CÁO NHÓM · '+escape(d['project']['name']),st['Title']),p(d['course']['title']+' — '+d['assignment']['title']),p('Xuất lúc '+d['generated_at']),Spacer(1,12),p(d['formula']),Spacer(1,18)]
        drawing=Drawing(650,190);bc=VerticalBarChart();bc.x=45;bc.y=35;bc.width=580;bc.height=145;bc.data=[[sum(t['status']==s for t in d['tasks']) for s in ('todo','in_progress','review','done')]];bc.categoryAxis.categoryNames=['Cần làm','Đang làm','Chờ duyệt','Hoàn thành'];bc.categoryAxis.labels.fontName='VN';bc.bars[0].fillColor=colors.HexColor('#1768AE');drawing.add(bc);story.append(drawing)
        for title,headers,rows in tabs:
            story.extend([PageBreak(),Paragraph(escape(title),st['Heading1']),Spacer(1,12)])
            table=Table([[p(c) for c in headers]]+[[p(c) for c in row] for row in rows],repeatRows=1,colWidths=[770/len(headers)]*len(headers))
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#DCEEFF')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F1F7FC')]),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]));story.append(table)
            if not rows:story.append(p('Chưa có dữ liệu.'))
        SimpleDocTemplate(out,pagesize=landscape(A4),leftMargin=32,rightMargin=32,topMargin=30,bottomMargin=30).build(story);mime='application/pdf'
    out.seek(0);return send_file(out,mimetype=mime,as_attachment=True,download_name=f'TeamSync-nhom-{d["project"]["id"]}.{fmt}')
