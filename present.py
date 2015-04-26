#!/usr/bin/env python

import json
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, request
import requests


# configuration
DEBUG = False
SECRET_KEY = 'development key'
USERNAME = 'admin'
PASSWORD = 'aghcb2015i'
SPONSOR_EVENT = 1438449
REGISTRANT_EVENT = 1438441
PORT=5001
APP_SERVER = "http://127.0.0.1:5000"
APP_KEY = '9Cn3gKNS3DB7FEck'

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
            return redirect(url_for('registration_summary'))
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You were logged out')
    return redirect(url_for('discount_code'))

@app.route( '/discount_code/', methods=[ 'GET', 'POST' ] )
def discount_code():
    # Answer the query if we had a search request.
    redeemed_codes = None
    if 'code' in request.values:
        flash( 'Showing data for discount code: %s' % ( request.values['code'] ) )
        data = {
            'discount_eventID' : SPONSOR_EVENT,
            'registrant_eventID' : REGISTRANT_EVENT,
            'discount_code' : request.values['code']
        }
        redeemed_codes = requests.post( "%s/data/discount_code/" % ( APP_SERVER ), json.dumps( data ) ).json()

        redeemed_codes['redemptions'].sort( key=lambda x: x['name'].split()[-1] )

    return render_template( "discount_code.html", redeemed_codes=redeemed_codes )

@app.route( '/code_summary/', methods=[ 'GET' ] )
def code_summary():
    data = {
        'eventID' : SPONSOR_EVENT,
        'api_key' : APP_KEY
    }
    discount_codes = requests.post( "%s/data/discounts/" % ( APP_SERVER ), json.dumps( data ) ).json()['discount_codes']

    codes_by_type = {}

    for discount_code in discount_codes:
        if discount_code['badge_type'] in codes_by_type:
            codes_by_type[discount_code['badge_type']] += ",%s=%s(%d)" % ( discount_code['discount_code'], discount_code['regonline_str'], discount_code['quantity'] )
        else:
            codes_by_type[discount_code['badge_type']] = "%s=%s(%d)" % ( discount_code['discount_code'], discount_code['regonline_str'], discount_code['quantity'] )

    badge_types = [ { "label" : key, "regonline_code_string" : value } for key, value in codes_by_type.items() ]
            
    return render_template( "code_summary.html", badge_types=badge_types )

@app.route( '/registration_summary/', methods=[ 'GET' ] )
def registration_summary():
    data = {
        'eventID' : SPONSOR_EVENT,
        'api_key' : APP_KEY
    }
    discount_codes = requests.post( "%s/data/discounts/" % ( APP_SERVER ), json.dumps( data ) ).json()['discount_codes']

    sponsors = requests.post( "%s/data/sponsors/" % ( APP_SERVER ), json.dumps( data ) ).json()['sponsors']

    data = {
        'eventID' : REGISTRANT_EVENT,
        'api_key' : APP_KEY
    }
    registrants = requests.post( "%s/data/registrants/" % ( APP_SERVER ), json.dumps( data ) ).json()['registrants']

    nonsponsored = 0
    reserved = 0
    redeemed = 0

    codes_by_sponsor = {}

    for discount_code in discount_codes:
        if discount_code['SponsorID'] in codes_by_sponsor:
            codes_by_sponsor[discount_code['SponsorID']].append( discount_code )
        else:
            codes_by_sponsor[discount_code['SponsorID']] = [ discount_code ]

        if discount_code['regonline_str'] == '-100%':
            reserved += discount_code['quantity']

    redemptions_by_code = {}

    for registrant in registrants:
        if registrant['discount_code']:
            redeemed += 1
            reserved -= 1
            if registrant['discount_code'] in redemptions_by_code:
                redemptions_by_code[registrant['discount_code']] += 1
            else:
                redemptions_by_code[registrant['discount_code']] = 1
        else:
            nonsponsored += 1
            
    for sponsor, codes in codes_by_sponsor.items():
        for code in codes:
            if code['discount_code'] in redemptions_by_code:
                code['redeemed'] = redemptions_by_code[code['discount_code']]
                code['available'] = code['quantity'] - redemptions_by_code[code['discount_code']]

    sponsors.sort( key=lambda x: x['Company'] )

    for sponsor in sponsors:
        sponsor['discount_codes'] = codes_by_sponsor.get( sponsor['ID'], [] )

    registration_summary = {
        "sponsors" : sponsors,
        "nonsponsored" : nonsponsored,
        "reserved" : reserved,
        "redeemed" : redeemed,
        "registerd" : nonsponsored + redeemed
    }

    return render_template( "registration_summary.html", registration_summary=registration_summary )        

if __name__ == '__main__':
    app.run( port=PORT )
