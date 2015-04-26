#!/usr/bin/env python

import os
import os.path
import pickle

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
    if os.path.isfile( "datastore/%s-%s.dat" % ( table, eventID ) ):
        with open( "datastore/%s-%s.dat" % ( table, eventID ), "r" ) as f:
            return pickle.load( f )
    else:
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
                items.append( new_item )

        # Create new.
        with open( "datastore/%s-%s.dat.new" % ( table, eventID ), "w" ) as f:
            pickle.dump( items, f )

        # Rename existinig if any.
        if os.path.isfile( "datastore/%s-%s.dat" % ( table, eventID ) ):
            os.rename( "datastore/%s-%s.dat" % ( table, eventID ), "datastore/%s-%s.dat.old" % ( table, eventID ) )

        # Rename new to current.
        os.rename( "datastore/%s-%s.dat.new" % ( table, eventID ), "datastore/%s-%s.dat" % ( table, eventID ) )

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
        # Create new.
        with open( "datastore/%s-%s.dat.new" % ( table, eventID ), "w" ) as f:
            pickle.dump( items, f )

        # Rename existinig if any.
        if os.path.isfile( "datastore/%s-%s.dat" % ( table, eventID ) ):
            os.rename( "datastore/%s-%s.dat" % ( table, eventID ), "datastore/%s-%s.dat.old" % ( table, eventID ) )

        # Rename new to current.
        os.rename( "datastore/%s-%s.dat.new" % ( table, eventID ), "datastore/%s-%s.dat" % ( table, eventID ) )
    else:
        raise Exception( "set_data called with no items to set." )
