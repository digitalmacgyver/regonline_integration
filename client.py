#!/usr/bin/env python

import json
import requests

if __name__ == '__main__':
    base_url = 'http://127.0.0.1:5000'
    api_key = 'secret_key'

    sponsors_url = "%s%s" % ( base_url, '/data/sponsors/' )
    sponsors_2014 = 1438449
    sponsor_data = {
        'api_key' : api_key,
        'eventID' : sponsors_2014
    }

    #result = requests.post( sponsors_url, json.dumps( sponsor_data ) )
    #print result.json()

    registrants_url = "%s%s" % ( base_url, '/data/registrants/' )
    registrants_2014 = 1438441
    registrant_data = {
        'api_key' : api_key,
        'eventID' : registrants_2014
    }

    #result = requests.post( registrants_url, json.dumps( registrant_data ) )
    #print result.json()

    discounts_url = "%s%s" % ( base_url, '/data/discounts/' )
    discounts_2014 = 1438449
    discount_data = {
        'api_key' : api_key,
        'eventID' : discounts_2014,
    }

    #result = requests.post( discounts_url, json.dumps( discount_data ) )
    #print result.json()

    discount_code_url = "%s%s" % ( base_url, '/data/discount_code/' )
    discount_code_2014 = 1438449
    discount_code_data = {
        'api_key' : api_key,
        'discount_eventID' : discount_code_2014,
        'registrant_eventID' : registrants_2014,
        'discount_code' : 'bankofamE2014abi'
    }

    result = requests.post( discount_code_url, json.dumps( discount_code_data ) )
    print result.json()
