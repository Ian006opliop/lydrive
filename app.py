import os, uuid, io
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
import qrcode

app = Flask(__name__)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# --- [LYTIX 旗艦配置] ---
app.config.update(
    SECRET_KEY='LYTIX_NEXUS_ULTRA_2025',
    SQLALCHEMY_DATABASE_URI='sqlite:///lydrive_nexus.db',
    UPLOAD_FOLDER='static/storage',
    GOOGLE_CLIENT_ID='1003122854509-q3n9k6bhri4ocgoj8go3of9967c12r1e.apps.googleusercontent.com',
    GOOGLE_CLIENT_SECRET='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'
)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
oauth = OAuth(app)

google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# --- 資料庫模型 ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(128))
    name = db.Column(db.String(64))
    avatar = db.Column(db.String(255), default='https://ui-avatars.com/api/?background=3b82f6&color=fff')
    is_verified = db.Column(db.Boolean, default=True)
    is_pro = db.Column(db.Boolean, default=False) # 會員狀態

class FileEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))
    sys_name = db.Column(db.String(255))
    size = db.Column(db.Integer)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Wormhole(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True)
    file_id = db.Column(db.Integer, db.ForeignKey('file_entry.id'))

@login_manager.user_loader
def load_user(uid): return User.query.get(int(uid))

# --- 登入與註冊路由 ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and user.password_hash and check_password_hash(user.password_hash, request.form['password']):
            login_user(user); return redirect(url_for('index'))
        flash('帳號或密碼錯誤')
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    email = request.form['email']
    if User.query.filter_by(email=email).first():
        flash('Email 已被註冊'); return redirect(url_for('login'))
    user = User(email=email, name=email.split('@')[0], 
                password_hash=generate_password_hash(request.form['password']))
    db.session.add(user); db.session.commit()
    login_user(user); return redirect(url_for('index'))

# --- 會員升級路由 ---
@app.route('/upgrade', methods=['GET', 'POST'])
@login_required
def upgrade():
    if request.method == 'POST':
        current_user.is_pro = True
        db.session.commit()
        flash('恭喜升級為 PRO 會員！')
        return redirect(url_for('index'))
    return render_template('upgrade.html')

# --- 檔案主介面 ---
@app.route('/')
@login_required
def index():
    files = FileEntry.query.filter_by(user_id=current_user.id).order_by(FileEntry.timestamp.desc()).all()
    used_bytes = sum(f.size for f in files)
    
    # 空間限制：一般 5GB / PRO 50GB
    limit_mb = 51200 if current_user.is_pro else 5120
    limit_bytes = limit_mb * 1024 * 1024
    percent = (used_bytes / limit_bytes) * 100 if limit_bytes > 0 else 0
    
    return render_template('index.html', files=files, used_space=used_bytes, limit_mb=limit_mb, percent=percent)

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    file = request.files.get('file')
    if file:
        sn = uuid.uuid4().hex
        content = file.read(); size = len(content); file.seek(0)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], sn))
        db.session.add(FileEntry(filename=file.filename, sys_name=sn, size=size, user_id=current_user.id))
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete/<int:file_id>', methods=['POST'])
@login_required
def delete_file(file_id):
    f = FileEntry.query.get_or_404(file_id)
    if f.user_id == current_user.id:
        try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], f.sys_name))
        except: pass
        Wormhole.query.filter_by(file_id=f.id).delete()
        db.session.delete(f); db.session.commit()
    return redirect(url_for('index'))

# --- 分享功能 ---
@app.route('/create_wormhole/<int:file_id>')
@login_required
def create_wormhole(file_id):
    token = uuid.uuid4().hex
    db.session.add(Wormhole(token=token, file_id=file_id)); db.session.commit()
    return jsonify({"share_url": url_for('access_wormhole', token=token, _external=True)})

@app.route('/qrcode/<token>')
def get_qrcode(token):
    img = qrcode.make(url_for('access_wormhole', token=token, _external=True))
    buf = io.BytesIO(); img.save(buf, format='PNG'); buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/wormhole/<token>')
def access_wormhole(token):
    wh = Wormhole.query.filter_by(token=token).first_or_404()
    f = FileEntry.query.get(wh.file_id)
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], f.sys_name), download_name=f.filename, as_attachment=True)

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
