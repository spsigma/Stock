"""
Lazy serialization and decoding wrappers for app_iter and wsgi.input
objects
"""

from paste.util.filemixin import FileMixin

class FileLengthWrapper(FileMixin):
    """
    Wraps a file-like object that has a fixed length, returning
    '' after the object has been exhausted.

    Files are read-only
    """
    
    def __init__(self, file, length):
        self.file = file
        self.length = length
        self._read = 0
        self.closed = False
        if hasattr(self.file, 'flush'):
            self.flush = self.file.flush
        if hasattr(self.file, 'seek'):
            self.seek = self._seek
        if hasattr(self.file, 'mode'):
            self.mode = self.file.mode

    def read(self, size=None):
        if self.closed:
            raise Exception("File already closed")
        if size is None:
            size = self.length - self._read
        data = self.file.read(size)
        self._read += len(data)
        return data

    def close(self):
        self.closed = True
        self.file.close()

    def tell(self):
        return self._read

    def _seek(self, offset):
        # @@ No whence
        self.file.seek(offset)
        self._read = offset

class FileAppIterWrapper(FileMixin):

    """
    Wraps a WSGI app_iter and presents a file-like interface to it.

    This does not call ``app_iter.close()`` until you close the file
    itself.  Example::

       >>> f = FileAppIterWrapper(['a', 'bc', 'def', 'ghijk'])
       >>> f.read(2)
       'ab'
       >>> f.read(1)
       'c'
       >>> f.read(1000)
       'defghijk'
       >>> f.read()
       ''
    """

    def __init__(self, app_iter):
        self.app_iter = app_iter
        self.app_iter_iter = iter(app_iter)
        self._buffer = ''
        self.closed = False

    def read(self, size=None):
        if size is None:
            data = self._buffer + ''.join(self.app_iter_iter)
            self._buffer = ''
            return data
        data = self._buffer
        while len(data) < size:
            try:
                data += self.app_iter_iter.next()
            except StopIteration:
                # Reached end of app_iter
                break
        # Even if size is now greater than the length of data, this
        # should return what data there is, and leave self._buffer as
        # the empty string
        self._buffer = data[size:]
        return data[:size]

    def close(self):
        if hasattr(self.app_iter, 'close'):
            self.app_iter.close()
        self.closed = True

class LazySerialize(object):

    """
    Iterator that serializes the data lazily, and returns the data as
    an iterator, but also allows the data to be retrieved without
    serialization.
    """

    def __init__(self, format, content_type, data):
        self.format = format
        self._serialized_iter = None
        self.content_type = content_type
        self.decoded = (format.type, data)

    def __iter__(self):
        return self

    def httpencode_dump_iter(self, content_type=None):
        assert (content_type is None
                or self.content_type is None
                or content_type == self.content_type), (
            "content_type argument and constructor do not "
            "match (got %r in constructor, %r now)"
            % (self.content_type, content_type))
        return self.format.dump_iter(
            self.decoded[1],
            content_type or self.content_type)

    def next(self):
        if self._serialized_iter is None:
            s_data = self.format.dump_iter(self.decoded[1], self.content_type)
            if isinstance(s_data, str):
                s_data = [s_data]
            self._serialized_iter = iter(s_data)
        return self._serialized_iter.next()

class ReplacementInput(object):

    """
    A replacement for a ``wsgi.input`` file that acts as a file, but
    lazily serializes the data.  Also, the data can be retrieved
    without serialization.
    """

    def __init__(self, format, decoded):
        self.format = format
        assert isinstance(decoded, tuple), (
            "decoded should be a tuple of (output_type, data), not %r" % decoded)
        self.decoded = decoded
        self._leftover = None
        self._read_finished = False

    def __repr__(self):
        return '<wsgi.input replacement serving %s>' % (
            self.decoded[0])

    def __iter__(self):
        return self

    def flush(self):
        pass

    def next(self):
        return self.read()

    def readline(self, size=None):
        if self._leftover is None:
            data = self.read()
            self._leftover = data.splitlines(True)
        if not self._leftover:
            return ''
        next = self._leftover.pop(0)
        return next

    def xreadlines(self):
        return self

    def read(self, size=None):
        if self._leftover is not None:
            next = ''.join(self._leftover)
            self._leftover = []
            return next
        if self._read_finished:
            return ''
        # We ignore size, but whatever...
        serialized = self.format.serialize(self.decoded[1])
        self._read_finished = True
        return serialized

if __name__ == '__main__':
    import doctest
    doctest.testmod()
    
