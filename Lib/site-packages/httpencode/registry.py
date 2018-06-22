"""
Finds formats given criteria or name.
"""

import pkg_resources

class NoFormatError(LookupError):
    """
    Raised when no matching format can be found
    """

__all__ = ['find_format_match', 'get_format',
           'NoFormatError']


# Dict of {format_name: (dist, ep_name)}
_format_names = {}
# Dict of {mimetype: {type: (dist, ep_name)}}
_format_mimetypes = {}
# Dict of {type: {mimetype: (dist, ep_name)}}
_format_types = {}

def find_format_match(type, mimetype):
    """
    Find a format object that can accept the given mimetype and produce the
    given type.

    If ``debug`` is true, then information will be logged about how a
    format is selected.
    """
    assert type
    assert mimetype
    if ';' in mimetype:
        mimetype = mimetype.split(';', 1)[0]
    try:
        value = _format_mimetypes[mimetype][type]
    except KeyError:
        raise NoFormatError(
            "No format found providing %s to %s"
            % (mimetype, type))
    else:
        return _load_ep(value)

def find_format_accept(type, accept_list):
    """
    Find a format that converts the given type to one of the provided
    mimetypes in accept_list, choosing whatever the first item in the
    list is.  Returns (format, content_type)

    If force_load is true, then we'll scan for items regardless of whether
    they are loaded.
    """
    assert accept_list, ("Empty accept list passed in")
    # First we'll try to see if the best match is loaded, in which case
    # we don't have to look further
    for mimetype in accept_list:
        try:
            value = _format_mimetypes[mimetype][type]
        except KeyError:
            pass
        else:
            return _load_ep(value), mimetype
    raise NoFormatError(
        "No format available to convert any of %s to %s"
        % (accept_list, type))

def find_accept_for_type(type):
    """
    Return a list of all the mimetypes we know how to convert into the
    given Python type
    """
    return _format_types.get(type, {}).keys()

def get_format(name):
    """
    Gets a format object by name

    Formats are named by having an entry point in [httpencode.format]
    named ``name <name>``
    """
    try:
        value = _format_names[name]
    except KeyError:
        raise NoFormatError(
            "No format found by the name %r" % name)
    else:
        return _load_ep(value)

def find_format_by_type(type, mimetypes):
    """
    Finds a format by its type, prefering the mimetypes given (in
    order).

    ``'*'`` can be used as a final mimetype, but if that is ambiguous
    it is an error.  (That is, if there are different formats that
    work with that Python type).
    """
    if isinstance(mimetypes, basestring):
        raise TypeError(
            "mimetypes must be a list (not %r)" % mimetypes)
    possible = _format_types.get(type)
    if not possible:
        raise NoFormatError(
            "No formats available for type %r" % type)
    for mimetype in mimetypes:
        if mimetype == '*':
            found = None
            for data in possible.values():
                if found is None:
                    found = data
                elif found != data:
                    raise TypeError(
                        "There are multiple formats that can serialize "
                        "the type %r (at least %r and %r)"
                        % (type, found, data))
            # They are all the same format, or there is only one
            # format
            return _load_ep(found)
        if mimetype in possible:
            return _load_ep(possible[mimetype])
    raise NoFormatError(
        "There is not format that serializes the type %r "
        "and produces any of the mimetypes %r"
        % (type, mimetypes))

def _load_ep(data):
    # Loads data=(dist_name, ep_name)
    dist = pkg_resources.get_distribution(data[0])
    return dist.load_entry_point(
        'httpencode.format', data[1])

def _dist_activated(dist):
    entries = dist.get_entry_map('httpencode.format')
    for name in entries:
        data = (dist.key, name)
        if name.startswith('name '):
            format_name = name[5:].strip()
            if _format_names.get(format_name, data) != data:
                raise pkg_resources.VersionConflict(
                    "Distribution %r has identical format name (%r) as distribution %r"
                    % (dist, format_name, _format_names[format_nmame][0]))
            _format_names[format_name] = data
            continue
        parts = name.split()
        if len(parts) != 3 or parts[1] != 'to':
            warnings.warn(
                'Entry point [httpencode.format] %r in distribution '
                '%r is not a valid format'
                % (name, dist))
            continue
        mimetype, type = parts[0], parts[2]
        mdict = _format_mimetypes.setdefault(mimetype, {})
        if mdict.get(type, data) != data:
            raise pkg_resources.VersionConflict(
                "Distribution %r has an identical conversion (%r) as distribution %r"
                % (dist, name, mdict[type][0]))
        mdict[type] = data
        tdict = _format_types.setdefault(type, {})
        # If mdict didn't have a dup, this shouldn't
        # either
        assert tdict.get(mimetype, data) == data
        tdict[mimetype] = data

# This calls dist_activated for all existing and future distributions
pkg_resources.add_activation_listener(_dist_activated)
