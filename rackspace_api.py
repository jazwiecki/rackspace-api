import base64
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
    from urllib2 import build_opener, HTTPRedirectHandler, URLError, HTTPError
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
        c = rackspace_api.Connection('user_key','secret_key')
        c.method('param')
    """

    def __init__(self, user_key=None, secret_key=None, domain=None):
        self.host = 'api.emailsrvr.com'
        self.user_key = user_key
        self.secret_key = secret_key
        self.domain = domain
        (major, minor, micro, releaselevel, serial) = sys.version_info
        parts = (major, minor, micro, '?')
        self.user_agent = "Python/%d.%d.%d rackspace_api/%s" % parts

    def list_lists(self, limit=None, marker=None, previouspage=None):
        """ returns a list of all the Exchange distribution lists in the domain
        	@parameter limit: number of results to return, max 100
        	@parameter marker: used in pagination. the common name of the last 
        						object in the previous result set.
        	@parameter previouspage: used in pagination. Boolean flag that returns
        						the previous page when used with the "marker" param.
        						
        """
        params = dict()
        if limit is not None:
            assert isinstance(limit, integer_types)
            params["limit"] = str(limit)
        if marker is not None:
            params["marker"] = str(marker)
        if previouspage is not None:
        	params["previouspage"] = str(previouspage)
        method = "domains/%s/ex/distributionlists" % self.domain
        data = self._call(self.host, method, params)
        return data

    # @classmethod
    def _generateSignature(self, timestamp):
        if not self.user_key or not self.secret_key:
            return ""
        signature_hash_source = '%s%s%s%s' % (self.user_key, self.user_agent, timestamp, self.secret_key)
        sha1_hash = hashlib.sha1(signature_hash_source).digest()
        signature = base64.b64encode(sha1_hash)
        return signature

    def _call(self, host, method, params, timeout=5000):

        timestamp = time.strftime('%Y%m%d%H%M%S') #YYYYMMDDHHmmss
        signature = '%s:%s:%s' % (self.user_key, timestamp, self._generateSignature(timestamp))

        request = "https://%(host)s/v1/%(method)s?%(params)s" % {
            'host': host,
            'method': method,
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
            if code != 200:
                raise RackspaceError(500, result)
            if not result.startswith('{'):
                raise RackspaceError(500, result)
            data = json.loads(result)
            return data
        except URLError as e:
            raise RackspaceError(500, "%s with resulted in %s" % (request,str(e)))
        except HTTPError as e:
            raise RackspaceError(e.code, e.read())
        except RackspaceError:
            raise
        except Exception:
            raise RackspaceError(None, sys.exc_info()[1])
