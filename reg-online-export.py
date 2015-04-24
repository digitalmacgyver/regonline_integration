#!/usr/bin/env python

import datetime
import json
import time

from suds.client import Client

import logging
logging.basicConfig( level=logging.INFO )
logging.getLogger( 'suds.clinet' ).setLevel( logging.DEBUG )

from datastore import get_sponsors, get_registrants, add_sponsors, add_registrants, get_discount_codes, add_discount_codes
from discount_codes import generate_discount_codes

regonline_api_key = '9mIRFe399oIBM0fnX5jxLtupSZlaizGgtHUEuDpUi34QWs66G6LxFDZ6wsdpgzCw'
regonline_wsdl = "https://www.regonline.com/api/default.asmx?WSDL"

#Get a list of all events
#result = client.service.GetEvents( filter=None, orderBy=None )
#print result

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
        raise Exception( "Unknown attendee type: '%s' - must be one of registrants or sponsors." % ( attendee_type ) )

    attendee_ids = { x['ID']:x for x in attendees }

    logging.info( "Getting registrations for eventID: %s" % ( eventID ) )
    result = client.service.GetRegistrationsForEvent( eventID=eventID, filter=None, orderBy=None )

    new_attendees = result[1][0]

    # DEBUG For testing limit this to 10 attendees.
    for attendee in new_attendees:

        # DEBUG
        #if attendee['ID'] != 70036016:
        #    continue
        #else:
        #    import pdb
        #    pdb.set_trace()

        try:
            # First check if we're dealing with an updated attendee.
            if attendee['ID'] in attendee_ids and attendee['ModDate'] > attendee_ids[attendee['ID']].get( 'ModDate', datetime.datetime.min ):
                # Delete our old view of this attendee.
                logging.info( ( "Deleting old version of attendee: %s" % ( attendee_ids[attendee['ID']] ) ).encode( 'utf-8' ) )
                attendees = [ x for x in attendees if x['ID'] != attendee['ID'] ]
                attendee_ids.pop( attendee['ID'] )

            if attendee['ID'] not in attendee_ids:
                logging.info( "Adding data for attendee: %s" % ( attendee['ID'] ) )

                # We need to add this attendee.
                add_attendee = {
                    'ID'                : attendee['ID'],
                    'RegTypeID'         : attendee['RegTypeID'],
                    'StatusID'          : attendee['StatusID'],
                    'StatusDescription' : attendee['StatusDescription'],
                    'FirstName'         : attendee['FirstName'],
                    'LastName'          : attendee['LastName'],
                    'Email'             : attendee['Email'],
                    'CancelDate'        : attendee['CancelDate'],
                    'IsSubstitute'      : attendee['IsSubstitute'],
                    'AddBy'             : attendee['AddBy'],
                    'AddDate'           : attendee['AddDate'],
                    'ModBy'             : attendee['ModBy'],
                    'ModDate'           : attendee['ModDate'],
                    'CCEmail'           : "",
                    'Company'           : "",
                    'Phone'             : "",
                    'RegistrationType'  : "",
                    'Title'             : "",
                }

                # DEBUG
                # grep -i 'object has no attribute' export-log4.txt
                
                optional_fields = [ 'CCEmail', 'Company', 'Phone', 'RegistrationType', 'Title' ]
                for field in optional_fields:
                    if field in attendee:
                        add_attendee[field] = attendee[field]

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
                        logging.error( "Failed to extract custom field data for eventID: %s, registrationID %s.  StatusCode=%s, Authority=%s" % ( eventID, attendee['ID'], custom_data5.StatusCode, custom_data5.Authority ) )

                        # DEBUG - perhaps our client is getting corrupted somehow after much use? 
                        # Get a new client and keep trying.
                        client = Client( regonline_wsdl )
                        token = client.factory.create( "TokenHeader" )
                        token.APIToken = regonline_api_key
                        client.set_options( soapheaders=token )
                        continue

                    if custom_data5.Data == '':
                        logging.warning( "No detailed registration data found for attendee %s with status %s" % ( attendee['ID'], attendee['StatusDescription'] ) )
                        continue

                    add_attendee['registration_type'] = custom_data5.Data.APICustomFieldResponse[0].CustomFieldNameOnReport
                    add_attendee['registration_amount'] = custom_data5.Data.APICustomFieldResponse[0].Amount

                    discount_code = ""
                    discount_amount = 0

                    if 'Password' in custom_data5.Data.APICustomFieldResponse[0]:
                        discount_code = custom_data5.Data.APICustomFieldResponse[0].Password
                        discount_amount = custom_data5.Data.APICustomFieldResponse[0].DiscountCodeCredit

                    add_attendee['discount_code'] = discount_code
                    add_attendee['discount_amount'] = discount_amount
                elif attendee_type == "sponsors":
                    # If this sponsor already has discount codes,
                    # don't add any new ones.
                    sponsors_with_discounts = { x['SponsorID']:True for x in discount_codes }
                    if attendee['ID'] in sponsors_with_discounts:
                        logging.warning( "Encountered sponsor %s who already has discount codes, skipping code generation." % ( attendee['ID'] ) )
                    else:
                        # Otherwise generate new discount codes.
                        try:
                            discount_codes += generate_discount_codes( eventID, attendee, discount_codes )
                        except Exception as e:
                            logging.error( "No discount codes found for sponsor: %s, error: %s" % ( attendee['ID'], e ) )

                logging.info( ( "Attendee data is: %s" % ( add_attendee ) ).encode( 'utf-8' ) )
                attendees.append( add_attendee )
            else:
                logging.info( "Skipping known attendee: %s" % ( attendee['ID'] ) )

        except Exception as e:
            logging.error( "General error %s while adding attendee %s - continuing." % ( e, attendee['ID'] ) )

    if attendee_type == "registrants":
        logging.info( "Persisting data for %d registrants." % ( len( attendees ) ) )
        add_registrants( eventID, attendees )
    elif attendee_type == 'sponsors':
        logging.info( "Persisting data for %d sponsors." % ( len( attendees ) ) )
        add_sponsors( eventID, attendees )
        add_discount_codes( eventID, discount_codes )
    else:
        raise Exception( "Unknown attendee type: '%s' - must be one of registrants or sponsors." % ( attendee_type ) )

if __name__ == "__main__":

    # Get a list of all registrations for GHC 2014.
    registrants_2014 = 1438441
    logging.info( "Exporting data for registrants." )
    export_event_data( registrants_2014, "registrants" )

    sponsors_2014 = 1438449
    logging.info( "Exporting data for sponsors." )
    export_event_data( sponsors_2014, "sponsors" )
