#!/usr/bin/env python

import json
from optparse import OptionParser
import os
import unicodecsv
import uuid

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

format_string = 'get_sponsors.py: { "name" : "%(name)s", "module" : "%(module)s", "lineno" : "%(lineno)s", "funcName" : "%(funcName)s", "level" : "%(levelname)s", "message" : %(message)s }'

sys_formatter = logging.Formatter( format_string )

syslog.setFormatter( sys_formatter )
syslog.setLevel( logging.INFO )
consolelog = logging.StreamHandler()
consolelog.setLevel( logging.DEBUG )

log.addHandler( syslog )
log.addHandler( consolelog )

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

regonline_password_file = '../config/regonline_api_key.txt'
regonline_api_key = get_password( regonline_password_file )
regonline_wsdl = "https://www.regonline.com/api/default.asmx?WSDL"
regonline_soap_namespace = 'http://www.regonline.com/api'

abi_namespace_uuid = '0b595c4e-3dc7-4972-8434-6a2e818ccb38'

def get_attendee_password( email ):
    '''Generate a deterministic, simple password based on an email.'''
    uid = get_attendee_id( email )
    return uid[:3] + uid[-3:]

def get_attendee_id( email ):
    '''Generate a deterministic, unique identifier based on email.'''
    return unicode( uuid.uuid5( uuid.UUID( abi_namespace_uuid ), email.encode( 'ascii', errors='ignore' ) ) )

def get_sponsors( eventID, output_dir ):

    # DoubleDutch's required header format.
    attendee_headers = [
        'Name (required)',
        'Description',
        'Categories',
        'Filters',
        'Exhibitor Staff',
        'Booth Name',
        'Website',
        'Twitter Handle',
        'Facebook URL',
        'LinkedIn URL',
        'Phone Number',
        'Email',
        'Image URL',
        'Exhibitor ID'
    ]

    known_attendees = {
        'Corporate Sponsors' : [],
        'Academic Sponsors' : [],
        'Lab & Nonprofit Sponsors' : [],
    }
    
    def sanitize_phone( phone_number ):
        if len( phone_number ):
            if len( phone_number ) == 1:
                # Can't be 1 character
                phone_number
            else:
                # Can't be more than 20 characters
                phone_number = phone_number[:20]
                # Conform to RegOnline allowed characters for this field
                phone_number = ''.join( [ x for x in phone_number if x in [ '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '-', '(', ')', ' ', '+', '.', 'x' ] ] )

    def get_attendee_type( regtype, regid ):
        if regtype in [ 'ABI Partners Only - Diamond', 'ABI Partners Only - Platinum', 'Corporate - Gold', 'Corporate - Silver' ]:
            return 'Corporate Sponsors'
        elif regtype in [ 'Academic - Gold', 'Academic - Silver', 'Academic - Bronze' ]:
            return 'Academic Sponsors'
        elif regtype in [ 'Lab & Non-Profit - Gold', 'Lab & Non-Profit - Gold', 'Lab & Non-Profit - Gold' ]:
            return 'Lab & Nonprofit Sponsors'
        elif regid == 79052836:
            return 'Lab & Nonprofit Sponsors'
        else:
            return None

    # Get RegOnline data
    imp = Import( 'http://schemas.xmlsoap.org/soap/encoding/' )
    imp.filter.add( regonline_soap_namespace )
    doctor = ImportDoctor( imp )

    client = Client( regonline_wsdl, doctor=doctor )
    token = client.factory.create( "TokenHeader" )
    token.APIToken = regonline_api_key
    client.set_options( soapheaders=token )

    log.info( json.dumps( { 'message' : "Getting registrations for eventID: %s" % ( eventID ) } ) )
    result = client.service.GetRegistrationsForEvent( eventID=eventID, filter=None, orderBy=None )

    attendees = result[1][0]

    for attendee in attendees:
        try:
            if unicode( attendee['StatusDescription'] ) == 'Declined':
                log.warning( json.dumps( { 'message' : "Ignoring attendee ID %s with registration status: %s" % ( attendee['ID'], unicode( attendee['StatusDescription'] ) ) } ) )
                continue

            registration_status = unicode( attendee['StatusDescription'] )
            if registration_status not in [ 'Confirmed', 'Attended', 'Approved' ]:
                log.warning( json.dumps( { 'message' : "Ignoring attendee ID %s with registration status: %s" % ( attendee['ID'], registration_status ) } ) )
                continue

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
                'Phone'             : "",
            }

            optional_fields = [ 'CCEmail', 'Company', 'Email', 'RegistrationType', 'Title', 'Phone' ]
            for field in optional_fields:
                if field in attendee and attendee[field] is not None:
                    add_attendee[field] = unicode( attendee[field] )
                    
            if not add_attendee['Email']:
                # Everyone should have an email, bomb out if we don't.
                log.error( json.dumps( { 'error' : 'No email for sponsor %s' % ( add_attendee['ID'] ) } ) )
                raise Exception( 'No email for sponsor %s' % ( add_attendee['ID'] ) )

            # If we get here, we need to add the attendee.

            attendee_type = get_attendee_type( add_attendee['RegistrationType'], add_attendee['ID'] )
            if attendee_type is None:
                # This is a show management, or additional sponsorship
                # opportunity record, skip it.
                continue

            known_attendees[attendee_type].append( [
                add_attendee['Company'][:99],
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                get_attendee_id( add_attendee['Company'][:99] + add_attendee['Email'] )
            ] )

            log.info( json.dumps( { 'message' : unicode( "Sponsor data is: %s" % ( add_attendee ) ) } ) )
        except Exception as e:
            log.error( json.dumps( { 'message' : "General error %s while processing sponsor %s - continuing." % ( e, attendee['ID'] ) } ) )

    for attendee_type in known_attendees.keys():
        attendee_file = attendee_type.lower().replace( ' ', '_' ).replace( '&', 'and' )
        with open( "%s/%s.csv" % ( output_dir, attendee_file ), 'wb' ) as f:
            writer = unicodecsv.writer( f, encoding='utf-8' )
            writer.writerow( attendee_headers )
            for attendee in sorted( known_attendees[attendee_type] ):
                writer.writerow( attendee )


if __name__ == "__main__":
    usage = "usage: %prog [-r registrant_event_id] [-s sponsor_event_id] [-c] [-f 900]"
    parser = OptionParser( usage = usage )
    parser.add_option( "-r", "--registrant-event-id",
                       dest = "sponsors_id",
                       help = "The RegOnline event ID for registrants." )
    parser.add_option( "-o", "--output-dir",
                       dest = "output_dir",
                       help = "Directory to put the CSV file for the merged results - we produce one such file for each sponsorship tier of Diamond, Platinum, Gold, Silver, and Bronze." )
    
    ( options, args ) = parser.parse_args()

    sponsors_id = 1639610
    if options.sponsors_id:
        sponsors_id = int( options.sponsors_id )
        
    output_dir = '/wintmp/abi/sponsors/'
    if options.output_dir:
        output_dir = options.output_dir

    # Get a list of all registrations for GHC 2014.
    try:
        log.info( json.dumps( { 'message' : "Exporting data for registrants." } ) )
        get_sponsors( sponsors_id, output_dir )
    except Exception as e:
        log.error( json.dumps( { 'message' : "Failed to get registrants, error was: %s" % ( e ) } ) )

