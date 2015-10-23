#!/usr/bin/env python

from optparse import OptionParser
import os
import re
import time
import unicodecsv
import uuid

import logging
import logging.handlers
logging.basicConfig( level=logging.INFO )
logging.getLogger( 'suds.client' ).setLevel( logging.WARNING )

log = logging.getLogger( __name__ )
log.setLevel( logging.DEBUG )

syslog = logging.handlers.SysLogHandler( address="/dev/log" )

format_string = 'fix_sessions.py: { "name" : "%(name)s", "module" : "%(module)s", "lineno" : "%(lineno)s", "funcName" : "%(funcName)s", "level" : "%(levelname)s", "message" : %(message)s }'

sys_formatter = logging.Formatter( format_string )

syslog.setFormatter( sys_formatter )
syslog.setLevel( logging.INFO )
consolelog = logging.StreamHandler()
consolelog.setLevel( logging.DEBUG )

log.addHandler( syslog )
log.addHandler( consolelog )

abi_namespace_uuid = '0b595c4e-3dc7-4972-8434-6a2e818ccb38'

def get_attendee_password( email ):
    '''Generate a deterministic, simple password based on an email.'''
    uid = get_attendee_id( email )
    return uid[:3] + uid[-3:]

def get_attendee_id( email ):
    '''Generate a deterministic, unique identifier based on email.'''
    return unicode( uuid.uuid5( uuid.UUID( abi_namespace_uuid ), email.encode( 'ascii', errors='ignore' ) ) )

attendee_file = '/wintmp/abi/asksheryl.csv'
attendee_file_out = '/wintmp/abi/asksheryl2.csv'

output = []

with open( attendee_file, 'rb' ) as f:
    reader = unicodecsv.reader( f, encoding='utf-8', errors='replace' )

    first = True

    for comment in reader:
        if len( comment ):
            fields = [ unicode( x ) for x in comment ]

            comment = fields[6]

            if first or re.search( r'#asksheryl', comment, re.IGNORECASE ):
                output.append( fields )
                first = False



with open( attendee_file_out, 'wb' ) as f:
    writer = unicodecsv.writer( f, encoding="utf-8" )

    for thing in output:
        writer.writerow( thing )


        
