#!/usr/bin/env python

'''Simple Restful JSON server for registrant data.'''

from flask import Flask, request, jsonify, url_for, abort

from datastore import get_sponsors, get_registrants, get_discount_codes

app = Flask( __name__ )

def has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)

@app.route( '/' )
def site_map():
    response_data = {}
    for rule in app.url_map.iter_rules():
        if "GET" in rule.methods and has_no_empty_params(rule):
            response_data[ url_for( rule.endpoint ) ] = rule.endpoint
    return jsonify( response_data )

valid_keys = { '9Cn3gKNS3DB7FEck' : True }

def auth_ok( data ):
    if valid_keys[data.get( 'api_key', '' )]:
        return True
    else:
        return False

@app.route( '/data/sponsors/', methods=[ 'POST' ] )
def sponsors():
    data = request.get_json( force=True, silent=True )

    return attendees( 'sponsors', data )

@app.route( '/data/registrants/', methods=[ 'POST' ] )
def registrants():
    data = request.get_json( force=True, silent=True )

    return attendees( 'registrants', data )

def attendees( table, data ):
    if auth_ok( data ):
        if 'eventID' in data:
            if table == 'sponsors':
                attendees = get_sponsors( data['eventID'] )
            elif table == 'registrants':
                attendees = get_registrants( data['eventID'] )
            else:
                return jsonify( { "error" : "Internal server error.",
                                  "success" : False, } )

            return jsonify( { table : attendees,
                              "success"  : True } )
        else:
            return jsonify( { "error" : "You must provide a valid eventID argument to this method.",
                              "success" : False } )
    else:
        return jsonify( { "error" : "You must provide a valid api_key argument to this method.",
                          "success" : False } )

@app.route( '/data/discounts/', methods=[ 'POST' ] )
def discounts():
    data = request.get_json( force=True, silent=True )

    if auth_ok( data ):
        if 'eventID' in data:
            discounts = get_discount_codes( data['eventID'] )

            return jsonify( { "discount_codes" : discounts,
                              "success"  : True } )
        else:
            return jsonify( { "error" : "You must provide a valid eventID argument to this method.",
                              "success" : False } )
    else:
        return jsonify( { "error" : "You must provide a valid api_key argument to this method.",
                          "success" : False } )

@app.route( '/data/discount_code/', methods=[ 'POST' ] )
def discount_code():
    data = request.get_json( force=True, silent=True )

    if 'discount_eventID' not in data:
        return jsonify( { "error" : "You must provide a valid discount_eventID argument to this method.",
                          "success" : False } )        
    if 'registrant_eventID' not in data:
        return jsonify( { "error" : "You must provide a valid registrant_eventID argument to this method.",
                          "success" : False } )        
    if 'discount_code' not in data:
        return jsonify( { "error" : "You must provide a valid discount_code argument to this method.",
                          "success" : False } )        

    discounts = get_discount_codes( data['discount_eventID'] )
    registrants = get_registrants( data['registrant_eventID'] )

    discount_code_data = {}
    for code in discounts:
        if data['discount_code'] == code['discount_code']:
            discount_code_data = code
            break

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

    attendees = [ get_fields( x ) for x in registrants if x['discount_code'] == data['discount_code'] ]

    return jsonify( { "discount_code_data" : discount_code_data,
                      "total" : discount_code_data.get( 'quantity', None ),
                      "redeemed" : len( attendees ),
                      "available" : discount_code_data.get( 'quantity', 0 ) - len( attendees ),
                      "redemptions" : attendees,
                      "success"  : True } )


if __name__ == '__main__':
    # Enables helpful server error responses with tracebacks etc., and
    # reloads the server on code changes.  Should be set to false in
    # any public facing deployment, as this allows execution of
    # arbitrary code from the web via debugging options.
    app.debug = True

    # This will only listen on 127.0.0.1
    app.run()
    # To listen on other interfaces use:
    # app.run( host='0.0.0.0' ) # Or, a different more restrictive mask