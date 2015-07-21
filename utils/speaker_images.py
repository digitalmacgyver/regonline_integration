#!/usr/bin/env python

import commands
import csv
import os

'''This utility script processes the speakers CSV file from linklings,
and a directory holding images names from the Linklings proceedings
download.  

It resizes images into the necessary format for DoubleDutch, namely a
560x600 JPG, and does so by shrinking it with its existing aspect
ratio, and putting it on a white background.

It copies the resulting image files to an output directory.
'''

def process_images( speakers_csv, indir, outdir, prefix='http://52.8.24.90/z3rbr4ngy/' ):
    images = []
    with open( speakers_csv, "rb" ) as f:
        reader = csv.reader( f )
        for row in reader:
            if len( row ) < 6:
                continue
            image = row[5]
            if len( image ) and image != 'Image URL':
                images.append( image )


    for image in images:
        try:
            input_file  = "%s/%s" % ( indir , image[len( prefix ):] )
            output_file = "%s/%s" % ( outdir, image[len( prefix ):] )
            if os.path.isfile( input_file ):
                ( status, output ) = commands.getstatusoutput( "convert %s -resize 560x600 -gravity center -extent 560x600 -background white %s" % ( input_file, output_file ) )
            else:
                print "WARNING: No input file found for attendee image %s in CSV file!" % ( input_file )
        except Exception as e:
            print "ERROR: %s" % ( e )
    
speakers_csv = '/wintmp/abi/speakers/speakers.csv'
indir  = '/wintmp/abi/speaker_images/input'
outdir = '/wintmp/abi/speaker_images/output'

process_images( speakers_csv, indir, outdir )
