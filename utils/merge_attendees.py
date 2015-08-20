#!/usr/bin/env python

import json
from optparse import OptionParser
import os
import time
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

format_string = 'merge_attendees.py: { "name" : "%(name)s", "module" : "%(module)s", "lineno" : "%(lineno)s", "funcName" : "%(funcName)s", "level" : "%(levelname)s", "message" : %(message)s }'

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

def merge_registrants( eventID, attendee_file, output_file ):

    # DoubleDutch's required header format.
    attendee_headers = [
        'First Name (required)',
        'Last Name (required)',
        'Email Address (required)',
        'Password (required)',
        'Title',
        'Company',
        'Biography',
        'Phone Number',
        'Image URL',
        'Attendee Groups',
        'Personal Agenda (Session IDs)',
        'Exhibitor ID',
        'Exhibitor Role',
        'Speaker ID',
        'Attendee ID'
    ]

    # Output file format
    output_headers = [ 
        'First Name (required)',	
        'Last Name (required)',	
        'Email Address (required)',	
        'Password (required)',	
        'Title',	
        'Company',	
        'Biography',	
        'Phone Number',	
        'Image URL',	
        'Address',	
        'Address (ext)',	
        'City',	
        'State/Province/Region',	
        'Postal Code',	
        'Country',	
        'Attendee ID',	
        'Attendee Groups',	
        'Personal Agenda (Session IDs)',	
        'Exhibitor ID',	
        'Exhibitor Role',	
        'Speaker ID',	
        'Variable Data 1',	
        'Variable Data 2',	
        'Variable Data 3',
    ]

    known_attendees = []

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
        return phone_number

    # Get data from the file.
    with open( attendee_file, 'rb' ) as f:
        reader = unicodecsv.reader( f, encoding='utf-8' )
        for attendee in reader:
            if len( attendee ) == 15:
                attendee = [ unicode( x ) for x in attendee ]

                # Set the users password.
                attendee[3] = get_attendee_password( attendee[2] )

                # Set the Title field to comply with DoubleDutch length limits.
                attendee[4] = attendee[4][:99]

                # Set the Company field to comply with DoubleDutch length limits.
                attendee[5] = attendee[5][:99]

                attendee[7] = sanitize_phone( attendee[7] )

                print "Working on %s" % ( attendee )

                known_attendees.append( [ attendee[0],
                                          attendee[1],
                                          attendee[2],
                                          attendee[3],
                                          attendee[4],
                                          attendee[5],
                                          attendee[6],
                                          attendee[7],
                                          attendee[8],
                                          '',
                                          '',
                                          '',
                                          '',
                                          '',
                                          '',
                                          attendee[-1],
                                          '', #Groups added in below.
                                          attendee[10],
                                          attendee[11],
                                          attendee[12],
                                          attendee[13],
                                          '',
                                          '',
                                          '' ] )

        known_attendees = known_attendees[1:]
        # DEBUG
        #known_attendees = known_attendees[1:10]
    
    known_emails = { x[2].lower():x for x in known_attendees }

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

    # DEBUG
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
                # Skip attendees who don't have an email.
                continue

            # If we get here, we need to add the attendee.

            # Avoid rate limiting.
            time.sleep( 2 )
                    
            custom_data1 = client.service.GetCustomFieldResponsesForRegistration( eventID=eventID, 
                                                                                  registrationID=attendee['ID'], 
                                                                                  pageSectionID=1 )

            group_labels = [
                'Professional Affiliation: Academic',
                'Professional Affiliation: Government',
                'Professional Affiliation: Industry',
                'Professional Affiliation: National Lab',
                'Professional Affiliation: Non-Profit',
                'Professioanl Affiliation: Unaffiliated',
                'Professional Affiliation: Other',
                'Interest: ABI.Locals',
                'Interest: ACM',
                'Interest: Artificial Intelligence',
                'Interest: Being a Mentor',
                'Interest: Being Mentored',
                'Interest: CRA-W',
                'Interest: Data Science',
                'Interest: Entrepreneurship',
                'Interest: Graphic Effects / Gaming',
                'Interest: Human-Computer Interactions',
                'Interest: IEEE',
                'Interest: Internet of Things',
                'Interest: ISOC',
                'Interest: Lean-In Circles',
                'Interest: NCWIT',
                'Interest: Open Source',
                'Interest: Organizational Change',
                'Interest: Privacy',
                'Interest: Productization',
                'Interest: Security',
                'Interest: Systers',
                'Interest: Wearables',
                'Ethnicity: African or African-American/Black',
                'Ethnicity: Alaska Native or American Indian/Native American',
                'Ethnicity: Asian or Asian-American',
                'Ethnicity: European or Euro-American/White',
                'Ethnicity: Native Hawaiian or Pacific Islander',
                'Ethnicity: Hispanic or Latina/o',
                'Ethnicity: Other',
                'Gender: Female',
                'Gender: Male',
                'Gender: Transgender',
                'Gender: Nonbinary',
                'Gender: Other',
                'Gender: Decline to state',
                'Agenda: Fall Partner Meeting',
                'Agenda: Global Women Technical Leaders Program',
                'Agenda: Private Reception',
                "Agenda: Senior Women's Program and Luncheon",
                'Agenda: Technical Executive Forum'
            ]
            
            groups_of_interest = [ x[x.find( ':' )+2:] for x in group_labels ]

            user_group_labels = [ "Registration: %s" % ( attendee.RegistrationType ) ]

            if custom_data1.Success != True:
                log.error( json.dumps( { 'message' : "Failed to extract custom field data for eventID: %s, registrationID %s.  StatusCode=%s, Authority=%s" % ( eventID, attendee['ID'], custom_data1.StatusCode, custom_data1.Authority ) } ) )
                # DEBUG - perhaps our client is getting corrupted somehow after much use? 
                # Get a new client and keep trying.
                client = Client( regonline_wsdl )
                token = client.factory.create( "TokenHeader" )
                token.APIToken = regonline_api_key
                client.set_options( soapheaders=token )
                continue

            for thing in custom_data1.Data.APICustomFieldResponse:
                field = thing.CustomFieldNameOnReport
                if 'ItemDescription' in thing:
                    value = thing.ItemDescription
                elif thing.Response == "True":
                    value = thing.CustomFieldNameOnForm
                else:
                    value = thing.Response

                if value in groups_of_interest:
                    user_group_labels.append( group_labels[groups_of_interest.index( value )] )


            if add_attendee['Email'].lower() in known_emails:
                # Fix up the ones from Linklings but otherwise leave them unchanged.
                known_emails[add_attendee['Email'].lower()][16] = ",".join( user_group_labels )
                continue
                
            known_attendees.append( [
                add_attendee['FirstName'],
                add_attendee['LastName'],
                add_attendee['Email'],
                get_attendee_password( add_attendee['Email'] ),
                add_attendee['Title'][:99],
                add_attendee['Company'][:99],
                '',
                sanitize_phone( add_attendee['Phone'] ),
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                get_attendee_id( add_attendee['Email'] ),                
                ",".join( user_group_labels ),
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                ] )

            log.info( json.dumps( { 'message' : unicode( "Attendee data is: %s" % ( add_attendee ) ) } ) )
        except Exception as e:
            log.error( json.dumps( { 'message' : "General error %s while adding attendee %s - continuing." % ( e, attendee['ID'] ) } ) )

    with open( output_file, 'wb' ) as f:
        writer = unicodecsv.writer( f, encoding='utf-8' )
        writer.writerow( output_headers )
        for attendee in sorted( known_attendees ):
            writer.writerow( attendee )

'''
ABI.Locals
ACM
African or African-American/Black
Age
Alaska Native or American Indian/Native American
Artificial Intelligence
Asian or Asian-American
Being Mentored
Being a Mentor
CRA-W
Data Science
Degree Currently Pursuing
Entrepreneurship
European or Euro-American/White
GHC 1994
GHC 1997
GHC 2000
GHC 2002
GHC 2004
GHC 2006
GHC 2007
GHC 2008
GHC 2009
GHC 2010
GHC 2011
GHC 2012
GHC 2013
GHC 2014
Gender specified
Gender.
Gluten-Free
Graphic Effects / Gaming
Hispanic or Latina/o
Human-Computer Interactions
IEEE
ISOC
Internet of Things
Job Role - Academic
Job Role - Govt/Lab/Unaffiliated
Job Role - Industry
Lean-In Circles
NCWIT
Native Hawaiian or Pacific Islander
Open Source
Organizational Change
Other Affiliation
Other Degree
Other Job Role
Other Race
Previous Attendee
Privacy
Productization
Professional Affiliation
RegistrationType
Security
State
StatusDescription
Syster
Systers
Title
Vegetarian or Vegan
Visual
Waitlist Type
Wearables
'''



if __name__ == "__main__":
    usage = "usage: %prog [-r registrant_event_id] [-s sponsor_event_id] [-c] [-f 900]"
    parser = OptionParser( usage = usage )
    parser.add_option( "-r", "--registrant-event-id",
                       dest = "registrants_id",
                       help = "The RegOnline event ID for registrants." )
    parser.add_option( "-f", "--attendee-file",
                       dest = "attendee_file",
                       help = "CSV file holding the known attendees from Linklings we are to merge with." )
    parser.add_option( "-o", "--output-file",
                       dest = "output_file",
                       help = "CSV file for the merged results - defautls to merged-attendee_file." )
    
    ( options, args ) = parser.parse_args()
    
    # GHC 2014
    #registrants_id = 1438441
    # Test 2015
    registrants_id = 1702108
    # DEBUG - test event
    #registrants_id = 1723537
    if options.registrants_id:
        registrants_id = int( options.registrants_id )
        
    attendee_file = '/wintmp/abi/speakers/attendee.csv'
    if options.attendee_file and os.path.isfile( options.attendee_file ):
        attendee_file  = options.attendee_file

    if options.output_file:
        output_file = options.output_file
    else:
        output_file = "%s/merged-%s" % ( os.path.split( attendee_file ) )

    # Get a list of all registrations for GHC 2014.
    try:
        log.info( json.dumps( { 'message' : "Exporting data for registrants." } ) )
        merge_registrants( registrants_id, attendee_file, output_file )
    except Exception as e:
        log.error( json.dumps( { 'message' : "Failed to get registrants, error was: %s" % ( e ) } ) )

