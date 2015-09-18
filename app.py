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
def logout():
	if session.get('access_token'):
		requests.post('https://api.dropboxapi.com/1/disable_access_token',
			headers={'Authorization': 'Bearer ' + session['access_token']})
	session.clear()
	return redirect(url_for('index'))

@app.route("/")
def index():
	return render_template('index.html')

@app.route('/revisions')
def revisions():
	link = request.args['link']
	metadata = requests.post('https://api.dropbox.com/1/metadata/link', params={'link': link},
		headers={'Authorization': 'Bearer ' + str(session['access_token'])}).json()
	dbx = Dropbox(session['access_token'])
	revisions_result = dbx.files_list_revisions(metadata['path'])

	if not revisions_result.is_deleted:
		return render_template('revisions.html', path=metadata['path'],
			revisions=revisions_result.entries)
	else:
		redirect(url_for('index'))

@app.route('/revision')
def revision():
	dbx = Dropbox(session['access_token'])
	f = dbx.files_download(request.args['path'], request.args['rev'])

	resp = make_response(f[1].content)
	resp.headers["Content-Disposition"] = "attachment; filename=" + f[0].name
	return resp

if __name__ == "__main__":
    app.run()
