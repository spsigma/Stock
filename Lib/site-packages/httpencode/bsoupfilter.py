from BeautifulSoup import BeautifulSoup, BeautifulStoneSoup
from httpencode.format import Format

def load_xml(fp, content_type):
    return BeutifulStoneSoup(fp.read())

def dump_xml_iter(data, content_type):
    return [data.prettify()]

bsoup_xml = Format(
    'bsoup_xml', ['text/xml', 'application/xml'],
    type='BeautifulSoup',
    load=load_xml,
    dump_iter=dump_xml_iter,
    secure=True)

def load_html(fp, content_type):
    return BeautifulSoup(fp.read())

def dump_html_iter(data, content_type):
    return [data.prettify()]

# Should include other HTML types
bsoup = Format(
    'bsoup', ['text/html'],
    type='BeautifulSoup',
    load=load_html,
    dump_iter=dump_html_iter,
    secure=True)
