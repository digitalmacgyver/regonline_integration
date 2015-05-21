#!/usr/bin/env python

from bdateutil import relativedelta
from collections import Counter
import datetime
from optparse import OptionParser
import json
import pytz
from simple_salesforce import Salesforce
import time

from datastore import get_sponsors, get_registrants, set_sponsors, set_registrants, get_discount_codes, set_discount_codes

from discount_codes import get_badge_type, get_badge_types

import logging
import logging.handlers
logging.basicConfig( level=logging.INFO )
logging.getLogger( 'suds.client' ).setLevel( logging.WARNING )

log = logging.getLogger( __name__ )
log.setLevel( logging.DEBUG )

syslog = logging.handlers.SysLogHandler( address="/dev/log" )

format_string = 'sf-export.py: { "name" : "%(name)s", "module" : "%(module)s", "lineno" : "%(lineno)s", "funcName" : "%(funcName)s", "level" : "%(levelname)s", "message" : %(message)s }'

sys_formatter = logging.Formatter( format_string )

syslog.setFormatter( sys_formatter )
syslog.setLevel( logging.INFO )
consolelog = logging.StreamHandler()
consolelog.setLevel( logging.DEBUG )

log.addHandler( syslog )
log.addHandler( consolelog )

from flask import Flask, render_template
from flask_mail import Mail, Message
app = Flask( __name__ )
app.config.from_pyfile( "./config/present.default.conf" )
mail =  Mail()

default_sponsor_event_id = app.config['SPONSOR_EVENT'] 

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
    SF_PASSWORD = get_password( app.config['SF_PASSWORD_FILE'] ),
    SF_TOKEN = get_password( app.config['SF_TOKEN_FILE'] ),
    MAIL_PASSWORD = get_password( app.config['MAIL_PASSWORD_FILE'] )
)

def sync_salesforce( sponsor_event_id=default_sponsor_event_id, sponsors=None ):
    sf = Salesforce(  instance=app.config['SF_INSTANCE'], 
                      username=app.config['SF_USER'],
                      password=app.config['SF_PASSWORD'],
                      security_token=app.config['SF_TOKEN'],
                      sandbox=app.config['SF_SANDBOX'],
                      version='32.0' )

    badge_types = get_badge_types( sponsor_event_id )

    # Actual production sponsors.
    if sponsors is None:
        sponsors = get_sponsors( sponsor_event_id )

    discount_codes = get_discount_codes( sponsor_event_id )

    discount_codes_by_id = { x['ID']:x for x in discount_codes }

    # Make a data structure for comparing discount codes:
    old_codes_by_sponsor = {}
    for code in discount_codes:
        if code['SponsorID'] in old_codes_by_sponsor:
            old_codes_by_sponsor[code['SponsorID']].append( code )
        else:
            old_codes_by_sponsor[code['SponsorID']] = [ code ]

    for sponsor in sponsors:
        log.debug( json.dumps( { 'message' : "Working on sponsor %s" % ( sponsor['ID'] ) } ) ) 

        sreg = sf.query_all( "SELECT id, opportunity__c FROM Registrations__c WHERE Confirmation_Number__c = '%s' AND Event_Number__c = '%s'" % ( sponsor['ID'], sponsor_event_id ) )

        if sreg['totalSize'] == 0:
            log.warning( json.dumps( { 'message' : "Skipping sponsor %s as they did not have any salesforce opportunities." % ( sponsor['ID'] ) } ) )
            continue
        elif sreg['totalSize'] > 1:
            message = "Expected 1 sponsorship for sponsor %s at event %s, but got %d" % ( sponsor['ID'], sponsor_event_id, sreg['totalSize'] )
            log.error( json.dumps( { 'message' : message } ) )
            raise Exception( message )

        old_codes = old_codes_by_sponsor.get( sponsor['ID'], [] )
        new_codes = []
        new_codes_by_id = {}

        opportunity_id = sreg['records'][0]['Opportunity__c']
        log.debug( json.dumps( { 'message' : "Working on opportunity %s" % ( opportunity_id ) } ) )

        oli = sf.query_all( "SELECT id, (Select id, discount_code__c, registrant_type__c, redeemable_quantity__c, percent_off__c, quantity, product2.name, CreatedDate, redeemable_event_id__c from OpportunityLineItems) FROM Opportunity WHERE id = '%s'" % ( opportunity_id ) )

        if oli['totalSize'] != 1:
            raise Exception( "Expected 1 opportunity for opportunity ID %s, sponsor %s at event %s, but got %d" % ( opportunity_id, sponsor['ID'], sponsor_event_id, sreg['totalSize'] ) )

        lis = oli['records'][0]['OpportunityLineItems']

        if lis is None:
            log.debug( json.dumps( { 'message' : "No line items for opporunity: %s, skipping." % ( opportunity_id ) } ) )
            continue

        for li in lis['records']:
            if li.get( 'Discount_Code__c', None ) is not None and li['Registrant_Type__c'] is not None:
                try:
                    discount_id = li['Discount_Code__c']
                    sponsor_id = sponsor['ID']
                    # DEBUG
                    #attendee_event_id = app.config['REGISTRANT_EVENT']
                    attendee_event_id = li['Redeemable_Event_Id__c']
                    discount_code = li['Discount_Code__c']
                    badge_type = get_badge_type( sponsor_event_id, li['Registrant_Type__c'], li['Percent_off__c'] )
                    quantity = li['Redeemable_Quantity__c']
                    code_source = li['Product2']['Name']
                    percent_off = li['Percent_off__c']
                    created_date = li['CreatedDate']
                    
                    if code_source not in [ 'Enterprise Pack', 'Bulk Purchase' ]:
                        code_source = sponsor['RegistrationType']

                    new_code = {
                        'ID' : discount_id,
                        'SponsorID' : sponsor['ID'],
                        'RegTypeID' : sponsor['RegTypeID'],
                        'RegistrationType' : sponsor['RegistrationType'],
                        'discount_code' : discount_code,
                        'quantity' : int( quantity ),
                        'badge_type' : badge_type,
                        'code_source' : code_source,
                        'regonline_str' : "-%d%%" % ( int( percent_off ) ),
                        'created_date' : pytz.utc.localize( datetime.datetime.strptime( created_date, "%Y-%m-%dT%H:%M:%S.000+0000" ) ).strftime( "%a, %d %b %Y %H:%M:%S %Z" )
                    }

                    new_codes.append( new_code )

                    new_codes_by_id[discount_id] = new_code
                except Exception as e:
                    log.error( json.dumps( { 'message' : "Failed to process line item: %s due to error %s proceeding." % ( li, e ) } ) )

        granted_codes = Counter( [ code['ID'] for code in old_codes ] ) 
        entitled_codes = Counter( [ code['ID'] for code in new_codes ] )

        added_entitlements = [ new_codes_by_id[x] for x in entitled_codes - granted_codes ]
        extra_entitlements = [ discount_codes_by_id[x] for x in granted_codes - entitled_codes ]
        upgraded_entitlements = []
        downgraded_entitlements = []
        for discount_id in entitled_codes:
            if discount_id in discount_codes_by_id:
                new_code = new_codes_by_id[discount_id]
                old_code = discount_codes_by_id[discount_id]
                
                if new_code['quantity'] > old_code['quantity']:
                    upgraded_entitlements.append( { 'new_code' : new_code, 
                                                    'old_code' : old_code } )
                elif new_code['quantity'] < old_code['quantity']:
                    downgraded_entitlements.append( { 'new_code' : new_code, 
                                                    'old_code' : old_code } )


        if len( added_entitlements ) or len( upgraded_entitlements ):
            for code_pair in upgraded_entitlements:
                new_code = code_pair['new_code']
                old_code = code_pair['old_code']
                
                discount_codes = [ x for x in discount_codes if x['ID'] != old_code['ID'] ]
                discount_codes.append( new_code )
                discount_codes_by_id[old_code['ID']] = new_code

            discount_codes += added_entitlements
            for entitlement in added_entitlements:
                discount_codes_by_id[entitlement['ID']] = entitlement

            # We were granted new codes, send an email.
            log.info( json.dumps( { 'message' : "NOTIFICATION: Sponsor %s has: %s new codes and %s upgraded_codes" % ( sponsor['ID'], entitled_codes - granted_codes, upgraded_entitlements ) } ) )

            # Send an email to the sponsor contacts about their new code.
            recipients = []
            if 'Email' in sponsor and len( sponsor['Email'] ):
                recipients.append( sponsor['Email'] )
            if 'CCEmail' in sponsor and len( sponsor['CCEmail'] ):
                recipients.append( sponsor['CCEmail'] )
        
            error_message = None
            if len( recipients ) == 0:
                # If there are no sponsor emails, send the admins a note.
                error_message = "ERROR, NO RECIPIENTS AVAILABLE FOR SPONSOR %d" % ( sponsor['ID'] )

            try:
                # DEBUG actually send to recipients here
                #email_recipients = app.config['ADMIN_MAIL_RECIPIENTS'] + recipients
                email_recipients = app.config['ADMIN_MAIL_RECIPIENTS']

                today = datetime.date.today()
                today_4pm = datetime.datetime( today.year, today.month, today.day, 16, tzinfo=pytz.timezone( 'PST8PDT' ) )
                tomorrow_4pm = today_4pm + relativedelta( bdays = +1 )
                when = tomorrow_4pm.astimezone( pytz.utc )

                extra_headers = {
                    'X-MC-SendAt' : when.strftime( "%Y-%m-%d %H:%M:%S" )
                }

                mail_message = Message( "Grace Hopper Celebration 2015 Discount Codes",
                                        sender = app.config['SEND_AS'],
                                        recipients = email_recipients,
                                        bcc = app.config['ADMIN_MAIL_RECIPIENTS'], 
                                        extra_headers = extra_headers )
        
                mail_codes = []
                for discount_code in sorted( [ y for y in discount_codes if y['SponsorID'] == sponsor['ID'] ], 
                                             key = lambda x: x['discount_code'] ):
                    discount_code['badge_type_name'] = badge_types[discount_code['badge_type']]['name']
                    discount_code['regonline_url'] = badge_types[discount_code['badge_type']]['regonline_url']
                    
                    discount_code['discount_search_url'] = "%s/%s?code=%s" % ( app.config['EXTERNAL_SERVER_BASE_URL'], 'discount_code/', discount_code['discount_code'] )
                    mail_codes.append( discount_code )

                if len( mail_codes ) > 0:
                    with app.test_request_context():
                        mail_message.html = render_template( "email_discount_code_summary.html", data={
                            'error_message'  : error_message,
                            'sponsor'        : sponsor,
                            'discount_codes' : mail_codes } )

                        mail.init_app( app )
                        mail.send( mail_message )

            except Exception as e:
                logging.error( json.dumps( { 'message' : "Failed to send notification email to %s, error was: %s" % ( email_recipients, e ) } ) )

        elif len( extra_entitlements ) or len( downgraded_entitlements ):
            # Somehow this sponsor has too much, complain.
            log.warning( json.dumps( { 'message' : "Sponsor %s has: %s extra entitlements and %s downgraded entitlements." % ( sponsor['ID'], granted_codes - entitled_codes, downgraded_entitlements ) } ) )

            try:
                differences = [ { 'discount_code' : x['discount_code'],
                                  'code_source' : x['code_source'],
                                  'badge_type'  : x['badge_type'],
                                  'quantity'    : x['quantity'] } for x in extra_entitlements ]
                for code_pair in downgraded_entitlements:
                    new_code = code_pair['new_code']
                    old_code = code_pair['old_code']
                    differences.append( { 'discount_code' : x['discount_code'],
                                          'code_source' : new_code['code_source'],
                                          'badge_type'  : new_code['badge_type'],
                                          'quantity'    : old_code['quantity'] - new_code['quantity'] } )

                email_recipients = app.config['ADMIN_MAIL_RECIPIENTS']

                mail_message = Message( "Warning: Discount Code Mismatch for %s" % ( sponsor['Company'] ),
                                        sender = app.config['SEND_AS'],
                                        recipients = email_recipients )
            
                
                with app.test_request_context():
                    mail_message.html = render_template( "email_abi_admin_discount_mismatch.html", data={
                        'sponsor'          : sponsor,
                        'differences'      : differences } )
                    mail.init_app( app )
                    mail.send( mail_message )

            except Exception as e:
                logging.error( json.dumps( { 'message' : "Failed to send notification email to %s, error was: %s" % ( email_recipients, e ) } ) )


        else:
            # All is well, nothing to do.
            log.debug( json.dumps( { 'message' : "Sponsor %s's current grants match its entitlements." % ( sponsor['ID'] ) } ) )
 
        # DEBUG
        #print new_codes

    #import pdb
    #pdb.set_trace()

    # Check if there are any discount codes that do not have a sponsor any longer.
    sponsors_by_id = { x['ID']:x for x in sponsors }
    obsolete_codes = [ x for x in discount_codes if x['SponsorID'] not in sponsors_by_id ]

    if len( obsolete_codes ):
        obsolete_codes_by_id = { x['ID']:x for x in obsolete_codes }
        discount_codes = [ x for x in discount_codes if x['ID'] not in obsolete_codes_by_id ]

        # Send email notification.
        email_recipients = app.config['ADMIN_MAIL_RECIPIENTS']
        
        mail_message = Message( "Warning: Deleting Obsolete Discount Code for %s" % ( sponsor['Company'] ),
                                sender = app.config['SEND_AS'],
                                recipients = email_recipients )
        
        with app.test_request_context():
            mail_message.html = render_template( "email_abi_admin_obsolete_code.html", data={
                'obsolete_codes'      : obsolete_codes } )
            mail.init_app( app )
            mail.send( mail_message )
        
    # Persist discount codes to disk.
    set_discount_codes( sponsor_event_id, discount_codes )

if __name__ == "__main__":
    usage = "usage: %prog [-r registrant_event_id] [-s sponsor_event_id] [-c] [-f 900]"
    parser = OptionParser( usage = usage )
    parser.add_option( "-s", "--sponsor-event-id",
                       dest = "sponsors_id",
                       help = "The RegOnline event ID for sponsors." )
    parser.add_option( "-c", "--continuous",
                       dest = "continuous",
                       action = "store_true",
                       default = False,
                       help = "Run continuously, defaults to false." )
    parser.add_option( "-f", "--frequency",
                       dest = "sleep_duration",
                       help = "If running continuously, how many seconds to sleep between runs." )
    
    ( options, args ) = parser.parse_args()
    
    # GHC 2014
    #registrants_id = 1438441
    # Test 2015
    #registrants_id = 1702108
    #if options.registrants_id:
    #    registrants_id = int( options.registrants_id )
        
    # GHC 2014
    #sponsors_id = 1438449
    # GHC 2015
    sponsors_id = 1639610
    # Test event
    #sponsors_id = 1711768
    if options.sponsors_id:
        sponsors_id = int( options.sponsors_id )

    continuous = options.continuous

    sleep_duration = 900
    if options.sleep_duration:
        sleep = int( options.sleep_duration )

    keep_going = True

    while keep_going:
        keep_going = False
        # Get a list of all registrations for GHC 2014.
        try:
            log.info( json.dumps( { 'message' : "Sycning with salesforce.com" } ) )
            sync_salesforce( sponsors_id )
        except Exception as e:
            log.error( json.dumps( { 'message' : "Failed to sync discount code data with salesforce.com, error was: %s" % ( e ) } ) )

        if continuous:
            keep_going = True
            log.info( json.dumps( { 'message' : "Sleeping for %d seconds" % ( sleep_duration ) } ) )
            time.sleep( sleep_duration )


