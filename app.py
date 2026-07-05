import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fz_fassara_secret_key_12345'

# Dauko DATABASE_URL na Render, idan babu amfani da SQLite na gida
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///fzfassara.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
REDIRECT_URI = os.environ.get('REDIRECT_URI', 'https://fzfassara.onrender.com/login/google/callback')

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_password'

# ---------------------------------------------------------------------------
# DATABASE MODELS
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=True)
    bio = db.Column(db.Text, default="")
    profile_pic = db.Column(db.String(150), default="default.jpg")
    is_admin = db.Column(db.Boolean, default=False)
    videos = db.relationship('Video', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    filename = db.Column(db.String(150), nullable=False)
    thumbnail = db.Column(db.String(150), default="default_thumb.jpg")
    category = db.Column(db.String(100), nullable=False)
    views = db.Column(db.Integer, default=0)
    downloads = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comments = db.relationship('Comment', backref='video', lazy=True)
    likes = db.relationship('Like', backref='video', lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)

class Watchlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    video_id = db.Column(db.Integer, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------
@app.route('/')
def welcome():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('welcome.html')

@app.route('/login', methods=['GET', 'POST'])
@app.route('/login_password', methods=['GET', 'POST'])
def login_password():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.password and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Kuskure a Imel ko Password!')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
@app.route('/signup', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        user_exists = User.query.filter((User.email == email) | (User.username == username)).first()
        if user_exists:
            flash('Wannan sunan ko Imel din riga an yi amfani da shi!')
            return redirect(request.url)

        hashed_pw = generate_password_hash(password, method='scrypt')
        new_user = User(username=username, email=email, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        flash('An kirkiiri account lafiya! Shiga yanzu.')
        return redirect(url_for('login_password'))
    
    try:
        return render_template('register_2.html')
    except:
        return render_template('register.html')

@app.route('/google-login')
def google_login():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        flash('Ba a saita Google Login ba tukuna a Render Envs!')
        return redirect(url_for('login_password'))
    try:
        google_provider_cfg = requests.get("https://accounts.google.com/.well-known/openid-configuration").json()
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]
        request_uri = requests.Request('GET', authorization_endpoint, params={
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": "openid email profile",
            "response_type": "code",
        }).prepare().url
        return redirect(request_uri)
    except Exception as e:
        flash(f'Google Login Error: {str(e)}')
        return redirect(url_for('login_password'))

@app.route('/login/google/callback')
def google_callback():
    code = request.args.get("code")
    try:
        google_provider_cfg = requests.get("https://accounts.google.com/.well-known/openid-configuration").json()
        token_endpoint = google_provider_cfg["token_endpoint"]
        token_response = requests.post(token_endpoint, data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code"
        }).json()

        if 'access_token' not in token_response:
            flash('Google Authentication Failed')
            return redirect(url_for('login_password'))

        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        userinfo_response = requests.get(userinfo_endpoint, headers={"Authorization": f"Bearer {token_response['access_token']}"}).json()

        if userinfo_response.get("email_verified"):
            email = userinfo_response["email"]
            name = userinfo_response.get("name", email.split('@')[0])
            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(username=name, email=email, password=None)
                db.session.add(user)
                db.session.commit()
            login_user(user)
            return redirect(url_for('dashboard'))
        
        # GYARA 1: Kara sako idan imel din Google ba shi da kariya
        flash('Google account email not verified!')
        return redirect(url_for('login_password'))
    except Exception as e:
        flash(f'Callback error: {str(e)}')
        return redirect(url_for('login_password'))

@app.route('/dashboard')
@login_required
def dashboard():
    tab = request.args.get('tab', 'home')
    videos = Video.query.all()
    watchlist_entries = Watchlist.query.filter_by(user_id=current_user.id).all()
    watchlist_video_ids = [w.video_id for w in watchlist_entries]
    watchlist_items = Video.query.filter(Video.id.in_(watchlist_video_ids)).all() if watchlist_video_ids else []
    return render_template('dashboard_2.html', active_tab=tab, videos=videos, watchlist_items=watchlist_items)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        video_file = request.files.get('video_file')
        thumb_file = request.files.get('thumbnail')

        if not video_file or video_file.filename == '':
            flash('Da fatan za a zaɓi fayil ɗin bidiyo!')
            return redirect(request.url)
        if not title:
            flash('Dole ne ka saka wa bidiyo suna!')
            return redirect(request.url)

        v_filename = secure_filename(video_file.filename)
        video_file.save(os.path.join(app.config['UPLOAD_FOLDER'], v_filename))

        t_filename = "default_thumb.jpg"
        if thumb_file and thumb_file.filename:
            t_filename = secure_filename(thumb_file.filename)
            thumb_file.save(os.path.join(app.config['UPLOAD_FOLDER'], t_filename))

        new_video = Video(title=title, description=description, category=category, filename=v_filename, thumbnail=t_filename, user_id=current_user.id)
        db.session.add(new_video)
        db.session.commit()
        flash('An dora bidiyo lafiya!')
        return redirect(url_for('dashboard'))
    return render_template('upload_2.html')

@app.route('/video/<int:video_id>', methods=['GET', 'POST'])
@login_required
def watch_video(video_id):
    video = Video.query.get_or_404(video_id)
    if request.method == 'POST' and 'comment' in request.form:
        comment_content = request.form.get('comment')
        if comment_content:
            new_comment = Comment(content=comment_content, user_id=current_user.id, video_id=video.id)
            db.session.add(new_comment)
            db.session.commit()

    video.views += 1
    db.session.commit()
    recommended = Video.query.filter(Video.category == video.category, Video.id != video.id).limit(4).all()
    has_liked = Like.query.filter_by(user_id=current_user.id, video_id=video.id).first() is not None
    likes_count = Like.query.filter_by(video_id=video.id).count()
    return render_template('video_2.html', video=video, recommended=recommended, has_liked=has_liked, likes=likes_count)

# GYARA 2: Dawo da duka sauran kofofin (Routes) domin gudun 404 a HTML
@app.route('/like/<int:video_id>')
@login_required
def like_video(video_id):
    existing_like = Like.query.filter_by(user_id=current_user.id, video_id=video_id).first()
    if existing_like:
        db.session.delete(existing_like)
    else:
        new_like = Like(user_id=current_user.id, video_id=video_id)
        db.session.add(new_like)
    db.session.commit()
    return redirect(url_for('watch_video', video_id=video_id))

@app.route('/watchlist/add/<int:video_id>')
@login_required
def add_to_watchlist(video_id):
    exists = Watchlist.query.filter_by(user_id=current_user.id, video_id=video_id).first()
    if not exists:
        new_item = Watchlist(user_id=current_user.id, video_id=video_id)
        db.session.add(new_item)
        db.session.commit()
        flash('An kara a jerin abubuwan kallo!')
    return redirect(url_for('dashboard'))

@app.route('/profile', methods=['POST'])
@login_required
def update_profile():
    bio = request.form.get('bio')
    profile_pic = request.files.get('profile_pic')
    if bio:
        current_user.bio = bio
    if profile_pic and profile_pic.filename:
        filename = secure_filename(profile_pic.filename)
        profile_pic.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        current_user.profile_pic = filename
    db.session.commit()
    flash('An sabunta bayanan fuska!')
    return redirect(url_for('dashboard', tab='profile'))

@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin:
        flash('Baka da ikon shiga nan!')
        return redirect(url_for('dashboard'))
    users = User.query.all()
    videos = Video.query.all()
    return render_template('admin_2.html', users=users, videos=videos)

@app.route('/privacy')
def privacy():
    return render_template('privacy_2.html')

@app.route('/terms')
def terms():
    return render_template('terms_2.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('welcome'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
