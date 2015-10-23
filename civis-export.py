#!/usr/bin/env python

from bs4 import BeautifulSoup
import csv
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

format_string = 'civis-export.py: { "name" : "%(name)s", "module" : "%(module)s", "lineno" : "%(lineno)s", "funcName" : "%(funcName)s", "level" : "%(levelname)s", "message" : %(message)s }'

sys_formatter = logging.Formatter( format_string )

syslog.setFormatter( sys_formatter )
syslog.setLevel( logging.INFO )
consolelog = logging.StreamHandler()
consolelog.setLevel( logging.DEBUG )

log.addHandler( syslog )
log.addHandler( consolelog )

from datastore import get_sponsors, get_registrants, set_sponsors, set_registrants, get_discount_codes, set_discount_codes
from sfexport import sync_salesforce

regonline_api_key = 'zJwb+gsNL7aHRy90c+Kob6WY1sIcmqnaNZQxiP0Yl33MvlnY0LIRVqMOUliPq8FC'
regonline_wsdl = "https://www.regonline.com/api/default.asmx?WSDL"
regonline_soap_namespace = 'http://www.regonline.com/api'

def get_add_on_entitlements( eventID ):
    '''Returns a hash of:
    { 
      sponsorID : [ {
        quantity : X,
        product_name : "Enterprise Pack" },
        ... } ],
      ...
    }
    '''
    try:
        # RegOnline has a malformed WSDL which blows up suds, so we
        # have to resort to capturing the raw XML response and parsing
        # it ourselves here.  See RegOnline case ID 02977376
        class RawReceive( MessagePlugin ):
            raw_result = None
            def received( self, context ):
                self.raw_result = context.reply
            def get_raw( self ):
                return self.raw_result

        rr = RawReceive()
        client = Client( regonline_wsdl )
        token = client.factory.create( "TokenHeader" )
        token.APIToken = regonline_api_key
        client.set_options( soapheaders=token, plugins=[rr] )

        # We know this throws an exception.
        log.info( json.dumps( { 'message' : "About to call GetRegistrationsMerchandiseForEvent, which we know will throw an exception." } ) )
        result = client.service.GetRegistrationsMerchandiseForEvent( eventID=eventID )
    except Exception as e:
        # Now we have to process the raw result as XML.
        raw_result = rr.get_raw()
        if raw_result is None:
            raise Exception( "ERROR: RegOnline must have fixed their WSDL! Must re-factor reg-online-export to account for it!" )

    merch = BeautifulSoup( raw_result )

    result = {}

    for sponsor in merch.find_all( "apiregistration" ):
        sponsorID = int( sponsor.id.text )
        sponsor_entitlements = []
        for merch_items in sponsor.find_all( "merchandiseitems" ):
            for item in merch_items.find_all( "merchandise" ):
                sponsor_entitlements.append( { "quantity" : int( item.quantitysold.text ),
                                               "product_name" : item.merchandisereceiptname.text } )
                
        log.info( json.dumps( { 'message' : "Found entitlements %s for SponsorID: %d" % ( sponsor_entitlements[-1], sponsorID ) } ) )
        result[sponsorID] = sponsor_entitlements

    return result

all_keys = {}

def export_event_data( eventID, attendee_type, filename ):
    imp = Import( 'http://schemas.xmlsoap.org/soap/encoding/' )
    imp.filter.add( regonline_soap_namespace )
    doctor = ImportDoctor( imp )

    client = Client( regonline_wsdl, doctor=doctor )
    token = client.factory.create( "TokenHeader" )
    token.APIToken = regonline_api_key
    client.set_options( soapheaders=token )


    attendees = []

    log.info( json.dumps( { 'message' : "Getting registrations for eventID: %s" % ( eventID ) } ) )
    result = client.service.GetRegistrationsForEvent( eventID=eventID, filter=None, orderBy=None )

    new_attendees = result[1][0]

    for attendee in new_attendees:
        try:
            log.info( json.dumps( { 'message' : "Working on attendee: %s" % ( attendee['ID'] ) } ) )

            # We need to add this attendee.
            add_attendee = {
                'ID'                : attendee['ID'],
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
                'RegistrationType'  : "",
                'Title'             : "",
                'Address1'          : "",
                'Address2'          : "",
                'City'              : "",
                'State'             : "",
                'Country'           : "",
                'PostalCode'        : "",
                'HomePhone'         : "",
                'DateOfBirth'       : "",
                'NationalityID'     : "",
            }

            optional_fields = [ 'CCEmail', 'Company', 'Email', 'RegistrationType', 'Title', 'Address1', 'Address2', 'City', 'CA', 'Country', 'PostalCode', 'HomePhone', 'DateOfBirth', 'NationalityID' ]
            for field in optional_fields:
                if field in attendee and attendee[field] is not None:
                    add_attendee[field] = attendee[field].encode( 'utf-8' )
                    
            # Since they are a registrant we need to get some custom
            # data about them.
                    
            # Avoid rate limiting.
            time.sleep( 2 )
                    
            custom_data1 = client.service.GetCustomFieldResponsesForRegistration( eventID=eventID, 
                                                                                  registrationID=attendee['ID'], 
                                                                                  pageSectionID=1 )

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
                else:
                    value = thing.Response
                add_attendee[field] = value
                all_keys[field] = True

            log.info( json.dumps( { 'message' : ( "Attendee data is: %s" % ( add_attendee ) ).encode( 'utf-8' ) } ) )

            for key in add_attendee.keys():
                all_keys[key] = True

            attendees.append( add_attendee )

        except Exception as e:
            log.error( json.dumps( { 'message' : "General error %s while adding attendee %s - continuing." % ( e, attendee['ID'] ) } ) )

    with open( "/wintmp/abi/civis/regonline/civis-%s.csv" % ( filename ), "w" ) as f:
        writer = csv.writer( f )
        writer.writerow( sorted( all_keys.keys() ) )

        for attendee in attendees:
            row = [ attendee.get( x, '' ) for x in sorted( all_keys.keys() ) ]
            writer.writerow( row )

if __name__ == "__main__":
    usage = "usage: %prog [-r registrant_event_id] [-s sponsor_event_id] [-c] [-f 900]"
    parser = OptionParser( usage = usage )
    parser.add_option( "-r", "--registrant-event-id",
                       dest = "registrants_id",
                       help = "The RegOnline event ID for registrants." )
    
    ( options, args ) = parser.parse_args()
    
    # GHC 2014
    #registrants_id = 1438441
    # Test 2015
    registrants_id = None
    if options.registrants_id:
        registrants_id = int( options.registrants_id )
        
    all_registrations = [ ( 'user_input', registrants_id ) ]
    if registrants_id is None:
        all_registrations = [ #( 'ghc2014', 1438441 ),
            ( 'ghc2015', 1702108 ) ]
        '''
                              ( 'ghc2013', 1243683 ),
                              ( 'ghc2012', 1085780 ),
                              ( 'ghc2011', 935320 ),
                              ( 'ghc2010', 863990 ),
                              ( 'ghc2009', 737946 ),
                              ( 'ghc2008', 607899 ),
                              ( 'ghc2007', 135375 ),
                              ( 'ghc2006', 98603 ),
                              ( 'ghcindia2014', 1592570 ),
                              ( 'ghcindia2013', 1308915 ),
                              ( 'ghcindia2012', 1155616 ),
                              ( 'ghcindia2011', 1000169 ),
                              ( 'ghcindia2010', 905204 ) ]
        '''
                              
    for registration in all_registrations:
        try:
            log.info( json.dumps( { 'message' : "Exporting data for registrants." } ) )
            export_event_data( registration[1], "registrants", registration[0] )
        except Exception as e:
            log.error( json.dumps( { 'message' : "Failed to get registrants, error was: %s" % ( e ) } ) )

