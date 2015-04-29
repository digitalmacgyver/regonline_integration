#!/usr/bin/env python

import datetime
import json
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, request
from flask_mail import Mail, Message
import requests
import time

import logging
import logging.handlers

from discount_codes import get_badge_types, generate_discount_code, get_sponsor_reporting_groups

# configuration
# NOTE - No logging is sent to syslog on exceptions if DEBUG is true.
DEBUG = False
SECRET_KEY = 'development key'
USERNAME = 'admin'
PASSWORD = 'aghcb2015i'

# 2014
#SPONSOR_EVENT = 1438449
#REGISTRANT_EVENT = 1438441

# 2015
SPONSOR_EVENT = 1639610
REGISTRANT_EVENT = 1702108


PORT=5001
APP_SERVER = "http://127.0.0.1:5000"
APP_KEY = '9Cn3gKNS3DB7FEck'

# This will differ in our actual deployment due to nginx.
EXTERNAL_SERVER_BASE_URL = 'http://ec2-52-12-132-124.us-west-2.compute.amazonaws.com'
SEND_AS = ( 'GHC 2015 Registration', 'registration@anitaborg.org' )
# DEBUG - send to Kathryn once in production.
#ADMIN_MAIL_RECIPIENTS = [ 'matt@viblio.com' ]
ADMIN_MAIL_RECIPIENTS = [ 'kathrynb@anitaborg.org', 'matt@viblio.com' ]

# Mail config
MAIL_SERVER = 'smtp.mandrillapp.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USE_SSL = False
MAIL_DEBUG = False
MAIL_USERNAME = 'matt@viblio.com'
MAIL_PASSWORD = 'MZDI2Ncl5L1qY--irqO81A'
DEFAULT_MAIL_SENDER = 'matt@viblio.com'

# create our little application
app = Flask(__name__)
app.config.from_object(__name__)
mail = Mail( app )

logging.basicConfig( level=logging.INFO )

log = app.logger
log.setLevel( logging.DEBUG )

syslog = logging.handlers.SysLogHandler( address="/dev/log" )

format_string = 'present.py: { "name" : "%(name)s", "module" : "%(module)s", "lineno" : "%(lineno)s", "funcName" : "%(funcName)s", "level" : "%(levelname)s", "message" : %(message)s }'

sys_formatter = logging.Formatter( format_string )

syslog.setFormatter( sys_formatter )
syslog.setLevel( logging.INFO )
consolelog = logging.StreamHandler()
consolelog.setLevel( logging.DEBUG )

log.addHandler( syslog )
log.addHandler( consolelog )

# NOTE - This does nothing if DEBUG is True.
@app.errorhandler( 500 )
def internal_error( error ):
    return render_template( 'error.html' )

@app.route('/login', methods=[ 'GET', 'POST' ] )
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'].strip() != app.config['USERNAME']:
            error = 'Invalid username'
        elif request.form['password'].strip() != app.config['PASSWORD']:
            error = 'Invalid password'
        else:
            session['logged_in'] = True
            flash( 'You were logged in' )
            logging.info( json.dumps( { 'message' : '%s authenticated' % ( request.form['username'].strip() ) } ) )
            return redirect( url_for( 'registration_summary' ) )

    if error:
        logging.error( json.dumps( { 'message' : 'Authentication failed: %s' % ( error ) } ) )

    return render_template( 'login.html', error=error )

@app.route('/logout')
def logout():
    session.pop( 'logged_in', None )
    flash( 'You were logged out' )
    logging.info( json.dumps( { 'message' : 'User logged out.' } ) )
    return redirect( url_for( 'discount_code' ) )

@app.route( '/', methods=[ 'GET', 'POST' ] )
@app.route( '/discount_code/', methods=[ 'GET', 'POST' ] )
def discount_code():
    # Answer the query if we had a search request.
    redeemed_codes = None
    if 'code' in request.values:
        data = {
            'discount_eventID' : SPONSOR_EVENT,
            'registrant_eventID' : REGISTRANT_EVENT,
            'discount_code' : request.values['code'].lower().strip()
        }
        redeemed_codes = requests.post( "%s/data/discount_code/" % ( APP_SERVER ), json.dumps( data ) ).json()

        if redeemed_codes['discount_code_data'] == {}:
            flash( "No data found for code: %s" % ( request.values['code'].strip() ) )
        else:
            flash( 'Showing data for discount code: %s' % ( request.values['code'].strip() ) )

            redeemed_codes['redemptions'].sort( key=lambda x: x['name'].split()[-1] )
            badge_types = get_badge_types( SPONSOR_EVENT )
            badge_type_name = redeemed_codes['discount_code_data']['badge_type']
            if redeemed_codes['discount_code_data']['badge_type'] in badge_types:
                badge_type_name = badge_types[redeemed_codes['discount_code_data']['badge_type']]['name']

            redeemed_codes['badge_type_name'] = badge_type_name

    return render_template( "discount_code.html", redeemed_codes=redeemed_codes )

@app.route( '/code_summary/', methods=[ 'GET' ] )
def code_summary():
    data = {
        'eventID' : SPONSOR_EVENT,
        'api_key' : APP_KEY
    }
    discount_codes = requests.post( "%s/data/discounts/" % ( APP_SERVER ), json.dumps( data ) ).json()['discount_codes']

    codes_by_type = {}
    last_updated_by_type = {}

    # DEBUG - This is just example code, in a real deployment we use
    # the badge_types returned by the get_badge_types function.
    #
    # Here we are currently using made up badge types backfired into our
    # registrant data.
    #for discount_code in discount_codes:
    #    if discount_code['badge_type'] in codes_by_type:
    #        codes_by_type[discount_code['badge_type']] += ",%s=%s(%d)" % ( discount_code['discount_code'], discount_code['regonline_str'], discount_code['quantity'] )
    #    else:
    #        codes_by_type[discount_code['badge_type']] = "%s=%s(%d)" % ( discount_code['discount_code'], discount_code['regonline_str'], discount_code['quantity'] )
    #badge_types = [ { "label" : key, "regonline_code_string" : value } for key, value in codes_by_type.items() ]
     
    def get_date( date_string ):
        return datetime.datetime.strptime( date_string, "%a, %d %b %Y %H:%M:%S %Z" )

    # DEBUG - this is the production version.
    badge_types = get_badge_types( SPONSOR_EVENT )
    discount_codes.sort( key=lambda x:['created_date'] )
    for discount_code in sorted( discount_codes, key=lambda x: get_date( x['created_date'] ) ):
        if discount_code['badge_type'] in codes_by_type:
            codes_by_type[discount_code['badge_type']] += ",%s=%s(%d)" % ( discount_code['discount_code'], discount_code['regonline_str'], discount_code['quantity'] )

            if get_date( last_updated_by_type[discount_code['badge_type']] ) < get_date( discount_code['created_date'] ):
                last_updated_by_type[discount_code['badge_type']] = discount_code['created_date']
        else:
            codes_by_type[discount_code['badge_type']] = "%s=%s(%d)" % ( discount_code['discount_code'], discount_code['regonline_str'], discount_code['quantity'] )
            last_updated_by_type[discount_code['badge_type']] = discount_code['created_date']
            

    code_summary = sorted( [ { "label" : v['name'], "regonline_code_string" : codes_by_type.get( k, '' ), "last_updated" : last_updated_by_type.get( k, 'N/A' ) } for k, v in badge_types.items() ] )
       
    return render_template( "code_summary.html", code_summary=code_summary )

@app.route( '/registration_summary/', methods=[ 'GET', 'POST' ] )
def registration_summary():
    data = {
        'eventID' : SPONSOR_EVENT,
        'api_key' : APP_KEY
    }
    
    #start = time.time()
    discount_codes = requests.post( "%s/data/discounts/" % ( APP_SERVER ), json.dumps( data ) ).json()['discount_codes']
    #print "Discount codes:", time.time() - start

    #start = time.time()
    sponsors = requests.post( "%s/data/sponsors/" % ( APP_SERVER ), json.dumps( data ) ).json()['sponsors']
    #print "Sponsors codes:", time.time() - start

    data = {
        'eventID' : REGISTRANT_EVENT,
        'api_key' : APP_KEY
    }
    #start = time.time()
    registrants = requests.post( "%s/data/registrants/" % ( APP_SERVER ), json.dumps( data ) ).json()['registrants']
    #print "Registrants codes:", time.time() - start

    badge_types = get_badge_types( SPONSOR_EVENT )

    # ==========================================================================
    # Handle the case where we are creating a new discount code for this sponsor.

    if "add_discount_code" in request.values:
        badge_type = request.values['badge_type']
        quantity = int( request.values['quantity'].strip() )
        sponsorID = int( request.values['sponsorID'] )

        sponsor = [ x for x in sponsors if x['ID'] == sponsorID ][0]
    
        discount_code = generate_discount_code( SPONSOR_EVENT, sponsor, badge_type, quantity, discount_codes )

        result = requests.post( "%s/data/discount_code/add/" % ( APP_SERVER ), json.dumps( { "eventID" : SPONSOR_EVENT, "discount_code_data" : discount_code } ) )

        mail_sent = False
        try:
            # DEBUG, add in mail recipients.
            mail_recipients = ADMIN_MAIL_RECIPIENTS
            mail_message = Message( "Grace Hopper Celebration 2015 Discount Codes",
                                    sender = SEND_AS,
                                    recipients = mail_recipients,
                                    bcc = ADMIN_MAIL_RECIPIENTS )

            discount_search_url = "%s%s?code=%s" % ( EXTERNAL_SERVER_BASE_URL, url_for( 'discount_code' ), discount_code['discount_code'] )
            mail_message.html = '<p>Your %s discount code for %d %s badges is:<br />%s</p><p>Register using this code at:<br /><a href="%s">%s</a></p><p>View a report of attendees who have redeemed this code, and remaining redemptions at:<br /><a href="%s">%s</a></p>' % (
                sponsor['Company'], 
                quantity, 
                badge_types[badge_type]['name'], 
                discount_code['discount_code'], 
                badge_types[badge_type]['regonline_url'],
                badge_types[badge_type]['regonline_url'],
                discount_search_url, 
                discount_search_url )
            mail.send( mail_message )
            mail_sent = True
        except Exception as e:
            flash( "ERROR! Failed to send email notification of discount code creation to: %s." % ( mail_recipients ) )

        if result.json()['success']:
            discount_codes.append( discount_code )

            success_message = 'Added %d %s badges to sponsor %s with discount code: %s.' % ( quantity, badge_types[badge_type]['name'], sponsor['Company'], discount_code['discount_code'] )

            if mail_sent:
                success_message += " Notification email sent to: %s" % ( mail_recipients )

            flash( success_message )
        else:
            raise Exception( "Failed to add code!" )

    # ==========================================================================


    # ==========================================================================
    # Handle the case where we are sending an reminder discount code email.

    if "send_email" in request.values:
        sponsorID = int( request.values['sponsorID'] )

        email_recipients = []
        try:
            email_recipients_raw = request.values['email_recipients'].replace( ';', ',' )
            email_recipients = [ x.strip() for x in email_recipients_raw.split( ',' ) ]
        except Exception as e:
            flash( "Invalid email address argument! Please enter a list of email addresses sperated by commas." )

        sponsor = [ x for x in sponsors if x['ID'] == sponsorID ][0]

        sponsor_discount_codes = [ x for x in discount_codes if x['SponsorID'] == sponsor['ID'] ]
    
        mail_sent = False
        try:

            # DEBUG, leave this variable alone here and actually send to the recipients in production.
            email_recipients = ADMIN_MAIL_RECIPIENTS

            mail_message = Message( "Grace Hopper Celebration 2015 Discount Codes",
                                    sender = SEND_AS,
                                    recipients = email_recipients,
                                    bcc = ADMIN_MAIL_RECIPIENTS)
            
            message_html = '<p>Your %s discount codes are:<ul>' % ( sponsor['Company'] )

            for discount_code in sorted( sponsor_discount_codes, key = lambda x: x['discount_code'] ):

                # All this error checking madness is for backfilled
                # data, for future data where we generated all the
                # codes there will always be valid badge types.
                badge_type_name = discount_code['badge_type']
                regonline_url = "[To be determined]"
                if discount_code['badge_type'] in badge_types:
                    badge_type_name = badge_types[discount_code['badge_type']]['name']
                    regonline_url = badge_types[discount_code['badge_type']]['regonline_url']

                discount_search_url = "%s%s?code=%s" % ( EXTERNAL_SERVER_BASE_URL, url_for( 'discount_code' ), discount_code['discount_code'] )
                message_html += '<li>%s<ul><li>Badge Type: %s</li><li>Quantity: %d</li><li>Registration Link: <a href="%s">%s</a></li><li>Registration Redemption Report: <a href="%s">%s</a></li></ul></li>' % ( 
                    discount_code['discount_code'],
                    badge_type_name,
                    discount_code['quantity'],
                    regonline_url,
                    regonline_url,
                    discount_search_url, 
                    discount_search_url )

            message_html += "</ul></p>"
            
            mail_message.html = message_html
            mail.send( mail_message )
            mail_sent = True
        except Exception as e:
            flash( "ERROR! Failed to send discount code summary to: %s." % ( email_recipients + ADMIN_MAIL_RECIPIENTS ) )

        if mail_sent:
            success_message = "Discount summary email sent to: %s" % ( email_recipients + ADMIN_MAIL_RECIPIENTS )
            flash( success_message )

    # ==========================================================================
    # Now display all the summary data.

    # Attendees who did not redeem a code.
    nonsponsored = 0
    # Attendees who did use a code.
    redeemed = 0
    # Code entitlements not accounted for.
    quantity = 0

    sponsors_by_id = { x['ID']:x for x in sponsors }
    discounts_by_code = {}

    # Used to aggregate some reports about Academic, Corporate, etc. sponsors and their registrants.
    sponsor_reporting_groups = get_sponsor_reporting_groups( SPONSOR_EVENT )    
    group_attendee_stats = { 
        'Other Sponsored' : { 'redeemed' : 0,
                              'quantity' : 0 },
    }

    # Used to compute redeemed / available for each particular sponsor
    # code.
    codes_by_sponsor = {}

    for discount_code in discount_codes:
        discounts_by_code[discount_code['discount_code']] = discount_code

        if discount_code['SponsorID'] in codes_by_sponsor:
            codes_by_sponsor[discount_code['SponsorID']].append( discount_code )
        else:
            codes_by_sponsor[discount_code['SponsorID']] = [ discount_code ]

        if discount_code['badge_type'] in badge_types:
            if badge_types[discount_code['badge_type']]['reserve_spot']:
                quantity += int( discount_code['quantity'] )

                sponsor_reporting_group = sponsor_reporting_groups.get( sponsors_by_id[discount_code['SponsorID']]['RegistrationType'], 'Other Sponsored' )
                if sponsor_reporting_group in group_attendee_stats:
                    group_attendee_stats[sponsor_reporting_group]['quantity'] += discount_code['quantity']
                else:
                    group_attendee_stats[sponsor_reporting_group] = { 'quantity' : discount_code['quantity'],
                                                                      'redeemed' : 0 }
        else:
            logging.warning( json.dumps( { 'message' : 'Unknown badge_type: %s found in discount codes.' % ( discount_code['badge_type'] ) } ) )

    redemptions_by_code = {}

    for registrant in registrants:
        if registrant['discount_code']:
            discount_code = discounts_by_code.get( registrant['discount_code'], {} )

            if discount_code.get( 'badge_type', None ) in badge_types:
                if badge_types[discount_code['badge_type']]['reserve_spot']:

                    sponsor_reporting_group = 'Other Sponsored'
                    if 'SponsorID' in discount_code:
                        if discount_code['SponsorID'] in sponsors_by_id:
                            if sponsors_by_id[discount_code['SponsorID']]['RegistrationType'] in sponsor_reporting_groups:
                                sponsor_reporting_group = sponsor_reporting_groups[sponsors_by_id[discount_code['SponsorID']]['RegistrationType']]
          
                    redeemed += 1
                    group_attendee_stats[sponsor_reporting_group]['redeemed'] += 1

                if registrant['discount_code'] in redemptions_by_code:
                    redemptions_by_code[registrant['discount_code']] += 1
                else:
                    redemptions_by_code[registrant['discount_code']] = 1
            else:
                nonsponsored += 1
        else:
            nonsponsored += 1

    for group_name, group_stats in group_attendee_stats.items():
        group_stats['reserved'] = group_stats['quantity'] - group_stats['redeemed']
            
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
        "reserved" : quantity - redeemed,
        "redeemed" : redeemed,
        "nonsponsored" : nonsponsored,
        "registered" : nonsponsored + redeemed,
        "group_attendee_stats" : [ { "name" : k, "data" : group_attendee_stats[k] } for k in sorted( group_attendee_stats.keys() ) ],
        "badge_type_names" : [ { "value" : k, "name" : badge_types[k]['name'] } for k in sorted( badge_types.keys() ) ]
    }

    return render_template( "registration_summary.html", registration_summary=registration_summary )        

if __name__ == '__main__':
    app.run( port=PORT )

