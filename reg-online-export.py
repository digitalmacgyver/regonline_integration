#!/usr/bin/env python

from bs4 import BeautifulSoup
import datetime
import json
from optparse import OptionParser
import time

from suds.client import Client
from suds.xsd.doctor import ImportDoctor, Import
from suds.plugin import MessagePlugin

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
from sfexport import sync_salesforce

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

regonline_password_file = './config/regonline_api_key.txt'
regonline_api_key = get_password( regonline_password_file )
regonline_wsdl = "https://www.regonline.com/api/default.asmx?WSDL"
regonline_soap_namespace = 'http://www.regonline.com/api'

def export_event_data( eventID, attendee_type ):
    imp = Import( 'http://schemas.xmlsoap.org/soap/encoding/' )
    imp.filter.add( regonline_soap_namespace )
    doctor = ImportDoctor( imp )

    client = Client( regonline_wsdl, doctor=doctor )
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

    for attendee in new_attendees:
        try:
            # First check if we're dealing with an updated attendee.
            if attendee['ID'] in attendee_ids and attendee['ModDate'] > attendee_ids[attendee['ID']].get( 'ModDate', datetime.datetime.min ):
                # Delete our old view of this attendee.
                log.info( json.dumps( { 'message' : "Deleting old version of attendee: %s" % unicode( attendee_ids[attendee['ID']] ) } ) )
                attendees = [ x for x in attendees if x['ID'] != attendee['ID'] ]
                attendee_ids.pop( attendee['ID'] )

            if unicode( attendee['StatusDescription'] ) == 'Declined':
                log.warning( json.dumps( { 'message' : "Ignoring attendee ID %s with registration status: %s" % ( attendee['ID'], unicode( attendee['StatusDescription'] ) ) } ) )
                continue

            if attendee['ID'] not in attendee_ids:
                registration_status = unicode( attendee['StatusDescription'] )
                if registration_status not in [ 'Confirmed', 'Attended', 'Approved' ]:
                    log.warning( json.dumps( { 'message' : "Ignoring attendee ID %s with registration status: %s" % ( attendee['ID'], registration_status ) } ) )
                    continue

                log.info( json.dumps( { 'message' : "Adding data for attendee: %s" % ( attendee['ID'] ) } ) )

                # We need to add this attendee.
                add_attendee = {
                    'ID'                : attendee['ID'],
                    'RegTypeID'         : attendee['RegTypeID'],
                    'StatusID'          : attendee['StatusID'],
                    'StatusDescription' : unicode( attendee['StatusDescription'] ),
                    'FirstName'         : unicode( attendee['FirstName'] ),
                    'LastName'          : unicode( attendee['LastName'] ),
                    'CancelDate'        : attendee['CancelDate'],
                    'IsSubstitute'      : attendee['IsSubstitute'],
                    'AddBy'             : attendee['AddBy'],
                    'AddDate'           : attendee['AddDate'],
                    'ModBy'             : attendee['ModBy'],
                    'ModDate'           : attendee['ModDate'],
                    'CCEmail'           : "",
                    'Company'           : "",
                    'Email'             : "",
                    'RegistrationType'  : "",
                    'Title'             : "",
                }

                optional_fields = [ 'CCEmail', 'Company', 'Email', 'RegistrationType', 'Title' ]
                for field in optional_fields:
                    if field in attendee and attendee[field] is not None:
                        add_attendee[field] = unicode( attendee[field] )

                if attendee_type == "registrants":
                    # Since they are a registrant we need to get some custom
                    # data about them.
                    
                    # Avoid rate limiting.
                    time.sleep( 2 )
                    
                    add_attendee['registration_type'] = ''
                    add_attendee['discount_code'] = ''

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
                        add_attendee['registration_type'] = unicode( custom_data5.Data.APICustomFieldResponse[0].CustomFieldNameOnReport )

                        discount_code = ""

                        if 'Password' in custom_data5.Data.APICustomFieldResponse[0]:
                            tmp_discount_code = custom_data5.Data.APICustomFieldResponse[0].Password
                            if tmp_discount_code is not None:
                                discount_code = unicode( tmp_discount_code ).strip().lower()

                        add_attendee['discount_code'] = discount_code

                log.info( json.dumps( { 'message' : unicode( "Attendee data is: %s" % ( add_attendee ) ) } ) )
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
            log.info( json.dumps( { 'message' : "Exporting data for registrants." } ) )
            export_event_data( registrants_id, "registrants" )
        except Exception as e:
            log.error( json.dumps( { 'message' : "Failed to get registrants, error was: %s" % ( e ) } ) )

        try:
            log.info( json.dumps( { 'message' : "Exporting data for sponsors." } ) )
            export_event_data( sponsors_id, "sponsors" )
        except Exception as e:
            log.error( json.dumps( { 'message' : "Failed to get registrants, error was: %s" % ( e ) } ) )

        try:
            log.info( json.dumps( { 'message' : "Exporting discount data for sponsors from salesforce." } ) )
            sync_salesforce( sponsors_id, get_sponsors( sponsors_id ) )
        except Exception as e:
            log.error( json.dumps( { 'message' : "Failed to sync data from salesforce, error was: %s" % ( e ) } ) )
        
        if continuous:
            keep_going = True
            log.info( json.dumps( { 'message' : "Sleeping for %d seconds" % ( sleep_duration ) } ) )
            time.sleep( sleep_duration )
