from functools import wraps
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

APP_KEY = os.environ['APP_KEY']
APP_SECRET = os.environ['APP_SECRET']

app = Flask(__name__)
app.config['DEBUG'] = os.environ.get('DEBUG') == 'True'
app.secret_key = os.environ['FLASK_SECRET_KEY']

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

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'access_token' not in session:
            return redirect(get_flow().start())
        else:
            return f(*args, **kwargs)
    return decorated

@app.route("/login")
def login():
	return redirect(get_dropbox_auth_flow().start())

@app.route('/oauth_callback')
def oauth_callback():
    '''Callback function for when the user returns from OAuth.'''
    access_token, user_id, url_state = get_dropbox_auth_flow().finish(request.args)
    session['access_token'] = access_token
    return redirect(url_for('index'))

@app.route('/logout')
@requires_auth
def logout():
	session.clear()
	return redirect(url_for('index'))

@app.route("/")
def index():
	return render_template('index.html')

@app.route('/revisions')
@requires_auth
def revisions():
	# Shared Link from Dropbox Chooser
	link = request.args['link']

	# Calling Dropbox API v1
	metadata = requests.post('https://api.dropbox.com/1/metadata/link', params={'link': link},
		headers={'Authorization': 'Bearer ' + str(session['access_token'])}).json()

	# Calling Dropbox API v2
	if not metadata.get('path'):
		return redirect(url_for('index'))
	else:
		dbx = Dropbox(session['access_token'])
		entries = dbx.files_list_revisions(metadata['path']).entries

		return render_template('revisions.html', path=metadata['path'],
			revisions=entries)

@app.route('/revision')
@requires_auth
def revision():
	dbx = Dropbox(session['access_token'])

	f = dbx.files_download(request.args['path'], request.args['rev'])
	resp = make_response(f[1].content)
	resp.headers["Content-Disposition"] = "attachment; filename=" + f[0].name

	return resp

if __name__ == "__main__":
    app.run()
