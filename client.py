#!/usr/bin/env python

import json
import requests

if __name__ == '__main__':
    base_url = 'http://127.0.0.1:5000'
    api_key = 'secret_key'

    sponsors_url = "%s%s" % ( base_url, '/data/sponsors/' )

    sponsors_2014 = 1438449
    
    data = {
        'api_key' : api_key,
        'eventID' : sponsors_2014
    }

    result = requests.post( sponsors_url, json.dumps( data ) )

    import pdb
    pdb.set_trace()

    result
