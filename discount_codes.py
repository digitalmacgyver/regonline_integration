#!/usr/bin/env python

import random
import uuid

from datastore import get_discount_codes

sponsor_entitlements_2015 = {
    'ABI Partners Only - Diamond' : [
        { 'product_code' : 'GHP5G',
          'badge_type' : 'general_full',
          'regonline_str' : '-100%',
          'quantity' : 20, },
        { 'product_code' : 'GHP5B',
          'badge_type' : 'booth',
          'regonline_str' : '-100%',
          'quantity' : 8, },
    ],
    'ABI Partners Only - Platinum' : [ 
        { 'product_code' : 'GHP5G',
          'badge_type' : 'general_full',
          'regonline_str' : '-100%',
          'quantity' : 10, },
        { 'product_code' : 'GHP5B',
          'badge_type' : 'booth',
          'regonline_str' : '-100%',
          'quantity' : 4, },
    ],
    'Corporate - Gold'             : [ 
        { 'product_code' : 'GHP5G',
          'badge_type' : 'general_full',
          'regonline_str' : '-100%',
          'quantity' : 5, },
        { 'product_code' : 'GHP5B',
          'badge_type' : 'booth',
          'regonline_str' : '-100%',
          'quantity' : 3, },
    ],
    'Corporate - Silver'           : [ 
        { 'product_code' : 'GHP5G',
          'badge_type' : 'general_full',
          'regonline_str' : '-100%',
          'quantity' : 3, },
        { 'product_code' : 'GHP5B',
          'regonline_str' : '-100%',
          'badge_type' : 'booth',
          'quantity' : 2, },
    ],
    'Academic - Gold'              : [ 
        { 'product_code' : 'GHP5A',
          'badge_type' : 'academic_full',
          'regonline_str' : '-100%',
          'quantity' : 3, },
        { 'product_code' : 'GHP5S',
          'badge_type' : 'student_20',
          'regonline_str' : '-20%',
          'quantity' : 100, },
    ],
    'Academic - Silver'            : [ 
        { 'product_code' : 'GHP5A',
          'badge_type' : 'academic_full',
          'regonline_str' : '-100%',
          'quantity' : 2, },
        { 'product_code' : 'GHP5S',
          'badge_type' : 'student_15',
          'regonline_str' : '-15%',
          'quantity' : 50, },
    ],
    'Academic - Bronze'            : [ 
        { 'product_code' : 'GHP5A',
          'badge_type' : 'academic_full',
          'regonline_str' : '-100%',
          'quantity' : 1, },
        { 'product_code' : 'GHP5S',
          'badge_type' : 'student_10',
          'regonline_str' : '-10%',
          'quantity' : 25, },
    ],
    'Lab & Non-Profit - Gold'      : [ 
        { 'product_code' : 'GHP5G',
          'badge_type' : 'general_full',
          'regonline_str' : '-100%',
          'quantity' : 3, },
    ],
    'Lab & Non-Profit - Silver'    : [ 
        { 'product_code' : 'GHP5G',
          'badge_type' : 'general_full',
          'regonline_str' : '-100%',
          'quantity' : 2, },
    ],
    'Lab & Non-Profit - Bronze'    : [ 
        { 'product_code' : 'GHP5G',
          'badge_type' : 'general_full',
          'regonline_str' : '-100%',
          'quantity' : 1, },
    ],
}

def generate_discount_codes( eventID, sponsor, all_existing_codes ):
    '''Takes in eventID and a sponsor object which can be either a suds
    object or a sponsor like hash from get_sponsors.

    Takes a list argument of all existing discount codes for that
    event.
    '''

    all_existing_code_values = { x['discount_code']:True for x in all_existing_codes }
    
    discount_code_template = {
        'SponsorID'        : sponsor['ID'],
        'RegTypeID'        : sponsor['RegTypeID'],
        'RegistrationType' : sponsor['RegistrationType'],
    }

    discount_codes = []

    if sponsor['RegistrationType'] in sponsor_entitlements_2015:
        for entitlement in sponsor_entitlements_2015[sponsor['RegistrationType']]:
            discount_code = discount_code_template

            discount_code['ID'] = str( uuid.uuid4() )

            discount_code['badge_type'] = entitlement['badge_type']
            discount_code['regonline_str'] = entitlement['regonline_str']
            discount_code['quantity'] = entitlement['quantity']
            # Get rid of any unicode stuff we don't want.
            company_abbr = sponsor['Company'].encode( 'ascii', 'ignore' ).upper()
            
            skip_chars = [ 'A', 'E', 'I', 'O', 'U', ' ', 'L' ]
            company_abbr = ''.join( [ c for c in company_abbr if c not in skip_chars ] )
            company_abbr = company_abbr.ljust( 4, '0' )
            company_abbr = company_abbr[:4]

            unique = False
            while not unique:
                random_string = get_random_string( 3 )
                new_discount_code = ( "%s-0-%s-%s-%03d" % ( company_abbr, entitlement['product_code'], random_string, entitlement['quantity'] ) ).upper()
                new_discount_code = new_discount_code.replace( '0', 'A' )
                new_discount_code = new_discount_code.replace( '1', 'B' )
                if new_discount_code not in all_existing_code_values:
                    unique = True
                else:
                    # We had a duplicate collision, try again with a new random string.
                    pass

            discount_code['discount_code'] = new_discount_code
            discount_codes.append( discount_code )
    else:
        raise Exception( "No sponsor codes found for registration type: %s" % ( sponsor['RegistrationType'] ) )
    
    return discount_codes

def get_random_string( length ):
    '''Return a random string of length'''
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    
    result = ""
    for i in range( length ):
        result += random.choice( alphabet )
        
    return result
        
    
