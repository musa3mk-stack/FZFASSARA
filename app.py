import os
import base64
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import requests

# High-performance enterprise system directory mapping for Pydroid3 Android Environment
project_root = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(project_root, 'templates')

app = Flask(__name__, template_folder=template_dir)
app.config['SECRET_KEY'] = 'fz_fassara_mega_ultra_premium_key_2026'

# SQLite Database Setup Configuration (Adaptive for Render/Local)
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

if database_url:
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    db_path = os.path.join(project_root, 'vtu_database.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Maximum 200MB file processing safety threshold
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024
app.config['UPLOAD_VIDEO_DIR'] = os.path.join(project_root, 'uploads')
app.config['UPLOAD_THUMB_DIR'] = os.path.join(project_root, 'thumbnails')

# Google OAuth Credentials Configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '://googleusercontent.com')
REDIRECT_URI = "https://onrender.com"

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'welcome'

# Automatic offline media storage setup folders
for folder in [app.config['UPLOAD_VIDEO_DIR'], app.config['UPLOAD_THUMB_DIR']]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# HARDCODED SUPER ADMIN CREDENTIALS CONFIGURATION
ADMIN_EMAIL = "musa3mk@gmail.com"
ADMIN_PASSWORD_PLAIN = "FZ12345@"

# Subscriber link join table for Channels system
subscribers = db.Table('subscribers',
    db.Column('channel_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('subscriber_id', db.Integer, db.ForeignKey('users.id'), primary_key=True)
)
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(200), nullable=True)
    bio = db.Column(db.String(300), default='No bio available.')
    profile_pic = db.Column(db.String(200), default='default_avatar.png')
    is_admin = db.Column(db.Boolean, default=False)
    is_premium = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    videos = db.relationship('Video', backref='uploader', lazy=True, cascade="all, delete-orphan")
    comments = db.relationship('Comment', backref='author', lazy=True, cascade="all, delete-orphan")
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade="all, delete-orphan")
    history = db.relationship('WatchHistory', backref='user', lazy=True, cascade="all, delete-orphan")
    watchlist = db.relationship('WatchLater', backref='user', lazy=True, cascade="all, delete-orphan")
    likes = db.relationship('VideoLike', backref='user', lazy=True, cascade="all, delete-orphan")

    subscriptions = db.relationship(
        'User', secondary=subscribers,
        primaryjoin=(subscribers.c.subscriber_id == id),
        secondaryjoin=(subscribers.c.channel_id == id),
        backref=db.backref('channel_subscribers', lazy='dynamic'),
        lazy='dynamic'
    )

class Video(db.Model):
    __tablename__ = 'videos'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    thumbnail = db.Column(db.String(200), nullable=False)
    is_locked = db.Column(db.Boolean, default=False)
    is_short = db.Column(db.Boolean, default=False)
    views = db.Column(db.Integer, default=0)
    downloads = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    comments = db.relationship('Comment', backref='video', lazy=True, cascade="all, delete-orphan")
    history_entries = db.relationship('WatchHistory', backref='video', lazy=True, cascade="all, delete-orphan")
    watchlist_entries = db.relationship('WatchLater', backref='video', lazy=True, cascade="all, delete-orphan")
    likes = db.relationship('VideoLike', backref='video', lazy=True, cascade="all, delete-orphan")

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comments.id'), nullable=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy=True, cascade="all, delete-orphan")

class WatchHistory(db.Model):
    __tablename__ = 'watch_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    watched_at = db.Column(db.DateTime, default=datetime.utcnow)

class WatchLater(db.Model):
    __tablename__ = 'watch_later'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

class VideoLike(db.Model):
    __tablename__ = 'video_likes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(300), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
# Injection script for automated browser notification client runtime prompts
@app.context_processor
def inject_permissions_script():
    script = """
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        if ("Notification" in window) {
            if (Notification.permission!== "granted" && Notification.permission!== "denied") {
                Notification.requestPermission().then(permission => {
                    if (permission === "granted") {
                        console.log("Notification access authorized successfully.");
                    }
                });
            }
        }
    });
    </script>
    """
    return dict(notifications_script=script)

# =========================================================================
# CORE CONTROLLER OPERATIONS ENGINE (FIXED & EXPANDED ROUTING LAYER)
# =========================================================================

@app.route('/')
def welcome():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('welcome.html')

@app.route('/dashboard')
@login_required
def dashboard():
    tab = request.args.get('tab', 'home')
    search_query = request.args.get('search', '')
    category_query = request.args.get('category', 'All')

    videos_query = Video.query

    if tab == 'shorts':
        videos_query = videos_query.filter_by(is_short=True)
    elif tab == 'premium':
        videos_query = videos_query.filter_by(is_locked=True)
    else:
        videos_query = videos_query.filter_by(is_short=False, is_locked=False)

    if search_query:
        videos_query = videos_query.filter(Video.title.contains(search_query))

    if category_query and category_query!= 'All':
        videos_query = videos_query.filter_by(category=category_query)

    all_videos = videos_query.order_by(Video.id.desc()).all()
    watchlist_items = WatchLater.query.filter_by(user_id=current_user.id).all()

    return render_template('dashboard.html', videos=all_videos, active_tab=tab, watchlist_items=watchlist_items)

@app.route('/privacy')
def privacy_policy():
    return render_template('privacy.html')

@app.route('/terms')
def terms_of_service():
    return render_template('terms.html')

@app.route('/login', methods=['GET', 'POST'])
def login_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Incorrect email or password!', 'danger')
    return render_template('login.html')
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter_by(email=email).first():
            flash('This email is already in use!', 'danger')
        else:
            hashed_pw = generate_password_hash(password, method='scrypt')
            new_user = User(name=name, email=email, password_hash=hashed_pw)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login/google')
def google_login():
    google_provider_cfg = requests.get("https://google.com").json()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    request_uri = requests.Request(
        'GET', authorization_endpoint,
        params={
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": "https://fzfassara.onrender.com/login/google/callback",
            "scope": "openid email profile",
            "response_type": "code",
        }
    ).prepare().url
    return redirect(request_uri)

@app.route('/login/google/callback')
def google_callback():
    code = request.args.get("code")
    google_provider_cfg = requests.get("https://google.com").json()
    token_endpoint = google_provider_cfg["token_endpoint"]

    token_response = requests.post(
        token_endpoint,
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET', ''),
            "redirect_uri": "https://fzfassara.onrender.com/login/google/callback",
            "grant_type": "authorization_code"
        }
    ).json()

    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    userinfo_response = requests.get(userinfo_endpoint, headers={"Authorization": f"Bearer {token_response['access_token']}"}).json()

    if userinfo_response.get("email_verified"):
        email = userinfo_response["email"]
        name = userinfo_response["name"]
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, name=name, is_premium=False)
            db.session.add(user)
            db.session.commit()
        login_user(user)
        return redirect(url_for('dashboard'))
    return "Google Authentication Failed.", 400

@app.route('/premium')
@login_required
def premium_hub():
    return render_template('premium.html')

@app.route('/video/<int:video_id>', methods=['GET', 'POST'])
@login_required
def watch_video(video_id):
    video = Video.query.get_or_404(video_id)
    if video.is_locked and not current_user.is_premium and not current_user.is_admin:
        flash('This is a Premium Video. You need to unlock premium tier access first.', 'warning')
        return redirect(url_for('premium_hub'))

    video.views += 1
    history_entry = WatchHistory(user_id=current_user.id, video_id=video.id)
    db.session.add(history_entry)
    db.session.commit()

    recommended = Video.query.filter(Video.category == video.category, Video.id!= video.id).limit(4).all()

    if request.method == 'POST' and 'comment_text' in request.form:
        comment_text = request.form.get('comment_text')
        parent_id = request.form.get('parent_id')
        if comment_text:
            new_comment = Comment(
                video_id=video.id, user_id=current_user.id,
                text=comment_text, parent_id=int(parent_id) if parent_id else None
            )
            db.session.add(new_comment)
            if parent_id:
                parent_comment = Comment.query.get(int(parent_id))
                if parent_comment and parent_comment.user_id!= current_user.id:
                    notif = Notification(user_id=parent_comment.user_id, message=f"{current_user.name} replied to your comment on movie: {video.title}")
                    db.session.add(notif)
            db.session.commit()
            flash('Comment added!', 'success')
            return redirect(url_for('watch_video', video_id=video.id))

    likes_count = VideoLike.query.filter_by(video_id=video.id).count()
    has_liked = VideoLike.query.filter_by(user_id=current_user.id, video_id=video.id).first() is not None
    return render_template('video.html', video=video, likes=likes_count, has_liked=has_liked, recommended=recommended)

@app.route('/video/<int:video_id>/like')
@login_required
def like_video(video_id):
    video = Video.query.get_or_404(video_id)
    existing_like = VideoLike.query.filter_by(user_id=current_user.id, video_id=video.id).first()
    if existing_like:
        db.session.delete(existing_like)
    else:
        new_like = VideoLike(user_id=current_user.id, video_id=video.id)
        db.session.add(new_like)
    db.session.commit()
    return redirect(url_for('watch_video', video_id=video.id))

@app.route('/watchlist')
@login_required
def watchlist():
    items = WatchLater.query.filter_by(user_id=current_user.id).order_by(WatchLater.id.desc()).all()
    return render_template('watchlist.html', items=items)

@app.route('/video/<int:video_id>/watchlist/add')
@login_required
def add_to_watchlist(video_id):
    video = Video.query.get_or_404(video_id)
    exists = WatchLater.query.filter_by(user_id=current_user.id, video_id=video.id).first()
    if not exists:
        entry = WatchLater(user_id=current_user.id, video_id=video.id)
        db.session.add(entry)
        db.session.commit()
        flash('Added to Watch Later!', 'success')
    return redirect(url_for('watch_video', video_id=video.id))

@app.route('/history')
@login_required
def watch_history_page():
    records = WatchHistory.query.filter_by(user_id=current_user.id).order_by(WatchHistory.id.desc()).all()
    return render_template('history.html', records=records)

@app.route('/video/<int:video_id>/download')
@login_required
def download_video(video_id):
    video = Video.query.get_or_404(video_id)
    video.downloads += 1
    db.session.commit()
    return send_from_directory(app.config['UPLOAD_VIDEO_DIR'], video.filename, as_attachment=True)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        is_premium_wall = request.form.get('is_premium') == 'true'
        is_short_tv = request.form.get('is_short') == 'true'

        video_file = request.files.get('video_file')
        thumb_file = request.files.get('thumbnail_file')

        if video_file and thumb_file:
            video_filename = secure_filename(video_file.filename)
            thumb_filename = secure_filename(thumb_file.filename)
            video_file.save(os.path.join(app.config['UPLOAD_VIDEO_DIR'], video_filename))
            thumb_file.save(os.path.join(app.config['UPLOAD_THUMB_DIR'], thumb_filename))

            new_video = Video(
                user_id=current_user.id, title=title, description=description,
                category=category, filename=video_filename, thumbnail=thumb_filename,
                is_locked=is_premium_wall, is_short=is_short_tv
            )
            db.session.add(new_video)
            db.session.commit()
            flash('Video published successfully!', 'success')
            return redirect(url_for('dashboard'))
    return render_template('upload.html')

@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin:
        abort(403)
    all_users = User.query.all()
    all_videos = Video.query.all()
    return render_template('admin.html', users=all_users, videos=all_videos)

@app.route('/admin/delete/video/<int:video_id>')
@login_required
def admin_delete_video(video_id):
    if not current_user.is_admin:
        abort(403)
    video = Video.query.get_or_404(video_id)
    db.session.delete(video)
    db.session.commit()
    flash('Video deleted permanently.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete/user/<int:user_id>')
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash('Cannot delete admin account!', 'danger')
        return redirect(url_for('admin_panel'))
    db.session.delete(user)
    db.session.commit()
    flash('User deleted permanently.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('welcome'))

def init_super_admin():
    admin_user = User.query.filter_by(email=ADMIN_EMAIL).first()
    if not admin_user:
        hashed_pw = generate_password_hash(ADMIN_PASSWORD_PLAIN, method='scrypt')
        super_admin = User(
            name="Super Admin", email=ADMIN_EMAIL, password_hash=hashed_pw,
            is_admin=True, is_premium=True, bio="Main System Control Administration Account Platform"
        )
        db.session.add(super_admin)
        db.session.commit()

with app.app_context():
    db.create_all()
    init_super_admin()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
