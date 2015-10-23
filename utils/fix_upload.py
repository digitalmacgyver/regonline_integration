#!/usr/bin/env python

from optparse import OptionParser
import glob
import os
import re
import shutil
import sys
import time
import unicodecsv
import uuid

index_file = '/wintmp/abi/p/index3.csv'
root = '/wintmp/abi/p/pdf3/'
outdir = '/wintmp/abi/p/output3/'

'''
TODO:

1. Get provisional data structure up.
2. Cross check in the other direction - folders for which there are no lines.

'''

with open( index_file, 'rb' ) as f:
    reader = unicodecsv.reader( f, encoding='utf-8', errors='replace' )

    total_files = 0

    seen_dirs = {}

    for pres in reader:
        if len( pres ):
            fields = [ unicode( x ) for x in pres ]

            if len( fields ) != 7:
                print "Skipping line: ", fields
                continue

            approval = fields[0]

            if approval == 'Approval':
                continue
            elif approval != 'Yes':
                print "Skipping talk without approval: ", fields
                continue

            speaker = fields[1]
            pres_dir = fields[6].replace( '\\', '/' )

            day = pres_dir.split( '/' )[1]

            speaker_prefix = speaker.replace( ' ', '_' )
            speaker_prefix = speaker_prefix.replace( '-', '_' )
            
            initial = re.compile( r'(_\w\._)' )

            if initial.search( speaker_prefix ):
                speaker_prefix = initial.sub( '_', speaker_prefix )

            if speaker_prefix == 'A.J._Brush':
                speaker_prefix = 'A_J__Brush'
            if speaker_prefix == 'Beste_Filiz_Yuksel':
                speaker_prefix = 'Beste_Yuksel'
            if speaker_prefix in [ 'E._Chang', 'E._Diane_Chang' ]:
                speaker_prefix = 'E__Chang'
            if speaker_prefix == 'Katherine_Lewis':
                speaker_prefix = 'Katie_Lewis'
            if speaker_prefix == 'Mary_Jane_Irwin':
                speaker_prefix = 'Mary_Irwin'
            if speaker_prefix == 'Mary_Lou_Soffa':
                speaker_prefix = 'Mary_Soffa'
            if speaker_prefix == 'Ana_Consuelo_Huaman_Quispe':
                speaker_prefix = 'Ana_Quispe'
            if speaker_prefix == 'Calkin_Suero_Montero':
                speaker_prefix = 'Calkin_Montero'
            if speaker_prefix == 'Carol_Maddren_Schofield':
                speaker_prefix = 'Carol_Schofield'
            if speaker_prefix == 'Elizabeth_H._Phillips':
                speaker_prefix = 'Elizabeth_Phillips'
            if speaker_prefix == 'Kristin_Yvonne_Rozier':
                speaker_prefix = 'Kristin_Rozier'
            if speaker_prefix == 'Lauren_Hayward_Schaefer':
                speaker_prefix = 'Lauren_Schaefer'
            if speaker_prefix == 'Malek_Ben_Salem':
                speaker_prefix = 'Malek_Salem'
            if speaker_prefix == 'Melinda_Briana_Epler':
                speaker_prefix = 'Melinda_Epler'
            if speaker_prefix == 'Meriam_Gay_Bautista':
                speaker_prefix = 'Meriam_Bautista'
            if speaker_prefix == 'Reena_Singhal_Lee':
                speaker_prefix = 'Reena_Lee'


            glob_expr = root + pres_dir + '*'

            pres_files = glob.glob( glob_expr )
            
            print "working on: ", glob_expr

            speaker_dir = None

            if len( pres_files ):
                #print "pres_files", pres_files
                for full in pres_files:
                    short = os.path.split( full )[-1]
                    if short.lower().find( speaker_prefix.lower() ) == 0:
                        speaker_dir = short
                    elif short.lower().find( speaker_prefix.lower() ) > 0:
                        print "WTF:", short, speaker_prefix
                        sys.exit( 0 )

            if not speaker_dir:
                print "COULDN'T FIND", speaker_prefix, " IN ", pres_files
            else:
                #shutil.copytree(src, dst, symlinks=False, ignore=None)
                total_files += len( glob.glob( root + pres_dir + speaker_dir ) )

                output_dir = outdir + speaker + '/' + day + '/'

                if output_dir in seen_dirs:
                    print "FIGURE OUT WHAT TO DO ABOUT ", root + pres_dir + speaker_dir, " WHICH HAS ALREADY BEEN SEEN"
                else:
                    shutil.copytree( root + pres_dir + speaker_dir, output_dir )
                seen_dirs[output_dir] = True


print "THERE WERE:", total_files, " TOTAL FILES"
