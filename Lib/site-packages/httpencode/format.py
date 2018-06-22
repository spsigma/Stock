"""
Implements Format objects, which represent different formats and
serializations.  Concrete implementations instantiate ``Format``.
"""

from paste.response import header_value
from httpencode.wrappers import LazySerialize, ReplacementInput, \
     FileLengthWrapper, FileAppIterWrapper
from httpencode import api

_doc_template = """\
Format object that produces %(type)s Python objects
from mimetypes: %(mimetypes)s"""

class Format(object):

    """
    Instances of this class represent some particular format.  This is
    the entry point for both response and request handling for the
    format.
    """

    def __init__(self, name, content_types, type, secure,
                 load, dump_iter,
                 want_unicode=False, choose_mimetype=None,
                 doc=None):
        """
        name:
            A nice readable name for the format.

        content_types:
            A list of mime types; the first one will be preferred.

        type:
            A string giving some indication what kind of Python object
            this produces.  'python' is just a generic python object;
            other kinds of objects should use the module or class
            name.

        load, dump_iter:
            load and dump_iter take two arguments -- either a file
            object or the Python object to be dumped, and then a
            content type.

        want_unicode:
            if true, then load and dump produce/consume unicode
            objects
            
        secure:
            if true, then this format can decode arbitrary strings without
            having to trust the source

        choose_mimetype:
            if given, this takes a Python object, preferred content
            type, and header dict and returns the content type
        
        doc:
            Any extra documentation you want associated with the
            object
        """
        self.name = name
        self.content_types = content_types
        self.type = type
        self.load = load
        self.dump_iter = dump_iter
        if choose_mimetype is not None:
            self.choose_mimetype = choose_mimetype
        self.want_unicode = want_unicode
        self.secure = secure
        if doc is None:
            doc = _doc_template % dict(
                type=type, mimetypes=', '.join(content_types))
        self.__doc__ = doc

    def __repr__(self):
        return '<Format %s convert %s to type=%s>' % (
            self.name, ', '.join(self.content_types), self.type)

    def choose_mimetype(self, request_headers, data):
        # @@ Should try to look at Accept
        return self.content_types[0]

    def parse_request(self, environ, trusted=False):
        """
        Takes the WSGI environment and parses the request for this
        format, possibly using a shortcut to avoid decoding.
        """
        if not trusted and not self.secure:
            raise api.InsecureFormatError(
                "%r cannot parse untrusted data" % self)
        input = environ['wsgi.input']
        if 'CONTENT_LENGTH' in environ:
            length = int(environ['CONTENT_LENGTH'])
        else:
            # If we don't have CONTENT_LENGTH then we'll read
            # until the end, or more likely hope that we find
            # what we need unserialized.
            # @@ Or should we default to 0?
            length = None
        if hasattr(input, 'decoded') and input.decoded[0] == self.type:
            return input.decoded[1]
        else:
            content_type = api.get_mimetype_from_environ(environ)
            if hasattr(input, 'httpencode_dump_iter'):
                input = FileAppIterWrapper(
                    input.httpencode_dump_iter(content_type))
            elif length:
                input = FileLengthWrapper(input, length)
            parsed = self.load(input, content_type)
            decoded = (self.type, parsed)
            environ['wsgi.input'] = ReplacementInput(
                self, decoded)
            return parsed

    def parse_wsgi_response(self, status, headers, app_iter, trusted=False):
        """
        Parses the app_iter.

        Note: does not call ``app_iter.close()``
        """
        if not trusted and not self.secure:
            raise api.InsecureFormatError(
                "%r cannot parse untrusted data" % self)
        if hasattr(app_iter, 'decoded'):
            type, data = app_iter.decoded
            if type == self.type:
                return data
        content_type = api.get_mimetype_from_headers(headers)
        input = FileAppIterWrapper(app_iter)
        data = self.load(input, content_type)
        return data

    def parse_response(self, response):
        """
        Parses the HTTPResponse-like object
        """
        content_type = api.get_mimetype_from_response(response)
        # Response objects happen to be file-like:
        data = self.load(response, content_type)
        return data

    def make_wsgi_input_length(self, body, headers, internal):
        content_type = header_value(headers, 'content-type')
        if internal:
            return LazySerialize(self, content_type, body), '1'
        else:
            data = ''.join(self.dump_iter(body, content_type))
            return StringIO(data), str(len(data))
    
    def responder(self, data, content_type=None, headers=None):
        """
        Returns a WSGI application that serves the given data, with an
        optional explicit content_type and optional additional
        headers.
        """
        return RPCResponder(self, data, content_type, headers)

class RPCResponder(object):

    def __init__(self, format, data, content_type=None, headers=None):
        self.format = format
        self.data = data
        if headers is None:
            headers = []
        elif hasattr(headers, 'items'):
            headers = headers.items()
        else:
            headers = list(headers)
        header_content_type = header_value(headers, 'content-type')
        if (header_content_type is not None
            and content_type is not None
            and header_content_type != content_type):
            raise TypeError(
                "You've given an explicit header of Content-Type: "
                "%s and passed content_type=%r, which is ambiguous"
                % (header_content_type, content_type))
        if header_content_type is None:
            if content_type is None:
                content_type = format.content_types[0]
            headers.append(('Content-Type', content_type))
        elif content_type is None:
            content_type = header_content_type
        self.content_type = content_type
        self.headers = headers

    def __call__(self, environ, start_response):
        start_response('200 OK', self.headers)
        # @@: I should check if this is an internal request
        return LazySerialize(
            self.format, self.content_type, self.data)

