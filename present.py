#!/usr/bin/env python

import json
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, request
import requests


# configuration
DEBUG = True
SECRET_KEY = 'development key'
USERNAME = 'admin'
PASSWORD = 'default'
SPONSOR_EVENT = 1438449
REGISTRANT_EVENT = 1438441
PORT=5001
APP_SERVER = "http://127.0.0.1:5000"
APP_KEY = 'secret_key'

# create our little application
app = Flask(__name__)
app.config.from_object(__name__)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] != app.config['USERNAME']:
            error = 'Invalid username'
        elif request.form['password'] != app.config['PASSWORD']:
            error = 'Invalid password'
        else:
            session['logged_in'] = True
            flash('You were logged in')
            # DEBUG - replace this with whatever goes at /.
            return redirect(url_for('show_entries'))
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You were logged out')
    return redirect(url_for('show_entries'))

@app.route( '/discount_code/', methods=[ 'GET', 'POST' ] )
def discount_code():
    # Answer the query if we had a search request.
    redeemed_codes = None
    if 'code' in request.values:
        data = {
            'discount_eventID' : SPONSOR_EVENT,
            'registrant_eventID' : REGISTRANT_EVENT,
            'discount_code' : request.values['code']
        }
        redeemed_codes = requests.post( "%s/data/discount_code/" % ( APP_SERVER ), json.dumps( data ) ).json()

    return render_template( "discount_code.html", redeemed_codes=redeemed_codes )


if __name__ == '__main__':
    app.run( port=PORT )

