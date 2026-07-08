import os
import uuid
import secrets
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)

# ---------------------------------------------------------------------------
# SECURITY / DEPLOYMENT CONFIG
# ---------------------------------------------------------------------------
# SECRET_KEY must come from the environment in production. If it changes on
# every restart (e.g. a randomly generated fallback), all logged-in sessions
# are invalidated AND the Google OAuth "state" cookie signed at login time
# won't match the one checked at /authorize/google, causing Google Login to
# fail with a "mismatching_state" / "CSRF Warning" error on Render.
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    # Fallback only for local development so the app still boots.
    # On Render, set SECRET_KEY as an Environment Variable so it stays
    # constant across restarts and across the multiple worker processes
    # a production server may run.
    SECRET_KEY = secrets.token_hex(32)
    print('WARNING: SECRET_KEY env var not set. Using a temporary random key '
          '(sessions and Google Login will break on restart). Set SECRET_KEY '
          'in your environment for production.')
app.config['SECRET_KEY'] = SECRET_KEY

# Debug mode must never be on in production (it exposes the Werkzeug
# debugger, which allows remote code execution). Control it with an env var
# instead of hardcoding it.
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'false').strip().lower() == 'true'

# Render (and most PaaS hosts) sit behind a reverse proxy that terminates
# TLS. Without ProxyFix, Flask thinks every request is plain HTTP, so
# url_for(..., _external=True) generates an http:// redirect_uri for Google
# OAuth. That won't match the https:// Authorized redirect URI configured in
# Google Cloud Console, and Google will reject the login with
# "redirect_uri_mismatch". ProxyFix fixes this by trusting the
# X-Forwarded-Proto / X-Forwarded-Host headers Render sets.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Force Flask to build https:// URLs (belt-and-braces alongside ProxyFix)
# when not running in local debug mode.
app.config['PREFERRED_URL_SCHEME'] = 'http' if app.config['DEBUG'] else 'https'

# Cookies should only travel over HTTPS in production, and SameSite=Lax lets
# the Google OAuth redirect back to your site still carry the session cookie
# that holds the "state" value (without it, the state check fails).
app.config['SESSION_COOKIE_SECURE'] = not app.config['DEBUG']
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True

# Hadawa da Database tare da wanke kowane sarari (space) ta atomatik
database_url = os.environ.get('DATABASE_URL')
if database_url:
    database_url = database_url.strip()  # Wannan yana goge space na kuskure lokacin tura kodi
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url if database_url else 'sqlite:///fzfassara.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Reject uploads over 200MB outright (adjust as needed) so a huge file can't
# exhaust disk/memory before your own validation even runs.
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'webm', 'mkv', 'avi'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename, allowed_extensions):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in allowed_extensions
    )


def unique_filename(filename):
    """Prefix with a UUID so uploads from different users never collide or
    overwrite each other, while keeping the sanitized original name."""
    safe_name = secure_filename(filename)
    ext = safe_name.rsplit('.', 1)[1].lower() if '.' in safe_name else ''
    return f"{uuid.uuid4().hex}.{ext}" if ext else f"{uuid.uuid4().hex}"


if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_password'

# ---------------------------------------------------------------------------
# Saita OAuth na Google Login
# ---------------------------------------------------------------------------
oauth = OAuth(app)
google_client_id = os.environ.get('GOOGLE_CLIENT_ID')
google_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

google = None
google_configured = False

if google_client_id and google_client_secret:
    google_client_id = google_client_id.strip()
    google_client_secret = google_client_secret.strip()

    google = oauth.register(
        name='google',
        client_id=google_client_id,
        client_secret=google_client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )
    google_configured = True
else:
    print('NOTE: GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are not set. '
          '"Continue with Google" will be hidden/disabled until both are '
          'configured in your environment variables on Render.')

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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)

# Create tables at import time, not just under `if __name__ == '__main__'`.
# On Render, gunicorn imports this module directly (`gunicorn app:app`) and
# NEVER executes the `if __name__ == '__main__':` block below, so
# db.create_all() was silently never running in production — meaning no
# tables existed, and any query (even the login-manager loading the current
# user) crashed with a 500 Internal Server Error. Running it here guarantees
# it happens both locally and under gunicorn.
with app.app_context():
    db.create_all()

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
            flash('Invalid email or password!')
    return render_template('login.html', google_configured=google_configured)

@app.route('/login/google')
def google_login():
    if not google_configured:
        flash('Google Login keys are not configured in Render Environment Variables!')
        return redirect(url_for('login_password'))
    # This must build an https:// URL that EXACTLY matches an "Authorized
    # redirect URI" entered in Google Cloud Console -> Credentials -> your
    # OAuth Client -> Authorized redirect URIs, e.g.:
    #   https://your-app.onrender.com/authorize/google
    # If PREFERRED_URL_SCHEME/ProxyFix above aren't taking effect for some
    # reason, this will come out as http:// and Google will reject the
    # request with "Error 400: redirect_uri_mismatch" — check the URL this
    # generates against your Google Console entry if that happens.
    redirect_uri = url_for('authorize_google', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize/google')
def authorize_google():
    if not google_configured:
        return redirect(url_for('login_password'))

    try:
        token = google.authorize_access_token()
    except Exception as e:
        # Most common causes on Render:
        #  - SECRET_KEY changes between requests (multiple workers/dynos
        #    without a shared, fixed SECRET_KEY env var) -> "state" mismatch
        #  - Session cookie blocked because SESSION_COOKIE_SECURE=True but
        #    the request came in as plain http (fixed by ProxyFix above)
        app.logger.error(f'Google OAuth token exchange failed: {e}')
        flash('Google sign-in failed (session/state mismatch). Please try again.')
        return redirect(url_for('login_password'))

    user_info = token.get('userinfo')
    if not user_info:
        # Some providers/configs don't return userinfo inline; parse the ID
        # token as a fallback instead of silently failing.
        try:
            user_info = google.parse_id_token(token, nonce=None)
        except Exception as e:
            app.logger.error(f'Google OAuth userinfo parsing failed: {e}')
            user_info = None

    if not user_info or not user_info.get('email'):
        flash('Could not retrieve your Google account email. Please try again or use email/password.')
        return redirect(url_for('login_password'))

    email = user_info.get('email')
    name = user_info.get('name') or user_info.get('given_name') or email.split('@')[0]

    user = User.query.filter_by(email=email).first()
    if not user:
        # Guard against a colliding username (e.g. two Google accounts
        # sharing a display name) which would otherwise hit the unique
        # constraint on User.username and raise a 500 error.
        base_username = secure_filename(name) or email.split('@')[0]
        username = base_username
        suffix = 1
        while User.query.filter_by(username=username).first():
            suffix += 1
            username = f"{base_username}{suffix}"

        user = User(username=username, email=email, is_admin=False)
        db.session.add(user)
        db.session.commit()

    login_user(user)
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['GET', 'POST'])
@app.route('/signup', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        user_exists = User.query.filter((User.email == email) | (User.username == username)).first()
        if user_exists:
            flash('Username or email already exists!')
            return redirect(request.url)

        hashed_pw = generate_password_hash(password, method='scrypt')
        new_user = User(username=username, email=email, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! Please log in.')
        return redirect(url_for('login_password'))
    
    return render_template('register.html', google_configured=google_configured)

@app.route('/dashboard')
@login_required
def dashboard():
    tab = request.args.get('tab', 'home')
    videos = Video.query.all()
    watchlist_entries = Watchlist.query.filter_by(user_id=current_user.id).all()
    watchlist_video_ids = [w.video_id for w in watchlist_entries]
    watchlist_items = Video.query.filter(Video.id.in_(watchlist_video_ids)).all() if watchlist_video_ids else []
    return render_template('dashboard.html', active_tab=tab, videos=videos, watchlist_items=watchlist_items)

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
            flash('Please select a video file!')
            return redirect(request.url)
        if not title:
            flash('Title is required!')
            return redirect(request.url)
        if not allowed_file(video_file.filename, ALLOWED_VIDEO_EXTENSIONS):
            flash('Unsupported video format. Allowed: ' + ', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS)))
            return redirect(request.url)
        if thumb_file and thumb_file.filename and not allowed_file(thumb_file.filename, ALLOWED_IMAGE_EXTENSIONS):
            flash('Unsupported thumbnail format. Allowed: ' + ', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS)))
            return redirect(request.url)

        v_filename = unique_filename(video_file.filename)
        video_file.save(os.path.join(app.config['UPLOAD_FOLDER'], v_filename))

        t_filename = "default_thumb.jpg"
        if thumb_file and thumb_file.filename:
            t_filename = unique_filename(thumb_file.filename)
            thumb_file.save(os.path.join(app.config['UPLOAD_FOLDER'], t_filename))

        new_video = Video(title=title, description=description, category=category, filename=v_filename, thumbnail=t_filename, user_id=current_user.id)
        db.session.add(new_video)
        db.session.commit()
        flash('Video uploaded successfully!')
        return redirect(url_for('dashboard'))
    return render_template('upload.html')

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
    return render_template('video.html', video=video, recommended=recommended, has_liked=has_liked, likes=likes_count)

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
        flash('Added to watchlist!')
    return redirect(url_for('dashboard'))

@app.route('/profile', methods=['POST'])
@login_required
def update_profile():
    bio = request.form.get('bio')
    profile_pic = request.files.get('profile_pic')
    if bio:
        current_user.bio = bio
    if profile_pic and profile_pic.filename:
        if not allowed_file(profile_pic.filename, ALLOWED_IMAGE_EXTENSIONS):
            flash('Unsupported image format. Allowed: ' + ', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS)))
            return redirect(url_for('dashboard', tab='profile'))
        filename = unique_filename(profile_pic.filename)
        profile_pic.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        current_user.profile_pic = filename
    db.session.commit()
    flash('Profile updated successfully!')
    return redirect(url_for('dashboard', tab='profile'))

@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin:
        flash('Access denied!')
        return redirect(url_for('dashboard'))
    users = User.query.all()
    videos = Video.query.all()
    return render_template('admin.html', users=users, videos=videos)

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('welcome'))

if __name__ == '__main__':
    # debug is now driven by the FLASK_DEBUG env var (see config above) and
    # defaults to False. On Render you should be running this via a
    # production WSGI server (e.g. gunicorn app:app) rather than this
    # __main__ block anyway.
    app.run(debug=app.config['DEBUG'], host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
