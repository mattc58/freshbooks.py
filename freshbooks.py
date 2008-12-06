"""
freshbooks.py - Python interface to the FreshBooks API (http://developers.freshbooks.com)

Library Maintainer:  
    Matt Culbreth
    mattculbreth@gmail.com
    http://mattculbreth.com

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
    
USAGE:

    import freshbooks
    
    freshbooks.setup('YOU.freshbooks.com', '<YOUR AUTH TOKEN>')
    clients = freshbooks.Client.list()
    client_1 = freshbooks.Client.get(<client_id>)
    
"""

import sys
import os
import urllib, urllib2
import xml.dom.minidom as xml_lib

# module level constants
VERSION = '0.1'     # Library version
API_VERSION = '2.1' # FreshBooks API version
SERVICE_URL = "/api/%s/xml-in" % API_VERSION

# module level variables
account_url = None
account_name = None
auth_token = None
request_headers = None
last_response = None

def setup(url, token, headers={}):
    '''
    This funtion sets the high level variables for use in the interface.
    '''
    global account_url, account_name, auth_token, request_headers
    
    account_url = url
    account_name = url[(url.find('//') +2):(url.find('freshbooks.com'))]
    auth_token = token
    request_headers = headers
    
#  these three classes are for typed exceptions  
class InternalError(Exception):
    pass
    
class AuthenticationError(Exception):
    pass
    
class UnknownSystemError(Exception):
    pass
    
class InvalidParameterError(Exception):
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
            e.appendChild(doc.createTextNode(str(value)))
            request.appendChild(e)
    doc.appendChild(request)
            
    # send it
    result = post(doc.toxml('utf-8'))
    last_response = Response(result)
    
    # check for failure and throw an exception
    if not last_response.success:
        msg = last_response.error_message
        if not msg:
            raise Exception("Error in response:  %s" % last_response.doc.toxml())
        if 'not formatted correctly' in msg:
            raise InternalError(msg)
        elif 'uthentication failed' in msg:
            raise AuthenticationError(msg)
        elif 'does not exit' in msg:
            raise UnknownSystemError(msg)
        elif 'Invalid parameter' in msg:
            raise InvalidParameterError(msg)
        else:
            raise Exception(msg)
            
    return last_response
    
def post(body):
    '''
    This function actually communicates with the FreshBooks API
    '''
    
    # setup HTTP basic authentication
    password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
    url = "https://" + account_url + SERVICE_URL
    password_mgr.add_password(None, url, auth_token, '')
    if request_headers:
        password_mgr.add_headers(request_headers)
    handler = urllib2.HTTPBasicAuthHandler(password_mgr)
    opener = urllib2.build_opener(handler)
    urllib2.install_opener(opener)    
    
    # make the request and return the response body
    response = urllib2.urlopen(url, body)
    response_content = response.read()
    return response_content

class Response(object):
    '''
    A response from FreshBooks
    '''
    def __init__(self, xml_raw):
        '''
        The constructor, taking in the xml as the source
        '''
        self._doc = xml_lib.parseString(xml_raw)
      
    @property  
    def doc(self):
        '''
        Return the document
        '''
        return self._doc
    
    @property
    def elements(self):
        '''
        Return the doc's elements
        '''
        return self._doc.childNodes
       
    @property 
    def success(self):
        '''
        return True if this is a successful response from the API
        '''
        return self._doc.firstChild.attributes['status'].firstChild.nodeValue == 'ok'
    
    @property    
    def error_message(self):
        '''
        returns the error message associated with this API response
        '''
        error = self._doc.getElementsByTagName('error')
        if error:
            return error[0].childNodes[0].nodeValue
        else:
            return None
            
class BaseObject(object):
    '''
    This serves as the base object for all FreshBooks objects.
    '''
    
    # this is used to provide typing help for certain type, ie
    # client.id is an int
    TYPE_MAPPINGS = {}
    
    # anonymous functions to do the conversions on type
    MAPPING_FUNCTIONS = {
        'int' : lambda val: int(val),
        'float' : lambda val: float(val)
    }

    @classmethod
    def _new_from_xml(cls, element):
        '''
        This internal method is used to create a new FreshBooks
        object from the XML.
        '''
        obj = cls()
        
        # basically just go through the XML creating attributes on the 
        # object.
        for elem in [node for node in element.childNodes if node.nodeType == node.ELEMENT_NODE]:
            val = None
            if elem.firstChild:
                val = elem.firstChild.nodeValue
                # HACK:  find another way to detect arrays, probably
                # based on a list of elements instead of a textnode
                if elem.nodeName == 'lines':
                    val = []
                    for item in [node for node in elem.childNodes if node.nodeType == node.ELEMENT_NODE]:
                        c = eval(item.nodeName.capitalize())
                        if c:
                            val.append(c._new_from_xml(item))
                        
                # if there is typing information supplied by 
                # the child class then use that
                elif cls.TYPE_MAPPINGS.has_key(elem.nodeName):
                    val = \
                        cls.MAPPING_FUNCTIONS[\
                            cls.TYPE_MAPPINGS[elem.nodeName]](val)
            setattr(obj, elem.nodeName, val)
            
        return obj
        
    def to_xml(self, doc, element_name=None):
        '''
        Create an XML representation of the object for use
        in sending to FreshBooks
        '''
        # The root element is the class name, downcased
        element_name = element_name or \
            self.name.lower()
        root = doc.createElement(element_name)
        
        # Add each member to the root element
        for key, value in self.__dict__.items():
            if isinstance(value, list):
                array = doc.createElement(key)
                for item in value:
                    item_name = 'line' if key == 'lines' else key[:-1]
                    array_item = doc.createElement(item_name)
                    array_item.appendChild(doc.createTextNode(str(item)))
                root.append(array)
            elif value:
                elem = doc.createElement(key)
                elem.appendChild(doc.createTextNode(str(value)))
                root.appendChild(elem)
        
        return root            
    
 
#-----------------------------------------------#
# Client
#-----------------------------------------------#      
class Client(BaseObject):
    '''
    The Client object
    '''
    
    TYPE_MAPPINGS = {'client_id' : 'int'}
    
    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        self.name = 'client'
        for att in ('client_id', 'first_name', 'last_name', 'organization','email', 'username', 'password', 'work_phone', 'home_phone', 'mobile', 'fax', 'notes', 'p_street1', 'p_street2', 'p_city', 'p_state', 'p_country', 'p_code','s_street1', 's_street2', 's_city', 's_state', 's_country', 's_code', 'url'):
            setattr(self, att, None)
        
    @classmethod
    def get(cls, client_id):
        '''
        Get a single object from the API
        '''
        resp = call_api('client.get', {'client_id' : client_id})
        
        if resp.success:
            clients = resp.doc.getElementsByTagName('client')
            if clients:
                return Client._new_from_xml(clients[0])
        
        return None

    @classmethod
    def list(cls, options = {}):
        '''  '''
        resp = call_api('client.list', options)
        result = None
        if (resp.success):
            result = [Client._new_from_xml(elem) for elem in resp.doc.getElementsByTagName('client')]
        
        return result
  
#-----------------------------------------------#
# Invoice
#-----------------------------------------------#      
class Invoice(BaseObject):
    '''
    The Invoice object
    '''

    TYPE_MAPPINGS = {'invoice_id' : 'int', 'client_id' : 'int',
        'po_number' : 'float', 'discount' : 'float', 'amount' : 'float'}

    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        self.name = 'invoice'
        for att in ('invoice_id', 'client_id', 'number', 'date', 'po_number',
      'terms', 'first_name', 'last_name', 'organization', 'p_street1', 'p_street2', 'p_city','p_state', 'p_country', 'p_code', 'amount', 'lines', 'discount', 'status', 'notes', 'url'):
            setattr(self, att, None)
        self.lines = []
        self.links = []

    @classmethod
    def get(cls, invoice_id):
        '''
        Get a single object from the API
        '''
        resp = call_api('invoice.get', {'invoice_id' : invoice_id})

        if resp.success:
            invoices = resp.doc.getElementsByTagName('invoice')
            if invoices:
                return Invoice._new_from_xml(invoices[0])

        return None

    @classmethod
    def list(cls, options = {}):
        '''  '''
        resp = call_api('invoice.list', options)
        result = None
        if (resp.success):
            result = [Invoice._new_from_xml(elem) for elem in resp.doc.getElementsByTagName('invoice')]

        return result
        
class Line(BaseObject):
    TYPE_MAPPINGS = {'unit_cost' : 'float', 'quantity' : 'float',
        'tax1_percent' : 'float', 'tax2_percent' : 'float', 'amount' : 'float'}

    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        self.name = 'line'
        for att in ('name', 'description', 'unit_cost', 'quantity', 'tax1_name',
        'tax2_name', 'tax1_percent', 'tax2_percent', 'amount'):
            setattr(self, att, None)


#-----------------------------------------------#
# Item
#-----------------------------------------------#      
class Item(BaseObject):
    '''
    The Item object
    '''

    TYPE_MAPPINGS = {'item_id' : 'int', 'unit_cost' : 'float',
        'quantity' : 'int', 'inventory' : 'int'}

    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        self.name = 'item'
        for att in ('item_id', 'name', 'description', 'unit_cost',
        'quantity', 'inventory'):
            setattr(self, att, None)

    @classmethod
    def get(cls, item_id):
        '''
        Get a single object from the API
        '''
        resp = call_api('item.get', {'item_id' : item_id})

        if resp.success:
            items = resp.doc.getElementsByTagName('item')
            if items:
                return Item._new_from_xml(items[0])

        return None

    @classmethod
    def list(cls, options = {}):
        '''  '''
        resp = call_api('item.list', options)
        result = None
        if (resp.success):
            result = [Item._new_from_xml(elem) for elem in resp.doc.getElementsByTagName('item')]

        return result

    

#-----------------------------------------------#
# Staff
#-----------------------------------------------#      
class Staff(BaseObject):
    '''
    The Staff object
    '''

    TYPE_MAPPINGS = {'staff_id' : 'int'}

    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        self.name = 'staff'
        for att in ('staff_id', 'username', 'first_name', 'last_name',
        'email', 'business_phone', 'mobile_phone', 'rate', 'last_login',
        'number_of_logins', 'signup_date', 
        'street1', 'street2', 'city', 'state', 'country', 'code'):
            setattr(self, att, None)

    @classmethod
    def get(cls, staff_id):
        '''
        Get a single object from the API
        '''
        resp = call_api('staff.get', {'staff_id' : staff_id})

        if resp.success:
            staffs = resp.doc.getElementsByTagName('staff')
            if staffs:
                return Staff._new_from_xml(staffs[0])

        return None

    @classmethod
    def list(cls, options = {}):
        '''  '''
        resp = call_api('staff.list', options)
        result = None
        if (resp.success):
            result = [Staff._new_from_xml(elem) for elem in resp.doc.getElementsByTagName('member')]

        return result

