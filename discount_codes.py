#!/usr/bin/env python

from collections import Counter
import datetime
import json
import logging
import random
import uuid

# Mail config
MAIL_SERVER = 'smtp.mandrillapp.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USE_SSL = False
MAIL_DEBUG = False
MAIL_USERNAME = 'matt@viblio.com'
MAIL_PASSWORD = 'MZDI2Ncl5L1qY--irqO81A'
DEFAULT_MAIL_SENDER = 'matt@viblio.com'
EXTERNAL_SERVER_BASE_URL = 'http://ec2-52-12-132-124.us-west-2.compute.amazonaws.com'
SEND_AS = ( 'GHC 2015 Registration', 'registration@anitaborg.org' )
ADMIN_MAIL_RECIPIENTS = [ 'kathrynb@anitaborg.org', 'matt@viblio.com' ]

from flask import Flask
from flask_mail import Mail, Message
app = Flask(__name__)
app.config.from_object(__name__)
mail = Mail( app )

from datastore import get_discount_codes

badge_types = {
    "general_full"  : { 'name'          : 'General',
                        'product_code'  : 'GHP5G',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : True,
                        'regonline_str' : '-100%' },
    "student_full"  : { 'name'          : 'Student',
                        'product_code'  : 'GHP5A',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : True,
                        'regonline_str' : '-100%' },
    "academic_full" : { 'name'          : 'Academic',
                        'product_code'  : 'GHP5A',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : True,
                        'regonline_str' : '-100%' },
    "transition_full" : { 'name'          : 'Transition',
                          'product_code'  : 'GHP5C',
                          'regonline_url' : '[To Be Determined]',
                          'reserve_spot'  : True,
                        'regonline_str' : '-100%' },
    "general_1"     : { 'name'          : 'General One Day',
                        'product_code'  : 'GHP5G',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : True,
                        'regonline_str' : '-100%' },
    "speaker_full"  : { 'name'          : 'Speaker Full Conference',
                        'product_code'  : 'GHP5G',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : True,
                        'regonline_str' : '-100%' },
    "speaker_1"     : { 'name'          : 'Speaker One Day',
                        'product_code'  : 'GHP5G',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : True,
                        'regonline_str' : '-100%' },
    "booth"         : { 'name'          : 'Booth Staff Only',
                        'product_code'  : 'GHP5B',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : True,
                        'summary_group' : 'Corporate',
                        'regonline_str' : '-100%' },
    "student_20"    : { 'name'          : 'Student 20% Off',
                        'product_code'  : 'GHP5S',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : False,
                        'regonline_str' : '-20%' },
    "student_15"    : { 'name'          : 'Student 15% Off',
                        'product_code'  : 'GHP5S',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : False,
                        'regonline_str' : '-15%' },
    "student_10"    : { 'name'          : 'Student 10% Off',
                        'product_code'  : 'GHP5S',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : False,
                        'regonline_str' : '-10%' },
}

sponsor_reporting_groups = {
    'ABI Partners Only - Diamond'  : 'Corporate',
    'ABI Partners Only - Platinum' : 'Corporate',
    'Corporate - Gold'             : 'Corporate', 
    'Corporate - Silver'           : 'Corporate', 
    'Academic - Gold'              : 'Academic', 
    'Academic - Silver'            : 'Academic', 
    'Academic - Bronze'            : 'Academic', 
    'Lab & Non-Profit - Gold'      : 'Lab and Non-Profit', 
    'Lab & Non-Profit - Silver'    : 'Lab and Non-Profit', 
    'Lab & Non-Profit - Bronze'    : 'Lab and Non-Profit', 
     # DEBUG - this one doesn't really have an affiliation, we'll lump
     # it in with corporate.
    'GHC Event Sponsorships and Enterprise Packages' : 'Corporate',
    'Show Management'              : 'Show Management',
 }

sponsor_entitlements_2015 = {
    'ABI Partners Only - Diamond'  : [
        { 'badge_type' : 'general_full',
          'quantity' : 20, },
        { 'badge_type' : 'booth',
          'quantity' : 8, },
    ],
    'ABI Partners Only - Platinum' : [ 
        { 'badge_type' : 'general_full',
          'quantity' : 10, },
        { 'badge_type' : 'booth',
          'quantity' : 4, },
    ],
    'Corporate - Gold'             : [ 
        { 'badge_type' : 'general_full',
          'quantity' : 5, },
        { 'badge_type' : 'booth',
          'quantity' : 3, },
    ],
    'Corporate - Silver'           : [ 
        { 'badge_type' : 'general_full',
          'quantity' : 3, },
        { 'badge_type' : 'booth',
          'quantity' : 2, },
    ],
    'Academic - Gold'              : [ 
        { 'badge_type' : 'academic_full',
          'quantity' : 3, },
        { 'badge_type' : 'student_20',
          'quantity' : 100, },
    ],
    'Academic - Silver'            : [ 
        { 'badge_type' : 'academic_full',
          'quantity' : 2, },
        { 'badge_type' : 'student_15',
          'quantity' : 50, },
    ],
    'Academic - Bronze'            : [ 
        { 'badge_type' : 'academic_full',
          'quantity' : 1, },
        { 'badge_type' : 'student_10',
          'quantity' : 25, },
    ],
    'Lab & Non-Profit - Gold'      : [ 
        { 'badge_type' : 'general_full',
          'quantity' : 3, },
    ],
    'Lab & Non-Profit - Silver'    : [ 
        { 'badge_type' : 'general_full',
          'quantity' : 2, },
    ],
    'Lab & Non-Profit - Bronze'    : [ 
        { 'badge_type' : 'general_full',
          'quantity' : 1, },
    ],
}

def get_badge_types( eventID=None ):
    # We only have one set of badge types, so ignore the eventID for now.
    return badge_types

def get_sponsor_reporting_groups( eventID=None ):
    # We only have one set of spornsor reporting groups, so ignore the eventID for now.
    return sponsor_reporting_groups

def get_entitlements_for_sponsor_type( sponsorType ):
    result = []

    if sponsorType in sponsor_entitlements_2015:
        for entitlement in sponsor_entitlements_2015:
            entitlement['code_source'] = sponsorType
            result.append( entitlement )

    return result

def generate_discount_codes( eventID, sponsor, all_existing_codes, add_ons=None ):
    '''Takes in eventID and a sponsor object which can be either a suds
    object or a sponsor like hash from get_sponsors.

    Takes a list argument of all existing discount codes for that
    event, and an optional list of add_on events for that sponsor.

    It consults the list of existing codes, and adds any entitlements
    that are not in place.

    It never deletes an existing entitlement, although it does send an
    email if there is a mismatch between what it computes the sponsor
    is entitled to and what it has been awarded.
    '''

    all_existing_code_values = { x['discount_code']:True for x in all_existing_codes }
    
    discount_codes = []

    existing_codes = [ x for x in all_existing_codes if x['SponsorID'] == sponsor['ID'] ]
    granted_codes = Counter( [ ( code['code_source'], code['badge_type'], code['quantity'] ) for code in existing_codes ] )

    entitlements = Counter( [ ( sponsor['RegistrationType'], entitlement['badge_type'], entitlement['quantity'] ) for entitlement in sponsor_entitlements_2015[sponsor['RegistrationType'] ] ] )

    for add_on in add_ons.get( sponsor['ID'], [] ):
        # DEBUG - This stuff should probably live in a configuration file.
        if add_on['product_name'] == 'Enterprise Pack':
            badge_type = 'general_full'
            if sponsor['RegistrationType'].startswith( 'Academic' ):
                badge_type = 'academic_full'
            
            entitlements.update( [ ( 'Enterprise Pack', badge_type, 10 ) ] * add_on['quantity'] )

    additional_entitlements = entitlements - granted_codes

    if sponsor['RegistrationType'] in sponsor_entitlements_2015:
        for entitlement in additional_entitlements.elements():
            #for entitlement in sponsor_entitlements_2015[sponsor['RegistrationType']]:

            ( code_source, badge_type, quantity ) = entitlement

            discount_code = {
                'SponsorID'        : sponsor['ID'],
                'RegTypeID'        : sponsor['RegTypeID'],
                'RegistrationType' : sponsor['RegistrationType'],
                'created_date'     : sponsor['AddDate'],
                'code_source'      : code_source
            }

            discount_code['ID'] = str( uuid.uuid4() )

            discount_code['badge_type'] = badge_type
            discount_code['regonline_str'] = badge_types[badge_type]['regonline_str']
            discount_code['quantity'] = quantity
            # Get rid of any unicode stuff we don't want.
            company_abbr = sponsor['Company'].encode( 'ascii', 'ignore' ).lower()
            
            skip_chars = [ 'a', 'e', 'i', 'o', 'u', 'l' ]
            company_abbr = ''.join( [ c for c in company_abbr if ( ( c.isalnum() ) and ( c not in skip_chars ) ) ] )
            company_abbr = company_abbr.ljust( 4, '0' )
            company_abbr = company_abbr[:4]

            unique = False
            while not unique:
                random_string = get_random_string( 3 )
                new_discount_code = "%s%s%03d" % ( company_abbr, random_string, quantity )
                new_discount_code = new_discount_code.replace( '0', 'a' )
                new_discount_code = new_discount_code.replace( '1', 'b' )
                if new_discount_code not in all_existing_code_values:
                    unique = True
                else:
                    # We had a duplicate collision, try again with a new random string.
                    pass

            discount_code['discount_code'] = new_discount_code
            discount_codes.append( discount_code )
            logging.info( json.dumps( { 'message' : "Created new discount_code: %s, data: %s" % ( new_discount_code, { k:v for k,v in discount_code.items() if k != 'created_date' } ) } ) )
    else:
        error_message = "No sponsor codes found for registration type: %s" % ( sponsor['RegistrationType'] )
        logging.error( json.dumps( { 'message' : error_message } ) )
        raise Exception( error_message )
    
    if granted_codes - entitlements != Counter():
        message = "Sponsor %d has more discount codes granted to them than they are entitled to: %s" % ( sponsor['ID'], granted_codes - entitlements )
        # Log this as an error so it gets sent out via Loggly to investigate.
        logging.error( json.dumps( { 'message' : message } ) )
        # Send an email to admins.
        try:
            email_recipients = ADMIN_MAIL_RECIPIENTS

            mail_message = Message( "Warning: Discount Code Mismatch for %s" % ( sponsor['Company'] ),
                                    sender = SEND_AS,
                                    recipients = email_recipients )
        
            message_html = ''
    
            message_html += '<p>Sponsor %s has granted discount codes which exceed their entitlement: %s</p>' % ( sponsor['Company'], granted_codes - entitlements )
            message_html += '<p>This may not be a problem, but it may indicate that this sponsor was upgraded, or cancelled some enterprise pack purchases, and now their discount codes do not match their entitlement.  Please verify.</p>'

            mail_message.html = message_html
            with app.test_request_context():
                mail.send( mail_message )

        except Exception as e:
            logging.error( json.dumps( { 'message' : "Failed to send notification email to %s, error was: %s" % ( email_recipients, e ) } ) )

    # Send an email to the user.
    recipients = []
    if 'Email' in sponsor and len( sponsor['Email'] ):
        recipients.append( sponsor['Email'] )
    if 'CCEmail' in sponsor and len( sponsor['CCEmail'] ):
        recipients.append( sponsor['CCEmail'] )
        
    error_message = None
    if len( recipients ) == 0:
        error_message = "ERROR, NO RECIPIENTS AVAILABLE FOR SPONSOR %d" % ( sponsor['ID'] )

    try:
        # DEBUG actually send to recipients here
        #email_recipients = ADMIN_MAIL_RECIPIENTS + recipients
        email_recipients = ADMIN_MAIL_RECIPIENTS

        mail_message = Message( "Grace Hopper Celebration 2015 Discount Codes",
                                sender = SEND_AS,
                                recipients = email_recipients,
                                bcc = ADMIN_MAIL_RECIPIENTS)
        
        message_html = ''

        if error_message is not None:
            message_html += "<p>%s</p>" % ( error_message )
    
        message_html += '<p>Your %s discount codes are:<ul>' % ( sponsor['Company'] )

        for discount_code in sorted( discount_codes, key = lambda x: x['discount_code'] ):
            # All this error checking madness is for backfilled
            # data, for future data where we generated all the
            # codes there will always be valid badge types.
            badge_type_name = discount_code['badge_type']
            regonline_url = badge_types[discount_code['badge_type']]['regonline_url']
            
            discount_search_url = "%s%s?code=%s" % ( EXTERNAL_SERVER_BASE_URL, '/discount_code/', discount_code['discount_code'] )
            message_html += '<li>%s<ul><li>Badge Type: %s</li><li>Quantity: %d</li><li>Registration Link: <a href="%s">%s</a></li><li>Registration Redemption Report: <a href="%s">%s</a></li></ul></li>' % ( 
                discount_code['discount_code'],
                badge_type_name,
                discount_code['quantity'],
                regonline_url,
                regonline_url,
                discount_search_url, 
                discount_search_url )

        mail_message.html = message_html
        with app.test_request_context():
            mail.send( mail_message )

    except Exception as e:
        logging.error( json.dumps( { 'message' : "Failed to send notification email to %s, error was: %s" % ( email_recipients, e ) } ) )


    return discount_codes

def get_random_string( length ):
    '''Return a random string of length'''
    alphabet = "bcdfghjkmnpqrstvwxyz23456789"
    
    result = ""
    for i in range( length ):
        result += random.choice( alphabet )
        
    return result
        
def generate_discount_code( eventID, sponsor, badge_type, quantity, all_existing_codes, code_source=None ):
    '''Takes in eventID and a sponsor object which can be either a suds
    object or a sponsor like hash from get_sponsors.

    Takes a list argument of all existing discount codes for that
    event.
    '''

    all_existing_code_values = { x['discount_code']:True for x in all_existing_codes }
    
    discount_code = {
        'SponsorID'        : sponsor['ID'],
        'RegTypeID'        : sponsor['RegTypeID'],
        'RegistrationType' : sponsor['RegistrationType'],
        'created_date'     : datetime.datetime.utcnow()
    }

    discount_codes = []

    discount_code['ID'] = str( uuid.uuid4() )

    discount_code['badge_type'] = badge_type

    if code_source == None:
        discount_code['code_source'] = 'Show Management'
    else:
        discount_code['code_source'] = code_source

    discount_code['regonline_str'] = badge_types[badge_type]['regonline_str']
    discount_code['quantity'] = quantity
    # Get rid of any unicode stuff we don't want.
    company_abbr = sponsor['Company'].encode( 'ascii', 'ignore' ).lower()
            
    # Avoid ambiguous characters and non-alphanumeric characters.
    skip_chars = [ 'a', 'e', 'i', 'o', 'u', 'l' ]
    company_abbr = ''.join( [ c for c in company_abbr if ( ( c.isalnum() ) and ( c not in skip_chars ) ) ] )
    company_abbr = company_abbr.ljust( 4, '0' )
    company_abbr = company_abbr[:4]

    unique = False
    while not unique:
        random_string = get_random_string( 3 )
        new_discount_code = "%s%s%03d" % ( company_abbr, random_string, quantity )
        new_discount_code = new_discount_code.replace( '0', 'a' )
        new_discount_code = new_discount_code.replace( '1', 'b' )
        if new_discount_code not in all_existing_code_values:
            unique = True
        else:
            # We had a duplicate collision, try again with a new random string.
            pass

    discount_code['discount_code'] = new_discount_code

    logging.info( json.dumps( { 'message' : "Created new discount_code: %s" % ( new_discount_code ),
                                'discount_code_data' : { k:v for k,v in discount_code.items() if k != 'created_date' } } ) )

    return discount_code
