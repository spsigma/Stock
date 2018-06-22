"""
Parses XML and HTML to `lxml <http://codespeak.net/lxml/>`_ nodes
"""

from lxml import etree
from httpencode.format import Format

def load_xml(fp, content_type):
    return etree.parse(fp)

def dump_xml_iter(data, content_type):
    return [etree.tostring(data)]

xml = Format(
    'lxml_xml', ['text/xml', 'application/xml'],
    type='lxml.etree',
    load=load_xml,
    dump_iter=dump_xml_iter,
    secure=True)

def load_html(fp, content_type):
    return etree.parse(fp, etree.HTMLParser())

def dump_html_iter(data, content_type):
    return [str(html_transform(data))]

html_xsl = '''
<xsl:transform xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="html" encoding="UTF-8" />
  <xsl:template match="/">
    <xsl:copy-of select="."/>
  </xsl:template>
</xsl:transform>
'''

html_transform = etree.XSLT(etree.XML(html_xsl))

# Should include other HTML types
html = Format(
    'lxml_html', ['text/html'],
    type='lxml.etree',
    load=load_html,
    dump_iter=dump_html_iter,
    secure=True)
