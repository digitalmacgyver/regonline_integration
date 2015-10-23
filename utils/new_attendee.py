#!/usr/bin/env python

import time
import unicodecsv

old_file = '/wintmp/abi/speakers/merged-attendee.csv.bak'
edit_file = '/wintmp/abi/speakers/attendee-export.csv'
new_file = '/wintmp/abi/speakers/merged-attendee.csv.backup.09232015'

# DEBUG
#new_file = '/wintmp/abi/speakers/test.csv'

print "DO NOT USE THIS WITHOUT CHECKING WHETHER ETHNIC AND GENDER GROUPINGS HAVE BEEN REMOVED."

def get_attendees( filename ):
    with open ( filename, 'rb' ) as f:
        reader = unicodecsv.reader( f, encoding='utf-8' )

        result = []

        for attendee in reader:
            result.append( attendee )

        return result

old = get_attendees( old_file )
edit = get_attendees( edit_file )
new = get_attendees( new_file )

'''
First Name (required),
Last Name (required),
Email Address (required),
Password (required),
Title,
Company,
Biography,
Phone Number,
Image URL,
Address,
Address (ext),
City,
State/Province/Region,
Postal Code,
Country,
Attendee ID,
Attendee Groups,Personal Agenda (Session IDs),Exhibitor ID,Exhibitor Role,Speaker ID,Variable Data 1,Variabl
e Data 2,Variable Data 3
'''

old_by_id = { x[15]:x for x in old[1:] }
edit_by_id = { x[15]:x for x in edit[1:] }
new_by_id = { x[15]:x for x in new[1:] }

result = [new[0]]

for person in new[1:]:

    if person[15] not in old_by_id:
        if len( person[16] ):
            groups = person[16].split( ',' )
            new_groups = []
            for group in groups:
                if group.startswith( 'Ethnicity' ):
                    continue
                elif group.startswith( 'Gender' ):
                    continue
                elif group in [ 'Agenda: Fall Partner Meeting',
                                'Agenda: Private Reception',
                                "Agenda: Senior Women's Program and Luncheon",
                                'Agenda: Technical Executive Forum',
                                'Speaker',
                                'Professioanl Affiliation: Unaffiliated',
                                'Professional Affiliation: Other Affiliation',
                                'Registration: Booth Staff Only',
                                'Registration: Speaker Full Conference',
                                'Registration: Speaker One Day', ]:
                    continue
                else:
                    new_groups.append( group )
            
            person[16] = ','.join( new_groups )
        print "NEW PERSON:", person, "\n\n"
        result.append( person )
    else:
        old_person = old_by_id[person[15]]
        edit_person = {}
        
        if person[15] not in edit_by_id:
            if len( person[16] ):
                groups = person[16].split( ',' )
                new_groups = []
                for group in groups:
                    if group.startswith( 'Ethnicity' ):
                        continue
                    elif group.startswith( 'Gender' ):
                        continue
                    elif group in [ 'Agenda: Fall Partner Meeting',
                                    'Agenda: Private Reception',
                                    "Agenda: Senior Women's Program and Luncheon",
                                    'Agenda: Technical Executive Forum',
                                    'Speaker',
                                    'Professioanl Affiliation: Unaffiliated',
                                    'Professional Affiliation: Other Affiliation', 
                                    'Registration: Booth Staff Only',
                                    'Registration: Speaker Full Conference',
                                    'Registration: Speaker One Day', ]:
                        continue
                    else:
                        new_groups.append( group )

                person[16] = ','.join( new_groups )

            result.append( person )
            print "PERSON NOT IN EDIT:", person, "\n\n"
            continue
        else:
            edit_person = edit_by_id[person[15]]

        changed = False
        message = ""

        # If edit is different from new, whine.
        
        edit_fields = [ ( 'First name', 0 ),
                        ( 'Last name', 1 ),
                        ( 'Email', 2 ),
                        ( 'Title', 4 ),
                        ( 'Company', 5 ),
                        ( 'Bio', 6 ) ]
        
        for ef in edit_fields:
            name = ef[0]
            idx = ef[1]

            if person[idx] != old_person[idx]:
                # The registration data changed, go with the new registration data.
                message += "%s changed - old | new | edit: %s | %s | %s " % ( name, old_person[idx], person[idx], edit_person[idx] )
                changed = 'USE_NEW'
            elif edit_person[idx] != old_person[idx]:
                # The profile in the app has changed, go with the edited profile.
                message += "%s changed - old | new | edit: %s | %s | %s " % ( name, old_person[idx], person[idx], edit_person[idx] )
                changed = 'USE_EDIT'



        '''
        if person[0] != old[0]:
            message += "First name changed from/to: %s | %s" % ( old[0], person[0] )
            changed = True
        if person[1] != old[1]:
            message += "Last name changed from/to: %s | %s" % ( old[1], person[1] )
            changed = True
        if person[2] != old[2]:
            message += "Email changed from/to: %s | %s" %( old[2], person[2] )
            changed = True
        if person[4] != old[4]:
            message += "Title changed from/to: %s | %s" % ( old[4], person[4] )
            changed = True
        if person[5] != old[5]:
            message += "Company changed from/to: %s | %s" % ( old[5], person[5] )
            changed = True
        if person[6] != old[6]:
            message += "Bio changed from/to: %s | %s" % ( old[6], person[6] )
            changed = True
        '''
 
        if changed:
            used = None
            if changed == 'USE_NEW':
                used = person
                #result.append( person )
            elif changed == 'USE_EDIT':
                used = edit_person
                #result.append( edit_person )
            else:
                raise Exception( "Unexpected change type: %s" % ( changed ) )

            print "CHANGED PERSON - USING", changed, used, "\n", message, "\n\n"
        else:
            pass
            #result.append( person )

output_file = '/wintmp/abi/speakers/merged-new-only.csv'

with open( output_file, 'wb' ) as f:
    writer = unicodecsv.writer( f, encoding='utf-8' )
    for thing in result:
        writer.writerow( thing )

