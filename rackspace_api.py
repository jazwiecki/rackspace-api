import base64
import functools
import hashlib
import json
import sys
import time
import types
import warnings

try:
    from urllib.request import build_opener, HTTPRedirectHandler
    from urllib.parse import urlencode
    from urllib.error import URLError, HTTPError
    string_types = str,
    integer_types = int,
    numeric_types = (int, float)
    text_type = str
    binary_type = bytes
except ImportError as e:
    from urllib2 import build_opener, HTTPRedirectHandler, URLError, HTTPError, Request
    from urllib import urlencode
    string_types = basestring,
    integer_types = (int, long)
    numeric_types = (int, long, float)
    text_type = unicode
    binary_type = str

class DontRedirect(HTTPRedirectHandler):
    def redirect_response(self, req, fp, code, msg, headers, newurl):
        if code in (301, 302, 303, 307):
            raise HTTPError(req.get_full_url(), code, msg, headers, fp)

class Error(Exception):
    pass

class RackspaceError(Error):
    def __init__(self, code, message):
        Error.__init__(self, message)
        self.code = code

def RateLimited(maxPerMinute):
    minInterval = 60.0 / float(maxPerMinute)
    def decorate(func):
        lastTimeCalled = [0.0]
        def rateLimitedFunction(*args,**kargs):
            elapsed = time.clock() - lastTimeCalled[0]
            leftToWait = minInterval - elapsed
            if leftToWait>0:
                time.sleep(leftToWait)
            ret = func(*args,**kargs)
            lastTimeCalled[0] = time.clock()
            return ret
        return rateLimitedFunction
    return decorate

def _utf8(s):
    if isinstance(s, text_type):
        s = s.encode('utf-8')
    assert isinstance(s, binary_type)
    return s


def _utf8_params(params):
    """encode a dictionary of URL parameters (including iterables) as utf-8"""
    assert isinstance(params, dict)
    encoded_params = []
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, numeric_types):
            v = str(v)
        if isinstance(v, (list, tuple)):
            v = [_utf8(x) for x in v]
        else:
            v = _utf8(v)
        encoded_params.append((k, v))
    return dict(encoded_params)

class Connection(object):
    """
    This is a python library for accessing the Rackspace API

    Usage:
        import rackspace_api
        c = rackspace_api.Connection('user_key','secret_key', 'domain.tld')
        c.method('param')

    Params:
        ***
        All distribution list/mailbox functions take the following
        keyword arguments:
        ***

        Search (string): A value to filter the list by Common Name and
        Display Name.

        Marker (string): The common name of the last item from the
        previous listing call. Use this to get the next page of data.

        Limit (integer): The maximum number of items to return

        Sort (string): "CN" or "Displayname"

        Order (string): "asc" or "desc"

        PreviousPage (bool): eturns the previous page based on Marker.
        If Marker is not specified, then the last page is returned.

        ExportTo (string): For listings that support exporting,
        this value can be a valid email address. An email will
        be sent containing a link to a CSV file of the requested data.

        ***
        All Exchange contacts (i.e. not mailboxes) take the following
        arguments
        ***

        size (integer): The maximum number of items to return (max 250)

        offset (integer): the offset for the result set

    """

    def __init__(self, user_key=None, secret_key=None, domain=None):
        self.host = 'api.emailsrvr.com'
        self.user_key = user_key
        self.secret_key = secret_key
        self.domain = domain
        (major, minor, micro, releaselevel, serial) = sys.version_info
        parts = (major, minor, micro, '?')
        self.user_agent = "Python/%d.%d.%d rackspace_api/%s" % parts

    def list_domains(self, **kwargs):
        """ returns info about our domain
        """

        path = "customers/me/domains"
        data = self._call(self.host, path, kwargs)
        return data

    def list_lists(self, **kwargs):
        """ returns a list of all the Exchange distribution lists in the domain

        """
        path = "domains/%s/ex/distributionlists" % self.domain
        data = self._call(self.host, path, kwargs)
        return data

    def list_members(self, common_name, **kwargs):
        """ returns a list of members for a distribution list with a
        given common_name

            @parameter common_name: the common name of the list in question
        """

        path = "customers/me/domains/%s/ex/distributionlists/%s/members" % (self.domain, common_name)
        data = self._call(self.host, path, kwargs)
        return data

    def list_senders(self, common_name, **kwargs):
        """ returns a list of approved senders for a distribution list
        with a given common_name

            @parameter common_name: the common name of the list in question
        """

        path = "customers/me/domains/%s/ex/distributionlists/%s/senders" % (self.domain, common_name)
        data = self._call(self.host, path, kwargs)
        return data

    def list_addresses(self, common_name, **kwargs):

        path = "customers/me/domains/%s/ex/distributionlists/%s/emailaddresses" % (self.domain, common_name)
        data = self._call(self.host, path, kwargs)
        return data

    def list_read(self, common_name, **kwargs):

        path = "customers/me/domains/%s/ex/distributionlists/%s" % (self.domain, common_name)
        data = self._call(self.host, path, kwargs)
        return data

    def list_export_all(self, email_address, **kwargs):
        """ send csv of all Exchange distribution lists to an email
        address

        @parameter email_address: string representing an email address
        to which the download link for the export should be sent

        """

        path = "customers/me/domains/%s/ex/distributionlists/" % self.domain

        params = kwargs
        params["exportTo"] = email_address
        data = self._call(self.host, path, params)
        return data

    def contact_list(self, **kwargs):

        path = "customers/me/domains/%s/ex/contacts" % self.domain
        data = self._call(self.host, path, kwargs)
        return data

    def contact_show(self, contact_name, **kwargs):

        path = "customers/me/domains/%s/ex/contacts/%s" % (self.domain, contact_name)
        data = self._call(self.host, path, kwargs)
        return data

    @RateLimited(30) #30 calls/minute max for "POST" and "PUT" operations
    def contact_add(self, user_name, display_name, external_email, **kwargs):

        kwargs['displayName'] = display_name
        kwargs['externalEmail'] = external_email
        kwargs['method'] = 'POST'
        path = "customers/me/domains/%s/ex/contacts/%s" % (self.domain, user_name)
        data = self._call(self.host, path, kwargs)
        return data

    def mailbox_list(self, account_type="ex", enabled=None, **kwargs):
        """ returns a list of Exchange mailboxes.
            takes an optional boolean status filter param called enabled,

            enabled = True -> return only enabled mailboxes
            enabled = False -> return only disabled mailboxes
            not used -> return mailboxes with both states
        """
        if enabled:
            kwargs["enabled"] = True
        elif enabled == False:  #explicitly test for false in case no param passed
            kwargs["enabled"] = False
        path = "customers/me/domains/%s/%s/mailboxes" % (self.domain, account_type)
        data = self._call(self.host, path, kwargs)
        return data

    def mailbox_show(self, mailbox_name, account_type="ex", **kwargs):
        """ returns full details about mailbox_name.
            account_type defaults to 'ex' ('Exchange') but passing in 'rs' ('Rackspace')
            will query Rackspace's IMAP accounts.
        """

        path = "customers/me/domains/%s/%s/mailboxes/%s" % (self.domain, account_type, mailbox_name)
        data = self._call(self.host, path, kwargs)
        return data

    def mailbox_show_permissions(self, mailbox_name, **kwargs):
        """ returns a list of users with permissions for a mailbox"""

        path = "customers/me/domains/%s/ex/mailboxes/%s/permissions" % (self.domain, mailbox_name)
        data = self._call(self.host, path, kwargs)
        return data

    @RateLimited(30) #30 calls/minute max for "POST" and "PUT" operations
    def mailbox_edit(self, mailbox_name, **kwargs):
        """
            mailbox_name (the Rackspace username only, no domain) is required
            popular kwargs include isHidden and emailForwardingAddress.
            emailForwardingAddress will ONLY take valid addresses w/in Exchange
        """

        kwargs['method'] = 'PUT'
        path = "customers/me/domains/%s/ex/mailboxes/%s" % (self.domain, mailbox_name)
        data = self._call(self.host, path, kwargs)
        return data

    def resource_show(self, resource_name, **kwargs):

        path = "customers/me/domains/%s/ex/resources/%s" % (self.domain, resource_name)
        data = self._call(self.host, path, kwargs)
        return data

    def resource_show_calendarprocessing(self, resource_name, **kwargs):

        path = "customers/me/domains/%s/ex/resources/%s/calendarProcessing" % (self.domain, resource_name)
        data = self._call(self.host, path, kwargs)
        return data    

    def resource_edit(self, resource_name, **kwargs):

        kwargs['method'] = 'PUT'
        path = "customers/me/domains/%s/ex/resources/%s" % (self.domain, resource_name)
        data = self._call(self.host, path, kwargs)
        return data

    # @classmethod
    def _generateSignature(self, timestamp):
        if not self.user_key or not self.secret_key:
            return ""
        sha1_source = self.user_key + self.user_agent + timestamp + self.secret_key
        sha1_hash = hashlib.sha1(sha1_source.encode('utf-8')).digest()
        signature = base64.b64encode(sha1_hash)
        return signature

    def _call(self, host, path, params, timeout=5000):

        timestamp = time.strftime('%Y%m%d%H%M%S').encode('utf-8') #YYYYMMDDHHmmss
        signature = ':'.join((self.user_key, timestamp, self._generateSignature(timestamp)))

        if params.get('method') == 'PUT':
            del params['method']
            url = "https://%(host)s/v1/%(path)s" % {
                'host': host,
                'path': path,
                }
            if params.get('test') == 'y':
                url = 'http://httpbin.org/put'
                del params['test']
            request = Request(url, data=urlencode(params))
            request.add_header('Content-Type', 'application/x-www-form-urlencoded')
            request.get_method = lambda: 'PUT'
        elif params.get('method') == 'POST':
            del params['method']
            url = "https://%(host)s/v1/%(path)s" % {
                'host': host,
                'path': path,
                }
            # url = 'http://httpbin.org/put'
            request = Request(url, data=urlencode(params))
            request.add_header('Content-Type', 'application/x-www-form-urlencoded')
            request.get_method = lambda: 'POST'
        else:
            request = "https://%(host)s/v1/%(path)s?%(params)s" % {
                'host': host,
                'path': path,
                'params': urlencode(params, doseq=1)
                }

        try:
            opener = build_opener(DontRedirect())
            opener.addheaders = [('X-Api-Signature', signature),
            					('User-Agent', self.user_agent),
            					('Accept-Encoding', 'gzip, deflate'),
            					('Accept', 'application/json')]

            response = opener.open(request)
            code = response.code
            result = response.read().decode('utf-8')
            if code not in (200, 202, 204):
                raise RackspaceError(500, result)
            if code != 202 and result.startswith('{'):
                data = json.loads(result)
            elif code == 202:
                data = "{'response': '202 Accepted'}"
            else:
                data = "{'code': '%d', 'response': '%s'}" % (code, result)
            return data
        except URLError as e:
            raise RackspaceError(500, "Rackspace response: %s" % (e.readlines()))
        except HTTPError as e:
            raise RackspaceError(e.code, e.read())
        except RackspaceError:
            raise
        except Exception:
            raise RackspaceError(None, sys.exc_info()[1])
