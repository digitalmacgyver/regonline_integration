#!/usr/bin/env python

import time
import unicodecsv

current_attendee = '/wintmp/abi/current/attendee-export.csv'
new_attendee = '/wintmp/abi/speakers/merged-attendee.csv'
out_attendee = '/wintmp/abi/speakers/merged-attendee-added.csv'

current_session = '/wintmp/abi/current/Agenda-export.csv'
new_session = '/wintmp/abi/sessions/sessions.csv'
out_session = '/wintmp/abi/sessions/sessions-added.csv'

current_speaker = '/wintmp/abi/current/Speakers-export.csv'
new_speaker = '/wintmp/abi/speakers/speakers.csv'
out_speaker = '/wintmp/abi/speakers/speakers-added.csv'

current_ac = '/wintmp/abi/current/ac.csv'
new_ac = '/wintmp/abi/sponsors/academic_sponsors.csv'
out_ac = '/wintmp/abi/sponsors/academic_sponsors-added.csv'
current_corp = '/wintmp/abi/current/corp.csv'
new_corp = '/wintmp/abi/sponsors/corporate_sponsors.csv'
out_corp = '/wintmp/abi/sponsors/corporate_sponsors-added.csv'
current_lab = '/wintmp/abi/current/lab.csv'
new_lab = '/wintmp/abi/sponsors/lab_and_nonprofit_sponsors.csv'
out_lab = '/wintmp/abi/sponsors/lab_and_nonprofit_sponsors-added.csv'

attendee_id_idx = 15
session_id_idx = 9
speaker_id_idx = 12
sponsors_id_idx = 15


def get_list( current_file, min_cols ):
    with open( current_file, 'rb' ) as f:
        reader = unicodecsv.reader( f, encoding = 'utf-8' )

        result = []
        for thing in reader:
            if len( thing ) < min_cols+1:
                print "Warning, skipping line without enough data:", thing
                continue
            result.append( thing )

        return result

def list_new( current_file, new_file, out_file, idx, optional_ids=None ):
    if optional_ids is None:
        optional_ids = []
        
    current = get_list( current_file, idx )
    new = get_list( new_file, idx )

    current_ids = { x[idx]:x for x in current }
    current_keys = {}

    if optional_ids:
        # Alternative way to pick up dupes, based on concatenating the
        # values of some columns.
        for thing in current:
            key = ''
            for key_idx in optional_ids:
                key += '%s,' % ( thing[key_idx] )
            current_keys[key] = thing

    # Set up headers, and add bonus column.
    #added = [ new[0] + [ 'Matches Existing' ] ]
    added = [ new[0] ]

    for thing in new:
        if thing[idx] not in current_ids:
            # We have a new thing.
            if optional_ids:
                key = ''
                for key_idx in optional_ids:
                    key += '%s,' % ( thing[key_idx] )
                if key in current_keys:
                    pass
                    #thing.append( current_keys[key][idx] )
                else:
                    pass
                    #thing.append( '' )

            added.append( thing )

    with open( out_file, 'w' ) as f:
        writer = unicodecsv.writer( f, encoding='utf-8' )

        for thing in added:
            writer.writerow( thing )


#list_new( current_ac, new_ac, out_ac, sponsors_id_idx )
#list_new( current_corp, new_corp, out_corp, sponsors_id_idx )
#list_new( current_lab, new_lab, out_lab, sponsors_id_idx )

#list_new( current_session , new_session , out_session , session_id_idx, [ 0, 1 ] )
#list_new( current_attendee, new_attendee, out_attendee, attendee_id_idx, [ 0, 1] )
list_new( current_speaker , new_speaker , out_speaker , speaker_id_idx , [ 0, 1 ] )

print "Check new attendees for emails ending in anitaborg.org for bogus linklings emails starting with stutib, susand, rosarior, monas, etc."
print "\n\nDO NOT ADD BACK IN THE SENIOR WOMENS PROGRAM"
