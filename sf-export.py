#!/usr/bin/env python

from collections import Counter
import datetime
from optparse import OptionParser
import json
import pytz
from simple_salesforce import Salesforce
import time

from datastore import get_sponsors, get_registrants, set_sponsors, set_registrants, get_discount_codes, set_discount_codes

from discount_codes import get_badge_type

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


from flask import Flask
app = Flask( __name__ )
app.config.from_pyfile( "./config/present.default.conf" )

sponsor_event_id = app.config['SPONSOR_EVENT'] 

def sync_salesforce():
    sf = Salesforce(  instance='test.salesforce.com', username='matt@viblio.com', password='e6IoNyQ8jihZLWlf', security_token='C4N1vrEFXwGYOcz0lQ3c6waRs', sandbox=True, version='32.0' )

    # Actual production sponsors.
    sponsors = get_sponsors( sponsor_event_id )

    discount_codes = get_discount_codes( sponsor_event_id )

    # Make a data structure for comparing discount codes:
    old_codes_by_sponsor = {}
    for code in discount_codes:
        if code['SponsorID'] in old_codes_by_sponsor:
            old_codes_by_sponsor[code['SponsorID']].append( code )
        else:
            old_codes_by_sponsor[code['SponsorID']] = [ code ]

    for sponsor in sponsors[:10]:
        sreg = sf.query_all( "SELECT id, opportunity__c FROM Registrations__c WHERE Confirmation_Number__c = '%s' AND Event_Number__c = '%s'" % ( sponsor['ID'], sponsor_event_id ) )

        # DEBUG - Re-enable this once we are working off real data, not sandbox data.
        #if sreg['totalSize'] != 1:
        #    raise Exception( "Expected 1 sponsorship for sponsor %s at event %s, but got %d" % ( sponsor['ID'], sponsor_event_id, sreg['totalSize'] ) )
        # Remove this once doing real testing.
        if sreg['totalSize'] != 1:
            print "Skipping sponsor %s as they did not have exactly one registration." % ( sponsor['ID'] )
            continue

        old_codes = old_codes_by_sponsor.get( sponsor['ID'], [] )
        new_codes = []

        opportunity_id = sreg['records'][0]['Opportunity__c']
        print "Working on opportunity %s" % ( opportunity_id )

        oli = sf.query_all( "SELECT id, (Select id, discount_code__c, registrant_type__c, redeemable_quantity__c, percent_off__c, quantity, product2.name, CreatedDate from OpportunityLineItems) FROM Opportunity WHERE id = '%s'" % ( opportunity_id ) )

        if oli['totalSize'] != 1:
            raise Exception( "Expected 1 opportunity for opportunity ID %s, sponsor %s at event %s, but got %d" % ( opportunity_id, sponsor['ID'], sponsor_event_id, sreg['totalSize'] ) )

        lis = oli['records'][0]['OpportunityLineItems']

        for li in lis['records']:
            if li.get( 'Discount_Code__c', None ) is not None and li['Registrant_Type__c'] is not None:
                try:
                    discount_id = li['Discount_Code__c']
                    sponsor_id = sponsor['ID']
                    attendee_event_id = app.config['REGISTRANT_EVENT']
                    # DEBUG - we should be getting this from salesforce.com
                    #attendee_event_id = 'Not in SF?'
                    discount_code = li['Discount_Code__c']
                    badge_type = get_badge_type( sponsor_event_id, li['Registrant_Type__c'], li['Percent_off__c'] )
                    quantity = li['Redeemable_Quantity__c']
                    code_source = li['Product2']['Name']
                    percent_off = li['Percent_off__c']
                    created_date = li['CreatedDate']
                    
                    new_codes.append( {
                    'ID' : discount_id,
                        'SponsorID' : sponsor['ID'],
                        'RegTypeID' : sponsor['RegTypeID'],
                        'RegistrationType' : sponsor['RegistrationType'],
                        'discount_code' : discount_code,
                        'quantity' : int( quantity ),
                        'badge_type' : badge_type,
                        'code_source' : sponsor['RegistrationType'],
                        'regonline_str' : "-%d%%" % ( int( percent_off ) ),
                        'created_date' : pytz.utc.localize( datetime.datetime.strptime( created_date, "%Y-%m-%dT%H:%M:%S.000+0000" ) ).strftime( "%a, %d %b %Y %H:%M:%S %Z" )
                    } )
                except Exception as e:
                    print "Failed to process line item: %s because of %s proceeding." % ( li, e )
                    
        granted_codes = Counter( [ code['ID'] for code in old_codes ] ) 
        entitled_codes = Counter( [ code['ID'] for code in new_codes ] )

        if ( entitled_codes - granted_codes ) != Counter():
            # We were granted new codes, send an email.
            print "NOTIFICATION: Sponsor %s has: %s new codes" % ( sponsor['ID'], entitled_codes - granted_codes )
            discount_codes += [ x for x in new_codes if x['ID'] in entitled_codes - granted_codes ]
        elif ( granted_codes - entitled_codes ) != Counter():
            # Somehow this sponsor has too much, complain.
            print "ERROR: Sponsor %s has: %s extra entitlements." % ( sponsor['ID'], granted_codes - entitled_codes )
        else:
            # All is well, nothing to do.
            print "Sponsor %s's current grants match its entitlements." % ( sponsor['ID'] )
            
    # DEBUG
    print new_codes

    # Persist discount codes to disk.
    set_discount_codes( sponsor_event_id, discount_codes )

if __name__ == "__main__":
    usage = "usage: %prog [-r registrant_event_id] [-s sponsor_event_id] [-c] [-f 900]"
    parser = OptionParser( usage = usage )
    parser.add_option( "-r", "--registrant-event-id",
                       dest = "registrants_id",
                       help = "The RegOnline event ID for registrants." )
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
    registrants_id = 1702108
    if options.registrants_id:
        registrants_id = int( options.registrants_id )
        
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
            log.info( json.dumps( { 'message' : "Sycnging with salesforce.com" } ) )
            sync_salesforce()
        except Exception as e:
            log.error( json.dumps( { 'message' : "Failed to sync discount code data with salesforce.com, error was: %s" % ( e ) } ) )

        if continuous:
            keep_going = True
            log.info( json.dumps( { 'message' : "Sleeping for %d seconds" % ( sleep_duration ) } ) )
            time.sleep( sleep_duration )


