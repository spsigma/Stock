from httpencode.registry import get_format, find_format_match, \
     find_format_accept
from paste.httpheaders import ACCEPT
from paste.response import header_value

class InsecureFormatError(Exception):
    """
    Raised when for some reason an insecure format is used in a
    non-trusted situation.
    """

def parse_request(environ, output_type=None, trusted=False,
                  format=None):
    """
    Parses a WSGI request, attempting to get the given output type.

    If ``trusted`` is true, then insecure formats will be allowed.
    """
    if format is None and output_type is None:
        raise TypeError(
            "You must give either an output_type or format argument")
    if format is None:
        format = find_format_match(output_type,
                                   get_mimetype_from_environ(environ, True))
    if output_type is not None:
        assert format.type == output_type, (
            "Type of format %r (%r) does not match given type %r"
            % (format, format.type, output_type))
        output_type = format.type
    return format.parse_request(environ, trusted=trusted)

def parse_response(response, output_type, trusted=False, format=None):
    """
    Parses an HTTPResponse, attempting to get the given output type.

    If ``trusted`` is true, then insecure formats will be allowed.
    """
    if format is None and output_type is None:
        raise TypeError(
            "You must give either an output_type or format argument")
    if format is None:
        format = find_format_match(output_type,
                                   get_mimetype_from_response(response, True))
    if output_type is not None:
        assert format.type == output_type, (
            "Type of format %r (%r) does not match given type %r"
            % (format, format.type, output_type))
    return format.parse_response(response, trusted=trusted)

def get_mimetype_from_environ(environ, strip_params=False):
    """
    Get the mimetype from the WSGI environ 
    """
    mimetype = environ.get('CONTENT_TYPE')
    if not mimetype:
        raise ValueError(
            "No CONTENT_TYPE in request environ")
    if strip_params:
        return mimetype.split(';', 1)[0]
    else:
        return mimetype

def get_mimetype_from_response(response, strip_params=False):
    """
    Get the mimetype from the HTTP response
    """
    mimetype = response.getheader('Content-type', None)
    if not mimetype:
        raise ValueError(
            'No Content-Type header in response')
    if strip_params:
        return mimetype.split(';', 1)[0]
    else:
        return mimetype

def get_mimetype_from_headers(headers, strip_params=False):
    mimetype = header_value(headers, 'Content-type')
    if not mimetype:
        raise ValueError(
            'No Content-Type header in headers: %r' % headers)
    if strip_params:
        return mimetype.split(';', 1)[0]
    else:
        return mimetype

class Responder(object):

    """
    WSGI application that serves a specific piece of data.  The data should
    not be mutated after creating this application.

    You must either pass in the type of the data (a string) or a format
    object that you want to use.  You can provide a default_format for use when
    the client doesn't pass in an Accept header.
    """

    def __init__(self, data, type=None, format=None, headers=None,
                 content_type=None, default_format=None):
        if type is None and format is None:
            raise TypeError(
                "You must provide a type or format argument")
        if type is not None and format is not None:
            assert format.type == type, (
                "type argument (%r) and format (%r; type=%r) do not match"
                % (type, format, format.type))
        self.data = data
        self.type = type
        if isinstance(format, basestring):
            format = get_format(format)
        self.format = format
        if isinstance(default_format, basestring):
            default_format = get_format(default_format)
        self.default_format = default_format
        self.headers = headers
        self.content_type = content_type

    def __call__(self, environ, start_response):
        content_type = None
        if self.format is None:
            accept = ACCEPT.parse(environ)
            if not accept:
                if self.default_format:
                    format = self.default_format
                else:
                    raise ValueError(
                        'No Accept header provided in a request, and no format or '
                        'default_format given')
            else:
                format, content_type = find_format_accept(self.type, accept)
        else:
            format = self.format
        app = format.responder(self.data, content_type=content_type)
        return app(environ, start_response)
            
