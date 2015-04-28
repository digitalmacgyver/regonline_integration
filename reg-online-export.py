#!/usr/bin/env python

import datetime
import json
from optparse import OptionParser
import time

from suds.client import Client

import logging
import logging.handlers
logging.basicConfig( level=logging.INFO )
logging.getLogger( 'suds.client' ).setLevel( logging.WARNING )

log = logging.getLogger( __name__ )
log.setLevel( logging.DEBUG )

syslog = logging.handlers.SysLogHandler( address="/dev/log" )

format_string = 'reg-online-export.py: { "name" : "%(name)s", "module" : "%(module)s", "lineno" : "%(lineno)s", "funcName" : "%(funcName)s", "level" : "%(levelname)s", "message" : %(message)s }'

sys_formatter = logging.Formatter( format_string )

syslog.setFormatter( sys_formatter )
syslog.setLevel( logging.INFO )
consolelog = logging.StreamHandler()
consolelog.setLevel( logging.DEBUG )

log.addHandler( syslog )
log.addHandler( consolelog )

from datastore import get_sponsors, get_registrants, set_sponsors, set_registrants, get_discount_codes, set_discount_codes
from discount_codes import generate_discount_codes

regonline_api_key = '9mIRFe399oIBM0fnX5jxLtupSZlaizGgtHUEuDpUi34QWs66G6LxFDZ6wsdpgzCw'
regonline_wsdl = "https://www.regonline.com/api/default.asmx?WSDL"

def export_event_data( eventID, attendee_type ):
    client = Client( regonline_wsdl )
    token = client.factory.create( "TokenHeader" )
    token.APIToken = regonline_api_key
    client.set_options( soapheaders=token )

    discount_codes = []
    if attendee_type == 'registrants':
        attendees = get_registrants( eventID )
    elif attendee_type == 'sponsors':
        attendees = get_sponsors( eventID )
        discount_codes = get_discount_codes( eventID )
    else:
        error_message = "Unknown attendee type: '%s' - must be one of registrants or sponsors." % ( attendee_type )
        log.error( json.dumps( { 'message' : error_message } ) )
        raise Exception( error_message )

    attendee_ids = { x['ID']:x for x in attendees }

    log.info( json.dumps( { 'message' : "Getting registrations for eventID: %s" % ( eventID ) } ) )
    result = client.service.GetRegistrationsForEvent( eventID=eventID, filter=None, orderBy=None )

    new_attendees = result[1][0]

    # DEBUG For testing limit this to 10 attendees.
    for attendee in new_attendees:
        try:
            # First check if we're dealing with an updated attendee.
            if attendee['ID'] in attendee_ids and attendee['ModDate'] > attendee_ids[attendee['ID']].get( 'ModDate', datetime.datetime.min ):
                # Delete our old view of this attendee.
                log.info( json.dumps( { 'message' : ( "Deleting old version of attendee: %s" % ( attendee_ids[attendee['ID']] ) ).encode( 'utf-8' ) } ) )
                attendees = [ x for x in attendees if x['ID'] != attendee['ID'] ]
                attendee_ids.pop( attendee['ID'] )

            if attendee['ID'] not in attendee_ids:
                log.info( json.dumps( { 'message' : "Adding data for attendee: %s" % ( attendee['ID'] ) } ) )

                # We need to add this attendee.
                add_attendee = {
                    'ID'                : attendee['ID'],
                    'RegTypeID'         : attendee['RegTypeID'],
                    'StatusID'          : attendee['StatusID'],
                    'StatusDescription' : attendee['StatusDescription'].encode( 'utf-8' ),
                    'FirstName'         : attendee['FirstName'].encode( 'utf-8' ),
                    'LastName'          : attendee['LastName'].encode( 'utf-8' ),
                    'CancelDate'        : attendee['CancelDate'],
                    'IsSubstitute'      : attendee['IsSubstitute'],
                    'AddBy'             : attendee['AddBy'],
                    'AddDate'           : attendee['AddDate'],
                    'ModBy'             : attendee['ModBy'],
                    'ModDate'           : attendee['ModDate'],
                    'CCEmail'           : "",
                    'Company'           : "",
                    'Email'             : "",
                    'Phone'             : "",
                    'RegistrationType'  : "",
                    'Title'             : "",
                }

                optional_fields = [ 'CCEmail', 'Company', 'Email', 'Phone', 'RegistrationType', 'Title' ]
                for field in optional_fields:
                    if field in attendee and attendee[field] is not None:
                        add_attendee[field] = attendee[field].encode( 'utf-8' )

                if attendee_type == "registrants":
                    # Since they are a registrant we need to get some custom
                    # data about them.
                    
                    # Avoid rate limiting.
                    time.sleep( 2 )
                    
                    add_attendee['registration_type'] = ''
                    add_attendee['registration_amount'] = ''
                    add_attendee['discount_code'] = ''
                    add_attendee['discount_amount'] = ''

                    custom_data5 = client.service.GetCustomFieldResponsesForRegistration( eventID=eventID, 
                                                                                          registrationID=attendee['ID'], 
                                                                                          pageSectionID=5 )
                    
                    if custom_data5.Success != True:
                        log.error( json.dumps( { 'message' : "Failed to extract custom field data for eventID: %s, registrationID %s.  StatusCode=%s, Authority=%s" % ( eventID, attendee['ID'], custom_data5.StatusCode, custom_data5.Authority ) } ) )

                        # DEBUG - perhaps our client is getting corrupted somehow after much use? 
                        # Get a new client and keep trying.
                        client = Client( regonline_wsdl )
                        token = client.factory.create( "TokenHeader" )
                        token.APIToken = regonline_api_key
                        client.set_options( soapheaders=token )
                        continue

                    if custom_data5.Data == '':
                        log.warning( json.dumps( { 'message' : "No detailed registration data found for attendee %s with status %s" % ( attendee['ID'], attendee['StatusDescription'] ) } ) )
                    else:
                        add_attendee['registration_type'] = custom_data5.Data.APICustomFieldResponse[0].CustomFieldNameOnReport.encode( 'utf-8' )
                        add_attendee['registration_amount'] = custom_data5.Data.APICustomFieldResponse[0].Amount

                        discount_code = ""
                        discount_amount = 0

                        if 'Password' in custom_data5.Data.APICustomFieldResponse[0]:
                            tmp_discount_code = custom_data5.Data.APICustomFieldResponse[0].Password
                            if tmp_discount_code is not None:
                                discount_code = tmp_discount_code.encode( 'utf-8' )
                            discount_amount = custom_data5.Data.APICustomFieldResponse[0].DiscountCodeCredit

                        add_attendee['discount_code'] = discount_code
                        add_attendee['discount_amount'] = discount_amount
                elif attendee_type == "sponsors":
                    # If this sponsor already has discount codes,
                    # don't add any new ones.
                    sponsors_with_discounts = { x['SponsorID']:True for x in discount_codes }
                    if attendee['ID'] in sponsors_with_discounts:
                        log.warning( json.dumps( { 'message' : "Encountered sponsor %s who already has discount codes, skipping code generation." % ( attendee['ID'] ) } ) )
                    else:
                        # Otherwise generate new discount codes.
                        try:
                            discount_codes += generate_discount_codes( eventID, attendee, discount_codes )
                        except Exception as e:
                            log.error( json.dumps( { 'message' : "No discount codes found for sponsor: %s, error: %s" % ( attendee['ID'], e ) } ) )

                log.info( json.dumps( { 'message' : ( "Attendee data is: %s" % ( add_attendee ) ).encode( 'utf-8' ) } ) )
                attendees.append( add_attendee )
            else:
                log.info( json.dumps( { 'message' : "Skipping known attendee: %s" % ( attendee['ID'] ) } ) )

        except Exception as e:
            log.error( json.dumps( { 'message' : "General error %s while adding attendee %s - continuing." % ( e, attendee['ID'] ) } ) )

    if attendee_type == "registrants":
        log.info( json.dumps( { 'message' : "Persisting data for %d registrants." % ( len( attendees ) ) } ) )
        set_registrants( eventID, attendees )
    elif attendee_type == 'sponsors':
        log.info( json.dumps( { 'message' : "Persisting data for %d sponsors." % ( len( attendees ) ) } ) )
        set_sponsors( eventID, attendees )
        try:
            set_discount_codes( eventID, discount_codes )
        except:
            log.warning( json.dumps( { 'message' : "No discount codes found." } ) )
    else:
        raise Exception( "Unknown attendee type: '%s' - must be one of registrants or sponsors." % ( attendee_type ) )

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
                       help = "Run continuously, defaults to false." )
    parser.add_option( "-f", "--frequency",
                       dest = "sleep_duration",
                       help = "If running continuously, how many seconds to sleep between runs." )
    
    ( options, args ) = parser.parse_args()

    registrants_id = 1438441
    if options.registrants_id:
        registrants_id = int( options.registrants_id )

    sponsors_id = 1438449
    if options.sponsors_id:
        sponsors_id = int( options.sponsors_id )

    continuous = options.continuous

    sleep_duration = 1500
    if options.sleep_duration:
        sleep = int( options.sleep_duration )

    keep_going = True

    while keep_going:
        # Get a list of all registrations for GHC 2014.
        try:
            log.info( json.dumps( { 'message' : "Exporting data for registrants." } ) )
            export_event_data( registrants_id, "registrants" )
        except Exception as e:
            log.error( json.dumps( { 'message' : "Failed to get registrants, error was: %s" % ( e ) } ) )

        try:
            log.info( json.dumps( { 'message' : "Exporting data for sponsors." } ) )
            export_event_data( sponsors_id, "sponsors" )
        except Exception as e:
            log.error( json.dumps( { 'message' : "Failed to get registrants, error was: %s" % ( e ) } ) )
        
        if not continuous:
            False
            log.info( json.dumps( { 'message' : "Sleeping for %d seconds" % ( sleep_duration ) } ) )
            time.sleep( sleep_duration )

    #wov_sponsors_2015 = 1441015
    #wov_registrants_2015 = 1376075
    #logging.info( "WOV Sponsors." )
    #export_event_data( wov_sponsors_2015, "sponsors" )
    #logging.info( "WOV Registrants." )
    #export_event_data( wov_registrants_2015, "registrants" )
