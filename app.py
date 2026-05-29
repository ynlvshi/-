"""
云律师团队 - Flask 后端
律师个人展示 + 文章博客 + 留言功能 + FAQ + 团队
"""
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
import os
import markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor


class LazyImageTreeprocessor(Treeprocessor):
    """给 Markdown 图片自动添加 loading=lazy"""
    def run(self, root):
        for img in root.iter('img'):
            img.set('loading', 'lazy')


class LazyImageExtension(Extension):
    def extendMarkdown(self, md):
        md.treeprocessors.register(LazyImageTreeprocessor(md), 'lazy_img', 15)


def render_markdown(content):
    return markdown.markdown(content, extensions=['extra', 'codehilite', LazyImageExtension()])

import uuid
import time
from collections import defaultdict
from werkzeug.utils import secure_filename

app = Flask(__name__)

# 持久化 secret_key
_secret_key = os.environ.get('FLASK_SECRET_KEY')
if not _secret_key:
    _key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.secret_key')
    try:
        with open(_key_file, 'r') as f:
            _secret_key = f.read().strip()
    except FileNotFoundError:
        _secret_key = os.urandom(24).hex()
        with open(_key_file, 'w') as f:
            f.write(_secret_key)
app.secret_key = _secret_key

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'legal.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============ 数据库模型 ============

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), default='')
    content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.String(300), default='')
    is_published = db.Column(db.Boolean, default=False)
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, include_content=False):
        d = {
            'id': self.id, 'title': self.title, 'category': self.category,
            'summary': self.summary, 'is_published': self.is_published,
            'view_count': self.view_count,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M')
        }
        if include_content:
            d['content'] = self.content
            d['content_html'] = render_markdown(self.content)
        return d


class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    issuer = db.Column(db.String(100), default='')
    date = db.Column(db.String(50), default='')
    category = db.Column(db.String(20), default='honor')
    description = db.Column(db.Text, default='')
    image_path = db.Column(db.String(300), default='')
    sort_order = db.Column(db.Integer, default=0)
    is_visible = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), default='')
    email = db.Column(db.String(100), default='')
    prefer_time = db.Column(db.String(50), default='')
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    reply = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'phone': self.phone,
            'email': self.email, 'prefer_time': self.prefer_time,
            'content': self.content, 'is_read': self.is_read,
            'reply': self.reply, 'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }


class SiteSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, default='')

    @staticmethod
    def get(key, default=''):
        s = SiteSetting.query.filter_by(key=key).first()
        return s.value if s else default


class Case(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    case_type = db.Column(db.String(50), default='')
    case_status = db.Column(db.String(50), default='')
    description = db.Column(db.Text, default='')
    process = db.Column(db.Text, default='')             # 办案过程
    legal_analysis = db.Column(db.Text, default='')      # 法律要点分析
    result = db.Column(db.Text, default='')
    client_testimonial = db.Column(db.Text, default='')  # 客户评价（脱敏）
    is_published = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'title': self.title, 'case_type': self.case_type,
            'case_status': self.case_status, 'description': self.description,
            'process': self.process, 'legal_analysis': self.legal_analysis,
            'result': self.result, 'client_testimonial': self.client_testimonial,
            'is_published': self.is_published, 'sort_order': self.sort_order,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else ''
        }


class Lawyer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(100), default='')
    specialty = db.Column(db.String(200), default='')
    intro = db.Column(db.Text, default='')
    phone = db.Column(db.String(20), default='')
    email = db.Column(db.String(100), default='')
    avatar = db.Column(db.String(300), default='')
    sort_order = db.Column(db.Integer, default=0)
    is_visible = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'title': self.title,
            'specialty': self.specialty, 'intro': self.intro,
            'phone': self.phone, 'email': self.email, 'avatar': self.avatar,
            'sort_order': self.sort_order, 'is_visible': self.is_visible
        }


class FAQ(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='通用')
    sort_order = db.Column(db.Integer, default=0)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============ 前台路由 ============

@app.route('/')
def index():
    articles = Article.query.filter_by(is_published=True).order_by(Article.created_at.desc()).limit(6).all()
    site_name = SiteSetting.get('site_name', '云律师团队')
    lawyer_intro = SiteSetting.get('lawyer_intro', '')
    lawyer_title = SiteSetting.get('lawyer_title', '执业律师')
    hero_years = SiteSetting.get('hero_years', '15+')
    hero_cases = SiteSetting.get('hero_cases', '500+')
    hero_satisfaction = SiteSetting.get('hero_satisfaction', '98%')
    qualifications = Certificate.query.filter_by(is_visible=True, category='qualification').order_by(Certificate.sort_order).all()
    honors = Certificate.query.filter_by(is_visible=True, category='honor').order_by(Certificate.sort_order).all()
    faq_preview = FAQ.query.filter_by(is_published=True).order_by(FAQ.sort_order).limit(4).all()
    return render_template('index.html',
                         articles=articles, site_name=site_name,
                         lawyer_intro=lawyer_intro, lawyer_title=lawyer_title,
                         hero_years=hero_years, hero_cases=hero_cases,
                         hero_satisfaction=hero_satisfaction,
                         qualifications=qualifications, honors=honors,
                         faq_preview=faq_preview)


@app.route('/about')
def about():
    site_name = SiteSetting.get('site_name', '云律师团队')
    lawyer_title = SiteSetting.get('lawyer_title', '执业律师')
    lawyer_full_intro = SiteSetting.get('lawyer_full_intro', '')
    lawyer_full_intro_html = render_markdown(lawyer_full_intro) if lawyer_full_intro else ''
    qualifications = Certificate.query.filter_by(is_visible=True, category='qualification').order_by(Certificate.sort_order).all()
    honors = Certificate.query.filter_by(is_visible=True, category='honor').order_by(Certificate.sort_order).all()
    return render_template('about.html', site_name=site_name, lawyer_title=lawyer_title,
                         lawyer_full_intro_html=lawyer_full_intro_html,
                         qualifications=qualifications, honors=honors)


@app.route('/articles')
def articles():
    category = request.args.get('category', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    query = Article.query.filter_by(is_published=True)
    if category:
        query = query.filter_by(category=category)
    pagination = query.order_by(Article.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    categories = [c[0] for c in db.session.query(Article.category).filter_by(is_published=True).distinct().all() if c[0]]
    return render_template('articles.html', articles=pagination.items,
                         pagination=pagination, categories=categories, current_category=category)


@app.route('/articles/<int:article_id>')
def article_detail(article_id):
    article = Article.query.get_or_404(article_id)
    article.view_count += 1
    db.session.commit()

    from html import unescape
    import re as _re
    plain = _re.sub(r'<[^>]+>', '', article.to_dict(include_content=True).get('content_html', ''))
    plain = unescape(plain).strip()
    meta_desc = plain[:150] + ('...' if len(plain) > 150 else '')

    # 相关文章（同分类，排除当前）
    related_articles = Article.query.filter_by(
        is_published=True, category=article.category
    ).filter(Article.id != article_id).order_by(
        Article.created_at.desc()
    ).limit(3).all()

    return render_template('article_detail.html',
                         article=article.to_dict(include_content=True),
                         meta_desc=meta_desc, related_articles=related_articles)


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        client_ip = request.remote_addr
        allowed, wait = check_rate_limit(f'contact:{client_ip}', max_attempts=3, window_seconds=3600)
        if not allowed:
            minutes = wait // 60
            flash(f'提交过于频繁，请 {minutes} 分钟后再试', 'error')
            return redirect(url_for('contact'))

        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        content = request.form.get('content', '').strip()

        if not name or not content:
            flash('请填写姓名和留言内容', 'error')
            return redirect(url_for('contact'))

        prefer_time = request.form.get('prefer_time', '').strip()
        msg = Message(name=name, phone=phone, email=email, content=content, prefer_time=prefer_time)
        db.session.add(msg)
        db.session.commit()

        pushplus_token = SiteSetting.get('pushplus_token', '')
        if pushplus_token:
            try:
                import requests
                push_content = f"""<b>新咨询预约</b>

<b>姓名：</b>{name}
<b>电话：</b>{phone or '未填写'}
<b>邮箱：</b>{email or '未填写'}
<b>时段：</b>{prefer_time or '未选择'}
<b>内容：</b>{content}

<a href="https://ynlawyers.com/admin/messages">点击查看详情</a>"""
                requests.post('http://www.pushplus.plus/send', json={
                    'token': pushplus_token,
                    'title': f'新咨询: {name} - {phone or "未留电话"}',
                    'content': push_content,
                    'template': 'html'
                }, timeout=5)
            except Exception:
                pass

        flash('预约已提交，我们会尽快与您联系确认！', 'success')
        return redirect(url_for('contact'))

    phone = SiteSetting.get('contact_phone', '')
    address = SiteSetting.get('contact_address', '')
    email_addr = SiteSetting.get('contact_email', '')
    return render_template('contact.html', phone=phone, address=address, email_addr=email_addr)


@app.route('/cases')
def cases_list():
    case_type = request.args.get('type', '')
    query = Case.query.filter_by(is_published=True)
    if case_type:
        query = query.filter_by(case_type=case_type)
    cases = query.order_by(Case.sort_order).all()
    types = [c[0] for c in db.session.query(Case.case_type).filter_by(is_published=True).distinct().all() if c[0]]
    return render_template('cases.html', cases=cases, case_types=types, current_type=case_type)


@app.route('/cases/<int:case_id>')
def case_detail(case_id):
    case = Case.query.get_or_404(case_id)
    # 相关案例（同类型）
    related_cases = Case.query.filter_by(
        is_published=True, case_type=case.case_type
    ).filter(Case.id != case_id).order_by(Case.sort_order).limit(3).all()
    return render_template('case_detail.html', case=case.to_dict(), related_cases=related_cases)


@app.route('/team')
def team():
    lawyers = Lawyer.query.filter_by(is_visible=True).order_by(Lawyer.sort_order).all()
    return render_template('team.html', lawyers=lawyers)


@app.route('/team/<int:lawyer_id>')
def lawyer_detail(lawyer_id):
    lawyer = Lawyer.query.get_or_404(lawyer_id)
    return render_template('lawyer_detail.html', lawyer=lawyer.to_dict())


@app.route('/services')
def services():
    return render_template('services.html')


@app.route('/govt')
def govt_services():
    govt_cases = Case.query.filter_by(is_published=True, case_type='政企服务').order_by(Case.sort_order).all()
    return render_template('govt.html', govt_cases=govt_cases)


@app.route('/faq')
def faq():
    faq_data = FAQ.query.filter_by(is_published=True).order_by(FAQ.sort_order).all()
    faq_categories = [c[0] for c in db.session.query(FAQ.category).filter_by(is_published=True).distinct().all() if c[0]]
    return render_template('faq.html', faq_data=faq_data, faq_categories=faq_categories)


@app.route('/robots.txt')
def robots_txt():
    return send_from_directory(os.path.join(basedir, 'static'), 'robots.txt')


@app.route('/sitemap.xml')
def sitemap():
    pages = [
        {'loc': '/', 'priority': '1.0', 'changefreq': 'weekly'},
        {'loc': '/about', 'priority': '0.8', 'changefreq': 'monthly'},
        {'loc': '/team', 'priority': '0.8', 'changefreq': 'monthly'},
        {'loc': '/services', 'priority': '0.8', 'changefreq': 'monthly'},
        {'loc': '/cases', 'priority': '0.7', 'changefreq': 'weekly'},
        {'loc': '/govt', 'priority': '0.7', 'changefreq': 'monthly'},
        {'loc': '/articles', 'priority': '0.7', 'changefreq': 'weekly'},
        {'loc': '/contact', 'priority': '0.6', 'changefreq': 'monthly'},
        {'loc': '/faq', 'priority': '0.6', 'changefreq': 'weekly'},
    ]
    base_url = request.url_root.rstrip('/')
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for page in pages:
        xml += f'  <url><loc>{base_url}{page["loc"]}</loc><priority>{page["priority"]}</priority><changefreq>{page["changefreq"]}</changefreq></url>\n'
    for article in Article.query.filter_by(is_published=True).all():
        lastmod = article.updated_at or article.created_at
        if lastmod:
            xml += f'  <url><loc>{base_url}/articles/{article.id}</loc><priority>0.6</priority><changefreq>monthly</changefreq><lastmod>{lastmod.strftime("%Y-%m-%d")}</lastmod></url>\n'
    for case in Case.query.filter_by(is_published=True).all():
        lastmod = case.created_at
        if lastmod:
            xml += f'  <url><loc>{base_url}/cases/{case.id}</loc><priority>0.5</priority><changefreq>monthly</changefreq><lastmod>{lastmod.strftime("%Y-%m-%d")}</lastmod></url>\n'
    xml += '</urlset>'
    return app.response_class(xml, mimetype='application/xml')


# ============ 后台路由 ============

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        admin_user = SiteSetting.get('admin_username', 'admin')
        admin_pass = SiteSetting.get('admin_password', 'admin123')
        if username == admin_user and password == admin_pass:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('用户名或密码错误', 'error')
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/admin')
@admin_required
def admin_dashboard():
    article_count = Article.query.count()
    message_count = Message.query.count()
    unread_messages = Message.query.filter_by(is_read=False).count()
    case_count = Case.query.count()
    faq_count = FAQ.query.count()
    return render_template('admin_dashboard.html',
                         article_count=article_count, message_count=message_count,
                         unread_messages=unread_messages, case_count=case_count,
                         faq_count=faq_count)


# ---- 文章管理 ----

@app.route('/admin/articles')
@admin_required
def admin_articles():
    articles = Article.query.order_by(Article.created_at.desc()).all()
    return render_template('admin_articles.html', articles=articles)


@app.route('/admin/articles/add', methods=['GET', 'POST'])
@admin_required
def admin_article_add():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        category = request.form.get('category', '').strip()
        summary = request.form.get('summary', '').strip()
        is_published = request.form.get('is_published') == 'on'
        if not title or not content:
            flash('标题和内容不能为空', 'error')
            return redirect(url_for('admin_article_add'))
        article = Article(title=title, content=content, category=category,
                         summary=summary, is_published=is_published)
        db.session.add(article)
        db.session.commit()
        flash('文章已保存', 'success')
        return redirect(url_for('admin_articles'))
    return render_template('admin_article_form.html', article=None)


@app.route('/admin/articles/edit/<int:article_id>', methods=['GET', 'POST'])
@admin_required
def admin_article_edit(article_id):
    article = Article.query.get_or_404(article_id)
    if request.method == 'POST':
        article.title = request.form.get('title', '').strip()
        article.content = request.form.get('content', '').strip()
        article.category = request.form.get('category', '').strip()
        article.summary = request.form.get('summary', '').strip()
        article.is_published = request.form.get('is_published') == 'on'
        article.updated_at = datetime.utcnow()
        db.session.commit()
        flash('文章已更新', 'success')
        return redirect(url_for('admin_articles'))
    return render_template('admin_article_form.html', article=article)


@app.route('/admin/articles/delete/<int:article_id>')
@admin_required
def admin_article_delete(article_id):
    article = Article.query.get_or_404(article_id)
    db.session.delete(article)
    db.session.commit()
    flash('文章已删除', 'success')
    return redirect(url_for('admin_articles'))


# ---- 留言管理 ----

@app.route('/admin/messages')
@admin_required
def admin_messages():
    messages = Message.query.order_by(Message.created_at.desc()).all()
    return render_template('admin_messages.html', messages=messages)


@app.route('/admin/messages/read/<int:msg_id>')
@admin_required
def admin_message_read(msg_id):
    msg = Message.query.get_or_404(msg_id)
    msg.is_read = True
    db.session.commit()
    return redirect(url_for('admin_messages'))


@app.route('/admin/messages/reply/<int:msg_id>', methods=['POST'])
@admin_required
def admin_message_reply(msg_id):
    msg = Message.query.get_or_404(msg_id)
    msg.reply = request.form.get('reply', '').strip()
    msg.is_read = True
    db.session.commit()
    flash('回复已保存', 'success')
    return redirect(url_for('admin_messages'))


@app.route('/admin/messages/delete/<int:msg_id>')
@admin_required
def admin_message_delete(msg_id):
    msg = Message.query.get_or_404(msg_id)
    db.session.delete(msg)
    db.session.commit()
    flash('留言已删除', 'success')
    return redirect(url_for('admin_messages'))


# ---- 证书管理 ----

@app.route('/admin/certificates')
@admin_required
def admin_certificates():
    certs = Certificate.query.order_by(Certificate.sort_order).all()
    return render_template('admin_certificates.html', certificates=certs)


@app.route('/admin/certificates/upload', methods=['POST'])
@admin_required
def admin_certificate_upload():
    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({'success': False, 'error': '未选择文件'})
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': '不支持的图片格式，仅支持 png/jpg/jpeg/gif/webp'})
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f'cert_{uuid.uuid4().hex[:12]}.{ext}'
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    return jsonify({'success': True, 'path': f'uploads/{filename}'})


@app.route('/admin/certificates/add', methods=['GET', 'POST'])
@admin_required
def admin_certificate_add():
    if request.method == 'POST':
        cert = Certificate(
            title=request.form.get('title', '').strip(),
            issuer=request.form.get('issuer', '').strip(),
            date=request.form.get('date', '').strip(),
            description=request.form.get('description', '').strip(),
            image_path=request.form.get('image_path', '').strip(),
            category=request.form.get('category', 'honor'),
            sort_order=int(request.form.get('sort_order', 0)),
            is_visible=request.form.get('is_visible') == 'on'
        )
        db.session.add(cert)
        db.session.commit()
        flash('荣誉信息已添加', 'success')
        return redirect(url_for('admin_certificates'))
    return render_template('admin_certificate_form.html', cert=None)


@app.route('/admin/certificates/edit/<int:cert_id>', methods=['GET', 'POST'])
@admin_required
def admin_certificate_edit(cert_id):
    cert = Certificate.query.get_or_404(cert_id)
    if request.method == 'POST':
        cert.title = request.form.get('title', '').strip()
        cert.issuer = request.form.get('issuer', '').strip()
        cert.date = request.form.get('date', '').strip()
        cert.description = request.form.get('description', '').strip()
        cert.category = request.form.get('category', 'honor')
        new_image = request.form.get('image_path', '').strip()
        if new_image:
            cert.image_path = new_image
        cert.sort_order = int(request.form.get('sort_order', 0))
        cert.is_visible = request.form.get('is_visible') == 'on'
        db.session.commit()
        flash('荣誉信息已更新', 'success')
        return redirect(url_for('admin_certificates'))
    return render_template('admin_certificate_form.html', cert=cert)


@app.route('/admin/certificates/delete/<int:cert_id>')
@admin_required
def admin_certificate_delete(cert_id):
    cert = Certificate.query.get_or_404(cert_id)
    db.session.delete(cert)
    db.session.commit()
    flash('荣誉信息已删除', 'success')
    return redirect(url_for('admin_certificates'))


# ---- 案例管理 ----

@app.route('/admin/cases')
@admin_required
def admin_cases():
    cases = Case.query.order_by(Case.sort_order).all()
    return render_template('admin_cases.html', cases=cases)


@app.route('/admin/cases/add', methods=['GET', 'POST'])
@admin_required
def admin_case_add():
    if request.method == 'POST':
        case = Case(
            title=request.form.get('title', '').strip(),
            case_type=request.form.get('case_type', '').strip(),
            case_status=request.form.get('case_status', '').strip(),
            description=request.form.get('description', '').strip(),
            process=request.form.get('process', '').strip(),
            legal_analysis=request.form.get('legal_analysis', '').strip(),
            result=request.form.get('result', '').strip(),
            client_testimonial=request.form.get('client_testimonial', '').strip(),
            is_published=request.form.get('is_published') == 'on',
            sort_order=int(request.form.get('sort_order', 0))
        )
        db.session.add(case)
        db.session.commit()
        flash('案例已添加', 'success')
        return redirect(url_for('admin_cases'))
    return render_template('admin_case_form.html', case=None)


@app.route('/admin/cases/edit/<int:case_id>', methods=['GET', 'POST'])
@admin_required
def admin_case_edit(case_id):
    case = Case.query.get_or_404(case_id)
    if request.method == 'POST':
        case.title = request.form.get('title', '').strip()
        case.case_type = request.form.get('case_type', '').strip()
        case.case_status = request.form.get('case_status', '').strip()
        case.description = request.form.get('description', '').strip()
        case.process = request.form.get('process', '').strip()
        case.legal_analysis = request.form.get('legal_analysis', '').strip()
        case.result = request.form.get('result', '').strip()
        case.client_testimonial = request.form.get('client_testimonial', '').strip()
        case.is_published = request.form.get('is_published') == 'on'
        case.sort_order = int(request.form.get('sort_order', 0))
        db.session.commit()
        flash('案例已更新', 'success')
        return redirect(url_for('admin_cases'))
    return render_template('admin_case_form.html', case=case)


@app.route('/admin/cases/delete/<int:case_id>')
@admin_required
def admin_case_delete(case_id):
    case = Case.query.get_or_404(case_id)
    db.session.delete(case)
    db.session.commit()
    flash('案例已删除', 'success')
    return redirect(url_for('admin_cases'))


# ---- FAQ 管理 ----

@app.route('/admin/faq')
@admin_required
def admin_faq():
    faqs = FAQ.query.order_by(FAQ.sort_order).all()
    return render_template('admin_faq.html', faqs=faqs)


@app.route('/admin/faq/add', methods=['GET', 'POST'])
@admin_required
def admin_faq_add():
    if request.method == 'POST':
        faq = FAQ(
            question=request.form.get('question', '').strip(),
            answer=request.form.get('answer', '').strip(),
            category=request.form.get('category', '通用'),
            sort_order=int(request.form.get('sort_order', 0)),
            is_published=request.form.get('is_published') == 'on'
        )
        if not faq.question or not faq.answer:
            flash('问题和回答不能为空', 'error')
            return redirect(url_for('admin_faq_add'))
        db.session.add(faq)
        db.session.commit()
        flash('FAQ 已添加', 'success')
        return redirect(url_for('admin_faq'))
    return render_template('admin_faq_form.html', faq=None)


@app.route('/admin/faq/edit/<int:faq_id>', methods=['GET', 'POST'])
@admin_required
def admin_faq_edit(faq_id):
    faq = FAQ.query.get_or_404(faq_id)
    if request.method == 'POST':
        faq.question = request.form.get('question', '').strip()
        faq.answer = request.form.get('answer', '').strip()
        faq.category = request.form.get('category', '通用')
        faq.sort_order = int(request.form.get('sort_order', 0))
        faq.is_published = request.form.get('is_published') == 'on'
        db.session.commit()
        flash('FAQ 已更新', 'success')
        return redirect(url_for('admin_faq'))
    return render_template('admin_faq_form.html', faq=faq)


@app.route('/admin/faq/delete/<int:faq_id>')
@admin_required
def admin_faq_delete(faq_id):
    faq = FAQ.query.get_or_404(faq_id)
    db.session.delete(faq)
    db.session.commit()
    flash('FAQ 已删除', 'success')
    return redirect(url_for('admin_faq'))


# ---- 团队管理 ----

@app.route('/admin/lawyers')
@admin_required
def admin_lawyers():
    lawyers = Lawyer.query.order_by(Lawyer.sort_order).all()
    return render_template('admin_lawyers.html', lawyers=lawyers)


@app.route('/admin/lawyers/add', methods=['GET', 'POST'])
@admin_required
def admin_lawyer_add():
    if request.method == 'POST':
        lawyer = Lawyer(
            name=request.form.get('name', '').strip(),
            title=request.form.get('title', '').strip(),
            specialty=request.form.get('specialty', '').strip(),
            intro=request.form.get('intro', '').strip(),
            phone=request.form.get('phone', '').strip(),
            email=request.form.get('email', '').strip(),
            avatar=request.form.get('avatar', '').strip(),
            sort_order=int(request.form.get('sort_order', 0)),
            is_visible=request.form.get('is_visible') == 'on'
        )
        if not lawyer.name:
            flash('姓名不能为空', 'error')
            return redirect(url_for('admin_lawyer_add'))
        db.session.add(lawyer)
        db.session.commit()
        flash('律师信息已添加', 'success')
        return redirect(url_for('admin_lawyers'))
    return render_template('admin_lawyer_form.html', lawyer=None)


@app.route('/admin/lawyers/edit/<int:lawyer_id>', methods=['GET', 'POST'])
@admin_required
def admin_lawyer_edit(lawyer_id):
    lawyer = Lawyer.query.get_or_404(lawyer_id)
    if request.method == 'POST':
        lawyer.name = request.form.get('name', '').strip()
        lawyer.title = request.form.get('title', '').strip()
        lawyer.specialty = request.form.get('specialty', '').strip()
        lawyer.intro = request.form.get('intro', '').strip()
        lawyer.phone = request.form.get('phone', '').strip()
        lawyer.email = request.form.get('email', '').strip()
        new_avatar = request.form.get('avatar', '').strip()
        if new_avatar:
            lawyer.avatar = new_avatar
        lawyer.sort_order = int(request.form.get('sort_order', 0))
        lawyer.is_visible = request.form.get('is_visible') == 'on'
        db.session.commit()
        flash('律师信息已更新', 'success')
        return redirect(url_for('admin_lawyers'))
    return render_template('admin_lawyer_form.html', lawyer=lawyer)


@app.route('/admin/lawyers/delete/<int:lawyer_id>')
@admin_required
def admin_lawyer_delete(lawyer_id):
    lawyer = Lawyer.query.get_or_404(lawyer_id)
    db.session.delete(lawyer)
    db.session.commit()
    flash('律师信息已删除', 'success')
    return redirect(url_for('admin_lawyers'))


# ---- 头像上传 ----

@app.route('/admin/upload_avatar', methods=['POST'])
@admin_required
def admin_upload_avatar():
    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({'success': False, 'error': '未选择文件'})
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': '不支持的格式，仅支持 png/jpg/jpeg/gif/webp'})
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f'avatar_{uuid.uuid4().hex[:8]}.{ext}'
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    _set_setting('lawyer_avatar', f'uploads/{filename}')
    return jsonify({'success': True, 'path': f'uploads/{filename}'})


def _set_setting(key, value):
    s = SiteSetting.query.filter_by(key=key).first()
    if s:
        s.value = value
    else:
        db.session.add(SiteSetting(key=key, value=value))
    db.session.commit()


# ---- API ----

@app.route('/api/cases/preview')
def api_cases_preview():
    cases = Case.query.filter_by(is_published=True).order_by(Case.sort_order).limit(3).all()
    return jsonify([c.to_dict() for c in cases])


@app.route('/api/chat', methods=['POST'])
def api_chat():
    import requests as req
    data = request.get_json()
    user_message = (data.get('message') or '').strip()
    if not user_message:
        return jsonify({'reply': '请输入您想咨询的法律问题。'})

    api_key = SiteSetting.get('deepseek_api_key', '')
    phone = SiteSetting.get('contact_phone', '182-0881-7847')

    if api_key:
        system_prompt = SiteSetting.get('chat_system_prompt',
            '你是"{name}"律师工作室的 AI 法律助手，{title}。'
            '你的任务是：1) 为潜在客户提供初步法律咨询引导；'
            '2) 解答常见法律问题；3) 引导用户留下联系方式以便律师回访。'
            '请用专业、友善的中文回答。重要提示：你提供的是法律信息参考，不构成正式法律意见。'
            .format(name=SiteSetting.get('lawyer_name', '邹卫华'), title=SiteSetting.get('lawyer_title', '执业律师')))

        try:
            resp = req.post(
                'https://api.deepseek.com/v1/chat/completions',
                headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                json={
                    'model': 'deepseek-chat',
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_message}
                    ],
                    'max_tokens': 800,
                    'temperature': 0.7
                },
                timeout=30
            )
            if resp.status_code == 200:
                reply = resp.json()['choices'][0]['message']['content']
            else:
                reply = f'抱歉，AI 服务暂时不可用，请直接拨打 {phone} 咨询。'
        except Exception:
            reply = f'抱歉，服务响应超时。请直接拨打电话 {phone} 咨询，我会尽快回复您。'
    else:
        reply = f'感谢您的咨询！目前在线客服暂时离线，请直接拨打 {phone}，我们会尽快为您解答。'

    # 推送所有在线咨询到微信
    pushplus_token = SiteSetting.get('pushplus_token', '')
    if pushplus_token:
        import requests as push_req
        try:
            push_content = f"""<b>💬 新在线咨询</b>

<b>访客IP：</b>{request.remote_addr}
<b>咨询问题：</b>{user_message[:200]}

<b>AI回复摘要：</b>{reply[:150]}...

━━━━━━━━━
<small>此消息来自网站 AI 法律助手</small>"""
            push_req.post('http://www.pushplus.plus/send', json={
                'token': pushplus_token,
                'title': f'在线咨询: {user_message[:30]}...',
                'content': push_content,
                'template': 'html'
            }, timeout=3)
        except Exception:
            pass

    return jsonify({'reply': reply})


# ---- 网站设置 ----

@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    if request.method == 'POST':
        settings_keys = [
            'site_name', 'site_description', 'lawyer_name', 'lawyer_title',
            'lawyer_intro', 'lawyer_full_intro',
            'hero_years', 'hero_cases', 'hero_satisfaction',
            'contact_phone', 'contact_address', 'contact_email',
            'admin_username', 'admin_password', 'icp_beian',
            'wechat_qrcode', 'deepseek_api_key', 'chat_system_prompt', 'pushplus_token',
            'baidu_tongji_id', 'google_analytics_id'
        ]
        for key in settings_keys:
            value = request.form.get(key, '').strip()
            if key == 'admin_password' and not value:
                continue
            s = SiteSetting.query.filter_by(key=key).first()
            if s:
                s.value = value
            else:
                db.session.add(SiteSetting(key=key, value=value))
        db.session.commit()
        flash('设置已保存', 'success')
        return redirect(url_for('admin_settings'))

    return render_template('admin_settings.html')


# ============ 数据库初始化 ============

def init_database():
    with app.app_context():
        db.create_all()

        # 自动迁移：为已有表添加缺失的列
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        # Case 表新增列
        if 'case' in inspector.get_table_names():
            cols = {c['name'] for c in inspector.get_columns('case')}
            for col_name, col_type in [
                ('process', 'TEXT'), ('legal_analysis', 'TEXT'), ('client_testimonial', 'TEXT')
            ]:
                if col_name not in cols:
                    try:
                        with db.engine.connect() as conn:
                            conn.execute(text(f'ALTER TABLE "case" ADD COLUMN {col_name} {col_type} DEFAULT \'\''))
                            conn.commit()
                    except Exception:
                        pass

        defaults = {
            'site_name': '云律师 团队',
            'site_description': '云南 · 专业 · 诚信 · 高效',
            'lawyer_name': '邹卫华',
            'lawyer_title': '执业律师',
            'lawyer_intro': '专业律师，致力于为客户提供优质法律服务。擅长民商事诉讼、刑事辩护、公司法务、婚姻家庭等领域的法律事务。',
            'lawyer_full_intro': '''## 个人简介

邹卫华，执业律师，具有丰富的法律实务经验。

## 执业领域

- **🏗 建设工程法律纠纷**（擅长领域）：工程款结算、工期索赔、质量鉴定、招投标争议等
- **民商事诉讼**：合同纠纷、债权债务、房产纠纷等
- **刑事辩护**：为当事人提供专业刑事法律辩护
- **公司法务**：企业法律顾问、合同审查、合规管理
- **婚姻家庭**：离婚纠纷、财产分割、子女抚养、遗产继承
- **劳动争议**：劳动合同纠纷、工伤赔偿等

## 执业理念

以专业立身，以诚信为本，竭诚为每一位当事人提供优质高效的法律服务。''',
            'contact_phone': '182-0881-7847',
            'contact_address': '云南省昆明市',
            'contact_email': 'kaolx@qq.com',
            'hero_years': '15+',
            'hero_cases': '500+',
            'hero_satisfaction': '98%',
            'admin_username': 'admin',
            'admin_password': 'admin123',
            'icp_beian': '',
            'wechat_qrcode': '',
            'deepseek_api_key': '',
            'chat_system_prompt': '',
            'pushplus_token': '',
            'baidu_tongji_id': '',
            'google_analytics_id': ''
        }
        for key, value in defaults.items():
            if not SiteSetting.query.filter_by(key=key).first():
                db.session.add(SiteSetting(key=key, value=value))

        if not Article.query.first():
            sample_articles = [
                {
                    'title': '民法典合同编重点解读',
                    'category': '法律实务',
                    'summary': '本文对民法典合同编的修订重点进行梳理，帮助读者理解合同法律规范的最新变化。',
                    'content': """# 民法典合同编重点解读

## 一、合同订立规则的变化

民法典合同编在《合同法》基础上进行了系统整合和完善：

### 1. 电子合同的订立
承认数据电文形式的合同效力，电子合同与传统书面合同具有同等法律效力。

### 2. 格式条款的规制
提供格式条款的一方未履行提示或说明义务的，相对方可以主张该条款不成为合同内容。

## 二、合同履行规则的完善

### 1. 情势变更制度
明确规定了情势变更的适用条件和法律效果，为应对不可预见的变化提供了法律依据。

### 2. 第三人利益合同
承认第三人可以请求债务人向其履行，扩大了合同的效力范围。

## 三、违约责任的新规

民法典明确了违约责任的归责原则，强化了对守约方的保护。""",
                    'is_published': True
                },
                {
                    'title': '劳动纠纷维权指南',
                    'category': '案例分析',
                    'summary': '劳动者遇到劳动争议时如何维权？本文为您梳理劳动纠纷的处理流程和法律要点。',
                    'content': """# 劳动纠纷维权指南

## 一、常见劳动纠纷类型

1. **工资报酬纠纷**：拖欠工资、未足额支付加班费等
2. **劳动合同纠纷**：违法解除合同、未签订书面合同等
3. **社会保险纠纷**：未依法缴纳社保、工伤保险待遇争议等

## 二、维权途径

### 1. 协商阶段
首先与用人单位协商解决，保留相关证据。

### 2. 劳动仲裁
协商不成的，向劳动仲裁委员会申请仲裁（免费）。

### 3. 法院诉讼
对仲裁结果不服的，可向人民法院提起诉讼。

## 三、重要提示

**注意时效**：劳动仲裁申请时效为一年，从知道权利被侵害之日起计算。
**保留证据**：劳动合同、工资单、考勤记录、聊天记录等都是重要证据。""",
                    'is_published': True
                },
                {
                    'title': '刑事案件中律师的作用与价值',
                    'category': '法律实务',
                    'summary': '在刑事案件中，律师在侦查、审查起诉、审判各阶段发挥着不可替代的重要作用。',
                    'content': """# 刑事案件中律师的作用与价值

## 一、侦查阶段

1. 为犯罪嫌疑人提供法律咨询
2. 代理申诉、控告
3. 申请变更强制措施
4. 了解涉嫌罪名和案件情况

## 二、审查起诉阶段

1. 查阅、摘抄、复制案卷材料
2. 调查取证
3. 发表辩护意见

## 三、审判阶段

1. 出庭辩护
2. 进行法庭辩论
3. 提出量刑建议""",
                    'is_published': True
                }
            ]
            for data in sample_articles:
                db.session.add(Article(**data))

        if not Certificate.query.first():
            sample_certs = [
                {'title': '律师执业资格证书', 'issuer': '云南省司法厅', 'date': '2010年', 'category': 'qualification', 'description': '中华人民共和国律师执业资格', 'sort_order': 0},
                {'title': '优秀律师称号', 'issuer': '昆明市律师协会', 'date': '2018年', 'category': 'honor', 'description': '年度优秀律师荣誉称号', 'sort_order': 0},
                {'title': '法律顾问资格认证', 'issuer': '云南省企业法律顾问协会', 'date': '2015年', 'category': 'qualification', 'description': '企业法律顾问专业资格认证', 'sort_order': 1},
                {'title': '公益法律服务先进个人', 'issuer': '云南省司法厅', 'date': '2020年', 'category': 'honor', 'description': '年度公益法律服务先进个人表彰', 'sort_order': 1},
            ]
            for data in sample_certs:
                db.session.add(Certificate(**data))

        if not Lawyer.query.first():
            sample_lawyers = [
                {'name': '邹卫华', 'title': '权益合伙人', 'specialty': '建设工程、政企法律顾问、民商事诉讼', 'intro': '执业 15 年以上，专注于建设工程法律纠纷及政企法律顾问服务，累计代理案件 500 余件。', 'sort_order': 0},
                {'name': '王律师', 'title': '执业律师', 'specialty': '婚姻家庭、遗产继承、劳动争议', 'intro': '执业多年，擅长婚姻家事及劳动争议案件，以调解见长，累计调解成功率超过 80%。', 'sort_order': 1},
                {'name': '杨云', 'title': '执业律师', 'specialty': '民商事诉讼、公司法务、合同纠纷', 'intro': '法学硕士，执业多年，专注民商事争议解决与企业法律顾问服务，以严谨细致的办案风格赢得客户信赖。', 'sort_order': 2},
            ]
            for data in sample_lawyers:
                db.session.add(Lawyer(**data))

        if not Case.query.first():
            sample_cases = [
                {
                    'title': '建设工程合同纠纷 — 成功追回工程款 280 万元',
                    'case_type': '建设工程', 'case_status': '胜诉',
                    'description': '委托人承接某商业综合体土建工程，发包方以工程质量不合格为由拒付尾款 280 万元。本律师团队介入后，通过申请工程质量司法鉴定，证明工程质量符合合同约定标准。',
                    'process': '1. 接案后第一时间申请财产保全，冻结发包方银行账户；\n2. 委托司法鉴定机构进行工程质量鉴定；\n3. 庭审中围绕鉴定结论进行充分质证和辩论；\n4. 法院采纳鉴定结论，支持我方全部诉讼请求。',
                    'legal_analysis': '建设工程合同纠纷中，质量鉴定是关键证据。根据《民法典》第788条，建设工程合同是承包人进行工程建设、发包人支付价款的合同。发包方以质量问题为由拒付工程款，需承担举证责任。本案中司法鉴定结论成为定案关键证据。',
                    'result': '法院判决发包方支付全部尾款及逾期利息，委托人合法权益得到全额保障。',
                    'client_testimonial': '邹律师团队非常专业，及时帮我们追回了工程款，让我们公司得以正常运营。',
                    'is_published': True, 'sort_order': 0
                },
                {
                    'title': '离婚财产纠纷 — 为女方争取到 70% 财产分割',
                    'case_type': '婚姻家庭', 'case_status': '调解成功',
                    'description': '委托人（女方）婚后发现男方存在隐匿、转移共同财产行为，涉及房产 3 套、公司股权及存款共计约 500 万元。',
                    'process': '1. 申请调查令，调取男方银行流水和财产记录；\n2. 梳理对方隐匿、转移财产的证据链；\n3. 多轮谈判协商，施加法律压力；\n4. 最终达成调解协议。',
                    'legal_analysis': '根据《民法典》第1092条，夫妻一方隐藏、转移、变卖、毁损、挥霍夫妻共同财产，或伪造夫妻共同债务企图侵占另一方财产的，分割夫妻共同财产时可以少分或不分。律师调查取证能力在此类案件中是核心要素。',
                    'result': '经律师调查取证及多轮谈判，双方达成调解协议，女方获得约 350 万元财产分割，远高于法定均分标准。',
                    'is_published': True, 'sort_order': 1
                },
                {
                    'title': '刑事辩护 — 依法争取到不起诉决定',
                    'case_type': '刑事辩护', 'case_status': '不起诉',
                    'description': '委托人因涉嫌经济犯罪被立案侦查，面临刑事追诉风险。律师第一时间介入，全面梳理案件事实和证据材料。',
                    'process': '1. 侦查阶段即介入，会见当事人了解案情；\n2. 梳理案卷材料，发现证据链存在重大瑕疵；\n3. 撰写详尽法律意见书提交检察机关；\n4. 多次与承办检察官沟通辩护意见。',
                    'legal_analysis': '审查起诉阶段是刑事辩护的关键窗口。根据《刑事诉讼法》第175条，对于二次补充侦查的案件，检察院仍认为证据不足、不符合起诉条件的，应作出不起诉决定。本案中律师在审查起诉阶段的充分辩护最终促使检察机关采纳了辩护意见。',
                    'result': '审查起诉阶段，律师提交详尽法律意见书，检察机关采纳辩护意见，依法作出不起诉决定。',
                    'is_published': True, 'sort_order': 2
                },
                {
                    'title': '某市属国企常年法律顾问 — 合同审查与合规管理',
                    'case_type': '政企服务', 'case_status': '服务中',
                    'description': '担任云南省某市属国有企业常年法律顾问，负责企业合同审查、招标合规、劳动用工风险排查及重大经营决策法律论证。',
                    'process': '1. 建立合同审查标准化流程；\n2. 定期进行法律风险排查；\n3. 参与重大决策会议提供法律意见；\n4. 为企业管理层提供法律培训。',
                    'legal_analysis': '国有企业法律顾问需兼顾合规与效率。重点关注招投标合规、国有资产保护、劳动用工规范等领域，同时需关注监察法规的适用。',
                    'result': '三年来为企业审查合同 600 余份，处理劳动争议 12 起，成功化解多起重大法律风险，获企业高度认可。',
                    'is_published': True, 'sort_order': 3
                }
            ]
            for data in sample_cases:
                db.session.add(Case(**data))

        if not FAQ.query.first():
            sample_faqs = [
                {'question': '建设工程合同纠纷应该找什么样的律师？', 'answer': '建议找有建设工程领域专业经验的律师。建设工程纠纷涉及工程款结算、工期索赔、质量鉴定等专业问题，需要律师同时具备法律知识和工程行业常识。云律师团队深耕建设工程领域15年以上，累计为施工企业追回工程款超千万元。', 'category': '建设工程', 'sort_order': 0},
                {'question': '拖欠工程款怎么办？', 'answer': '首先收集合同、工程验收单、结算资料等证据；其次向发包方发出书面催告函；协商无果的，可向法院起诉并申请财产保全，查封对方财产。建议尽早委托专业律师介入，避免超过诉讼时效。', 'category': '建设工程', 'sort_order': 1},
                {'question': '离婚财产如何分割？', 'answer': '婚后取得的财产原则上均等分割。但需注意：一方婚前财产归个人；继承或赠与明确给一方的归个人；一方隐匿、转移财产的可以少分或不分。建议提前咨询律师了解自身合法权益。', 'category': '婚姻家庭', 'sort_order': 2},
                {'question': '被刑事拘留后家属应该怎么做？', 'answer': '第一时间委托专业刑事律师介入。律师可在侦查阶段会见当事人、了解案情、申请取保候审、提供法律咨询。侦查阶段是刑事辩护的黄金窗口期，尽早委托律师至关重要。', 'category': '刑事辩护', 'sort_order': 3},
                {'question': '工伤如何认定和索赔？', 'answer': '工伤认定需满足工作时间、工作场所、工作原因三要素。发生工伤后应立即送医并向单位报告，单位应在30日内申请工伤认定。单位不申请的，职工或近亲属可在1年内自行申请。认定后进行劳动能力鉴定，根据伤残等级获得相应赔偿。', 'category': '劳动争议', 'sort_order': 4},
                {'question': '请律师一般需要多少钱？', 'answer': '律师费因案件类型、复杂程度、标的额等因素而异。一般按以下几种方式收费：计件收费（如刑事案件按阶段）、按标的额比例收费（如经济纠纷）、计时收费。建议预约面谈后，我们会根据您的具体情况提供透明的费用方案。首次咨询免费。', 'category': '通用', 'sort_order': 5},
                {'question': '合同纠纷的诉讼时效是多久？', 'answer': '根据民法典规定，普通诉讼时效为3年，从知道或应当知道权利受到损害以及义务人之日起计算。诉讼时效可以因权利人主张权利、义务人同意履行等事由中断而重新计算。建议尽早维权，避免超过时效丧失胜诉权。', 'category': '民商诉讼', 'sort_order': 6},
                {'question': '委托律师需要准备什么材料？', 'answer': '一般需要准备：身份证件、与案件相关的合同协议、往来函件、付款凭证、聊天记录等证据材料。不同案件类型所需材料不同，预约咨询时我们会告知您具体需要准备的材料清单。', 'category': '通用', 'sort_order': 7},
            ]
            for data in sample_faqs:
                db.session.add(FAQ(**data))

        db.session.commit()
        print("[OK] 数据库初始化完成！")
        print("    管理员账号: admin / admin123")


# ============ 数据库迁移 ============

def migrate_database():
    """部署时执行：迁移旧数据到新版本，仅修改默认值，不覆盖用户自定义设置"""
    with app.app_context():
        # 1. site_name：旧默认值 → 新默认值
        s = SiteSetting.query.filter_by(key='site_name').first()
        if s and s.value in ('邹卫华律师工作室', '邹卫华律师团队'):
            s.value = '云律师 团队'

        # 2. icp_beian：如果为空则填入
        s = SiteSetting.query.filter_by(key='icp_beian').first()
        if not s or not s.value:
            if s:
                s.value = '滇ICP备2026006037号-2'
            else:
                db.session.add(SiteSetting(key='icp_beian', value='滇ICP备2026006037号-2'))

        # 3. 删除 李律师，添加 杨云
        li = Lawyer.query.filter_by(name='李律师').first()
        if li:
            db.session.delete(li)

        if not Lawyer.query.filter_by(name='杨云').first():
            db.session.add(Lawyer(
                name='杨云', title='执业律师',
                specialty='民商事诉讼、公司法务、合同纠纷',
                intro='法学硕士，执业多年，专注民商事争议解决与企业法律顾问服务，以严谨细致的办案风格赢得客户信赖。',
                sort_order=2, is_visible=True
            ))

        db.session.commit()
        print("[OK] 数据库迁移完成！")


# ============ 全局模板上下文 ============

@app.context_processor
def inject_globals():
    site_name = SiteSetting.get('site_name', '云律师团队')
    phone = SiteSetting.get('contact_phone', '')
    address = SiteSetting.get('contact_address', '')
    icp = SiteSetting.get('icp_beian', '')
    lawyer_name = SiteSetting.get('lawyer_name', '邹卫华')
    lawyer_title = SiteSetting.get('lawyer_title', '执业律师')
    site_description = SiteSetting.get('site_description', '专业 · 诚信 · 高效')
    lawyer_avatar = SiteSetting.get('lawyer_avatar', '')
    wechat_qrcode = SiteSetting.get('wechat_qrcode', '')
    return dict(
        now=lambda: datetime.now(),
        site_name=site_name,
        phone=phone, address=address, icp=icp,
        lawyer_name=lawyer_name, lawyer_title=lawyer_title,
        site_description=site_description, lawyer_avatar=lawyer_avatar,
        wechat_qrcode=wechat_qrcode, SiteSetting=SiteSetting
    )


@app.after_request
def add_cache_headers(response):
    if request.path.startswith('/static/'):
        response.cache_control.max_age = 86400
        response.cache_control.public = True
    return response


# 简单 IP 频率限制（生产环境建议用 Redis）
_rate_limit_store = defaultdict(list)


def check_rate_limit(key, max_attempts=3, window_seconds=3600):
    now = time.time()
    attempts = [t for t in _rate_limit_store[key] if now - t < window_seconds]
    _rate_limit_store[key] = attempts
    if len(attempts) >= max_attempts:
        return False, int(window_seconds - (now - attempts[0]))
    _rate_limit_store[key].append(now)
    return True, 0


# ============ 错误处理 ============

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    db.session.rollback()
    return render_template('500.html'), 500


if __name__ == '__main__':
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        print("=" * 40)
        print("   云律师团队")
        print("=" * 40)
        init_database()
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    if debug_mode:
        print("DEBUG 模式已开启，生产环境请勿使用！")
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
