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


'''REST like server which always responds with JSON.

All endpoints accept only POSTs.

data = { 
   eventID : 'blahblahblah',
   api_key : 'blahblahblah',
   ...optional or mandatory arguments...
}


All JSON responses have a success=true or false field indicating
whether the operation was successful.

Authentication is very simple - the authenticated endpoints must
provide an API key which can be validated via JSON like:

The data server will have the following APIs, the numbers indicate the
priority order in which they will be added:

DONE:
1 - /data/sponsors/
Authentication required
Returns a list of all sponsors
1 - /data/registrants/
Authentication required
Returns a list of all registrants
1 - /data/discounts/
Authentication may be required depending on mode


TBD:

2 - /data/new_discount/
Authentication required
Takes the following arguments on POST in data { } JSON
sponsorID (TBD how we are storing this, as a number or as a string)
Registration Type [TBD details, but likely one of General or Academic]
Quantity (number)
Returns success or failure, on success returns the value of /data/discounts/discount_code - which includes the value of the code created

3 - /data/send_sponsor_email/
Authentication required
Takes the following arguments on POST in data {} JSON
emails - list of recipient emails
sponsorID
Sends an email to the emails and any build in admin emails with the sponsorship information for that sponsor, namely the list of their discount codes, the quantities remaining, their type, and the URL to register them at.

'''

valid_keys = { 'secret_key' : True }

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
            "registration_type" : registrant['RegistrationType'],
            "registration_date" : registrant['AddDate']
        }

    attendees = [ get_fields( x ) for x in registrants if x['discount_code'] == data['discount_code'] ]

    return jsonify( { "discount_code_data" : discount_code_data,
                      "total" : discount_code_data['quantity'],
                      "redeemed" : len( attendees ),
                      "available" : discount_code_data['quantity'] - len( attendees ),
                      "redemptions" : attendees,
                      "success"  : True } )


'''
@app.route( '/get_movies/', methods=[ 'GET', 'POST'] )
def get_movies():
    movies = load_movies( movies_dir )
    
    return jsonify( { "data" : [ { 'movie_id' : x['title'], 'partition' : x['partition'] } for y, x in movies.items() ] } )

@app.route( '/get_stats_for_movies/',
            methods=[ 'GET', 'POST'] )
def get_stats_for_movies():
    
    data = request.get_json( force=True, silent=True )

    movies = load_movies( movies_dir )

    if data is None:
        # All movies if there is no data.
        return jsonify( movies )
    else:
        return jsonify( { "data" : { key:value for key, value in movies.items() if value['title'] in data } } )

@app.route( '/get_dimensions/', methods=[ 'GET', 'POST'] )
def get_dimensions():
    return jsonify( { "data" : all_dimensions } )

@app.route( '/get_projections/', methods=[ 'GET', 'POST'] )
def get_projections():
    return jsonify( { "data" : proj_dimensions } )

@app.route( '/get_graph_for_movies/',             
            methods=[ 'GET', 'POST'] )
def get_graph_for_movies():

    data = request.get_json( force=True, silent=True )

    # What source dimensions should we care about, and what weights
    # should we ascribe to them.
    req_dimensions = data.get( "dimensions", [] )
    if len( req_dimensions ) == 0:
        req_dimensions = all_dimensions
    dimension_weights = {}
    req_dimension_weights = data.get( "dimension_weights", {} )
    for dim in req_dimensions:
        if dim in req_dimension_weights:
            dimension_weights[dim] = req_dimension_weights[dim]            
        else:
            dimension_weights[dim] = 1

    # What dimensions should we project onto.
    req_proj_dimensions = data.get( "proj_dimensions", [] )
    if len( req_proj_dimensions ) == 0:
        req_proj_dimensions = [ 'eccentricity' ]
    shading_key = data.get( "shading_key", None )

    movies = None
    all_movies = load_movies( movies_dir )

    requested_movies = data.get( "movie_ids", [] )
    if len( requested_movies ) == 0:
        movies = all_movies
    else:
        movies = { key:value for key, value in all_movies.items() if value['title'] in requested_movies }

    results = []

    for graph_props in data["graph_properties"]:
        epsilon = graph_props["epsilon"]
        slide = graph_props["slide"]
        width = graph_props["width"]

        nodes, edges, filtered_cliques, max_epsilon = get_graphs( movies, req_dimensions, dimension_weights, proj_dimensions, epsilon, width, slide, shading_key )
        results.append( { "nodes" : nodes, "edges" : edges, "filtered_cliques" : filtered_cliques, 'max_epsilon' : max_epsilon } )

    return jsonify( { "data" : results } )
'''

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
