import sys
import urlparse
import re
from cStringIO import StringIO
import httplib2
from paste.request import construct_url
from paste.util.multidict import MultiDict
from httpencode.registry import get_format, find_format_match, find_format_by_type, \
     find_accept_for_type
from httpencode.format import Format
from paste.response import header_value, replace_header, remove_header

__all__ = ['HTTP']

# @@: Can 0-9 be in a scheme?  Probably good enough either way
scheme_re = re.compile(r'^[a-zA-Z0-9]+:')

class HTTP(object):

    default_encoding = 'utf8'
    default_input_content_type = None
    default_input_format = None
    prefer_input_mimetypes = [
        "application/x-www-forurlencoded",
        "multipart/form-data",
        "application/xml",
        "*"]
    default_post_input_type = 'python'
    # Set this to send all requests to this app (for testing):
    mock_wsgi_app = None
    redirections = httplib2.DEFAULT_MAX_REDIRECTS

    def __init__(self, cache=None, default_encoding=None,
                 default_input_content_type=None,
                 default_input_format=None,
                 prefer_input_mimetypes=None,
                 default_post_input_type=None,
                 redirections=None):
        self.httplib2 = httplib2.Http(cache)
        self.cache = cache
        if default_encoding is not None:
            self.default_encoding = default_encoding
        if default_input_content_type is not None:
            self.default_input_content_type = default_input_content_type
        if default_input_format is not None:
            if isinstance(default_input_format, basestring):
                default_input_format = get_format(default_input_format)
            self.default_input_format = default_input_format
        if prefer_input_mimetypes is not None:
            if isinstance(prefer_input_mimetypes, basestring):
                raise TypeError(
                    "prefer_input_mimetypes must be a list (not %r)"
                    % prefer_input_mimetypes)
            self.prefer_input_mimetypes = prefer_input_mimetypes
        if default_post_input_type is not None:
            self.default_post_input_type = default_post_input_type
        if redirections is not None:
            self.redirections = redirections
        for name in ['add_credentials', 'clear_credentials']:
            setattr(self, name, getattr(self.httplib2, name))
        self._raw_request = self.httplib2.request

    def clone(self, cache=None, default_encoding=None,
              default_input_content_type=None,
              default_input_format=None,
              prefer_input_mimetypes=None,
              default_post_input_type=None,
              redirections=None):
        """
        Create another HTTP instance with the same settings as the
        current one, but potentially overriding some settings.
        """
        if cache is None:
            cache = self.cache
        if default_encoding is None:
            default_encoding = self.default_encoding
        if default_input_content_type is None:
            default_input_content_type = self.default_input_content_type
        if prefer_input_mimetypes is None:
            prefer_input_mimetypes = self.prefer_input_mimetypes
        if default_post_input_type is None:
            default_post_input_type = self.default_post_input_type
        if redirections is None:
            redirections = self.redirections
        return self.__class__(
            cache=cache, default_encoding=default_encoding,
            default_input_content_type=default_input_content_type,
            prefer_input_mimetypes=prefer_input_mimetypes,
            default_post_input_type=default_post_input_type,
            redirections=redirections)

    def GET(self, uri, headers=None,
            wsgi_request=None, output=None, trusted=False):
        return self.request(
            uri, method='GET', body=None, headers=headers,
            wsgi_request=wsgi_request,
            input=None, output=output, trusted=trusted)

    def POST(self, uri, body=None, headers=None,
             wsgi_request=None, input=None, output=None, trusted=False):
        if not isinstance(body, basestring) and not input:
            input = self.default_post_input_type
        return self.request(
            uri, method='POST', body=body, headers=headers,
            wsgi_request=wsgi_request,
            input=input, output=output, trusted=trusted)

    def PUT(self, uri, body=None, headers=None,
            wsgi_request=None, input=None, output=None, trusted=False):
        return self.request(
            uri, method='PUT', body=body, headers=headers,
            wsgi_request=wsgi_request,
            input=input, output=output, trusted=trusted)

    def DELETE(self, uri, headers=None,
               wsgi_request=None, output=None, trusted=False):
        return self.request(
            uri, method='PUT', body=None, headers=headers,
            wsgi_request=wsgi_request,
            input=None, output=output, trusted=trusted)

    def request(self, uri, method="GET", body=None, headers=None,
                wsgi_request=None,
                input=None, output=None, trusted=False):
        method = method.upper()
        wsgi_request = self._coerce_wsgi_request(wsgi_request)
        headers = self._coerce_headers(headers)
        if isinstance(output, basestring) and output.startswith('name '):
            output = get_format(output[5:].strip())
        input, body, headers = self._coerce_input(
            input, body, headers)
        if body and not header_value(headers, 'content-type'):
            # We have to add a content type...
            content_type = input.choose_mimetype(headers, body)
            replace_header(headers, 'content-type', content_type)
        headers = self._set_accept(headers, output)
        if wsgi_request is not None:
            uri = self._resolve_uri(uri, wsgi_request)
            if self._internally_resolvable(uri, wsgi_request):
                return self._internal_request(
                    uri, method=method, body=body, headers=headers,
                    wsgi_request=wsgi_request,
                    input=input, output=output, trusted=trusted)
        else:
            if not scheme_re.search(uri):
                raise ValueError(
                    'You gave a non-absolute URI (%r) and no wsgi_request to '
                    'normalize it against' % uri)
        return self._external_request(
            uri, method=method, body=body, headers=headers,
            wsgi_request=wsgi_request,
            input=input, output=output, trusted=trusted)

    def _set_accept(self, headers, output):
        if not output:
            # We apparently don't care what we get
            return headers
        if isinstance(output, Format):
            accept = output.content_types
        elif isinstance(output, basestring):
            # Can't be a name, we already resolved that already
            accept = find_accept_for_type(output)
        else:
            raise TypeError(
                "output should be a mimetype or Format object, not %r"
                % output)
        replace_header(headers, 'Accept', ', '.join(accept))
        return headers
        

    def _resolve_uri(self, uri, wsgi_request):
        orig_uri = construct_url(wsgi_request)
        return urlparse.urljoin(orig_uri, uri)

    def _coerce_wsgi_request(self, wsgi_request):
        if wsgi_request is not None and hasattr(wsgi_request, 'environ'):
            wsgi_request = wsgi_request.environ
        return wsgi_request

    def _coerce_headers(self, headers):
        if headers is None:
            return []
        if hasattr(headers, 'headers'):
            # Message-style headers; treating them like a dict will
            # cause folding, which can break requests (particularly
            # Set-Cookie)
            return [
                tuple(h.split(': ', 1)) for h in headers.headers]
        elif hasattr(headers, 'items'):
            return headers.items()
        else:
            return list(headers)

    def _coerce_input(self, input, body, headers):
        # Case when there's no request body:
        if body is None or body == '':
            return None, '', headers
        if isinstance(input, Format):
            # We've got an explicit format
            return input, body, headers
        if isinstance(input, basestring) and input.startswith('name '):
            # A named format
            input = get_format(input[5:].strip())
            return input, body, headers
        if not input and isinstance(body, basestring):
            if isinstance(body, unicode):
                if not self.default_input_encoding:
                    raise ValueError(
                        "There is no default_input_encoding, and you gave a unicode request body")
                input = input.encode(self.default_input_encoding)
                # Should we set charset in the Content-type at this
                # time?
            return input, body, headers
        if not input:
            # @@: Should this perhaps default to 'python'?
            # Or should we autodetect dict and list as 'python'?
            if self.default_input_format:
                input = self.default_input_format
            else:
                raise ValueError(
                    "You gave a non-string body (%r) and no input "
                    "(nor is there a default_input_format)" % body)
            return input, body, headers
        if isinstance(input, basestring):
            # Must be a type of Python object
            input = find_format_by_type(
                input, self.prefer_input_mimetypes)
        else:
            # I don't know what it is...?
            raise TypeError(
                "Invalid value for input: %r" % input)
        return input, body, headers

    def _internally_resolvable(self, uri, wsgi_request):
        if self.mock_wsgi_app is not None:
            return True
        if 'paste.recursive.script_name' not in wsgi_request:
            return False
        scheme, netloc, path, qs, fragment = urlparse.urlsplit(uri)
        if scheme != wsgi_request.get('wsgi.url_scheme', False):
            return False
        if 'HTTP_HOST' not in wsgi_request:
            return False
        if (self._normalize_netloc(scheme, netloc) !=
            self._normalize_netloc(wsgi_request['wsgi.url_scheme'], wsgi_request['HTTP_HOST'])):
            return False
        script_name = wsgi_request['paste.recursive.script_name']
        if not path.startswith(script_name):
            return False
        return True

    def _normalize_netloc(self, scheme, netloc):
        if ':' not in netloc:
            if scheme.lower() == 'http':
                netloc += ':80'
            elif scheme.lower() == 'https':
                netloc += '443'
            else:
                raise ValueError(
                    'Do not understand scheme: %r' % scheme)
        return netloc

    def _internal_request(self, uri, method, body, headers,
                          wsgi_request, input, output, trusted):
        if self.mock_wsgi_app is not None:
            script_name = ''
            app = self.mock_wsgi_app
        else:
            script_name = wsgi_request['paste.recursive.script_name']
            app = wsgi_request['paste.recursive.include_app_iter'].application
        scheme, netloc, path, fragment, qs = urlparse.urlsplit(uri)
        environ = self._make_internal_environ(
            uri, script_name, method, input, body, headers,
            wsgi_request)
        out = []
        caught = []
        def start_response(status, headers, exc_info=None):
            caught[:] = [status, headers]
            # @@: Is there anything I should do with exc_info?
            return out.append
        app_iter = app(environ, start_response)
        if out or not caught:
            # Damn, used the writer, have to collect output:
            # (or they didn't call start_response yet, same result)
            try:
                for item in app_iter:
                    out.append(item)
            finally:
                if hasattr(app_iter, 'close'):
                    app_iter.close()
            if not caught:
                raise Exception(
                    "Application %r did not call start_response"
                    % app)
            status, headers = caught
            return self._create_response(
                status, headers, output, app_iter=out)
        else:
            status, headers = caught
            return self._create_response(
                status, headers, output, app_iter, trusted)

    def _make_internal_environ(self, uri, script_name, method,
                               input, body, headers, wsgi_request):
        scheme, netloc, path, qs, fragment = urlparse.urlsplit(uri)
        assert path.startswith(script_name)
        path_info = path[len(script_name):]
        assert not path_info or path_info.startswith('/')
        if ':' in netloc:
            server_name, server_port = netloc.split(':', 1)
        else:
            server_name = netloc
            if scheme == 'http':
                server_port = '80'
            elif scheme == 'https':
                server_port = '443'
            else:
                raise TypeError(
                    "Unknown scheme: %r" % scheme)
        wsgi_input, content_length = self._make_input(input, body, headers, True)
        environ = {
            'REQUEST_METHOD': method,
            'SCRIPT_NAME': script_name,
            'PATH_INFO': path_info,
            'SERVER_NAME': server_name,
            'SERVER_PORT': server_port,
            'SERVER_PROTOCOL': "HTTP/1.0", # @@: 1.1?
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': scheme,
            'wsgi.input': wsgi_input,
            'CONTENT_LENGTH': content_length,
            # @@: Better error stream?
            'wsgi.errors': wsgi_request['wsgi.errors'],
            'wsgi.multithread': wsgi_request['wsgi.multithread'],
            'wsgi.multiprocess': wsgi_request['wsgi.multiprocess'],
            'wsgi.run_once': False,
            'httpencode.internal_request': True
            }
        for name, value in headers:
            name = 'HTTP_' + name.upper().replace('-', '_')
            if name == 'HTTP_CONTENT_TYPE':
                name = 'CONTENT_TYPE'
            elif name == 'HTTP_CONTENT_LENGTH':
                name = 'CONTENT_LENGTH'
            environ[name] = value
        return environ

    def _make_input(self, input, body, headers, internal):
        if input:
            return input.make_wsgi_input_length(body, headers, internal)
        else:
            return StringIO(body), str(len(body))

    def _serialize_body(self, input, body, headers):
        if input:
            return ''.join(input.dump_iter(body, header_value(headers, 'content-type')))
        else:
            return body
    
    def _external_request(self, uri, method, body, headers,
                          wsgi_request, input, output, trusted):
        body = self._serialize_body(input, body, headers)
        # @@: Does httplib2 handle Content-Length?
        dict_headers = MultiDict(headers)
        (res, content) = self.httplib2.request(
            uri, method=method,
            body=body, headers=dict_headers, redirections=self.redirections)
        status = '%s %s' % (res.status, res.reason)
        # @@: Hrm...
        headers = res.items()
        remove_header(headers, 'status')
        return self._create_response(
            status, headers, output, [content], trusted)
    
    def _create_response(self, status, headers, output, app_iter, trusted):
        content_type = header_value(headers, 'content-type')
        if app_iter is None:
            # @@: Can this really happen?
            # What happens with a 204 No Content?
            return self._make_response(
                status, headers, data=None)
        if not output:
            # Easy, return plain output
            # @@: Check charset?
            return self._make_response(
                status, headers, data=''.join(app_iter))
        if isinstance(output, basestring):
            if output.startswith('name '):
                output = get_format(output[5:].strip())
            else:
                # Must be a Python type
                output = find_format_match(
                    output, content_type)
        elif isinstance(output, Format):
            pass
        else:
            raise TypeError(
                "Invalid value for output: %r" % output)
        data = output.parse_wsgi_response(
            status, headers, app_iter, trusted=trusted)
        return self._make_response(
            status, headers, data=data)

    def _make_response(self, status, headers, data):
        return data
    
