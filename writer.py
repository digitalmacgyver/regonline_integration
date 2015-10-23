#!/usr/bin/env python

import csv

import datetime

from datastore import get_sponsors, get_registrants, set_discount_codes

def create_csv( filename, data ):
    with open( filename, 'w' ) as f:
        if len( data ): 
            writer = csv.writer( f )

            headers = sorted( data[0].keys() )
            writer.writerow( headers )
        
            for point in data:
                writer.writerow( [ point[key] for key in sorted( point.keys() ) ] )

def read_csv( filename ):
    with open( filename, 'r' ) as f:
        reader = csv.reader( f )

        first = True

        headers = []
        
        result = []

        now = datetime.datetime.now()

        for row in reader:
            if first:
                first = False
                headers = row
            else:
                tmp = {}
                for idx, column in enumerate( headers ):
                    if column == 'created_date':
                        tmp[column] = now
                    elif column in [ 'SponsorID', 'quantity', 'RegTypeID' ]:
                        tmp[column] = int( row[idx] )
                    else:
                        tmp[column] = row[idx]

                result.append( tmp )

        return result
            
if __name__ == '__main__':
    registrants_2014 = 1438441
    sponsors_2014 = 1438449

    registrants_wov_2015 = 1376075
    sponsors_wov_2015 = 1441015

    sponsors_2015 = 1639610
    registrants_2015 = 1702108
    
    #sponsor_code = sponsors_2015
    #registrant_code = registrants_2015

    sponsor_code = sponsors_wov_2015
    registrant_code = registrants_wov_2015

    #sponsors = get_sponsors( sponsor_code )
    #discount_codes = get_discount_codes( sponsor_code )
    #registrants = get_registrants( registrant_code )

    #create_csv( '/wintmp/abi/wov_sponsors_2015.csv', sponsors )
    #create_csv( '/wintmp/abi/wov_registrants_2015.csv', registrants )
    #create_csv( '/wintmp/abi/wov_discounts_2015.csv', discount_codes )

    #sponsors = read_csv( '/wintmp/abi/wov_sponsors_2015.csv' )
    #registrants = read_csv( '/wintmp/abi/wov_registrants_2015.csv' )
    discount_codes = read_csv( '/wintmp/abi/wov_discounts.csv' )

    set_discount_codes( sponsor_code, discount_codes )
