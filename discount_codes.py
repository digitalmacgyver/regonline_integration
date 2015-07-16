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

from flask import Flask, render_template
app = Flask(__name__)
app.config.from_pyfile( "./config/present.default.conf" )
#app.config.from_envvar( "DISCOUNT_CODES_CONFIG" )

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
                        'regonline_url' : 'https://www.regonline.com?eventID=1702108&rTypeID=228781',
                        'reserve_spot'  : True,
                        'cost'          : 850,
                        'regonline_str' : '-100%' },
    "student_full"  : { 'name'          : 'Student',
                        'regonline_url' : 'https://www.regonline.com?eventID=1702108&rTypeID=228782',
                        'reserve_spot'  : True,
                        'cost'          : 300,
                        'regonline_str' : '-100%' },
    "academic_full" : { 'name'          : 'Academic',
                        'regonline_url' : 'https://www.regonline.com?eventID=1702108&rTypeID=228783',
                        'reserve_spot'  : True,
                        'cost'          : 475,
                        'regonline_str' : '-100%' },
    "transition_full" : { 'name'          : 'Transition',
                          'regonline_url' : 'https://www.regonline.com?eventID=1702108&rTypeID=228784',
                          'reserve_spot'  : True,
                        'cost'          : 500,
                        'regonline_str' : '-100%' },
    "general_1"     : { 'name'          : 'General One Day',
                        'regonline_url' : 'https://www.regonline.com?eventID=1702108&rTypeID=228785',
                        'reserve_spot'  : True,
                        'cost'          : 500,
                        'regonline_str' : '-100%' },
    "speaker_full"  : { 'name'          : 'Speaker Full Conference',
                        'regonline_url' : 'https://www.regonline.com?eventID=1702108&rTypeID=228786',
                        'reserve_spot'  : True,
                        'cost'          : 500,
                        'regonline_str' : '-100%' },
    "speaker_1"     : { 'name'          : 'Speaker One Day',
                        'regonline_url' : 'https://www.regonline.com?eventID=1702108&rTypeID=228787',
                        'reserve_spot'  : True,
                        'cost'          : 200,
                        'regonline_str' : '-100%' },
    "booth"         : { 'name'          : 'Booth Staff Only',
                        'regonline_url' : 'https://www.regonline.com?eventID=1702108&rTypeID=228807',
                        'reserve_spot'  : True,
                        'cost'          : 0,
                        'summary_group' : 'Corporate',
                        'regonline_str' : '-100%' },
    "student_discount" : { 'name'       : 'Student Discounts',
                           'regonline_url' : 'https://www.regonline.com?eventID=1702108&rTypeID=228782',
                           'reserve_spot' : False,
                        'cost'          : 255,
                           'regonline_str' : '' },
    "student_20"    : { 'name'          : 'Student 20% Off',
                        'regonline_url' : 'https://www.regonline.com?eventID=1702108&rTypeID=228782',
                        'reserve_spot'  : False,
                        'cost'          : 255,
                        'regonline_str' : '-20%' },
    "student_15"    : { 'name'          : 'Student 15% Off',
                        'regonline_url' : 'https://www.regonline.com?eventID=1702108&rTypeID=228782',
                        'reserve_spot'  : False,
                        'cost'          : 255,
                        'regonline_str' : '-15%' },
    "student_10"    : { 'name'          : 'Student 10% Off',
                        'regonline_url' : 'https://www.regonline.com?eventID=1702108&rTypeID=228782',
                        'reserve_spot'  : False,
                        'cost'          : 255,
                        'regonline_str' : '-10%' },
    "scholar"       : { 'name'          : 'GHC Scholar',
                        'regonline_url' : 'https://www.regonline.com?eventID=1702108&rTypeID=240108',
                        'reserve_spot'  : True,
                        'cost'          : 255,
                        'regonline_str' : '-100%' },
}

def get_badge_type( eventID, registration_type, percent_discount ):
    # For the time being we ignore eventID.
    
    if int( percent_discount ) in [ 10, 15, 20 ]:
        if registration_type == 'Student':
            return "student_%d" % ( int( percent_discount ) )

    regonline_to_internal = {
        'General'                 : 'general_full',
        'Student'                 : 'student_full',
        'Academic'                : 'academic_full',
        'Transition'              : 'transition_full',
        'One Day'                 : 'general_1',
        'Speaker Full Conference' : 'speaker_full',
        'Speaker One Day'         : 'speaker_1',
        'Booth Staff Only'        : 'booth',
        'GHC Scholar'             : 'scholar'
    }
             
    if registration_type in regonline_to_internal:
        return regonline_to_internal[registration_type]
    else:
        raise Exception( "Unknown badge type for RegOnline RegistrationType: %s and Discount Percent: %d" % ( registration_type, int( percent_discount ) ) )



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
    'GHC Event Sponsorships' : 'Corporate',
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

