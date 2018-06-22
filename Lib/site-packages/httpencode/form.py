from cStringIO import StringIO
import cgi
import urllib
from httpencode.format import Format

def load_form(fp, content_type):
    environ = {
        'REQUEST_METHOD': 'POST',
        'CONTENT_TYPE': content_type,
        'QUERY_STRING': '',
        }
    if hasattr(fp, 'file'):
        # Unwrap, because we know we won't read past the end
        environ['CONTENT_LENGTH'] = fp.length
        fp = fp.file
    else:
        # We really need to get the content length :(
        data = fp.read()
        fp = StringIO(data)
        environ['CONTENT_LENGTH'] = len(data)
    fs = cgi.FieldStorage(fp=fp,
                          environ=environ,
                          keep_blank_values=1)
    return fs

def dump_form_iter(data, content_type):
    if isinstance(data, cgi.FieldStorage):
        # @@: We don't deal with MiniFieldStorage; should we?
        data = [
            (field.name, field.value)
            for field in data.list]
    elif hasattr(data, 'items'):
        # Allow for dictionaries
        data = data.items()
    # We should update headers to be multipart/form-data if there was
    # a file upload of some sort
    return [urllib.urlencode(data, doseq=True)]

# We should figure out when to get dump to multipart/form-data
form = Format(
    'form', ['application/x-www-form-urlencoded', 'multipart/form-data'],
    type='cgi.FieldStorage',
    load=load_form,
    dump_iter=dump_form_iter,
    secure=True)

# @@: This should be a multidict:
def load_pyform(fp, content_type):
    fs = load_form(fp, content_type)
    result = {}
    for field in fs.list:
        if field.name in result:
            if not isinstance(result[field.name], list):
                result[field.name] = [result[field.name], field.value]
            else:
                result[field.name].append(field.value)
        else:
            result[field.name] = field.value
    return result

def dump_pyform_iter(data, content_type):
    return dump_form_iter(data, content_type)

pyform = Format(
    'pyform', ['application/x-www-form-urlencoded', 'multipart/form-data'],
    type='python',
    load=load_pyform,
    dump_iter=dump_pyform_iter,
    secure=True)

