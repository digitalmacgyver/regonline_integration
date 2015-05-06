#!/usr/bin/env python

from bdateutil import relativedelta
from collections import Counter
import datetime
import json
import logging
import pytz
import random
import uuid

from datastore import get_discount_codes

from flask import Flask
from flask_mail import Mail, Message
app = Flask(__name__)
app.config.from_pyfile( "./config/present.default.conf" )
#app.config.from_envvar( "DISCOUNT_CODES_CONFIG" )
mail = Mail()

app.config.update( MAIL_PASSWORD = None )
with open( app.config['MAIL_PASSWORD_FILE'], "r" ) as f:
    for key in f.readlines():
        key = key.strip()
        if key.startswith( '#' ):
            continue
        elif len( key ) == 0:
            continue
        else:
            app.config.update( MAIL_PASSWORD = key )
            break

# This data structure controls lots of behavior throughout the app.
#
# The name is used to display this badge type in administrative web
# forms.
#
# The regonline_url is used in email templates to refer recipients to
# the correct registration URL to redeem their codes.
#
# The reserve_spot field controls whether in reporting we treat
# reservations of these codes as occupying a reserved spot or not.
#
# The regonline_str is the amount of the discount this badge confers
# encoded in a manner consistent with how RegOnline's syntax requires.
#
badge_types = {
    "general_full"  : { 'name'          : 'General',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : True,
                        'regonline_str' : '-100%' },
    "student_full"  : { 'name'          : 'Student',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : True,
                        'regonline_str' : '-100%' },
    "academic_full" : { 'name'          : 'Academic',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : True,
                        'regonline_str' : '-100%' },
    "transition_full" : { 'name'          : 'Transition',
                          'regonline_url' : '[To Be Determined]',
                          'reserve_spot'  : True,
                        'regonline_str' : '-100%' },
    "general_1"     : { 'name'          : 'General One Day',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : True,
                        'regonline_str' : '-100%' },
    "speaker_full"  : { 'name'          : 'Speaker Full Conference',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : True,
                        'regonline_str' : '-100%' },
    "speaker_1"     : { 'name'          : 'Speaker One Day',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : True,
                        'regonline_str' : '-100%' },
    "booth"         : { 'name'          : 'Booth Staff Only',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : True,
                        'summary_group' : 'Corporate',
                        'regonline_str' : '-100%' },
    "student_20"    : { 'name'          : 'Student 20% Off',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : False,
                        'regonline_str' : '-20%' },
    "student_15"    : { 'name'          : 'Student 15% Off',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : False,
                        'regonline_str' : '-15%' },
    "student_10"    : { 'name'          : 'Student 10% Off',
                        'regonline_url' : '[To Be Determined]',
                        'reserve_spot'  : False,
                        'regonline_str' : '-10%' },
}

# For reporting purposes, we wish to group various redemptions into
# different categories, this achieves that mapping.
#
# Keys are the RegOnline registration types of the sponsors who
# granted the codes, values are the reporting group labels.
# 
# These codes pertain to the GHC 2015 Sponsors registration in
# RegOnline.
#
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
    'Show Management'              : 'Show Management',
     # DEBUG - this one doesn't really have an affiliation, we'll lump
     # it in with corporate.
    'GHC Event Sponsorships and Enterprise Packages' : 'Corporate',
 }

# For each RegOnline GHC 2015 sponsor RegistrationType define their
# basic entitlements in terms of badge_type keys and quantities.
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
    'GHC Event Sponsorships and Enterprise Packages' : [],
    'Show Management' : []
}

def get_badge_types( eventID=None ):
    '''We only have one set of badge types, so ignore the eventID for now.
    '''
    return badge_types

def get_sponsor_reporting_groups( eventID=None ):
    '''We only have one set of sponsor reporting groups, so ignore the
    eventID for now.'''

    return sponsor_reporting_groups

def generate_discount_codes( eventID, sponsor, all_existing_codes, 
                             add_ons=None ):
    '''Takes in eventID and a sponsor object which can be either a suds
    object or a sponsor like hash from get_sponsors.

    Takes a list argument of all existing discount codes for that
    event (this is used to ensure unique code values), and an optional
    list of add_on entitlements for that sponsor.

    It consults the list of existing codes, and adds any entitlements
    that are not in place.

    It never deletes an existing entitlement, although it does send an
    email to the administrators if there is a mismatch between what it
    computes the sponsor is entitled to and what it has been awarded.

    It raises an exception if we are asked to generate discount codes
    for a RegOnline sponsor['RegistrationType'] we don't recognize.
    '''

    # A hash keyed off the existing codes.
    all_existing_code_values = { x['discount_code']:True for x in all_existing_codes }
    
    # The return value of this function, those codes which we
    # generated.
    discount_codes = []

    # A list of the codes for this sponsor.
    existing_codes = [ x for x in all_existing_codes if x['SponsorID'] == sponsor['ID'] ]
    # Formulate the existing codes of this sponsor as a mapping of:
    #
    # ( code_source, badge_type, quantity ) tuples to the number of
    # times that tuple is granted.
    granted_codes = Counter( [ ( code['code_source'], code['badge_type'], code['quantity'] ) for code in existing_codes ] )

    # Now generate a list of what this sponsor is entitled too.
    #
    # The default entitlements based on the sponsorship level:
    entitlements = Counter( [ ( sponsor['RegistrationType'], entitlement['badge_type'], entitlement['quantity'] ) for entitlement in sponsor_entitlements_2015[sponsor['RegistrationType'] ] ] )

    # Now generate a list of what this sponsor is entitled too.
    #
    # Any additional enterprise packs the sponsor has purchased which
    # are good for 10 additional reserved general admission badges.
    for add_on in add_ons.get( sponsor['ID'], [] ):
        # DEBUG - This stuff should probably live in a configuration file.
        if add_on['product_name'] == 'Enterprise Pack':
            badge_type = 'general_full'
            if sponsor['RegistrationType'].startswith( 'Academic' ):
                badge_type = 'academic_full'
            
            entitlements.update( [ ( 'Enterprise Pack', badge_type, 10 ) ] * add_on['quantity'] )

        elif add_on['product_name'].startswith( "Bulk Purchase - " ):
            badge_type = "%s_full" % ( add_on['product_name'].lower().split()[-1] )
            entitlements.update( [ ( add_on['product_name'], badge_type, 10 ) ] * add_on['quantity'] )

    # The Python Counter type allows this subtraction method to
    # calculate what this sponsor is entitled to minus what they have
    # already been granted.
    additional_entitlements = entitlements - granted_codes

    # If not issue a warning, this entire system only works with the
    # encoded RegOnline RegistrationTypes from 2015.
    if sponsor['RegistrationType'] in sponsor_entitlements_2015:
        # Grant any entitlements not previously granted.
        for entitlement in additional_entitlements.elements():

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

            # Generate a unique RegOnline redemption code for this
            # discount code.  RegOnline prohibits non-alphanumeric
            # characters in the code, and limits the total duration to
            # 16 characters or so.

            # Get rid of any unicode stuff we don't want.
            company_abbr = sponsor['Company'].encode( 'ascii', 'ignore' ).lower()
            
            # Remove any vowels to help shorten the company name down
            # to 4 characters, and ignore any characters which are
            # ambiguous under capitalization or certain fonts.
            skip_chars = [ 'a', 'e', 'i', 'o', 'u', 'l' ]
            company_abbr = ''.join( [ c for c in company_abbr if ( ( c.isalnum() ) and ( c not in skip_chars ) ) ] )
            company_abbr = company_abbr.ljust( 4, '0' )
            company_abbr = company_abbr[:4]

            # On the off chance that we generated a duplicate code
            # (perhaps tow companies have similar names, or one
            # company has zillions of codes...)
            unique = False
            while not unique:
                random_string = get_random_string( 3 )
                new_discount_code = "%s%s%03d" % ( company_abbr, random_string, quantity )
                # We prohibit 0 and 1 as being ambiguous with O and l
                # in some fonts.
                new_discount_code = new_discount_code.replace( '0', 'a' )
                new_discount_code = new_discount_code.replace( '1', 'b' )
                if new_discount_code not in all_existing_code_values:
                    unique = True
                else:
                    # We had a duplicate collision, try again with a
                    # new random string.
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
            email_recipients = app.config['ADMIN_MAIL_RECIPIENTS']

            mail_message = Message( "Warning: Discount Code Mismatch for %s" % ( sponsor['Company'] ),
                                    sender = app.config['SEND_AS'],
                                    recipients = email_recipients )
            
            message_html = ''
    
            message_html += '<p>Sponsor %s with RegOnline ID %d has granted discount codes which exceed their entitlement: %s</p>' % ( sponsor['Company'], sponsor['ID'], granted_codes - entitlements )
            message_html += '<p>This may not be a problem, but it may indicate that this sponsor was upgraded, or canceled some enterprise pack purchases, and now their discount codes do not match their entitlement.  Please verify.</p>'

            mail_message.html = message_html
            with app.test_request_context():
                mail.init_app( app )
                mail.send( mail_message )

        except Exception as e:
            logging.error( json.dumps( { 'message' : "Failed to send notification email to %s, error was: %s" % ( email_recipients, e ) } ) )

    # Send an email to the sponsor contacts about their new code.
    recipients = []
    if 'Email' in sponsor and len( sponsor['Email'] ):
        recipients.append( sponsor['Email'] )
    if 'CCEmail' in sponsor and len( sponsor['CCEmail'] ):
        recipients.append( sponsor['CCEmail'] )
        
    error_message = None
    if len( recipients ) == 0:
        # If there are no sponsor emails, send the admins a note.
        error_message = "ERROR, NO RECIPIENTS AVAILABLE FOR SPONSOR %d" % ( sponsor['ID'] )

    try:
        # DEBUG actually send to recipients here
        #email_recipients = app.config['ADMIN_MAIL_RECIPIENTS'] + recipients
        email_recipients = app.config['ADMIN_MAIL_RECIPIENTS']

        today = datetime.date.today()
        today_4pm = datetime.datetime( today.year, today.month, today.day, 16, tzinfo=pytz.timezone( 'PST8PDT' ) )
        tomorrow_4pm = today_4pm + relativedelta( bdays = +1 )
        when = tomorrow_4pm.astimezone( pytz.utc )

        extra_headers = {
            'X-MC-SendAt' : when.strftime( "%Y-%m-%d %H:%M:%S" )
        }

        mail_message = Message( "Grace Hopper Celebration 2015 Discount Codes",
                                sender = app.config['SEND_AS'],
                                recipients = email_recipients,
                                bcc = app.config['ADMIN_MAIL_RECIPIENTS'], 
                                extra_headers = extra_headers )
        
        message_html = ''

        if error_message is not None:
            message_html += "<p>%s</p>" % ( error_message )
    
        message_html += '<p>Your %s discount codes are:<ul>' % ( sponsor['Company'] )

        for discount_code in sorted( discount_codes, key = lambda x: x['discount_code'] ):
            badge_type_name = discount_code['badge_type']
            regonline_url = badge_types[discount_code['badge_type']]['regonline_url']
            
            discount_search_url = "%s%s?code=%s" % ( app.config['EXTERNAL_SERVER_BASE_URL'], '/discount_code/', discount_code['discount_code'] )
            message_html += '<li>%s<ul><li>Source: %s</li><li>Badge Type: %s</li><li>Quantity: %d</li><li>Registration Link: <a href="%s">%s</a></li><li>Registration Redemption Report: <a href="%s">%s</a></li></ul></li>' % ( 
                discount_code['discount_code'],
                discount_code['code_source'],
                badge_type_name,
                discount_code['quantity'],
                regonline_url,
                regonline_url,
                discount_search_url, 
                discount_search_url )

        mail_message.html = message_html
        with app.test_request_context():
            mail.init_app( app )
            mail.send( mail_message )

    except Exception as e:
        logging.error( json.dumps( { 'message' : "Failed to send notification email to %s, error was: %s" % ( email_recipients, e ) } ) )


    return discount_codes

def get_random_string( length ):
    '''Helper function that generates a random string of the desired
    length.'''

    # Ignore vowels which might make unfortunate words and ambiguous
    # characters like 0O1l.
    alphabet = "bcdfghjkmnpqrstvwxyz23456789"
    
    result = ""
    for i in range( length ):
        result += random.choice( alphabet )
        
    return result
        
def generate_discount_code( eventID, sponsor, badge_type, quantity, all_existing_codes, code_source=None ):
    '''Takes in eventID, sponsor object which can be either a suds object
    or a sponsor like hash from get_sponsors, and quantity.

    Takes a list argument of all existing discount codes for that
    event.

    Optionally takes in a code_source, if not specified defaults to
    'Show Management'
    '''

    all_existing_code_values = { x['discount_code']:True for x in all_existing_codes }
    
    discount_code = {
        'SponsorID'        : sponsor['ID'],
        'RegTypeID'        : sponsor['RegTypeID'],
        'RegistrationType' : sponsor['RegistrationType'],
        'created_date'     : pytz.utc.localize( datetime.datetime.utcnow() )
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

    # Generate our RegOnline compatible redemption code.
    #
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
            # We had a duplicate collision, try again with a new random 
            # string.
            pass

    discount_code['discount_code'] = new_discount_code

    logging.info( json.dumps( { 'message' : "Created new discount_code: %s" % ( new_discount_code ),
                                'discount_code_data' : { k:v for k,v in discount_code.items() if k != 'created_date' } } ) )

    return discount_code
