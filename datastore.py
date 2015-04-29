#!/usr/bin/env python

import json
import logging
import os
import os.path
import cPickle as pickle

# For now just store things in a flat file, in the future we'll make
# this a database.

# GET

def get_sponsors( eventID ):
    return get_data( "sponsors", eventID )

def get_registrants( eventID ):
    return get_data( "registrants", eventID )

def get_discount_codes( eventID ):
    return get_data( "discount_codes", eventID )

def get_data( table, eventID ):
    data_file = "datastore/%s-%s.dat" % ( table, eventID )
    if os.path.isfile( "%s" % ( data_file ) ):
        with open( "%s" % ( data_file ), "r" ) as f:
            logging.info( json.dumps( { 'eventID' : eventID, 
                                        'message' : 'Loading %s data from data file %s' % ( table, data_file ) } ) )
            return pickle.load( f )
    else:
        logging.info( json.dumps( { 'eventID' : eventID,
                                    'message' : 'No prior %s data, returning empty result set.' % ( table ) } ) )
        return []

# Update

def add_sponsors( eventID, new_sponsors ):
    '''Takes in a list of sponsors'''
    return add_data( "sponsors", eventID, new_sponsors )

def add_registrants( eventID, new_registrants ):
    '''Takes in a list of registrants'''
    return add_data( "registrants", eventID, new_registrants )

def add_discount_codes( eventID, new_codes ):
    '''Takes in a list of discount codes'''
    return add_data( "discount_codes", eventID, new_codes )

def add_data( table, eventID, new_data ):
    if len( new_data ):
        items = get_data( table, eventID )
        item_ids = { x['ID']:x for x in items }
    
        for new_item in new_data:
            if new_item['ID'] not in item_ids:
                logging.info( json.dumps( { 'eventID' : eventID,
                                            'message' : 'Adding %s data for new attendee ID: %s' % ( table, new_item['ID'] ) } ) )
                items.append( new_item )

        data_file = "datastore/%s-%s.dat" % ( table, eventID )
        data_file_new = data_file + ".new"
        data_file_old = data_file + ".old"

        # Create new.
        with open( "%s.new" % ( data_file ), "w" ) as f:
            pickle.dump( items, f )

        # Rename existing if any.
        if os.path.isfile( "%s" % ( data_file ) ):
            os.rename( "%s" % ( data_file ), "%s" % ( data_file_old ) )

        # Rename new to current.
        os.rename( "%s" % ( data_file_new ), "%s" % ( data_file ) )
        logging.info( json.dumps( { 'eventID' : eventID, 
                                    'message' : 'Renaming data file from %s to %s' % ( data_file_new, data_file ) } ) )
        return

# Overwrite
def set_sponsors( eventID, new_sponsors ):
    '''Takes in a list of sponsors'''
    return set_data( "sponsors", eventID, new_sponsors )

def set_registrants( eventID, new_registrants ):
    '''Takes in a list of registrants'''
    return set_data( "registrants", eventID, new_registrants )

def set_discount_codes( eventID, new_codes ):
    '''Takes in a list of discount codes'''
    return set_data( "discount_codes", eventID, new_codes )

def set_data( table, eventID, items ):
    if len( items ):
        data_file = "datastore/%s-%s.dat" % ( table, eventID )
        data_file_new = data_file + ".new"
        data_file_old = data_file + ".old"

        # Create new.
        with open( "%s" % ( data_file_new ), "w" ) as f:
            pickle.dump( items, f )

        # Rename existing if any.
        if os.path.isfile( "%s" % ( data_file ) ):
            os.rename( "%s" % ( data_file ), "%s" % ( data_file_old ) )

        # Rename new to current.
        os.rename( "%s" % ( data_file_new ), "%s" % ( data_file ) )
        logging.info( json.dumps( { 'eventID' : eventID, 
                                    'message' : 'Renaming data file from %s to %s' % ( data_file_new, data_file ) } ) )

        return
    else:
        error_message = "Refusing to empty %s all data for eventID %s." % ( table, eventID )
        logging.warning( json.dumps( { 'eventID' : eventID, 
                                       'message' : error_message } ) )
        raise Exception( error_message )
