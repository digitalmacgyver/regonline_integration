#!/usr/bin/env python

import json
import logging
import logging.handlers

from flask import Flask, request, jsonify, url_for, abort

from datastore import get_sponsors, get_registrants, get_discount_codes, set_discount_codes

app = Flask( __name__ )
app.config.from_pyfile( "./config/dataserver.default.conf" )

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

# Load out API keys from configuration.
valid_keys = {}
with open( app.config['API_KEY_FILE'], "r" ) as f:
    for key in f.readlines():
        key = key.strip()
        if key.startswith( '#' ):
            continue
        elif len( key ) == 0:
            continue
        else:
            valid_keys[key] = True

def has_no_empty_params(rule):
    '''Boilerplate that generates an site listing.'''
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)

@app.route( '/' )
def site_map():
    '''Default site map boilerplate.'''
    response_data = {}
    for rule in app.url_map.iter_rules():
        if "POST" in rule.methods and has_no_empty_params(rule):
            response_data[ url_for( rule.endpoint ) ] = rule.endpoint
    return jsonify( response_data )

def auth_ok( data ):
    '''If the user has called an authenticated endpoint, check that their
    API key is valid.'''
    if valid_keys[data.get( 'api_key', '' )]:
        logging.info( json.dumps( { 'message' : 'Authentication successful.' } ) )
        return True
    else:
        logging.error( json.dumps( { 'message' : 'Authentication failed: %s',
                                     'data' : data } ) )
        return False

@app.route( '/data/sponsors/', methods=[ 'POST' ] )
def sponsors():
    '''This method requires authentication.  It accepts a post with a JSON
    body of this format:

    { 
      api_key : authorized_key,
      eventID : RegOnline ID of the event ( int ),
    }

    Return a list of sponsors data structures as extracted from
    RegOnline:

    { success : True,
      [ {
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
        'CCEmail'           : "", # Populated if present in RegOnline
        'Company'           : "", # Populated if present in RegOnline
        'Email'             : "", # Populated if present in RegOnline
        'RegistrationType'  : "", # Populated if present in RegOnline
        'Title'             : "", # Populated if present in RegOnline
        }
      ]
    }
    '''
    data = request.get_json( force=True, silent=True )

    return attendees( 'sponsors', data )

@app.route( '/data/registrants/', methods=[ 'POST' ] )
def registrants():
    '''This method requires authentication.  It accepts a post with a JSON
    body of this format:

    { 
      api_key : authorized_key,
      eventID : RegOnline ID of the event ( int ),
    }
   
    Return a list of registrant data structures as extracted from RegOnline:

    { success : True,
      [ {
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
        'CCEmail'           : "", # Populated if present in RegOnline
        'Company'           : "", # Populated if present in RegOnline
        'Email'             : "", # Populated if present in RegOnline
        'RegistrationType'  : "", # Populated if present in RegOnline
        'Title'             : "", # Populated if present in RegOnline
        'registration_type' : "", # Populated from the additional data field in custom 
                                    page 5 in RegOnline
        'discount_code'     : "", # The discount code the user entered in custom page 5 
                                    in RegOnline
        }
      ]
    }
    '''

    data = request.get_json( force=True, silent=True )

    return attendees( 'registrants', data )

def attendees( table, data ):
    '''Internal method which abstracts the logic of data access for any
    type of attendee, be they sponsor or registrant.
    '''

    if auth_ok( data ):
        if 'eventID' in data:
            if table == 'sponsors':
                attendees = get_sponsors( data['eventID'] )
            elif table == 'registrants':
                attendees = get_registrants( data['eventID'] )
            else:
                logging.error( json.dumps( { 'message' : 'Invalid table type %s in call to attendees.' % ( table ) } ) )
                return jsonify( { "error" : "Internal server error.",
                                  "success" : False, } )

            return jsonify( { table : attendees,
                              "success"  : True } )
        else:
            logging.error( json.dumps( { 'message' : 'No eventID in call to attendees.' } ) )
            return jsonify( { "error" : "You must provide a valid eventID argument to this method.",
                              "success" : False } )
    else:
        logging.error( json.dumps( { 'message' : 'No api_key in call to attendees.' } ) )
        return jsonify( { "error" : "You must provide a valid api_key argument to this method.",
                          "success" : False } )

@app.route( '/data/discounts/', methods=[ 'POST' ] )
def discounts():
    '''This method requires authentication.  It accepts a post with a JSON
    body of this format:

    { 
      api_key : authorized_key,
      eventID : ID of the event, ( int )
    }

    Returns a list of all discount codes.  Discount codes have the
    following data:

    { success : True,
      [ { 
        ID               : A UUID for this particular code,
        SponsorID        : RegOnline ID of the sponsor who owns this code,
        RegTypeID        : RegOnline RegTypeID of the sponsor who owns this code,
        RegistrationType : RegOnline ReigstrationType of the sponsor who owns this code,
        discount_code    : The redemption string attendees enter to redeem this code
                           this code is stripped of surrounding whitespace and lower cased,
        quantity         : The number of redemptions available for this code (int),
        badge_type       : One of the key values of the hash returned by 
                           discount_codes::get_badge_types,
        code_source      : RegOnline RegistrationType for default codes, or the optional
                           argument sent to discount_codes::generate_discount_code method 
                           ("show management" from our web UI),
        regonline_str    : The discount amount in RegOnline format, e.g. '-10%',
        created_date     : The date this code was created:
                              * The AddDate of the RegOnline sponsor for basic codes
                              * The date the code was created for manually generated codes 
                                through the discount_codes::generate_discount_code method,
        }
      ]
    }
    '''

    data = request.get_json( force=True, silent=True )

    if auth_ok( data ):
        if 'eventID' in data:
            discounts = get_discount_codes( data['eventID'] )

            return jsonify( { "discount_codes" : discounts,
                              "success"  : True } )
        else:
            logging.error( json.dumps( { 'message' : 'No eventID in call to attendees.' } ) )
            return jsonify( { "error" : "You must provide a valid eventID argument to this method.",
                              "success" : False } )
    else:
        logging.error( json.dumps( { 'message' : 'No api_key in call to attendees.' } ) )
        return jsonify( { "error" : "You must provide a valid api_key argument to this method.",
                          "success" : False } )

@app.route( '/data/discount_code/', methods=[ 'POST' ] )
def discount_code():
    '''This method is open to the public.  It accepts a post with a JSON
    body of this format:

    {
      discount_eventID   : RegOnline ID of the event being attended ( int ),
      registrant_eventID : RegOnline ID of the attendee ( int ),
      discount_code      : The discount_code code value of interest.  Discount codes 
                           have their whitespace stripped from the beginning and end, 
                           and are treated in a case insensitive manner.
    }

    Returns a summary of the requested discount code, and the
    registered attendees who have used that code.  If no code is
    entered, an error is returned, if the search code is only
    whitespace or is not found an empty result with 0 values and empty
    hashes and arrays is returned.

    {
     discount_code_data : {
       The keys and values of discount_codes as described above for the discount_code
       in question
     },
     total              : Quantity of redemptions available,
     redeemed           : Redemptions against this code,
     available          : Remaining redemptions available,
     redemptions        : [ {
         name              : Attendee name,
         company           : Attendee company,
         title             : Attendee job title,
         status            : Registration status from RegOnline,
         registration_type : Registration type from RegOnline,
         registration_date : Date of the registration
     }  ],
     success            : True
    }

    '''

    data = request.get_json( force=True, silent=True )

    if 'discount_eventID' not in data:
        logging.error( json.dumps( { 'message' : 'No discount_eventID in call to attendees.' } ) )
        return jsonify( { "error" : "You must provide a valid discount_eventID argument to this method.",
                          "success" : False } )        

    if 'registrant_eventID' not in data:
        logging.error( json.dumps( { 'message' : 'No registrant_eventID in call to attendees.' } ) )
        return jsonify( { "error" : "You must provide a valid registrant_eventID argument to this method.",
                          "success" : False } )        

    if 'discount_code' not in data:
        logging.error( json.dumps( { 'message' : 'No discount_code in call to attendees.' } ) )
        return jsonify( { "error" : "You must provide a valid discount_code argument to this method.",
                          "success" : False } )        

    # Codes are case insensitive and ignore surrounding whitespace.
    search_code = data['discount_code'].lower().strip()

    if len( search_code ) == 0:
        logging.warning( json.dumps( { 'message' : 'Empty discount_code in call to attendees.' } ) )
        return jsonify ( { "discount_code_data" : {},
                          "total" : 0,
                          "redeemed" : 0,
                          "available" : 0,
                          "redemptions" : [],
                          "success"  : True } )

    discounts = get_discount_codes( data['discount_eventID'] )
    registrants = get_registrants( data['registrant_eventID'] )

    discount_code_data = {}
    for code in discounts:
        if search_code == code['discount_code'].lower().strip():
            discount_code_data = code
            break

    if discount_code_data == {}:
        logging.warning( json.dumps( { 'message' : 'No attendees found for discount code: %s' % ( search_code ) } ) )

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

    attendees = [ get_fields( x ) for x in registrants if x['discount_code'].lower().strip() == search_code ]

    return jsonify( { "discount_code_data" : discount_code_data,
                      "total" : discount_code_data.get( 'quantity', 0 ),
                      "redeemed" : len( attendees ),
                      "available" : discount_code_data.get( 'quantity', 0 ) - len( attendees ),
                      "redemptions" : attendees,
                      "success"  : True } )

@app.route( '/data/discount_code/delete/', methods=[ 'POST' ] )
def discount_code_delete():
    '''Delete an existing discount code, given these parameters on a POST in JSON
    format:

    {
      eventID : The RegOnline event of the sponsor of this code,
      api_key : authorized_key,
      discount_code : A string of the discount code to be deleted
    }
    '''

    data = request.get_json( force=True, silent=True )

    if auth_ok( data ):
        if 'eventID' not in data:
            logging.error( json.dumps( { 'message' : 'No eventID in call to discount_code_delete.' } ) )
            return jsonify( { "error" : "You must provide a valid eventID argument to this method.",
                              "success" : False } )

        if 'discount_code' not in data:
            logging.error( json.dumps( { 'message' : 'No discount_code in call to discount_code_delete.' } ) )
            return jsonify( { "error" : "You must provide a valid discount_code argument to this method.",
                              "success" : False } )        
        

        discount_code_delete = data['discount_code'].lower().strip()
    
        discounts = get_discount_codes( data['eventID'] )
        discounts = [ x for x in discounts if x['discount_code'] != discount_code_delete ]

        set_discount_codes( data['eventID'], discounts )

        return jsonify( { "success" : True } )

    else:
        logging.error( json.dumps( { 'message' : 'No api_key in call to discount_code/add.' } ) )
        return jsonify( { "error" : "You must provide a valid api_key argument to this method.",
                          "success" : False } )

if __name__ == '__main__':
    app.run( port=app.config['PORT'] )
