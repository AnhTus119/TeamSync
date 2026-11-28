import os, threading, shutil
from pathlib import Path
import pytest
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright, expect
from test_workflow import app, template, name_of, demo, MA, TH, QB, GL, GV, GV_AI

@pytest.fixture
def browser(app):
    server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    with sync_playwright() as pw:
        exe=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or next((x for x in ('/opt/pw-browsers/chromium',) if os.path.exists(x)),None)
        b=pw.chromium.launch(executable_path=exe,headless=True,args=['--no-sandbox'])
        yield b,f'http://127.0.0.1:{server.server_port}'
        b.close()
    server.shutdown();thread.join()

def login(browser,email):
    b,url=browser;context=b.new_context(viewport={'width':1440,'height':1000});page=context.new_page()
    page.goto(url+'/login');page.get_by_label('Email',exact=True).fill(email);page.get_by_label('Mật khẩu',exact=True).fill('12345');page.get_by_role('button',name='Đăng nhập',exact=True).click();page.wait_for_url('**/home');return page,url

def test_real_drag_drop_review_history_report(browser,app,tmp_path):
    d=demo(app);tid,pid=d['tid'],d['pid']
    student,url=login(browser,TH);errors=[];student.on('pageerror',lambda e:errors.append(str(e)))
    student.goto(f'{url}/tasks/{tid}');student.get_by_label('Nội dung bàn giao').fill('Bản sửa đã kiểm tra thông báo lỗi')
    student.locator('#dropzone').evaluate("el=>{const d=new DataTransfer();d.items.add(new File(['Bai nop moi'],'demo.txt',{type:'text/plain'}));el.dispatchEvent(new DragEvent('drop',{dataTransfer:d,bubbles:true,cancelable:true}))}")
    student.get_by_role('button',name='Gửi duyệt',exact=True).click();expect(student.get_by_role('heading',name='Lần nộp 2')).to_be_visible()
    leader,_=login(browser,MA);leader.goto(f'{url}/tasks/{tid}');leader.get_by_role('button',name='Yêu cầu sửa',exact=True).click();expect(leader.locator('#review-error')).to_contain_text('Bạn cần bổ sung')
    leader.get_by_label('Nhận xét (bắt buộc khi yêu cầu sửa)').fill('Bổ sung tài liệu chạy chương trình');leader.get_by_role('button',name='Yêu cầu sửa',exact=True).click();expect(leader.locator('.submission-card.focus .feedback')).to_contain_text('Bổ sung tài liệu chạy chương trình')
    student.reload();student.get_by_label('Nội dung bàn giao').fill('Đã bổ sung hướng dẫn chạy');student.get_by_label('Dùng lại tệp của lần nộp gần nhất').check();student.get_by_role('button',name='Gửi duyệt',exact=True).click();expect(student.get_by_role('heading',name='Lần nộp 3')).to_be_visible()
    leader.reload();leader.get_by_role('button',name='Duyệt hoàn thành',exact=True).click();expect(leader.locator('.submission-card.focus').get_by_text('Đã duyệt',exact=True)).to_be_visible()
    leader.get_by_role('button',name='Xem bản cũ',exact=True).click();expect(leader.locator('#history')).to_be_visible();leader.get_by_role('button',name='Ẩn bản cũ',exact=True).click();expect(leader.locator('#history')).to_be_hidden()
    leader.goto(f'{url}/projects/{pid}?tab=report');expect(leader.locator('#contribution-chart')).to_be_visible()
    with leader.expect_download() as download:leader.get_by_role('link',name='Excel',exact=True).click()
    path=tmp_path/'report.xlsx';download.value.save_as(path)
    from openpyxl import load_workbook
    wb=load_workbook(path);assert 'Đánh giá chéo' in wb.sheetnames and wb['Đóng góp'].max_row==5
    expect(leader.get_by_role('heading',name='Báo cáo đã lưu')).to_have_count(0);expect(leader.get_by_role('button',name='Lưu bản báo cáo hiện tại')).to_have_count(0)
    shots=tmp_path;leader.screenshot(path=str(shots/'tested-report.png'),full_page=True)
    leader.set_viewport_size({'width':390,'height':844});leader.goto(f'{url}/projects/{pid}');expect(leader.get_by_role('heading',name='Free2do')).to_be_visible();assert not leader.evaluate('document.documentElement.scrollWidth>innerWidth');leader.screenshot(path=str(shots/'tested-mobile.png'),full_page=True)
    assert not errors

def test_browser_teacher_create_and_peer(browser,app):
    """Đánh giá chéo theo công việc: thành viên không làm task đánh giá người làm; giảng viên chỉ theo dõi."""
    d=demo(app);pid=d['pid']
    teacher,url=login(browser,GV);teacher.goto(f'{url}/courses/{d["cid"]}?tab=brief')
    expect(teacher.get_by_role('button',name='Mở đợt đánh giá chéo')).to_have_count(0)
    student,_=login(browser,TH);student.goto(f'{url}/home');student.locator('.alert-item[data-alert=peer_pending]').click();student.wait_for_url('**tab=peer**')
    card=student.locator('.peer-task.needs',has_text='Chuẩn hóa mẫu phản hồi khách hàng');expect(card).to_be_visible()
    card.get_by_role('button',name='Đánh giá người làm').click();dlg=student.get_by_role('dialog')
    fs=dlg.locator('fieldset').first;fs.get_by_label('Hợp tác').select_option('8');fs.get_by_label('Chất lượng').select_option('6');fs.get_by_label('Nhận xét (tùy chọn)').fill('Đúng hạn')
    dlg.locator('fieldset').nth(1).get_by_role('checkbox').check();dlg.get_by_role('button',name='Lưu',exact=True).click();expect(student.get_by_role('dialog')).to_have_count(0)
    expect(student.locator('.peer-task.needs')).to_have_count(0);expect(student.get_by_role('button',name='Sửa đánh giá')).to_be_visible()
    teacher.goto(f'{url}/projects/{pid}?tab=peer');expect(teacher.locator('.peer-task',has_text='Chuẩn hóa mẫu phản hồi khách hàng')).to_contain_text('Đã nhận 1 phiếu')
    expect(teacher.get_by_role('button',name='Đánh giá người làm')).to_have_count(0)
    teacher.goto(url+'/home');teacher.get_by_role('button',name='Tạo lớp',exact=True).click();teacher.get_by_label('Mã lớp',exact=True).fill('TEST-01');teacher.get_by_label('Tên học phần').fill('Lớp kiểm thử');teacher.get_by_role('dialog').get_by_role('button',name='Lưu',exact=True).click();expect(teacher.get_by_role('heading',name='Lớp kiểm thử')).to_be_visible()


def test_browser_teacher_three_menus_groups_and_no_reload(browser):
    """Giảng viên: chỉ Tổng quan / Timeline / Học phần; mở lớp thấy ngay các nhóm; chuyển trang không tải lại."""
    gv, url = login(browser, GV); errors = []; gv.on('pageerror', lambda e: errors.append(str(e)))
    expect(gv.locator('#main-nav a')).to_have_text(['Tổng quan', 'Timeline', 'Học phần'])
    expect(gv.locator('#project-nav')).to_be_hidden()
    gv.evaluate('window.__same = 1')
    gv.locator('#main-nav a', has_text='Học phần').click(); gv.locator('.course-row').first.click()
    expect(gv.locator('.group-card')).to_have_count(5); assert '/courses/' in gv.url
    expect(gv.get_by_role('link', name='Nhóm dự án · 5')).to_have_attribute('aria-current', 'page')
    gv.locator('[data-search-input]').fill('free'); expect(gv.locator('.group-card:visible')).to_have_count(1)
    gv.locator('.group-card:visible').click(); gv.wait_for_url('**/projects/*')
    expect(gv.locator('#main-nav a.active')).to_have_text('Học phần')
    gv.locator('#main-nav a', has_text='Timeline').click(); gv.locator('#tl-grid').wait_for()
    expect(gv.locator('#tl-course')).to_be_visible(); expect(gv.locator('.tl-item.cat-task')).to_have_count(0)
    for path in ('/submissions', '/kanban', '/projects'):
        gv.goto(url + path); gv.wait_for_url('**/home')
    gv.go_back(); gv.go_back()
    gv.goto(url + '/home'); gv.evaluate('window.__same = 1'); gv.locator('#main-nav a', has_text='Học phần').click(); gv.locator('.course-row').first.wait_for()
    assert gv.evaluate('window.__same') == 1  # same document: sidebar and page were not reloaded
    assert not errors, errors

def open_alert(page, title):
    """Click the alert for a task, expanding 'Xem thêm' first when the list is collapsed."""
    item = page.locator('.alert-item', has_text=title).first
    item.wait_for(state='attached')
    more = page.locator('[data-action=more-alerts]')
    if not item.is_visible() and more.count():
        more.click()
    item.click()


def ids(page, url, title):
    """Task and project id for a task title, read through the normal API with the page's session."""
    return page.evaluate("async t=>{const r=await fetch('/api/v1/workflow/tasks');const d=(await r.json()).data;const x=d.items.find(i=>i.title===t);return [x.id,x.project_id]}", title)


def test_browser_demo_flow_criteria_referral_resubmit(browser):
    """Giảng viên thêm tiêu chí → nộp gắn tiêu chí → người trong lần nộp bị chặn → chuyển GV → GV yêu cầu sửa → nộp lại → duyệt."""
    gv, url = login(browser, GV_AI); errors = []; gv.on('pageerror', lambda e: errors.append(str(e)))
    gv.goto(url + '/courses'); gv.locator('.course-row', has_text='Trí tuệ nhân tạo').click()
    gv.get_by_role('link', name='Đề bài & tiêu chí', exact=True).click()
    expect(gv.get_by_role('heading', name='Tiêu chí minh chứng')).to_be_visible()
    gv.get_by_role('button', name='Thêm tiêu chí').click(); gv.get_by_label('Tên tiêu chí').fill('Bảng ước tính tích hợp')
    gv.get_by_role('dialog').get_by_role('button', name='Lưu', exact=True).click()
    expect(gv.get_by_role('cell', name='Bảng ước tính tích hợp')).to_be_visible()

    ma, _ = login(browser, MA); ma.on('pageerror', lambda e: errors.append(str(e)))
    tid, pid = ids(ma, url, 'Cập nhật ước tính đầu việc tích hợp')
    ma.goto(f'{url}/tasks/{tid}'); old_text = 'Bảng ước tính cho 8 đầu việc tích hợp.'
    ma.get_by_label('Nội dung bàn giao').fill('Lần 2: bổ sung bảng ước tính')
    ma.locator('#dropzone').evaluate("el=>{const d=new DataTransfer();d.items.add(new File(['uoc tinh'],'uoc-tinh.txt',{type:'text/plain'}));el.dispatchEvent(new DragEvent('drop',{dataTransfer:d,bubbles:true,cancelable:true}))}")
    ma.get_by_label('Bảng ước tính tích hợp').select_option(label='Tệp mới: uoc-tinh.txt')
    ma.get_by_role('button', name='Gửi duyệt', exact=True).click()
    expect(ma.get_by_role('heading', name='Lần nộp 2')).to_be_visible()
    card = ma.locator('.submission-card.focus')
    expect(card.get_by_role('cell', name='Bảng ước tính tích hợp')).to_be_visible()
    expect(card.locator('.block-note')).to_contain_text('có tên trong lần nộp')
    expect(card.get_by_role('button', name='Duyệt hoàn thành')).to_have_count(0)

    th, _ = login(browser, TH); th.goto(f'{url}/tasks/{tid}')
    reviewer = th.evaluate("async p=>{const r=await fetch('/api/v1/projects/'+p);const d=(await r.json()).data;return d.members.find(m=>m.role!=='leader'&&m.user.email!=='" + MA + "').user.email}", pid)
    th.get_by_role('button', name='Chuyển giảng viên duyệt').click(); th.get_by_label('Lý do chuyển').fill('Nhờ giảng viên kiểm tra cách ước tính')
    th.get_by_role('dialog').get_by_role('button', name='Lưu', exact=True).click()
    expect(th.locator('.referral')).to_contain_text('Nhờ giảng viên kiểm tra cách ước tính')

    gv.goto(url + '/home'); gv.locator('#review-list').wait_for()  # giảng viên: bài được chuyển nằm ở Tổng quan
    gv.locator('#review-list').get_by_role('row', name='Cập nhật ước tính').get_by_role('link', name='Xem để duyệt').click()
    expect(gv.get_by_role('heading', name='Lần nộp 2')).to_be_visible()
    expect(gv.locator('.referral')).to_contain_text('Nhờ giảng viên kiểm tra')
    gv.get_by_role('button', name='Yêu cầu sửa', exact=True).click(); expect(gv.locator('#review-error')).to_contain_text('Bạn cần bổ sung')
    gv.get_by_label('Nhận xét (bắt buộc khi yêu cầu sửa)').fill('Bổ sung ước tính phần xác thực')
    gv.get_by_role('button', name='Yêu cầu sửa', exact=True).click()
    expect(gv.locator('.submission-card.focus .feedback')).to_contain_text('Bổ sung ước tính phần xác thực')

    ma.reload(); ma.get_by_label('Nội dung bàn giao').fill('Lần 3: thêm phần xác thực')
    ma.get_by_label('Dùng lại tệp của lần nộp gần nhất').check(); ma.get_by_role('button', name='Gửi duyệt', exact=True).click()
    expect(ma.get_by_role('heading', name='Lần nộp 3')).to_be_visible()
    qb, _ = login(browser, reviewer); qb.goto(f'{url}/tasks/{tid}')
    qb.get_by_role('button', name='Duyệt hoàn thành', exact=True).click()
    expect(qb.locator('.submission-card.focus').get_by_text('Đã duyệt', exact=True)).to_be_visible()
    # Lần 1 vẫn còn nguyên: nút Lần 1 mở đúng nội dung cũ theo ID
    qb.get_by_role('link', name='Lần 1', exact=True).click()
    expect(qb.locator('.submission-card.focus')).to_contain_text(old_text)
    expect(qb.locator('.submission-card.focus')).to_contain_text('Thiếu ước tính cho phần xác thực.')
    assert 'submission=' in qb.url
    qb.goto(f'{url}/projects/{pid}?tab=report'); expect(qb.get_by_role('heading', name='Minh chứng theo tiêu chí')).to_be_visible()
    assert not errors, errors


def test_browser_dashboard_navigation_and_toggle(browser):
    ma, url = login(browser, MA); errors = []; ma.on('pageerror', lambda e: errors.append(str(e)))
    mine = ma.evaluate("async()=>(await (await fetch('/api/v1/workflow/tasks?scope=mine')).json()).data.items")
    queue = ma.evaluate("async()=>(await (await fetch('/api/v1/workflow/submissions')).json()).data.counts.to_review")
    repair = sum(t['status'] == 'in_progress' and t['latest_submission_status'] == 'returned' for t in mine)
    f2d = [t for t in mine if t['project_name'] == 'Free2do']
    cards = ma.locator('.metric'); expect(cards).to_have_count(6)
    names = cards.locator('.metric-head > span').all_inner_texts()
    assert names == ['Cần sửa', 'Đến hạn / quá hạn', 'Chờ duyệt', 'Dự án tham gia', 'Dự án làm lead', 'Điểm đánh giá chéo']
    ma.get_by_role('button', name='Tròn').click(); expect(ma.locator('.pie-card')).to_have_count(3)
    expect(ma.get_by_role('button', name='Tròn')).to_have_attribute('aria-pressed', 'true')
    ma.reload(); expect(ma.locator('.pie-card')).to_have_count(3)
    ma.get_by_role('button', name='Cột').click(); expect(cards).to_have_count(6)
    targets = [('Cần sửa', 'filter=repair'), ('Đến hạn / quá hạn', 'filter=due'), ('Chờ duyệt', 'filter=review'), ('Dự án tham gia', '/projects'), ('Dự án làm lead', 'lead=1'), ('Điểm đánh giá chéo', '/projects')]
    for label, part in targets:
        ma.goto(url + '/home'); ma.get_by_role('link', name='Xem danh sách: ' + label).click(); ma.wait_for_load_state('networkidle')
        assert part in ma.url or part.replace('filter=', '') + '=1' in ma.url, (label, ma.url)
        if 'repair' in part:
            expect(ma.locator('[data-filter=repair]')).to_have_attribute('aria-pressed', 'true')
            expect(ma.locator('.pk-card')).to_have_count(repair)
        if 'lead' in part:
            expect(ma.locator('.project-card:visible')).to_have_count(2)
    ma.goto(url + '/home'); ma.get_by_role('link', name=f'Bài cần tôi duyệt · {queue}').click()
    expect(ma.get_by_role('tab', name=f'Cần tôi duyệt {queue}')).to_have_attribute('aria-selected', 'true')
    ma.goto(url + '/home'); open_alert(ma, 'Sửa lỗi tạo phiếu hỗ trợ'); assert 'submission=' in ma.url
    expect(ma.locator('.submission-card.focus')).to_be_visible()
    ma.goto(url + '/kanban'); ma.get_by_role('combobox', name='Lọc theo dự án').select_option(label='Free2do · Đội Hỗ trợ')
    expect(ma.locator('.pk-card')).to_have_count(len(f2d))
    ma.get_by_role('button', name='Quá hạn').click(); expect(ma.locator('.pk-card')).to_have_count(sum(t['overdue'] for t in f2d))
    ma.goto(url + '/projects'); ma.get_by_role('button', name='Tôi làm lead').click(); expect(ma.locator('.project-card:visible')).to_have_count(2)
    ma.locator('#avatar').click(); expect(ma.locator('#account-menu')).to_contain_text(MA)
    expect(ma.locator('#avatar')).to_have_attribute('aria-expanded', 'true')
    ma.get_by_role('button', name='Đăng xuất').click(); ma.wait_for_url('**/login')
    assert not errors, errors


def test_browser_import_course_tabs_and_mobile(browser, tmp_path):
    gv, url = login(browser, GV); errors = []; gv.on('pageerror', lambda e: errors.append(str(e)))
    gv.goto(url + '/courses'); gv.locator('.course-row', has_text='Phát triển ứng dụng Web').click()
    expect(gv.get_by_role('link', name='Nhóm dự án · 5', exact=True)).to_have_attribute('aria-current', 'page')  # default tab
    for tab in ('Sinh viên', 'Nhóm dự án · 5', 'Đề bài & tiêu chí'):
        gv.get_by_role('link', name=tab, exact=True).click(); expect(gv.get_by_role('link', name=tab, exact=True)).to_have_attribute('aria-current', 'page')
    gv.get_by_role('link', name='Sinh viên', exact=True).click()
    bad = tmp_path / 'ds.csv'; bad.write_text('student_code,full_name,email\nTSNEW051,An Bình,anbinh@example.org\nTSNEW052,Bảo Linh,email-khong-hop-le\n', encoding='utf-8')
    gv.get_by_role('button', name='Nhập CSV / Excel').click(); gv.locator('#import-file').set_input_files(str(bad))
    expect(gv.locator('#import-status')).to_contain_text('2 dòng · 1 dòng cần sửa')
    expect(gv.locator('tr.row-error')).to_contain_text('email sai định dạng')
    expect(gv.get_by_role('button', name='Xác nhận nhập')).to_be_disabled()
    bad.write_text('student_code,full_name,email\nTSNEW051,An Bình,anbinh@example.org\nTSNEW052,Bảo Linh,baolinh@example.org\n', encoding='utf-8')
    with gv.expect_file_chooser() as fc: gv.get_by_role('button', name='Chọn tệp khác').click()
    fc.value.set_files(str(bad)); expect(gv.locator('#import-status')).to_contain_text('tất cả hợp lệ')
    gv.get_by_role('button', name='Xác nhận nhập').click(); expect(gv.get_by_role('dialog')).to_have_count(0)
    expect(gv.get_by_role('cell', name='Bảo Linh', exact=True)).to_be_visible(); assert 'tab=students' in gv.url
    gv.set_viewport_size({'width': 390, 'height': 844})
    for path in ('/home', '/timeline', '/courses', gv.url.replace(url, '')):
        gv.goto(url + path); gv.wait_for_load_state('networkidle')
        assert not gv.evaluate('document.documentElement.scrollWidth>innerWidth'), path
    expect(gv.locator('#sidebar')).to_be_hidden(); gv.get_by_role('button', name='Bật/tắt thanh điều hướng').click(); expect(gv.locator('#sidebar')).to_be_visible()
    gv.screenshot(path=str(tmp_path / 'mobile.png'))
    assert not errors, errors


def test_browser_overview_four_columns_and_alert_cases(browser):
    ma, url = login(browser, MA); errors = []; ma.on('pageerror', lambda e: errors.append(str(e)))
    order = lambda: ma.locator('.dashboard-columns > section h2').all_inner_texts()
    ma.locator('.dashboard-columns').wait_for()
    assert order() == ['Task sắp hết hạn', 'Cập nhật dự án', 'Cảnh báo cần xử lý', 'Thông báo gần đây']
    tops = ma.evaluate("[...document.querySelectorAll('.dashboard-columns > section')].map(s=>Math.round(s.getBoundingClientRect().top))")
    assert len(set(tops)) == 1, tops  # one row on desktop
    for width in (1100, 390):
        ma.set_viewport_size({'width': width, 'height': 900}); assert order()[2] == 'Cảnh báo cần xử lý'
        assert not ma.evaluate('document.documentElement.scrollWidth>innerWidth'), width
    ma.set_viewport_size({'width': 1440, 'height': 1000})
    ma.get_by_role('button', name='Bật/tắt thanh điều hướng').click(); assert not ma.evaluate('document.documentElement.scrollWidth>innerWidth')
    ma.get_by_role('button', name='Bật/tắt thanh điều hướng').click()
    ma.locator('#avatar').click()
    expect(ma.locator('#logout')).to_have_text('Đăng xuất'); expect(ma.locator('#menu-settings svg')).to_have_count(1); expect(ma.locator('#logout svg')).to_have_count(1)
    ma.keyboard.press('Escape')

    def with_alerts(make):
        def handle(route):
            r = route.fetch(); body = r.json(); body['data']['alerts'] = make(body['data']['alerts']); route.fulfill(response=r, json=body)
        ma.route('**/api/v1/workflow/home', handle); ma.reload(); ma.locator('.dashboard-columns').wait_for(); ma.wait_for_load_state('networkidle'); ma.unroute('**/api/v1/workflow/home')
    long = 'Kiểm thử hồi quy toàn bộ luồng đặt hàng trên điện thoại và máy tính bảng với dữ liệu thật của khách hàng doanh nghiệp'
    with_alerts(lambda a: [{**a[0], 'task_title': long if i == 0 else f'{a[0]["task_title"]} {i}'} for i in range(7)])
    expect(ma.locator('.alert-item:visible')).to_have_count(4)
    ma.get_by_role('button', name='Xem thêm (3)').click(); expect(ma.locator('.alert-item:visible')).to_have_count(7)
    ma.get_by_role('button', name='Thu gọn').click(); expect(ma.locator('.alert-item:visible')).to_have_count(4)
    assert not ma.evaluate('document.documentElement.scrollWidth>innerWidth')
    with_alerts(lambda a: [])
    assert order() == ['Task sắp hết hạn', 'Cập nhật dự án', 'Thông báo gần đây']
    widths = ma.evaluate("[...document.querySelectorAll('.dashboard-columns > section')].map(s=>Math.round(s.getBoundingClientRect().width))")
    grid = ma.evaluate("Math.round(document.querySelector('.dashboard-columns').getBoundingClientRect().width)")
    assert len(set(widths)) == 1 and sum(widths) > grid * 0.95, (widths, grid)  # three panels share the full row
    ma.reload(); open_alert(ma, 'Sửa lỗi tạo phiếu hỗ trợ'); ma.wait_for_url('**submission=**')
    expect(ma.locator('.submission-card.focus')).to_be_visible()
    assert not errors, errors


def test_browser_projects_toolbar_tint_sort_and_create(browser, app):
    ma, url = login(browser, MA); errors = []; ma.on('pageerror', lambda e: errors.append(str(e)))
    ma.goto(url + '/projects'); ma.locator('#project-grid').wait_for()
    assert ma.locator('.page-head').count() == 0  # no title block on list pages
    expect(ma.locator('.projects-toolbar').get_by_role('button', name='Tạo dự án')).to_be_visible()
    expect(ma.locator('#project-sort')).to_have_value('progress-desc')
    def cards():
        return ma.evaluate("[...document.querySelectorAll('#project-grid .project-card')].filter(c=>!c.hidden).map(c=>({p:+c.dataset.progress,t:[...c.classList].find(x=>x.startsWith('tier-')),c:c.dataset.created}))")
    cs = cards()
    assert [c['p'] for c in cs] == sorted((c['p'] for c in cs), reverse=True)
    tier = lambda p: 'tier-p0' if p == 0 else 'tier-p1' if p < .25 else 'tier-p25' if p < .5 else 'tier-p50' if p < 1 else 'tier-p100'
    assert all(c['t'] == tier(c['p']) for c in cs)
    colors = {'tier-p0': 'rgb(252, 250, 249)', 'tier-p1': 'rgb(231, 239, 246)', 'tier-p25': 'rgb(224, 239, 237)', 'tier-p50': 'rgb(220, 233, 224)', 'tier-p100': 'rgb(207, 229, 209)'}
    shown = ma.evaluate("[...document.querySelectorAll('#project-grid .project-card')].map(c=>[[...c.classList].find(x=>x.startsWith('tier-')),getComputedStyle(c).backgroundColor])")
    assert all(colors[t] == bg for t, bg in shown)
    ma.locator('#project-sort').select_option('progress-asc'); cs = cards(); assert [c['p'] for c in cs] == sorted(c['p'] for c in cs)
    ma.locator('#project-sort').select_option('created-desc'); cs = cards(); assert [c['c'] for c in cs] == sorted((c['c'] for c in cs), reverse=True)
    ma.get_by_role('button', name='Tôi làm lead').click(); ma.locator('#project-q').fill('free')
    expect(ma.locator('.project-card:visible')).to_have_count(1)
    ma.get_by_role('button', name='Tạo dự án').click(); expect(ma.get_by_role('dialog')).to_contain_text('không có học phần nào')
    sv, _ = login(browser, demo(app)['free'][0]); sv.goto(url + '/projects')
    sv.get_by_role('button', name='Tạo dự án').click(); d = sv.get_by_role('dialog')
    d.get_by_label('Học phần (đề bài nhóm)').select_option(label='Phát triển ứng dụng Web · Ứng dụng web quản lý công việc nhóm')
    d.get_by_label('Tên nhóm dự án').fill('Nhóm thử nghiệm')
    sv.route('**/api/v1/assignments/*/projects', lambda r: r.fulfill(status=409, json={'error': {'code': 'X', 'message': 'Đề bài không còn nhận nhóm'}}) if r.request.method == 'POST' else r.continue_())
    d.get_by_role('button', name='Tạo dự án').click(); expect(d.locator('.error')).to_contain_text('Đề bài không còn nhận nhóm')
    expect(d.get_by_label('Tên nhóm dự án')).to_have_value('Nhóm thử nghiệm')
    sv.unroute('**/api/v1/assignments/*/projects'); d.get_by_role('button', name='Tạo dự án').click()
    sv.wait_for_url('**/projects/*?tab=members'); expect(sv.get_by_role('heading', name='Nhóm thử nghiệm')).to_be_visible()
    sv.set_viewport_size({'width': 390, 'height': 844}); sv.goto(url + '/projects'); sv.locator('#project-grid').wait_for()
    assert not sv.evaluate('document.documentElement.scrollWidth>innerWidth')
    assert not errors, errors


def test_browser_personal_kanban_submissions_and_nav(browser):
    gl, url = login(browser, GL); errors = []; gl.on('pageerror', lambda e: errors.append(str(e)))
    expect(gl.locator('#main-nav a .nav-icon svg')).to_have_count(6)
    assert gl.locator('.brand').evaluate('e=>getComputedStyle(e).fontFamily').startswith('Audiowide')  # wordmark unchanged
    assert 'Audiowide' not in gl.locator('#att-title').evaluate('e=>getComputedStyle(e).fontFamily')  # page titles use the body font
    gl.goto(url + '/kanban'); gl.locator('.pk-board').wait_for()
    expect(gl.get_by_role('button', name='Việc của tôi')).to_have_count(0)
    mine = gl.evaluate("async()=>{const r=await fetch('/api/v1/workflow/tasks?scope=mine');return (await r.json()).data.items.length}")
    assert gl.locator('.pk-card').count() == mine
    counts = gl.locator('.pk-count').all_inner_texts(); assert sum(map(int, counts)) == mine
    review = gl.evaluate("async()=>{const r=await fetch('/api/v1/workflow/submissions');return (await r.json()).data.to_review.map(x=>x.task_title)}")
    shown = gl.locator('.pk-card h3').all_inner_texts(); assert not set(review) & set(shown)
    # priority high → medium → low, then earlier due first, inside every column
    for col in gl.locator('.pk-column').all():
        pr = col.locator('.pk-card').evaluate_all("cs=>cs.map(c=>({high:0,medium:1,low:2})[c.dataset.priority])")
        assert pr == sorted(pr)
    gl.get_by_role('button', name='Quá hạn').click(); assert all('Quá hạn' in t for t in gl.locator('.pk-card .pk-tags').all_inner_texts())
    gl.get_by_role('button', name='Quá hạn').click(); gl.locator('#kanban-q').fill('zzzz-khong-co')
    expect(gl.locator('.pk-empty')).to_have_count(4); assert gl.locator('.pk-count').all_inner_texts() == ['0', '0', '0', '0']
    gl.goto(url + '/kanban?filter=repair'); gl.locator('.pk-board').wait_for()
    expect(gl.locator('[data-filter=repair]')).to_have_attribute('aria-pressed', 'true')
    gl.locator('#kanban-q').fill(''); gl.goto(url + '/kanban'); gl.locator('.pk-card').first.click(); gl.wait_for_url('**/tasks/*')
    gl.goto(url + '/submissions'); gl.get_by_role('tab', name='Cần sửa').click()
    rows = gl.locator('#sub-list tr.sub-row'); assert all('Cần sửa' in t for t in rows.all_inner_texts())
    assert gl.locator('.page-head').count() == 0
    gl.set_viewport_size({'width': 390, 'height': 844}); gl.goto(url + '/kanban'); gl.locator('.pk-board').wait_for()
    assert not gl.evaluate('document.documentElement.scrollWidth>innerWidth')
    assert not errors, errors


def test_browser_timeline_read_only_and_editable(browser):
    ma, url = login(browser, MA); errors = []; ma.on('pageerror', lambda e: errors.append(str(e)))
    ma.goto(url + '/timeline'); ma.locator('#tl-grid').wait_for()
    expect(ma.locator('.tl-item.cat-task').first).to_be_visible()
    assert ma.locator('#tl-grid [draggable=true]').count() == 0  # Lịch của tôi: chỉ xem
    ma.locator('.tl-item[data-action^="tl-view"]').first.click(); expect(ma.get_by_role('dialog')).to_contain_text('Người tạo')
    ma.keyboard.press('Escape')
    ma.get_by_role('link', name='Lịch tôi tạo').click(); ma.wait_for_url('**view=created'); ma.locator('#tl-grid').wait_for()
    ma.get_by_role('button', name='Thêm lịch').click(); d = ma.get_by_role('dialog')
    d.get_by_label('Tiêu đề').fill('Họp kiểm thử timeline'); d.locator('select[name=category]').select_option('meeting')
    d.get_by_role('button', name='Thêm').click(); item = ma.locator('.tl-item', has_text='Họp kiểm thử timeline')
    expect(item).to_be_visible()
    assert 'cat-meeting' in item.get_attribute('class')
    col0 = item.evaluate("e=>getComputedStyle(e).gridColumnStart")
    # drag two columns to the right (real HTML5 drag & drop)
    box = item.bounding_box(); grid = ma.locator('#tl-grid').bounding_box(); width = grid['width'] / ma.evaluate("getComputedStyle(document.getElementById('tl-grid')).getPropertyValue('--days')|0")
    item.drag_to(ma.locator('#tl-grid'), source_position={'x': 10, 'y': 10}, target_position={'x': box['x'] - grid['x'] + 10 + 2 * width, 'y': box['y'] - grid['y'] + 10})
    at_col = "c=>{const e=[...document.querySelectorAll('.tl-item')].find(x=>x.textContent.includes('Họp kiểm thử timeline'));return e&&+getComputedStyle(e).gridColumnStart===c}"
    ma.wait_for_function(at_col, arg=int(col0) + 2)
    item = ma.locator('.tl-item', has_text='Họp kiểm thử timeline')
    item.focus(); ma.keyboard.press('Alt+ArrowLeft'); item = ma.locator('.tl-item', has_text='Họp kiểm thử timeline'); expect(item).to_be_visible()
    ma.wait_for_function(at_col, arg=int(col0) + 1)
    ma.locator('.tl-item', has_text='Họp kiểm thử timeline').click(); d = ma.get_by_role('dialog')
    d.get_by_label('Tiêu đề').fill('Họp kiểm thử timeline (đã sửa)'); d.locator('select[name=category]').select_option('deadline'); d.get_by_role('button', name='Lưu').click()
    item = ma.locator('.tl-item', has_text='(đã sửa)'); expect(item).to_be_visible(); assert 'cat-deadline' in item.get_attribute('class')
    ma.get_by_role('button', name='Sau ›').click(); ma.wait_for_url('**from=**'); ma.go_back(); ma.locator('#tl-grid').wait_for()
    expect(ma.locator('.tl-item', has_text='(đã sửa)')).to_be_visible()
    ma.locator('.tl-item', has_text='(đã sửa)').click(); ma.once('dialog', lambda dlg: dlg.accept())
    ma.get_by_role('dialog').get_by_role('button', name='Xóa mục lịch').click(); expect(ma.locator('.tl-item', has_text='(đã sửa)')).to_have_count(0)
    ma.set_viewport_size({'width': 390, 'height': 844}); ma.reload(); ma.locator('#tl-grid').wait_for()
    assert not ma.evaluate('document.documentElement.scrollWidth>innerWidth')
    assert not errors, errors


def test_browser_member_poster_cards(browser, app):
    from test_workflow import Client
    pid = demo(app)['pid']
    leaver = Client(app, GL); x = leaver.req(f'/workflow/projects/{pid}/departures', {'reason': 'Chuyển lớp'}, code=201)
    Client(app, MA).req(f'/workflow/departures/{x["id"]}/vote', {'version': x['version'], 'agree': True})
    page, url = login(browser, TH); errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(f'{url}/projects/{pid}?tab=members'); page.locator('.member-grid').wait_for()
    cards = page.locator('.member-card'); expect(cards).to_have_count(3)
    expect(cards.first.locator('.role-pill')).to_have_text('Trưởng nhóm')
    expect(page.locator('.members-left')).to_contain_text(name_of(app, GL))
    assert name_of(app, GL) not in page.locator('.member-grid').inner_text()
    expect(cards.first.locator('.ms-row')).to_contain_text('Chưa có điểm')
    assert cards.first.locator('.member-name').evaluate('e=>getComputedStyle(e).fontFamily').startswith('Electrolize')
    srcs = page.locator('.member-photo img').evaluate_all('xs=>xs.map(x=>x.getAttribute("src"))')
    assert all(s.startswith('/static/img/avatars/') for s in srcs)
    page.reload(); page.locator('.member-grid').wait_for()
    assert page.locator('.member-photo img').evaluate_all('xs=>xs.map(x=>x.getAttribute("src"))') == srcs  # stable per user id
    def broken(route):
        r = route.fetch(); body = r.json(); body['data']['members'][0]['user']['avatar_url'] = '/static/img/khong-ton-tai.png'; route.fulfill(response=r, json=body)
    page.route(f'**/api/v1/projects/{pid}', broken); page.reload(); page.locator('.member-grid').wait_for(); page.unroute(f'**/api/v1/projects/{pid}')
    page.wait_for_function("()=>[...document.querySelectorAll('.member-photo img')].every(i=>i.getAttribute('src').startsWith('/static/img/avatars/') && i.naturalWidth>0)")
    expect(page.get_by_role('button', name='Xin rời nhóm')).to_be_visible()
    head = page.locator('.project-head.ph-row')
    assert head.evaluate("e=>{const t=[...e.children].map(c=>Math.round(c.getBoundingClientRect().top+c.getBoundingClientRect().height/2));return Math.max(...t)-Math.min(...t)}") < 20  # one row
    page.set_viewport_size({'width': 390, 'height': 844}); page.reload(); page.locator('.member-grid').wait_for()
    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
    assert not errors, errors


def test_browser_ai_schedule_apply_undo_redo_next_month(browser):
    """AI sắp lịch: Xác nhận là thêm ngay vào khoảng đang xem; Hoàn tác xóa; → thêm lại."""
    th, url = login(browser, TH); errors = []; th.on('pageerror', lambda e: errors.append(str(e)))
    th.goto(url + '/timeline?view=created'); th.locator('#tl-grid').wait_for()
    for _ in range(2):
        th.get_by_role('button', name='Sau ›').click(); th.wait_for_url('**from=**'); th.locator('#tl-grid').wait_for()
    th.wait_for_load_state('networkidle')
    before = th.locator('#tl-grid .tl-item').count()
    th.get_by_role('button', name='AI sắp lịch').click(); d = th.get_by_role('dialog')
    expect(d).not_to_contain_text('GEMINI_API_KEY')
    expect(th.locator('[data-action=ai-undo]')).to_be_disabled(); expect(th.locator('[data-action=ai-redo]')).to_be_disabled()
    d.get_by_role('button', name='Xác nhận').click(); expect(th.get_by_role('dialog')).to_have_count(0)  # runs in the background
    expect(th.locator('#toasts .toast.ok')).to_contain_text('Đã thêm', timeout=15000)
    th.wait_for_function("n=>document.querySelectorAll('#tl-grid .tl-item').length>n", arg=before)
    added = th.locator('#tl-grid .tl-item').count()
    expect(th.locator('[data-action=ai-undo]').first).to_be_enabled(); expect(th.locator('.ai-history [data-action=ai-redo]')).to_be_disabled()
    th.locator('.ai-history').get_by_role('button', name='↶ Hoàn tác').click(); expect(th.locator('#notice')).to_contain_text('Đã hoàn tác')
    expect(th.locator('#tl-grid .tl-item')).to_have_count(before)
    expect(th.locator('.ai-history [data-action=ai-undo]')).to_be_disabled(); expect(th.locator('.ai-history [data-action=ai-redo]')).to_be_enabled()
    th.locator('.ai-history [data-action=ai-redo]').click(); expect(th.locator('#notice')).to_contain_text('Đã thêm lại')
    expect(th.locator('#tl-grid .tl-item')).to_have_count(added)
    expect(th.locator('.ai-history [data-action=ai-redo]')).to_be_disabled(); expect(th.locator('.ai-history [data-action=ai-undo]')).to_be_enabled()
    th.goto(url + '/projects/' + str(th.evaluate("async()=>(await (await fetch('/api/v1/workflow/home')).json()).data.projects[0].id")) + '?tab=peer')
    expect(th.get_by_role('heading', name='Đánh giá chéo theo công việc')).to_have_count(0)
    assert not errors, errors
