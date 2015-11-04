#!/usr/local/bin/python
"""
This is a py.test script

Example usage on Unix:
bitly-api-python $ RACKSPACE_USER_KEY=<userkey> RACKSPACE_SECRET=<secret> RACKSPACE_DOMAIN=<domain> nosetests
or 'export' the two environment variables prior to running nosetests
"""
import os
import sys
sys.path.append('../')
import rackspace_api

RACKSPACE_USER_KEY = "RACKSPACE_USER_KEY"
RACKSPACE_SECRET = "RACKSPACE_SECRET"
RACKSPACE_DOMAIN = "RACKSPACE_DOMAIN"


def get_connection():
    """Create a Connection base on username and access token credentials"""
    if RACKSPACE_USER_KEY not in os.environ:
        raise ValueError("Environment variable '{}' required".format(RACKSPACE_USER_KEY))
    if RACKSPACE_SECRET not in os.environ:
        raise ValueError("Environment variable '{}' required".format(RACKSPACE_SECRET))         
    if RACKSPACE_DOMAIN not in os.environ:
        raise ValueError("Environment variable '{}' required".format(RACKSPACE_DOMAIN))
    user_key = os.getenv(RACKSPACE_USER_KEY)
    secret = os.getenv(RACKSPACE_SECRET)
    domain = os.getenv(RACKSPACE_DOMAIN)
    rackspace = rackspace_api.Connection(user_key=user_key,secret_key=secret,domain=domain)
    return rackspace


def testApi():
    rackspace = get_connection()
    data = rackspace.list_domains()
    assert data['domains'] is not None