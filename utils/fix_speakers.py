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

speaker_file = '/wintmp/abi/speakers/speakers.csv'

speakers = []

unique_speakers = {}

with open( speaker_file, 'rb' ) as f:
    reader = unicodecsv.reader( f, encoding='utf-8' )
    for speaker in reader:
        if len( speaker ):
            speaker = [ unicode( x ) for x in speaker ]

            if speaker[-1] in unique_speakers:
                print "DUPLICATE SPEAKER:", speaker
            else:
                unique_speakers[speaker[-1]] = True

            speaker[2] = speaker[2][:99]

            speaker[3] = speaker[3][:99]
            

            desc = speaker[4]
            before_hashtag = desc.replace( '\n', '<br />' )
            #p = re.compile( r'\s+#(\D\w+?)(\W)' )
            #desc = p.sub( r' dd://hashtag/\1 \2', before_hashtag ) 
            desc = before_hashtag
            speaker[4] = desc

            speakers.append( speaker )

with open( speaker_file, 'wb' ) as f:
    writer = unicodecsv.writer( f, encoding="utf-8" )

    for speaker in speakers:
        writer.writerow( speaker )


        
