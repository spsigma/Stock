from simplejson import load, dump, loads, dumps
from httpencode.format import Format

def dump_json_iter(data, content_type):
    return [dumps(data)]

def load_json(fp, content_type):
    data = fp.read()
    # @@: For some reason simplejson is not liking \', even though
    # that seems entirely reasonable to me.  So we'll fix
    # it up:
    data = data.replace("\\'", "'")
    return loads(data)

json = Format(
    'json', ['application/json', 'text/x-json'],
    type='python',
    dump_iter=dump_json_iter,
    load=load_json,
    secure=True,
    )
