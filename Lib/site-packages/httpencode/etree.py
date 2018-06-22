try:
    from xml.etree import ElementTree as etree
except ImportError:
    import elementtree.ElementTree as etree
from httpencode.format import Format

def load(fp, content_type):
    data = etree.parse(fp)
    return data

def dump_iter(data, content_type):
    return [etree.tostring(data)]

xml = Format(
    'ElementTree', ['text/xml', 'application/xml'], 'etree',
    dump_iter=dump_iter,
    load=load,
    secure=True)
