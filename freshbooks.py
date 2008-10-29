"""
freshbooks.py - Python interface to the FreshBooks API (http://developers.freshbooks.com)

Library Maintainer:  Matt Culbreth, mattculbreth@gmail.com, http://mattculbreth.com

#####################################################################

This work is distributed under an MIT License: 
http://www.opensource.org/licenses/mit-license.php

The MIT License

Copyright (c) 2008 Matt Culbreth (http://mattculbreth.com)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

#####################################################################

Hello, this is an open source Python library that serves as an interface to FreshBooks.
The code is heavily based on the existing Ruby implementation 
by Ben Vinegar of the same interface:
    http://freshbooks.rubyforge.org/
    
"""

import sys
import os
import urllib
import xml.dom.minidom as xml_lib

# module level constants
VERSION = '0.1'     # Library version
API_VERSION = '2.1' # FreshBooks API version
SERVICE_URL = "/api/%s/xml-in" % API_VERSION

# module level variables
account_url = None
auth_token = None
last_response = None

def setup(url, token):
    '''
    This funtion sets the high level variables for use in the interface.
    '''
    global account_url, auth_token
    
    account_url = url
    auth_token = token
  
#  these three classes are for typed exceptions  
class InternalError(Exception):
    pass
    
class AuthenticationError(Exception):
    pass
    
class UnknownSystemError(Exception):
    pass


def call_api(method, elems = []):
    '''
    This function calls into the FreshBooks API and returns the Response
    '''
    global last_response
    
    # make the request, which is an XML document
    doc = xml_lib.Document()
    request = doc.createElement('request')
    request.setAttribute('method', method)
    for key, value in elems.items():
        if isinstance(value, BaseObject):
            request.appendChild(value.to_xml())
        else:
            e = doc.createElement(key)
            e.appendChild(doc.createTextNode(value))
            request.appendChild(e)
            
    # send it
    result = post(doc.toxml('utf-8'))
    last_response = Response(result)
    
    # check for failure and throw an exception
    if last_response.is_failure():
        if 'not formatted correctly' in response.error_msg:
            raise InternalError(response.error_msg)
        elif 'uthentication failed' in response.error_msg:
            raise AuthenticationError(response.error_msg)
        elif 'does not exit' in response.error_msg:
            raise UnknownSystemError(response.error_msg)
        else:
            raise Exception(error_msg)
            
    return last_response
    
class Response(object):
    '''
    A response from FreshBooks
    '''
    def __init__(self, xml_raw):
        '''
        The constructor, taking in the xml as the source
        '''
        self._doc = xml_lib.parse(xml_raw)
        
    def _get_doc(self):
        '''
        Return the document
        '''
        return self._doc
    doc = property(_get_doc)
    
    def _get_elements(self):
        '''
        Return the doc's elements
        '''
        return self._doc.childNodes
        
    def is_success(self):
        '''
        return True if this is a successful response from the API
        '''
        return self._doc.firstChild.attributes['status'] == 'ok'
        
    def is_failure(self):
        '''
        returns True if this NOT a successful response from the API
        '''
        return not self.is_success()
        
    def _get_error_msg(self):
        '''
        returns the error message associated with this API response
        '''
        error = self._doc.getElementsByTagName('error')
        if error:
            return error.firstchild.nodeValue
        else:
            return None
    error_msg = property(_get_error_msg)
 
    
class BaseObject(object):
    '''
    The parent object for all FreshBook types
    '''
    def __init__(self):
        pass
        
    def to_xml(self):
        '''
        Return a string of XML for this object
        '''
        return xml_lib.Element('BaseObject')

#   elems.each do |key, value|
#     if value.is_a?(BaseObject)
#       elem = value.to_xml
#       request.add_element elem
#     else
#       request.add_element(Element.new(key)).text = value.to_s
#     end
#   end
# 
#   result = self.post(request.to_s)
# 
#   @@response = Response.new(result)
# 
#   #
#   # Failure
#   #
#   if @@response.fail?
#     error_msg = @@response.error_msg
# 
#     # Raise an exception for unexpected errors
# 
#     raise InternalError.new       if error_msg =~ /not formatted correctly/
#     raise AuthenticationError.new if error_msg =~ /[Aa]uthentication failed/
#     raise UnknownSystemError.new  if error_msg =~ /does not exist/
#   end
# 
#   @@response
# end
