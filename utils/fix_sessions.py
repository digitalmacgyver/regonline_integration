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

attendee_file = '/wintmp/abi/sessions/sessions.csv'

attendees = []

with open( attendee_file, 'rb' ) as f:
    reader = unicodecsv.reader( f, encoding='utf-8' )
    for attendee in reader:
        if len( attendee ):
            attendee = [ unicode( x ) for x in attendee ]

            attendee[0] = attendee[0][:249]
            
            # DoubleDutch doesn't allow session descriptions to start
            # with a # in their uploader.
            if attendee[0][0] == '#':
                attendee[0] = ' ' + attendee[0][:248]

            before_hashtag = attendee[1].replace( '\n', '<br />' )
            #p = re.compile( r'\s+#(\D\w+?)(\W)' )
            #attendee[1] = p.sub( r' dd://hashtag/\1 \2', before_hashtag )
            attendee[1] = before_hashtag

            m = attendee[1]

            if len( attendee[0] ) == 0:
                print "ERROR: ", attendee

            attendees.append( attendee )

with open( attendee_file, 'wb' ) as f:
    writer = unicodecsv.writer( f, encoding="utf-8" )

    for attendee in attendees:
        writer.writerow( attendee )


        
