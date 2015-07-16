#!/usr/bin/env python

from bdateutil import relativedelta
import csv
import datetime
import json
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, request, make_response
from flask_mail import Mail, Message
import pytz
import requests
import StringIO
import time
from validate_email import validate_email

import logging
import logging.handlers

from discount_codes import get_badge_types, get_sponsor_reporting_groups

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
    # The secret_key is used for CSS protection by Flask, not by our
    # system.
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
            redeemed_codes['redemptions'].sort( key=lambda x: x['name'].split()[-1] )
            badge_types = get_badge_types( app.config['SPONSOR_EVENT'] )
            badge_type_name = redeemed_codes['discount_code_data']['badge_type']
            if redeemed_codes['discount_code_data']['badge_type'] in badge_types:
                badge_type_name = badge_types[redeemed_codes['discount_code_data']['badge_type']]['name']

            redeemed_codes['badge_type_name'] = badge_type_name

    # ==========================================================================
    # Return the appropriate stuff for the whole HTML page, or a
    # particular CSV table.
    # ==========================================================================
    if "download_csv" in request.values:
        download_content = request.values['download_content']

        if download_content == 'discount_code_search':

            csv_rows = [ [ 'Name', 'Company', 'Title', 'Registration Type', 'Status', 'Registration Date' ] ]

            if redeemed_codes['discount_code_data'] != {}:
                for attendee in redeemed_codes['redemptions']:
                    csv_rows.append( [
                        attendee.get( 'name', '' ).encode( 'utf-8' ),
                        attendee.get( 'company', '' ).encode( 'utf-8' ),
                        attendee.get( 'title', '' ).encode( 'utf-8' ),
                        attendee.get( 'registration_type', '' ),
                        attendee.get( 'status', '' ),
                        attendee.get( 'registration_date', '' ) ] )

            download_filename = "sponsor-attendees-%s.csv" % ( datetime.datetime.now().strftime( "%Y-%m-%d-%H%M%S"  ) )

            si = StringIO.StringIO()
            writer = csv.writer( si )
            for row in csv_rows:
                writer.writerow( row )
            output = make_response( si.getvalue() )
            output.headers["Content-Disposition"] = "attachment; filename=%s" % ( download_filename )
            output.headers["Content-type"] = "text/csv"
            return output

        else:
            raise Exception( "Unknown download_content type: %s requested." % ( download_content ) )

    else:
        if 'code' in request.values:
            flash( 'Showing data for discount code: %s' % ( request.values['code'].strip() ) )

        return render_template( "discount_code.html", redeemed_codes=redeemed_codes )

@app.route( '/code_summary/', methods=[ 'GET' ] )
@app.route( '/code_summary/<only_code>', methods=[ 'GET' ] )
def code_summary( only_code=None ):
    '''Admin only - return a summary of all codes for input into RegOnline.'''
    
    if only_code is not None:
        only_code = only_code.strip().lower()
    
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
        registration_type = discount_code['badge_type']
        if registration_type in [ 'student_10', 'student_15', 'student_20' ]:
            if discount_code.get( 'ID', '' )[-4:] != 'spay':
                registration_type = 'student_discount'
            else:
                registration_type = 'student_full'

        if registration_type in codes_by_type:
            codes_by_type[registration_type] += ",%s=%s(%d)" % ( discount_code['discount_code'], discount_code['regonline_str'], discount_code['quantity'] )

            if get_date( last_updated_by_type[registration_type] ) < get_date( discount_code['created_date'] ):
                last_updated_by_type[registration_type] = discount_code['created_date']
        else:
            codes_by_type[registration_type] = "%s=%s(%d)" % ( discount_code['discount_code'], discount_code['regonline_str'], discount_code['quantity'] )
            last_updated_by_type[registration_type] = discount_code['created_date']

            
    if only_code in badge_types or only_code == 'student':
        # DEBUG - Disable this logic now that we're partitioning full and student discounts.
        #if only_code and only_code in [ 'student', 'student_full', 'student_10', 'student_15', 'student_20' ]:
        #    only_code = [ 'student_full', 'student_10', 'student_15', 'student_20' ]
        #else:
        #    only_code = [ only_code ]
        

        template = "only_code.html"
        code_summary = sorted( [ { "label" : v['name'], "regonline_code_string" : codes_by_type.get( k, '' ), "last_updated" : last_updated_by_type.get( k, 'N/A' ) } for k, v in badge_types.items() if k in only_code ] )
    else:
        template = "code_summary.html"
        # This is how we used to handle things when we didn't partition full student discounts.
        # code_summary = sorted( [ { "label" : v['name'], "regonline_code_string" : codes_by_type.get( k, '' ), "last_updated" : last_updated_by_type.get( k, 'N/A' ) } for k, v in badge_types.items() if k not in [ 'student_10', 'student_15', 'student_20' ] ] )
        code_summary = sorted( [ { "label" : v['name'], "regonline_code_string" : codes_by_type.get( k, '' ), "last_updated" : last_updated_by_type.get( k, 'N/A' ) } for k, v in badge_types.items() if k not in [ 'student_10', 'student_15', 'student_20' ] ] )

    return render_template( template, code_summary=code_summary )

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

        if sponsors_by_id.get( discount_code['SponsorID'], None ) is None:
            log.error( json.dumps( { "message" : "Found discount code for SponsorID: %s, but no such sponsor exists!  Discount code is: %s" % ( discount_code['SponsorID'], discount_code ) } ) )
            continue

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
        elif discount_code['code_source'].startswith( 'Bulk' ):
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
    '''Admin only, summarises all registration counts and sponsor data.'''

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
            #email_recipients = app.config['ADMIN_MAIL_RECIPIENTS']

            mail_message = Message( "Grace Hopper Celebration 2015 Registration Codes",
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
            if app.config['SEND_EMAIL']:
                mail.send( mail_message )
            else:
                log.debug( json.dumps( { 'message' : 'Skipping sending of email to %s due to SEND_EMAIL configuration.' % ( email_recipients ) } ) )
            mail_sent = True
        except Exception as e:
            flash( "ERROR occurred while trying to send registration code summary to: %s." % ( email_recipients ) )

        if mail_sent:
            success_message = "Registration summary email sent to: %s" % ( email_recipients )
            flash( success_message )

    # ==========================================================================
    # Handle the case where we are deleting a code.
    if "delete_code" in request.values:
        delete_discount_code = request.values['delete_discount_code'].lower().strip()

        dc = [ x for x in discount_codes if x['discount_code'] == delete_discount_code ]

        if len( dc ) == 0:
            flash( "Error, no code found to delete for: %s" % ( delete_discount_code ) )
        elif len( dc ) > 1:
            flash( "Error, more than one code found to delete for: %s, contact reporting tool administrator." % ( delete_discount_code ) )
        else:
            dc = dc[0]

            data = {
                'discount_code'      : delete_discount_code,
                'eventID'   : app.config['SPONSOR_EVENT'],
                'api_key' : app.config['APP_KEY']
            }

            deletion_status = requests.post( "%s/data/discount_code/delete/" % ( app.config['APP_SERVER'] ), json.dumps( data ) ).json()

            message = ""

            if 'success' in deletion_status and deletion_status['success']:
                message = "Discount code %s deleted." % ( delete_discount_code )
                flash( message )
                discount_codes = [ x for x in discount_codes if x['discount_code'] != delete_discount_code ]
            else:
                message = "Failed to delete discount code: %s, error was: %s" % ( delete_discount_code, deletion_status.get( 'error', 'Internal Error' ) )
                flash( message )

            mail_sent = False
            try:
                email_recipients = app.config['ADMIN_MAIL_RECIPIENTS']

                mail_message = Message( message,
                                        sender = app.config['SEND_AS'],
                                        recipients = email_recipients )

                for discount_code in [ dc ]:
                    discount_code['badge_type_name'] = badge_types[discount_code['badge_type']]['name']
                    discount_code['regonline_url'] = badge_types[discount_code['badge_type']]['regonline_url']
                
                mail_message.html = render_template( "email_discount_code_delete.html", data={
                    'sponsor'        : [ x for x in sponsors if x['ID'] == dc['SponsorID']][0],
                    'message'        : message,
                    'discount_codes' : [ dc ] } )

                mail.init_app( app )

                if app.config['SEND_EMAIL']:
                    mail.send( mail_message )
                else:
                    log.debug( json.dumps( { 'message' : 'Skipping sending of email to %s due to SEND_EMAIL configuration.' % ( email_recipients ) } ) )
            except Exception as e:
                flash( "ERROR %s occurred while trying to send discount code deletion notice to: %s." % ( e, email_recipients ) )

                # Note - we set this to true even when we're not
                # actually sending mail due to configuration, as this
                # controls website messaging, and we want it to appear
                # we're sending email even during testing.
                mail_sent = True

            if mail_sent:
                success_message = "Registration code deletion notification sent to: %s" % ( email_recipients )
                flash( success_message )


    # ==========================================================================
    # Now display all the summary data.

    # Attendees who did not redeem a code.
    nonsponsored = 0
    # Attendees who did reserve a code, but it's not a reserved code.
    nonreserved = 0
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

    # We want a report that breaks down things by discount code type.
    # The discount code type is the tuple of: ( badge_type,
    # regonline_str )
    discount_code_types = {}

    # Used to compute redeemed / available for each particular sponsor
    # code.
    codes_by_sponsor = {}

    for discount_code in discount_codes:
        if sponsors_by_id.get( discount_code['SponsorID'], None ) is None:
            log.error( json.dumps( { "message" : "Found discount code for SponsorID: %s, but no such sponsor exists!  Discount code is: %s" % ( discount_code['SponsorID'], discount_code ) } ) )
            continue

        discounts_by_code[discount_code['discount_code']] = discount_code

        if discount_code['SponsorID'] in codes_by_sponsor:
            codes_by_sponsor[discount_code['SponsorID']].append( discount_code )
        else:
            codes_by_sponsor[discount_code['SponsorID']] = [ discount_code ]


        registration_type = discount_code['badge_type']
        if registration_type in [ 'student_10', 'student_15', 'student_20' ]:
            if discount_code.get( 'ID', '' )[-4:] != 'spay':
                registration_type = 'student_discount'
            else:
                registration_type = 'student_full'

        discount_code_type = ( registration_type, discount_code['regonline_str'] )
        if discount_code_type in discount_code_types:
            discount_code_types[discount_code_type]['quantity'] += discount_code['quantity']
        else:
            discount_code_types[discount_code_type] = { 
                'quantity' : discount_code['quantity'],
                'is_reserved' : "%s" % ( badge_types[registration_type].get( 'reserve_spot', True ) ),
                'cost' : badge_types[registration_type].get( 'cost', 0 ) * float( 100 + int( discount_code['regonline_str'][:-1] ) ) / 100 ,
                'redeemed' : 0
            }

        if registration_type in badge_types:
            if badge_types[registration_type]['reserve_spot']:
                quantity += int( discount_code['quantity'] )

                sponsor_reporting_group = sponsor_reporting_groups.get( sponsors_by_id[discount_code['SponsorID']]['RegistrationType'], 'Other Sponsored' )
                if sponsor_reporting_group in group_attendee_stats:
                    group_attendee_stats[sponsor_reporting_group]['quantity'] += discount_code['quantity']
                else:
                    group_attendee_stats[sponsor_reporting_group] = { 'quantity' : discount_code['quantity'],
                                                                      'redeemed' : 0 }
        else:
            logging.warning( json.dumps( { 'message' : 'Unknown badge_type: %s found in discount codes.' % ( registration_type ) } ) )

    redemptions_by_code = {}

    for registrant in registrants:
        if registrant['discount_code']:

            discount_code = discounts_by_code.get( registrant['discount_code'], {} )

            # Only count up codes that match to an existing discount
            # code.
            if discount_code.get( 'badge_type', False ):

                registration_type = discount_code['badge_type']
                if registration_type in [ 'student_10', 'student_15', 'student_20' ]:
                    if discount_code.get( 'ID', '' )[-4:] != 'spay':
                        registration_type = 'student_discount'
                    else:
                        registration_type = 'student_full'

                discount_code_type = ( registration_type, discount_code['regonline_str'] )
                if discount_code_type in discount_code_types:
                    discount_code_types[discount_code_type]['redeemed'] += 1

            if discount_code.get( 'badge_type', None ) in badge_types:

                registration_type = discount_code['badge_type']
                if registration_type in [ 'student_10', 'student_15', 'student_20' ]:
                    if discount_code.get( 'ID', '' )[-4:] != 'spay':
                        registration_type = 'student_discount'
                    else:
                        registration_type = 'student_full'

                if badge_types[registration_type]['reserve_spot']:
                    sponsor_reporting_group = 'Other Sponsored'
                    if 'SponsorID' in discount_code:
                        if discount_code['SponsorID'] in sponsors_by_id:
                            if sponsors_by_id[discount_code['SponsorID']]['RegistrationType'] in sponsor_reporting_groups:
                                sponsor_reporting_group = sponsor_reporting_groups[sponsors_by_id[discount_code['SponsorID']]['RegistrationType']]
          
                    redeemed += 1
                    group_attendee_stats[sponsor_reporting_group]['redeemed'] += 1
                else:
                    nonreserved += 1

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

    for discount_code_type, stats in discount_code_types.items():
        stats['allotted'] = stats['quantity'] - stats['redeemed']
            
    for sponsor, codes in codes_by_sponsor.items():
        for code in codes:
            if code['discount_code'] in redemptions_by_code:
                code['redeemed'] = redemptions_by_code[code['discount_code']]
                code['available'] = code['quantity'] - redemptions_by_code[code['discount_code']]
            else:
                code['available'] = code['quantity']

    sponsors.sort( key=lambda x: x['Company'] )

    for sponsor in sponsors:
        sponsor['discount_codes'] = sorted( codes_by_sponsor.get( sponsor['ID'], [] ), key=lambda x: x['discount_code'] )

    #import pdb
    #pdb.set_trace()

    registration_summary = {
        "sponsors" : sponsors,
        "reserved" : quantity - redeemed,
        "redeemed" : redeemed,
        "nonsponsored" : nonsponsored,
        "nonreserved" : nonreserved,
        "registered" : nonsponsored + redeemed + nonreserved,
        "group_attendee_stats" : [ { "name" : k, "data" : group_attendee_stats[k] } for k in sorted( group_attendee_stats.keys() ) ],
        "discount_type_stats" : [ { "name" : "%s %s" % ( k ), "data" : discount_code_types[k] } for k in sorted( discount_code_types.keys() ) ],
        "badge_type_names" : [ { "value" : k, "name" : badge_types[k]['name'] } for k in sorted( badge_types.keys() ) ]
    }

    # ==========================================================================
    # Return the appropriate stuff for the whole HTML page, or a
    # particular CSV table.
    # ==========================================================================

    if "download_csv" in request.values:
        download_content = request.values['download_content']

        if download_content == 'registration_summary':

            csv_rows = [ [ 'Company Name', 'Contact Email', 'Sponsorship', 'Registration code', 'Registration code Report URL', 'Registration code Redemption URL', 'Total', 'Redeemed', 'Unused' ] ]

            for sponsor in registration_summary['sponsors']:
                for discount_code in sponsor['discount_codes']:
                    csv_rows.append( [
                        sponsor.get( 'Company', '' ).encode( 'utf-8' ),
                        sponsor.get( 'Email', '' ).encode( 'utf-8' ),
                        sponsor.get( 'RegistrationType', '' ),
                        discount_code.get( 'discount_code', '' ),
                        "%s%s?code=%s" % ( app.config['EXTERNAL_SERVER_BASE_URL'], url_for( 'discount_code' ), discount_code.get( 'discount_code', '' ) ),
                        badge_types[discount_code['badge_type']]['regonline_url'],
                        discount_code.get( 'quantity', 0 ),
                        discount_code.get( 'redeemed', 0 ),
                        discount_code.get( 'available', 0 ) ] )
            
            download_filename = "registration-summary-%s.csv" % ( datetime.datetime.now().strftime( "%Y-%m-%d-%H%M%S"  ) )

        else:
            raise Exception( "Unknown download_content type: %s requested." % ( download_content ) )
                             
        si = StringIO.StringIO()
        writer = csv.writer( si )
        for row in csv_rows:
            writer.writerow( row )
        output = make_response( si.getvalue() )
        output.headers["Content-Disposition"] = "attachment; filename=%s" % ( download_filename )
        output.headers["Content-type"] = "text/csv"
        return output
    else:
        return render_template( "registration_summary.html", registration_summary=registration_summary )

@app.route( '/sponsor_summary/', methods=[ 'GET', 'POST' ] )
def sponsor_summary():
    '''Will eventually be limited to particular sponsors, right now admin only.'''

    sponsor_email = None
    if 'sponsor_email' in request.values:
        if validate_email( request.values['sponsor_email'].strip().lower() ):
            sponsor_email = request.values['sponsor_email'].strip().lower()

    data = {
        'eventID' : app.config['SPONSOR_EVENT'],
        'api_key' : app.config['APP_KEY']
    }
    sponsors = [ x for x in requests.post( "%s/data/sponsors/" % ( app.config['APP_SERVER'] ), json.dumps( data ) ).json()['sponsors'] if ( x['Email'].strip().lower() == sponsor_email or x['CCEmail'].strip().lower() == sponsor_email ) ]
    sponsors_by_id = { x['ID']:x for x in sponsors }

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
            #email_recipients = app.config['ADMIN_MAIL_RECIPIENTS']

            mail_message = Message( "Grace Hopper Celebration 2015 Registration Codes",
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
            if app.config['SEND_EMAIL']:
                mail.send( mail_message )
            else:
                log.debug( json.dumps( { 'message' : 'Skipping sending of email to %s due to SEND_EMAIL configuration.' % ( email_recipients ) } ) )
            mail_sent = True
        except Exception as e:
            flash( "ERROR occurred while trying to send registration code summary to: %s. %s" % ( email_recipients, e ) )

        if mail_sent:
            success_message = "Registration summary email sent to: %s" % ( email_recipients )
            flash( success_message )

    # ==========================================================================
    # Now display all the summary data.

    # Attendees who did not redeem a code.
    nonsponsored = 0
    # Attendees who redeemed a code, but the code is not reserved.
    nonreserved = 0
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
        if sponsors_by_id.get( discount_code['SponsorID'], None ) is None:
            log.error( json.dumps( { "message" : "Found discount code for SponsorID: %s, but no such sponsor exists!  Discount code is: %s" % ( discount_code['SponsorID'], discount_code ) } ) )
            continue

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
                else:
                    nonreserved += 1

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
            else:
                code['available'] = code['quantity']

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

    # ==========================================================================
    # Return the appropriate stuff for the whole HTML page, or a
    # particular CSV table.
    # ==========================================================================

    sponsor_summary = {
        "sponsor_email"        : sponsor_email,
        "sponsors"             : sponsors,
        "reserved"             : quantity - redeemed,
        "redeemed"             : redeemed,
        "nonsponsored"         : nonsponsored,
        "nonreserved"          : nonreserved,
        "registered"           : nonsponsored + redeemed + nonreserved,
        "group_attendee_stats" : [ { "name" : k, "data" : group_attendee_stats[k] } for k in sorted( group_attendee_stats.keys() ) ],
        "badge_type_names"     : [ { "value" : k, "name" : badge_types[k]['name'] } for k in sorted( badge_types.keys() ) ],
        "registrants"          : public_registrants
    }

    if "download_csv" in request.values:
        download_content = request.values['download_content']

        if download_content == 'sponsor_summary_sponsors':

            csv_rows = [ [ 'Company Name', 'Contact Email', 'Sponsorship', 'Registration code', 'Registration code Report URL', 'Registration code Redemption URL', 'Total', 'Redeemed', 'Unused' ] ]

            for sponsor in sponsor_summary['sponsors']:
                for discount_code in sponsor['discount_codes']:
                    csv_rows.append( [
                        sponsor.get( 'Company', '' ).encode( 'utf-8' ),
                        sponsor.get( 'Email', '' ).encode( 'utf-8' ),
                        sponsor.get( 'RegistrationType', '' ),
                        discount_code.get( 'discount_code', '' ),
                        "%s%s?code=%s" % ( app.config['EXTERNAL_SERVER_BASE_URL'], url_for( 'discount_code' ), discount_code.get( 'discount_code', '' ) ),
                        badge_types[discount_code['badge_type']]['regonline_url'],
                        discount_code.get( 'quantity', 0 ),
                        discount_code.get( 'redeemed', 0 ),
                        discount_code.get( 'available', 0 ) ] )
            
            download_filename = "sponsor-summary-%s.csv" % ( datetime.datetime.now().strftime( "%Y-%m-%d-%H%M%S"  ) )

        elif download_content == 'sponsor_summary_registrants':
            csv_rows = [ [ 'Name', 'Company', 'Title', 'Registration Type', 'Status', 'Registration Date' ] ]

            for attendee in sponsor_summary['registrants']:
                csv_rows.append( [
                    attendee.get( 'name', '' ).encode( 'utf-8' ),
                    attendee.get( 'company', '' ).encode( 'utf-8' ),
                    attendee.get( 'title', '' ).encode( 'utf-8' ),
                    attendee.get( 'registration_type', '' ),
                    attendee.get( 'status', '' ),
                    attendee.get( 'registration_date', '' ) ] )

            download_filename = "sponsor-attendees-%s.csv" % ( datetime.datetime.now().strftime( "%Y-%m-%d-%H%M%S"  ) )

        else:
            raise Exception( "Unknown download_content type: %s requested." % ( download_content ) )
                             
        si = StringIO.StringIO()
        writer = csv.writer( si )
        for row in csv_rows:
            writer.writerow( row )
        output = make_response( si.getvalue() )
        output.headers["Content-Disposition"] = "attachment; filename=%s" % ( download_filename )
        output.headers["Content-type"] = "text/csv"
        return output

    else:
        if 'sponsor_email' in request.values:
            if len( sponsors ) == 0:
                flash( "No data found for sponsor email: %s" % ( request.values['sponsor_email'].strip() ) )
            else:
                flash( 'Showing data for sponsor email: %s' % ( request.values['sponsor_email'].strip() ) )

        return render_template( "sponsor_summary.html", sponsor_summary=sponsor_summary )

if __name__ == '__main__':
    app.run( port=app.config['PORT'] )

