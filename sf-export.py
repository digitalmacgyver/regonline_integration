#!/usr/bin/env python

from simple_salesforce import Salesforce

from datastore import get_sponsors, get_registrants, set_sponsors, set_registrants, get_discount_codes, set_discount_codes

from flask import Flask
app = Flask( __name__ )
app.config.from_pyfile( "./config/present.default.conf" )

sf = Salesforce(  instance='test.salesforce.com', username='matt@viblio.com', password='e6IoNyQ8jihZLWlf', security_token='C4N1vrEFXwGYOcz0lQ3c6waRs', sandbox=True, version='32.0' )

sponsor_event_id = app.config['SPONSOR_EVENT'] 

# Actual production sponsors.
sponsors = get_sponsors( sponsor_event_id )

# Bogus test sponsors in SF.com test database:
#sponsors = [
#    { 'ID' : '80757386' } ]

# Bogus value
sponsor_event_id = '1639610.0'

# Build up a list of entitlements.

# DEBUG
# Limit our processing for testing purposes.

print "%18s, %7s, %10s, %s, %30s, %s, %4s, %27s, %5s, %s" % ( 'discount_id', 'spsr_evt_id', 'sponsor_id', 'attendee_event_id', 'discount_code', 'badge_type', 'quantity', 'code_source', 'percent_off', 'created_date' )

for sponsor in sponsors:
    sreg = sf.query_all( "SELECT id, opportunity__c FROM Registrations__c WHERE Confirmation_Number__c = '%s' AND Event_Number__c = '%s'" % ( sponsor['ID'], sponsor_event_id ) )

    # DEBUG - Re-enable this once we are working off real data, not sandbox data.
    #if sreg['totalSize'] != 1:
    #    raise Exception( "Expected 1 sponsorship for sponsor %s at event %s, but got %d" % ( sponsor['ID'], sponsor_event_id, sreg['totalSize'] ) )
    # Remove this once doing real testing.
    if sreg['totalSize'] != 1:
        continue


    opportunity_id = sreg['records'][0]['Opportunity__c']

    oli = sf.query_all( "SELECT id, (Select id, discount_code__c, quantity, product2.name, CreatedDate from OpportunityLineItems) FROM Opportunity WHERE id = '%s'" % ( opportunity_id ) )

    if oli['totalSize'] != 1:
        raise Exception( "Expected 1 opportunity for opportunity ID %s, sponsor %s at event %s, but got %d" % ( opportunity_id, sponsor['ID'], sponsor_event_id, sreg['totalSize'] ) )

    #print "Working on opportunity %s" % ( opportunity_id )

    lis = oli['records'][0]['OpportunityLineItems']

    for li in lis['records']:
        if li.get( 'Discount_Code__c', None ) is not None:

            discount_id = li['Id']
            sponsor_id = sponsor['ID']
            attendee_event_id = 'Not in SF?'
            discount_code = li['Discount_Code__c']
            badge_type = 'Not in SF?'
            quantity = li['Quantity']
            code_source = li['Product2']['Name']
            percent_off = 'Not in SF?'
            created_date = li['CreatedDate']

            print "%18s, %7s, %10s, %s, %30s, %s, %4d, %27s, %5s, %s" % ( discount_id, sponsor_event_id, sponsor_id, attendee_event_id, discount_code, badge_type, quantity, code_source, percent_off, created_date )

            #print "Working on opportunity line item %s" % ( li['Id'] )


#x = 2

