import threading, shutil
from pathlib import Path
import pytest
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright, expect
from test_workflow import app, template

@pytest.fixture
def browser(app):
    server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    with sync_playwright() as pw:
        b=pw.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
        yield b,f'http://127.0.0.1:{server.server_port}'
        b.close()
    server.shutdown();thread.join()

def login(browser,email):
    b,url=browser;context=b.new_context(viewport={'width':1440,'height':1000});page=context.new_page()
    page.goto(url+'/login');page.get_by_label('Email',exact=True).fill(email);page.get_by_label('Mật khẩu',exact=True).fill('12345');page.get_by_role('button',name='Đăng nhập',exact=True).click();page.wait_for_url('**/home');return page,url

def test_real_drag_drop_review_history_report(browser,tmp_path):
    student,url=login(browser,'sv2@gmail.com');errors=[];student.on('pageerror',lambda e:errors.append(str(e)))
    student.goto(url+'/tasks/1');student.get_by_label('Nội dung bàn giao').fill('Bản sửa đã kiểm tra thông báo lỗi')
    student.locator('#dropzone').evaluate("el=>{const d=new DataTransfer();d.items.add(new File(['Bai nop moi'],'demo.txt',{type:'text/plain'}));el.dispatchEvent(new DragEvent('drop',{dataTransfer:d,bubbles:true,cancelable:true}))}")
    student.get_by_role('button',name='Gửi duyệt',exact=True).click();expect(student.get_by_role('heading',name='Lần nộp 2')).to_be_visible()
    leader,_=login(browser,'sv1@gmail.com');leader.goto(url+'/tasks/1');leader.get_by_role('button',name='Yêu cầu sửa',exact=True).click();expect(leader.locator('#review-error')).to_contain_text('Bạn cần bổ sung')
    leader.get_by_label('Nhận xét (bắt buộc khi yêu cầu sửa)').fill('Bổ sung tài liệu chạy chương trình');leader.get_by_role('button',name='Yêu cầu sửa',exact=True).click();expect(leader.get_by_text('Bổ sung tài liệu chạy chương trình',exact=True)).to_be_visible()
    student.reload();student.get_by_label('Nội dung bàn giao').fill('Đã bổ sung hướng dẫn chạy');student.get_by_label('Dùng lại file của lần nộp gần nhất').check();student.get_by_role('button',name='Gửi duyệt',exact=True).click();expect(student.get_by_role('heading',name='Lần nộp 3')).to_be_visible()
    leader.reload();leader.get_by_role('button',name='Duyệt hoàn thành',exact=True).click();expect(leader.get_by_text('Đã duyệt',exact=True)).to_be_visible()
    leader.get_by_role('button',name='Xem bản cũ',exact=True).click();expect(leader.locator('#history')).to_be_visible();leader.get_by_role('button',name='Ẩn bản cũ',exact=True).click();expect(leader.locator('#history')).to_be_hidden()
    leader.goto(url+'/projects/1?tab=report');expect(leader.locator('#contribution-chart')).to_be_visible()
    with leader.expect_download() as download:leader.get_by_role('link',name='Excel',exact=True).click()
    path=tmp_path/'report.xlsx';download.value.save_as(path)
    from openpyxl import load_workbook
    wb=load_workbook(path);assert 'Đánh giá chéo' in wb.sheetnames and wb['Đóng góp'].max_row==7
    leader.get_by_role('button',name='Lưu bản báo cáo hiện tại').click();expect(leader.get_by_role('link',name='PDF',exact=True)).to_have_count(2)
    shots=Path('/workspace/screens');shots.mkdir(exist_ok=True);leader.screenshot(path=str(shots/'tested-report.png'),full_page=True)
    leader.set_viewport_size({'width':390,'height':844});leader.goto(url+'/projects/1');expect(leader.get_by_role('heading',name='Nhóm 01')).to_be_visible();assert not leader.evaluate('document.documentElement.scrollWidth>innerWidth');leader.screenshot(path=str(shots/'tested-mobile.png'),full_page=True)
    assert not errors

def test_browser_teacher_create_and_peer(browser):
    teacher,url=login(browser,'gv1@gmail.com');teacher.goto(url+'/courses/1');teacher.get_by_role('button',name='Mở đợt đánh giá chéo').click();teacher.get_by_role('dialog').get_by_role('button',name='Lưu',exact=True).click();expect(teacher.get_by_role('dialog')).to_have_count(0)
    student,_=login(browser,'sv2@gmail.com');student.goto(url+'/projects/1?tab=peer');student.get_by_role('button',name='Đánh giá thành viên',exact=True).click();fs=student.locator('fieldset').first;fs.get_by_role('checkbox').uncheck();fs.get_by_label('Thái độ hợp tác').select_option('8');fs.get_by_label('Chất lượng công việc').select_option('6');student.get_by_role('dialog').get_by_role('button',name='Lưu',exact=True).click();expect(student.get_by_role('dialog')).to_have_count(0)
    teacher.goto(url+'/projects/1?tab=peer');teacher.get_by_role('button',name='Đóng đợt',exact=True).click();expect(teacher.get_by_role('cell',name='Sinh viên 01',exact=True)).to_be_visible();student.reload();expect(student.get_by_role('cell',name='Sinh viên 01',exact=True)).to_be_visible()
    teacher.goto(url+'/home');teacher.get_by_role('button',name='Tạo lớp',exact=True).click();teacher.get_by_label('Mã lớp',exact=True).fill('TEST-01');teacher.get_by_label('Tên học phần').fill('Lớp kiểm thử');teacher.get_by_role('dialog').get_by_role('button',name='Lưu',exact=True).click();expect(teacher.get_by_role('heading',name='Lớp kiểm thử')).to_be_visible()
