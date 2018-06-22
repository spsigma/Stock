# (c) 2005 Ian Bicking and contributors; written for Paste (http://pythonpaste.org)
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
"""
The httpencode package exports these for getting formatters:

``get_format(mimetype, [output])``

Exceptions:

* NoFormatError

Also these functions are exported for doing requests:

* ``GET``
* ``POST``
* ``PUT``
* ``DELETE``
"""

from httpencode.registry import get_format, NoFormatError
from httpencode.http import HTTP

from httpencode.api import parse_request, parse_response, \
     Responder
