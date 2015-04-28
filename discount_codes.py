#!/usr/bin/env python

import random
import uuid

from datastore import get_discount_codes

badge_types = {
    "general_full"  : { 'name'          : 'General Full',
                        'product_code'  : 'GHP5G',
                        'regonline_url' : '[To Be Determined]',
                        'regonline_str' : '-100%' },
    "booth"         : { 'name'          : 'Booth Staff',
                        'product_code'  : 'GHP5B',
                        'regonline_url' : '[To Be Determined]',
                        'regonline_str' : '-100%' },
    "academic_full" : { 'name'          : 'Academic Full',
                        'product_code'  : 'GHP5A',
                        'regonline_url' : '[To Be Determined]',
                        'regonline_str' : '-100%' },
    "student_20"    : { 'name'          : 'Student 20% Off',
                        'product_code'  : 'GHP5S',
                        'regonline_url' : '[To Be Determined]',
                        'regonline_str' : '-20%' },
    "student_15"    : { 'name'          : 'Student 15% Off',
                        'product_code'  : 'GHP5S',
                        'regonline_url' : '[To Be Determined]',
                        'regonline_str' : '-15%' },
    "student_10"    : { 'name'          : 'Student 10% Off',
                        'product_code'  : 'GHP5S',
                        'regonline_url' : '[To Be Determined]',
                        'regonline_str' : '-10%' },
    "general_1"     : { 'name'          : 'General Day 1',
                        'product_code'  : 'GHP5G',
                        'regonline_url' : '[To Be Determined]',
                        'regonline_str' : '-100%' },
    "general_2"     : { 'name'          : 'General Day 2',
                        'product_code'  : 'GHP5G',
                        'regonline_url' : '[To Be Determined]',
                        'regonline_str' : '-100%' },
    "general_3"     : { 'name'          : 'General Day 3',
                        'product_code'  : 'GHP5G',
                        'regonline_url' : '[To Be Determined]',
                        'regonline_str' : '-100%' },
    "speaker_full"  : { 'name'          : 'Speaker Full',
                        'product_code'  : 'GHP5G',
                        'regonline_url' : '[To Be Determined]',
                        'regonline_str' : '-100%' },
    "speaker_1"     : { 'name'          : 'Speaker Day 1',
                        'product_code'  : 'GHP5G',
                        'regonline_url' : '[To Be Determined]',
                        'regonline_str' : '-100%' },
    "speaker_2"     : { 'name'          : 'Speaker Day 2',
                        'product_code'  : 'GHP5G',
                        'regonline_url' : '[To Be Determined]',
                        'regonline_str' : '-100%' },
    "speaker_3"     : { 'name'          : 'Speaker Day 3',
                        'product_code'  : 'GHP5G',
                        'regonline_url' : '[To Be Determined]',
                        'regonline_str' : '-100%' },
}


sponsor_entitlements_2015 = {
    'ABI Partners Only - Diamond' : [
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

def get_badge_types( eventID ):
    '''Return an array of badge ID, badge name types for this eventID.'''
    # We only have one set of badge types, so ignore the eventID for now.
    return badge_types


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
            discount_code['regonline_str'] = badge_types[entitlement['badge_type']]['regonline_str']
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
                new_discount_code = ( "%s-0-%s-%s-%03d" % ( company_abbr, badge_types[entitlement['badge_type']]['product_code'], random_string, entitlement['quantity'] ) ).upper()
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
        
def generate_discount_code( eventID, sponsor, badge_type, quantity, all_existing_codes ):
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

    discount_code = discount_code_template

    discount_code['ID'] = str( uuid.uuid4() )

    discount_code['badge_type'] = badge_type
    discount_code['regonline_str'] = badge_types[badge_type]['regonline_str']
    discount_code['quantity'] = quantity
    # Get rid of any unicode stuff we don't want.
    company_abbr = sponsor['Company'].encode( 'ascii', 'ignore' ).upper()
            
    skip_chars = [ 'A', 'E', 'I', 'O', 'U', ' ', 'L' ]
    company_abbr = ''.join( [ c for c in company_abbr if c not in skip_chars ] )
    company_abbr = company_abbr.ljust( 4, '0' )
    company_abbr = company_abbr[:4]

    unique = False
    while not unique:
        random_string = get_random_string( 3 )
        new_discount_code = ( "%s-0-%s-%s-%03d" % ( company_abbr, badge_types[badge_type]['product_code'], random_string, quantity ) ).upper()
        new_discount_code = new_discount_code.replace( '0', 'A' )
        new_discount_code = new_discount_code.replace( '1', 'B' )
        if new_discount_code not in all_existing_code_values:
            unique = True
        else:
            # We had a duplicate collision, try again with a new random string.
            pass

    discount_code['discount_code'] = new_discount_code

    return discount_code
    
