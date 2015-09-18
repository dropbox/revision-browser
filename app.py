import datetime
import os
import urlparse
import requests

from dropbox import Dropbox
from dropbox.oauth import DropboxOAuth2Flow
from flask import (
	Flask,
	make_response,
	redirect,
	render_template,
	request,
	session,
	url_for
	)
from flask.ext.login import (
	current_user,
	LoginManager,
	login_required,
	login_user,
	logout_user,
	UserMixin
	)
from flask.ext.sqlalchemy import SQLAlchemy

APP_KEY = os.environ['APP_KEY']
APP_SECRET = os.environ['APP_SECRET']

app = Flask(__name__)
app.config['DEBUG'] = os.environ['DEBUG'] == 'True'
app.secret_key = os.environ['FLASK_SECRET_KEY']
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/test.db'

login_manager = LoginManager()
login_manager.init_app(app)

db = SQLAlchemy(app)

class User(db.Model, UserMixin):
	id = db.Column(db.Text, primary_key=True)
	name = db.Column(db.Text)
	email = db.Column(db.Text)
	access_token = db.Column(db.Text)

	def __init__(self, id, name, email, access_token):
		self.id = id
		self.name = name
		self.email = email
		self.access_token = access_token

@login_manager.user_loader
def load_user(id):
	return User.query.filter_by(id = id).first()

def get_url(route):
    '''Generate a proper URL, forcing HTTPS if not running locally'''
    host = urlparse.urlparse(request.url).hostname
    url = url_for(route,
                  _external=True,
                  _scheme='http' if host in ('127.0.0.1', 'localhost') else
                  'https')

    return url

def get_dropbox_auth_flow():
    return DropboxOAuth2Flow(APP_KEY, APP_SECRET, get_url('oauth_callback'),
                             session, 'dropbox-csrf-token')

@app.route("/login")
def login():
	return redirect(get_dropbox_auth_flow().start())

@app.route('/oauth_callback')
def oauth_callback():
    '''Callback function for when the user returns from OAuth.'''
    access_token, user_id, url_state = get_dropbox_auth_flow().finish(request.args)
    dbx = Dropbox(access_token)
    account = dbx.users_get_current_account()
    user = User.query.filter_by(id = account.account_id).first()

    if not user:
    	user = User(account.account_id, account.name.display_name, account.email, access_token)
    	db.session.add(user)
    	db.session.commit()

    login_user(user)

    return redirect(url_for('index'))

@app.route("/logout")
def logout():
	logout_user()
	return redirect(url_for('index'))

@app.route("/")
def index():
	return render_template('index.html')

@app.route('/revisions')
@login_required
def revisions():
	link = request.args['link']
	metadata = requests.post('https://api.dropbox.com/1/metadata/link', params={'link': link},
		headers={'Authorization': 'Bearer ' + str(current_user.access_token)}).json()
	dbx = Dropbox(current_user.access_token)
	revisions_result = dbx.files_list_revisions(metadata['path'])
	if not revisions_result.is_deleted:
		return render_template('revisions.html', path=metadata['path'], revisions=revisions_result.entries)
	else:
		redirect(url_for('index'))

@app.route('/revision')
@login_required
def revision():
	dbx = Dropbox(current_user.access_token)
	f = dbx.files_download(request.args['path'], request.args['rev'])
	resp = make_response(f[1].content)
	resp.headers["Content-Disposition"] = "attachment; filename=" + f[0].name
	return resp

if __name__ == "__main__":
    app.run()
