#!/usr/bin/env python

import json
import time

from suds.client import Client

import logging
logging.basicConfig( level=logging.INFO )
logging.getLogger( 'suds.clinet' ).setLevel( logging.DEBUG )

from datastore import get_sponsors, get_registrants, add_sponsors, add_registrants

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

    logging.info( "Getting registrations for eventID: %s" % ( eventID ) )
    result = client.service.GetRegistrationsForEvent( eventID=eventID, filter=None, orderBy=None )

    new_attendees = result[1][0]

    if attendee_type == 'registrants':
        attendees = get_registrants( eventID )
    elif attendee_type == 'sponsors':
        attendees = get_sponsors( eventID )
    else:
        raise Exception( "Unknown attendee type: '%s' - must be one of registrants or sponsors." % ( attendee_type ) )

    attendee_ids = { x['ID']:x for x in attendees }

    # DEBUG For testing limit this to 10 attendees.
    for attendee in new_attendees[:10]:
        try:
            if attendee['ID'] not in attendee_ids:
                logging.info( "Adding data for attendee: %s" % ( attendee['ID'] ) )

                # We need to add this attendee.
                add_attendee = {
                    'ID'                : attendee['ID'],
                    'RegTypeID'         : attendee['RegTypeID'],
                    'RegistrationType'  : attendee['RegistrationType'],
                    'StatusID'          : attendee['StatusID'],
                    'StatusDescription' : attendee['StatusDescription'],
                    'FirstName'         : attendee['FirstName'],
                    'LastName'          : attendee['LastName'],
                    'Email'             : attendee['Email'],
                    'Company'           : attendee['Company'],
                    'Phone'             : attendee['Phone'],
                    'CancelDate'        : attendee['CancelDate'],
                    'IsSubstitute'      : attendee['IsSubstitute'],
                    'AddBy'             : attendee['AddBy'],
                    'AddDate'           : attendee['AddDate'],
                    'Title'             : "",
                    'CCEmail'           : "",
                }

                if 'Title' in attendee:
                    # For some reason not all fields have this.
                    add_attendee['Title'] =  attendee['Title']

                if 'CCEmail' in attendee:
                    # For some reason not all fields have this.
                    add_attendee['CCEmail'] =  attendee['CCEmail']

                if attendee_type == "registrants":
                    # Since they are a registrant we need to get some custom
                    # data about them.
                    
                    # Avoid rate limiting.
                    time.sleep( 2 )
                    custom_data5 = client.service.GetCustomFieldResponsesForRegistration( eventID=eventID, 
                                                                                          registrationID=attendee['ID'], 
                                                                                          pageSectionID=5 )

                    add_attendee['registration_type'] = custom_data5.Data.APICustomFieldResponse[0].CustomFieldNameOnReport
                    add_attendee['registration_amount'] = custom_data5.Data.APICustomFieldResponse[0].Amount

                    discount_code = ""
                    discount_amount = 0

                    if 'Password' in custom_data5.Data.APICustomFieldResponse[0]:
                        discount_code = custom_data5.Data.APICustomFieldResponse[0].Password
                        discount_amount = custom_data5.Data.APICustomFieldResponse[0].DiscountCodeCredit

                    add_attendee['discount_code'] = discount_code
                    add_attendee['discount_amount'] = discount_amount

                logging.info( "Attendee data is: %s" % ( add_attendee ) )
                attendees.append( add_attendee )
            else:
                logging.info( "Skipping known attendee: %s" % ( attendee['ID'] ) )

        except Exception as e:
            logging.error( "ERROR: %s, %s - continuing." % ( attendee, e ) )

    if attendee_type == "registrants":
        logging.info( "Persisting data for %d registrants." % ( len( attendees ) ) )
        add_registrants( eventID, attendees )
    elif attendee_type == 'sponsors':
        logging.info( "Persisting data for %d sponsors." % ( len( attendees ) ) )
        add_sponsors( eventID, attendees )
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
