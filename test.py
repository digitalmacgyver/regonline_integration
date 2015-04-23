#!/usr/bin/env python

import json
#from pysimplesoap.client import SoapClient, SoapHeader
#import requests

from suds.client import Client

import logging
logging.basicConfig( level=logging.INFO )
logging.getLogger( 'suds.clinet' ).setLevel( logging.DEBUG )

#login = 'https://www.regonline.com/api/default.asmx/Login'
#username = 'mhayward'
#password = '#0^Y5!qxwfvobdtI'
key = '9mIRFe399oIBM0fnX5jxLtupSZlaizGgtHUEuDpUi34QWs66G6LxFDZ6wsdpgzCw'

#data = {
#    "username" : username,
#    "password" : password,
#    "APIToken" : key,
#    "filter" : "",
#    "orderBy" : "",
#}

#headers = {
#    "APIToken" : key,
    #"username" : username,
    #"password" : password
#}

wsdl = "https://www.regonline.com/api/default.asmx?WSDL"
#client = SoapClient( wsdl=wsdl, ns="web", trace=True )
#client['TokenHeader'] = headers
#response = client.GetEvents( { "filter" : None, "orderBy" : None } )

# This is working:

#1438441

client = Client( wsdl )
token = client.factory.create( "TokenHeader" )
token.APIToken = key
client.set_options( soapheaders=token )

# Get a list of all events
#result = client.service.GetEvents( filter=None, orderBy=None )
#print result

# This gets a list of everyone who filled in custom field 1232968,
# which I believe is a access code, but it doesn't get the code they
# filled in.
#result = client.service.GetRegistrationsForCustomField( eventID=1438441, cfid=1232968, filter=None, orderBy=None )


# General approach:
#
# Build a local database of registration data.
# 
# 1. Run get RegistrationsForEvent.
# 2. Determine new registrations.
# 3. For new registrations, get their details.
# 4. Save details in local database so we don't look them up next time.

import time

# Get a list of all registrations for GHC 2014.
start = time.time()
result = client.service.GetRegistrationsForEvent( eventID=1438441, filter=None, orderBy=None )
end = time.time()
print "It took %f seconds to get all registrant data." % ( end - start )
#print result

attendees = result[1][0]

#person = attendees[0]

data = []

for person in attendees:
    #custom_data_agenda = client.service.GetCustomFieldResponsesForRegistration( eventID=1438441, registrationID=person['ID'], pageSectionID=0 )
    #custom_data1 = client.service.GetCustomFieldResponsesForRegistration( eventID=1438441, registrationID=person['ID'], pageSectionID=1 )
    #custom_data2 = client.service.GetCustomFieldResponsesForRegistration( eventID=1438441, registrationID=person['ID'], pageSectionID=2 )
    #custom_data3 = client.service.GetCustomFieldResponsesForRegistration( eventID=1438441, registrationID=person['ID'], pageSectionID=3 )
    #custom_data4 = client.service.GetCustomFieldResponsesForRegistration( eventID=1438441, registrationID=person['ID'], pageSectionID=4 )
    # pageSectionID=5 is the Event Fee page.
    try:
        time.sleep( 2 )
        start = time.time()
        custom_data5 = client.service.GetCustomFieldResponsesForRegistration( eventID=1438441, registrationID=person['ID'], pageSectionID=5 )
        discount_code = None
        if 'Password' in custom_data5.Data.APICustomFieldResponse[0]:
            discount_code = custom_data5.Data.APICustomFieldResponse[0].Password
            print "For: %s %s %s - %s - CFID: %s %s: %s (discount code '%s' : %s, %s)" % ( 
                person.FirstName,
                person.LastName,
                person.Email,
                person.Company,
                custom_data5.Data.APICustomFieldResponse[0].CFID,
                custom_data5.Data.APICustomFieldResponse[0].CustomFieldNameOnReport ,
                custom_data5.Data.APICustomFieldResponse[0].Amount ,
                discount_code,
                custom_data5.Data.APICustomFieldResponse[0].DiscountCodeCredit ,
                custom_data5.Data.APICustomFieldResponse[0].GroupDiscountCredit )
            data.append( { 
                "name" : "%s %s" % ( person.FirstName, person.LastName ),
                "email" : person.Email,
                "company" : person.Company,
                "registration_type" : custom_data5.Data.APICustomFieldResponse[0].CustomFieldNameOnReport,
                "registration_amount" : custom_data5.Data.APICustomFieldResponse[0].Amount,
                "discount_code" : discount_code,
                "discount_amount" : custom_data5.Data.APICustomFieldResponse[0].DiscountCodeCredit } )
        end = time.time()
        print " It took %f seconds to process 1 registrant." % ( end - start )
    except Exception as e:
        print "ERROR: %s, %s, %s - continuing." % ( person, custom_data5, e 


'''
For Sponsors:
ID
RegTypeID
RegistrationType
StatusID
StatusDescription
FirstName
LastName
Title
Email
Company
Phone
Extension
CCEmail
CancelDate
IsSubstitute
AddBy
AddDate
For Registrants:
All of the above, plus:
registration_type
registration_amount
discount_code
discount_amount


'''

import pickle
with open( "registrations.dat", "w" ) as f:
    pickle.dump( data, f )

#response = requests.post( url, data, headers=headers )
#response = requests.post( url, headers=headers )
#response = requests.post( login, data )

#get_events = "https://www.regonine.com/api/default.asmx/GetEvents"

#response = requests.post( get_events, data, headers=headers )

#print response.text
