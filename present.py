#!/usr/bin/env python

from bdateutil import relativedelta
import datetime
import json
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, request
from flask_mail import Mail, Message
import pytz
import requests
import time
from validate_email import validate_email

import logging
import logging.handlers

from discount_codes import get_badge_types, generate_discount_code, get_sponsor_reporting_groups

# create our little application
app = Flask(__name__)

app.config.from_pyfile( "./config/present.default.conf" )
#app.config.from_envvar( "PRESENT_CONFIG" )

# =======================================================================================
# Set up logging.
# =======================================================================================

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

# =======================================================================================
# Create mail object.
# =======================================================================================

mail = Mail()

# =======================================================================================
# Set up secure tokens and passwords.
# =======================================================================================

def get_password( password_file ):
    '''Utility function to load in our various passwords.'''
    password = None
    with open( password_file, "r" ) as f:
        for key in f.readlines():
            key = key.strip()
            if key.startswith( '#' ):
                continue
            elif len( key ) == 0:
                continue
            else:
                password = key
                break

    return password

app.config.update(
    SECRET_KEY = get_password( app.config['SECRET_KEY_FILE'] ),
    PASSWORD = get_password( app.config['PASSWORD_FILE'] ),
    APP_KEY = get_password( app.config['APP_PASSWORD_FILE'] ),
    MAIL_PASSWORD = get_password( app.config['MAIL_PASSWORD_FILE'] )
)


# =======================================================================================
# Various web pages.
# =======================================================================================

# NOTE - This does nothing if DEBUG is True.
@app.errorhandler( 500 )
def internal_error( error ):
    return render_template( 'error.html' )

@app.route('/login', methods=[ 'GET', 'POST' ] )
def login():
    '''Admin login that unlocks additional functionality - for ABI personnel only.'''
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
    '''Search request for input discount code.'''

    redeemed_codes = None
    if 'code' in request.values:
        data = {
            'discount_eventID' : app.config['SPONSOR_EVENT'],
            'registrant_eventID' : app.config['REGISTRANT_EVENT'],
            'discount_code' : request.values['code'].lower().strip()
        }
        redeemed_codes = requests.post( "%s/data/discount_code/" % ( app.config['APP_SERVER'] ), json.dumps( data ) ).json()

        if redeemed_codes['discount_code_data'] == {}:
            flash( "No data found for code: %s" % ( request.values['code'].strip() ) )
        else:
            flash( 'Showing data for discount code: %s' % ( request.values['code'].strip() ) )

            redeemed_codes['redemptions'].sort( key=lambda x: x['name'].split()[-1] )
            badge_types = get_badge_types( app.config['SPONSOR_EVENT'] )
            badge_type_name = redeemed_codes['discount_code_data']['badge_type']
            if redeemed_codes['discount_code_data']['badge_type'] in badge_types:
                badge_type_name = badge_types[redeemed_codes['discount_code_data']['badge_type']]['name']

            redeemed_codes['badge_type_name'] = badge_type_name

    return render_template( "discount_code.html", redeemed_codes=redeemed_codes )

@app.route( '/code_summary/', methods=[ 'GET' ] )
def code_summary():
    '''Admin only - return a summary of all codes for input into RegOnline.'''

    data = {
        'eventID' : app.config['SPONSOR_EVENT'],
        'api_key' : app.config['APP_KEY']
    }
    discount_codes = requests.post( "%s/data/discounts/" % ( app.config['APP_SERVER'] ), json.dumps( data ) ).json()['discount_codes']

    codes_by_type = {}
    last_updated_by_type = {}

    def get_date( date_string ):
        return datetime.datetime.strptime( date_string, "%a, %d %b %Y %H:%M:%S %Z" )

    badge_types = get_badge_types( app.config['SPONSOR_EVENT'] )

    discount_codes.sort( key=lambda x:['created_date'] )

    for discount_code in discount_codes:
        if discount_code['badge_type'] in codes_by_type:
            codes_by_type[discount_code['badge_type']] += ",%s=%s(%d)" % ( discount_code['discount_code'], discount_code['regonline_str'], discount_code['quantity'] )

            if get_date( last_updated_by_type[discount_code['badge_type']] ) < get_date( discount_code['created_date'] ):
                last_updated_by_type[discount_code['badge_type']] = discount_code['created_date']
        else:
            codes_by_type[discount_code['badge_type']] = "%s=%s(%d)" % ( discount_code['discount_code'], discount_code['regonline_str'], discount_code['quantity'] )
            last_updated_by_type[discount_code['badge_type']] = discount_code['created_date']

    code_summary = sorted( [ { "label" : v['name'], "regonline_code_string" : codes_by_type.get( k, '' ), "last_updated" : last_updated_by_type.get( k, 'N/A' ) } for k, v in badge_types.items() ] )
       
    return render_template( "code_summary.html", code_summary=code_summary )

@app.route( '/bulk_purchases/', methods=[ 'GET', 'POST' ] )
def bulk_purchases():
    '''Admin only, lists all Enterprise Pack and Bulk Purchases.'''

    data = {
        'eventID' : app.config['SPONSOR_EVENT'],
        'api_key' : app.config['APP_KEY']
    }
    
    discount_codes = requests.post( "%s/data/discounts/" % ( app.config['APP_SERVER'] ), json.dumps( data ) ).json()['discount_codes']

    sponsors = requests.post( "%s/data/sponsors/" % ( app.config['APP_SERVER'] ), json.dumps( data ) ).json()['sponsors']

    badge_types = get_badge_types( app.config['SPONSOR_EVENT'] )

    sponsor_reporting_groups = get_sponsor_reporting_groups( app.config['SPONSOR_EVENT'] )    

    sponsors_by_id = { x['ID']:x for x in sponsors }
    discounts_by_code = {}

    enterprise_packs_by_sponsor = {}
    bulk_purchases_by_sponsor = {}

    total_enterprise_packs = 0
    total_bulk_purchases = 0

    enterprise_group_purchase_stats = {}
    bulk_group_purchase_stats = {}

    for discount_code in discount_codes:
        entitlement = ( discount_code['SponsorID'], 
                        sponsors_by_id[discount_code['SponsorID']]['Company'], 
                        discount_code['code_source'], 
                        badge_types[discount_code['badge_type']]['name'], 
                        discount_code['RegistrationType'] )
        quantity = discount_code['quantity'] / 10
        if discount_code['code_source'] == 'Enterprise Pack':
            total_enterprise_packs += quantity
            if entitlement in enterprise_packs_by_sponsor:
                enterprise_packs_by_sponsor[entitlement] += quantity
            else:
                enterprise_packs_by_sponsor[entitlement] = quantity
        elif discount_code['code_source'].startswith( 'Bulk Purchase' ):
            total_bulk_purchases += quantity
            if entitlement in bulk_purchases_by_sponsor:
                bulk_purchases_by_sponsor[entitlement] += quantity
            else:
                bulk_purchases_by_sponsor[entitlement] = quantity
        else:
            # Don't tally up group based stats if we're not working
            # with certain sponsor types.
            continue

        sponsor_reporting_group = sponsor_reporting_groups.get( sponsors_by_id[discount_code['SponsorID']]['RegistrationType'], 'Other Sponsored' )
        if discount_code['code_source'] == 'Enterprise Pack':
            if sponsor_reporting_group in enterprise_group_purchase_stats:
                enterprise_group_purchase_stats[sponsor_reporting_group] += quantity
            else:
                enterprise_group_purchase_stats[sponsor_reporting_group] = quantity
        else:
            if sponsor_reporting_group in bulk_group_purchase_stats:
                bulk_group_purchase_stats[sponsor_reporting_group] += quantity
            else:
                bulk_group_purchase_stats[sponsor_reporting_group] = quantity

    bulk_purchases = {
        "total_enterprise_packs" : total_enterprise_packs,
        "total_bulk_purchases"   : total_bulk_purchases,
        "enterprise_group_purchase_stats" : enterprise_group_purchase_stats,
        "bulk_group_purchase_stats" : bulk_group_purchase_stats,
        "enterprise_packs_by_sponsor" : [ { "SponsorID"         : key[0],
                                            "Company"           : key[1],
                                            "code_source"       : key[2],
                                            "badge_type"        : key[3],
                                            "RegistrationType"  : key[4],
                                            "quantity"          : value }
                                          for key, value in sorted( enterprise_packs_by_sponsor.items(), key=lambda k: k[0][1] ) ],
        "bulk_purchases_by_sponsor" : [ { "SponsorID"         : key[0],
                                          "Company"           : key[1],
                                          "code_source"       : key[2],
                                          "badge_type"        : key[3],
                                          "RegistrationType"  : key[4],
                                          "quantity"          : value }
                                        for key, value in sorted( bulk_purchases_by_sponsor.items(), key=lambda k: k[0][1] ) ]
    }

    return render_template( "bulk_purchases.html", bulk_purchases=bulk_purchases )

@app.route( '/registration_summary/', methods=[ 'GET', 'POST' ] )
def registration_summary():
    '''Admin only, summaries all registration counts and sponsor data.'''

    data = {
        'eventID' : app.config['SPONSOR_EVENT'],
        'api_key' : app.config['APP_KEY']
    }
    
    discount_codes = requests.post( "%s/data/discounts/" % ( app.config['APP_SERVER'] ), json.dumps( data ) ).json()['discount_codes']

    sponsors = requests.post( "%s/data/sponsors/" % ( app.config['APP_SERVER'] ), json.dumps( data ) ).json()['sponsors']

    data = {
        'eventID' : app.config['REGISTRANT_EVENT'],
        'api_key' : app.config['APP_KEY']
    }
    registrants = requests.post( "%s/data/registrants/" % ( app.config['APP_SERVER'] ), json.dumps( data ) ).json()['registrants']

    badge_types = get_badge_types( app.config['SPONSOR_EVENT'] )

    # ==========================================================================
    # Handle the case where we are creating a new discount code for this sponsor.
    # ==========================================================================

    if "add_discount_code" in request.values:
        badge_type = request.values['badge_type']
        quantity = int( request.values['quantity'].strip() )
        sponsorID = int( request.values['sponsorID'] )

        sponsor = [ x for x in sponsors if x['ID'] == sponsorID ][0]
    
        discount_code = generate_discount_code( app.config['SPONSOR_EVENT'], sponsor, badge_type, quantity, discount_codes )

        def get_date_string( date ):
            return date.strftime( "%a, %d %b %Y %H:%M:%S %Z" )

        discount_code['created_date'] = get_date_string( discount_code['created_date'] )

        result = requests.post( "%s/data/discount_code/add/" % ( app.config['APP_SERVER'] ), json.dumps( { "eventID" : app.config['SPONSOR_EVENT'], "discount_code_data" : discount_code, "api_key" : app.config['APP_KEY']  } ) )

        mail_sent = False
        try:
            # DEBUG, add in mail recipients.
            mail_recipients = app.config['ADMIN_MAIL_RECIPIENTS']

            # We want this mail to go out at 4 pm on the next business
            # day.
            today = datetime.date.today()
            today_4pm = datetime.datetime( today.year, today.month, today.day, 16, tzinfo=pytz.timezone( 'PST8PDT' ) )
            tomorrow_4pm = today_4pm + relativedelta( bdays = +1 )
            when = tomorrow_4pm.astimezone( pytz.utc )
            
            extra_headers = {
                'X-MC-SendAt' : when.strftime( "%Y-%m-%d %H:%M:%S" )
            }

            mail_message = Message( "Grace Hopper Celebration 2015 Discount Codes",
                                    sender = app.config['SEND_AS'],
                                    recipients = mail_recipients,
                                    bcc = app.config['ADMIN_MAIL_RECIPIENTS'],
                                    extra_headers = extra_headers )

            discount_search_url = "%s%s?code=%s" % ( app.config['EXTERNAL_SERVER_BASE_URL'], url_for( 'discount_code' ), discount_code['discount_code'] )

            mail_message.html = render_template( "email_add_discount_code.html", data={
                'sponsor'             : sponsor,
                'quantity'            : quantity,
                'discount_code'       : discount_code,
                'badge_type_name'     : badge_types[badge_type]['name'],
                'regonline_url'       : badge_types[badge_type]['regonline_url'],
                'discount_search_url' : discount_search_url } )

            mail.init_app( app )
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
            flash( "Invalid email address argument! Please enter a list of email addresses separated by commas." )

        sponsor = [ x for x in sponsors if x['ID'] == sponsorID ][0]

        sponsor_discount_codes = [ x for x in discount_codes if x['SponsorID'] == sponsor['ID'] ]

        mail_sent = False
        try:
            # DEBUG, leave this variable alone here and actually send to the recipients in production.
            email_recipients = app.config['ADMIN_MAIL_RECIPIENTS']

            mail_message = Message( "Grace Hopper Celebration 2015 Discount Codes",
                                    sender = app.config['SEND_AS'],
                                    recipients = email_recipients,
                                    bcc = app.config['ADMIN_MAIL_RECIPIENTS'])

            for discount_code in sorted( sponsor_discount_codes, 
                                         key = lambda x: x['discount_code'] ):
                discount_code['badge_type_name'] = badge_types[discount_code['badge_type']]['name']
                discount_code['regonline_url'] = badge_types[discount_code['badge_type']]['regonline_url']
                
                discount_code['discount_search_url'] = "%s%s?code=%s" % ( app.config['EXTERNAL_SERVER_BASE_URL'], url_for( 'discount_code' ), discount_code['discount_code'] )
        
            mail_message.html = render_template( "email_discount_code_summary.html", data={
                'sponsor'        : sponsor,
                'discount_codes' : sponsor_discount_codes } )

            mail.init_app( app )
            mail.send( mail_message )
            mail_sent = True
        except Exception as e:
            flash( "ERROR! Failed to send discount code summary to: %s." % ( email_recipients + app.config['ADMIN_MAIL_RECIPIENTS'] ) )

        if mail_sent:
            success_message = "Discount summary email sent to: %s" % ( email_recipients + app.config['ADMIN_MAIL_RECIPIENTS'] )
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
    sponsor_reporting_groups = get_sponsor_reporting_groups( app.config['SPONSOR_EVENT'] )    
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

@app.route( '/sponsor_summary/', methods=[ 'GET', 'POST' ] )
def sponsor_summary():
    '''Will eventually be limited to particular sponsors, right now admin only.'''

    sponsor_email = None
    if 'sponsor_email' in request.values:
        if validate_email( request.values['sponsor_email'].strip().lower() ):
            sponsor_email = request.values['sponsor_email'].strip().lower()

    # DEBUG - hard code this for now.
    #sponsor_email = "cindy.stanphill@hp.com"

    data = {
        'eventID' : app.config['SPONSOR_EVENT'],
        'api_key' : app.config['APP_KEY']
    }
    sponsors = [ x for x in requests.post( "%s/data/sponsors/" % ( app.config['APP_SERVER'] ), json.dumps( data ) ).json()['sponsors'] if ( x['Email'].strip().lower() == sponsor_email or x['CCEmail'].strip().lower() == sponsor_email ) ]
    sponsors_by_id = { x['ID']:x for x in sponsors }

    if 'sponsor_email' in request.values:
        if len( sponsors ) == 0:
            flash( "No data found for sponsor email: %s" % ( request.values['sponsor_email'].strip() ) )
        else:
            flash( 'Showing data for sponsor email: %s' % ( request.values['sponsor_email'].strip() ) )

    discount_codes = [ x for x in requests.post( "%s/data/discounts/" % ( app.config['APP_SERVER'] ), json.dumps( data ) ).json()['discount_codes'] if x['SponsorID'] in sponsors_by_id ]
    discounts_by_code = { x['discount_code']:x for x in discount_codes }

    include_company_data = False

    if include_company_data:
        # Try to build up a list of alternate company names that
        # registrants might have entered in the company box that all mean
        # the same thing.
        company_suffixes = [ 'co', 'co.', 'corp', 'corp.', 'corporation', 'inc', 'inc.', 'incorporated', 'llc', 'llc.' ]
        companies = {}
        for sponsor in sponsors:
            if len( sponsor['Company'].strip() ):
                company = sponsor['Company'].lower().strip()
                company = ' '.join( company.split() )
                companies[company] = True
        
                # Remove any suffixes and trailing commas.
                words = company.split()
                if len( words ) > 1:
                    if words[-1] in company_suffixes:
                        if words[-2][-1] == ',':
                            words[-2] = words[-2][:-1]
                        words = [ w for w in words if len( w ) ]
                    companies[' '.join( words )] = True

    data = {
        'eventID' : app.config['REGISTRANT_EVENT'],
        'api_key' : app.config['APP_KEY']
    }
    all_registrants = requests.post( "%s/data/registrants/" % ( app.config['APP_SERVER'] ), json.dumps( data ) ).json()['registrants']

    # Boil down our registrants to those who used one of our codes, or
    # those who come from our company.
    registrants = [ x for x in all_registrants if x['discount_code'] in discounts_by_code ]

    if include_company_data:
        other_registrants = [ x for x in all_registrants if x['discount_code'] not in discounts_by_code ]
        registrants += [ x for x in other_registrants if x['Company'] in companies ]

    badge_types = get_badge_types( app.config['SPONSOR_EVENT'] )

    # ==========================================================================
    # Handle the case where we are sending an reminder discount code email.

    if "send_email" in request.values:
        sponsorID = int( request.values['sponsorID'] )

        email_recipients = []
        try:
            email_recipients_raw = request.values['email_recipients'].replace( ';', ',' )
            email_recipients = [ x.strip() for x in email_recipients_raw.split( ',' ) ]
        except Exception as e:
            flash( "Invalid email address argument! Please enter a list of email addresses separated by commas." )

        sponsor = [ x for x in sponsors if x['ID'] == sponsorID ][0]

        sponsor_discount_codes = [ x for x in discount_codes if x['SponsorID'] == sponsor['ID'] ]

        mail_sent = False
        try:
            # DEBUG, leave this variable alone here and actually send to the recipients in production.
            email_recipients = app.config['ADMIN_MAIL_RECIPIENTS']

            mail_message = Message( "Grace Hopper Celebration 2015 Discount Codes",
                                    sender = app.config['SEND_AS'],
                                    recipients = email_recipients,
                                    bcc = app.config['ADMIN_MAIL_RECIPIENTS'])
            
            for discount_code in sorted( sponsor_discount_codes, 
                                         key = lambda x: x['discount_code'] ):

                discount_code['badge_type_name'] = badge_types[discount_code['badge_type']]['name']
                discount_code['regonline_url'] = badge_types[discount_code['badge_type']]['regonline_url']
                
                discount_code['discount_search_url'] = "%s%s?code=%s" % ( app.config['EXTERNAL_SERVER_BASE_URL'], url_for( 'discount_code' ), discount_code['discount_code'] )

            mail_message.html = render_template( "email_discount_code_summary.html", data={
                'sponsor'        : sponsor,
                'discount_codes' : sponsor_discount_codes } )

            mail.init_app( app )
            mail.send( mail_message )
            mail_sent = True
        except Exception as e:
            flash( "ERROR! Failed to send discount code summary to: %s. %s" % ( email_recipients + app.config['ADMIN_MAIL_RECIPIENTS'], e ) )

        if mail_sent:
            success_message = "Discount summary email sent to: %s" % ( email_recipients + app.config['ADMIN_MAIL_RECIPIENTS'] )
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

    # Used to aggregate some reports about Academic, Corporate, etc. sponsors and their registrants.
    sponsor_reporting_groups = get_sponsor_reporting_groups( app.config['SPONSOR_EVENT'] )    
    group_attendee_stats = { 
        'Other Sponsored' : { 'redeemed' : 0,
                              'quantity' : 0 },
    }

    # Used to compute redeemed / available for each particular sponsor
    # code.
    codes_by_sponsor = {}

    for discount_code in discount_codes:
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

    # Private function that strips down a registrant data to what we
    # can give out publicly to someone with the code.
    def get_fields( registrant ):
        return {
            "name" : "%s %s" % ( registrant['FirstName'], registrant['LastName'] ),
            "company" : registrant['Company'],
            "title" : registrant['Title'],
            "status" : registrant['StatusDescription'],
            "registration_type" : registrant['RegistrationType'],
            "registration_date" : registrant['AddDate']
        }
    
    public_registrants = [ get_fields( x ) for x in registrants ]

    sponsor_summary = {
        "sponsor_email"        : sponsor_email,
        "sponsors"             : sponsors,
        "reserved"             : quantity - redeemed,
        "redeemed"             : redeemed,
        "nonsponsored"         : nonsponsored,
        "registered"           : nonsponsored + redeemed,
        "group_attendee_stats" : [ { "name" : k, "data" : group_attendee_stats[k] } for k in sorted( group_attendee_stats.keys() ) ],
        "badge_type_names"     : [ { "value" : k, "name" : badge_types[k]['name'] } for k in sorted( badge_types.keys() ) ],
        "registrants"          : public_registrants
    }

    return render_template( "sponsor_summary.html", sponsor_summary=sponsor_summary )

if __name__ == '__main__':
    app.run( port=app.config['PORT'] )

