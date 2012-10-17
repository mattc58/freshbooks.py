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
    
    # get data
    freshbooks.setup('YOU.freshbooks.com', '<YOUR AUTH TOKEN>')
    clients = freshbooks.Client.list()
    client_1 = freshbooks.Client.get(<client_id>)
    
    # update data
    changed_client = freshbooks.Client()
    changed_client.client_id = client_1.client_id
    changed_client.first_name = u'Jane'
    r = freshbooks.call_api('client.update', changed_client)
    assert(r.success)
    
"""

import sys, os, datetime
import urllib, urllib2
import xml.dom.minidom as xml_lib

# module level constants
VERSION = '0.5'     # Library version
API_VERSION = '2.1' # FreshBooks API version
SERVICE_URL = "/api/%s/xml-in" % API_VERSION

# module level variables
account_url = None
account_name = None
auth_token = None
user_agent = None
request_headers = None
last_response = None

def setup(url, token, user_agent_name=None, headers={}):
    '''
    This funtion sets the high level variables for use in the interface.
    '''
    global account_url, account_name, auth_token, user_agent, request_headers
    
    account_url = url
    if url.find('//') == -1:
        account_name = url[:(url.find('freshbooks.com') - 1)]
    else:
        account_name = url[(url.find('//') + 2):(url.find('freshbooks.com') - 1)]
    auth_token = token
    user_agent = user_agent_name
    request_headers = headers
    if 'user-agent' not in [x.lower() for x in request_headers.keys()]:
        if not user_agent:
            user_agent = 'Python:%s' % account_name
        request_headers['User-Agent'] = user_agent
    
#  these three classes are for typed exceptions  
class InternalError(Exception):
    pass
    
class AuthenticationError(Exception):
    pass
    
class UnknownSystemError(Exception):
    pass
    
class InvalidParameterError(Exception):
    pass


def call_api(method, elems = {}):
    '''
    This function calls into the FreshBooks API and returns the Response
    '''
    global last_response
    
    # make the request, which is an XML document
    doc = xml_lib.Document()
    request = doc.createElement('request')
    request.setAttribute('method', method)
    if isinstance(elems, BaseObject):
        request.appendChild(elems.to_xml(doc))
    else:
        for key, value in elems.items():
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
    url = ""
    if account_url.find('//') == -1:
        url = "https://"
    url += account_url + SERVICE_URL
    password_mgr.add_password(None, url, auth_token, '')
    handler = urllib2.HTTPBasicAuthHandler(password_mgr)
    opener = urllib2.build_opener(handler)
    urllib2.install_opener(opener)    
    
    # make the request and return the response body
    request = urllib2.Request(url, body, request_headers)
    response = urllib2.urlopen(request)
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
        
    def __repr__(self):
        '''
        Print the Response and show the XML document
        '''
        s = "Response: success: %s, error_message: %s" % \
            (self.success,self.error_message)
        s += "\nResponse Document: \n%s" % self.doc.toxml()
        return s
      
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
        'float' : lambda val: float(val),
        'bool' : lambda val: bool(int(val)) if val in ('0', '1') else val,
        'datetime' : lambda val: \
            datetime.datetime.strptime(val, 
            '%Y-%m-%d %H:%M:%S') if (val != '0000-00-00 00:00:00' and len(val) == 19) else datetime.datetime.strptime(val, '%Y-%m-%d') if len(val) == 10 else val
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
        
    @classmethod
    def get(cls, object_id, element_name = None):
        '''
        Get a single object from the API
        '''
        resp = call_api('%s.get' % cls.object_name, {'%s_id' % cls.object_name : object_id})

        if resp.success:
            items = resp.doc.getElementsByTagName(element_name or cls.object_name)
            if items:
                return cls._new_from_xml(items[0])

        return None
        
    @classmethod
    def list(cls, options = {}, element_name = None, get_all=False):
        '''  
        Get a summary list of this object.
        If get_all is True then the paging will be checked to get all of the items.
        '''
        result = None
        if get_all:
            options['per_page'] = 100
            options['page'] = 1
            objects = []
            while True:
                resp = call_api('%s.list' % cls.object_name, options)
                if not resp.success:
                    return result
                new_objects = resp.doc.getElementsByTagName(element_name or cls.object_name)
                objects.extend(new_objects)
                if len(new_objects) < options['per_page']:
                    break
                options['page'] += 1
            result = [cls._new_from_xml(elem) for elem in objects] 
        else:        
            resp = call_api('%s.list' % cls.object_name, options)
            if (resp.success):
                result = [cls._new_from_xml(elem) for elem in \
                    resp.doc.getElementsByTagName(element_name or cls.object_name)]

        return result
        
        
    def to_xml(self, doc, element_name=None):
        '''
        Create an XML representation of the object for use
        in sending to FreshBooks
        '''
        # The root element is the class name, downcased
        element_name = element_name or \
            self.object_name.lower()
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
    object_name = 'client'
    
    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        # self.object_name = 'client'
        for att in ('client_id', 'first_name', 'last_name', 'organization','email', 'username', 'password', 'work_phone', 'home_phone', 'mobile', 'fax', 'notes', 'p_street1', 'p_street2', 'p_city', 'p_state', 'p_country', 'p_code','s_street1', 's_street2', 's_city', 's_state', 's_country', 's_code', 'url'):
            setattr(self, att, None)
        
  
#-----------------------------------------------#
# Invoice
#-----------------------------------------------#      
class Invoice(BaseObject):
    '''
    The Invoice object
    '''

    object_name = 'invoice'
    TYPE_MAPPINGS = {'invoice_id' : 'int', 'client_id' : 'int',
        'po_number' : 'int', 'discount' : 'float', 'amount' : 'float',
        'date' : 'datetime', 'amount_outstanding' : 'float', 
        'paid' : 'float'}

    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        for att in ('invoice_id', 'client_id', 'number', 'date', 'po_number',
      'terms', 'first_name', 'last_name', 'organization', 'p_street1', 'p_street2', 
      'p_city','p_state', 'p_country', 'p_code', 'amount', 'amount_outstanding', 'paid', 
      'lines', 'discount', 'status', 'notes', 'url'):
            setattr(self, att, None)
        self.lines = []
        self.links = []

        
#-----------------------------------------------#
# Line--really just a part of Invoice
#-----------------------------------------------#      
class Line(BaseObject):
    TYPE_MAPPINGS = {'unit_cost' : 'float', 'quantity' : 'float',
        'tax1_percent' : 'float', 'tax2_percent' : 'float', 'amount' : 'float'}

    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        for att in ('name', 'description', 'unit_cost', 'quantity', 'tax1_name',
        'tax2_name', 'tax1_percent', 'tax2_percent', 'amount'):
            setattr(self, att, None)
    
    @classmethod
    def get(cls, object_id, element_name = None):
        '''
        The Line doesn't do this
        '''
        raise NotImplementedError("the Line doesn't support this")

    @classmethod
    def list(cls, options = {}, element_name = None):
        '''
        The Line doesn't do this
        '''
        raise NotImplementedError("the Line doesn't support this")


#-----------------------------------------------#
# Item
#-----------------------------------------------#      
class Item(BaseObject):
    '''
    The Item object
    '''

    object_name = 'item'
    TYPE_MAPPINGS = {'item_id' : 'int', 'unit_cost' : 'float',
        'quantity' : 'int', 'inventory' : 'int'}

    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        for att in ('item_id', 'name', 'description', 'unit_cost',
        'quantity', 'inventory'):
            setattr(self, att, None)


#-----------------------------------------------#
# Payment
#-----------------------------------------------#      
class Payment(BaseObject):
    '''
    The Payment object
    '''
    object_name = 'payment'
    TYPE_MAPPINGS = {'client_id' : 'int', 'invoice_id' : 'int',
        'amount' : 'float', 'date' : 'datetime'}

    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        for att in ('payment_id', 'client_id', 'invoice_id', 'date',
        'amount', 'type', 'notes'):
            setattr(self, att, None)


#-----------------------------------------------#
# Recurring
#-----------------------------------------------#      
class Recurring(BaseObject):
    '''
    The Recurring object
    '''

    object_name = 'recurring'
    TYPE_MAPPINGS = {'recurring_id' : 'int', 'client_id' : 'int',
        'po_number' : 'int', 'discount' : 'float', 'amount' : 'float',
        'occurrences' : 'int', 'date' : 'datetime'}

    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        for att in ('recurring_id', 'client_id', 'date', 'po_number',
      'terms', 'first_name', 'last_name', 'organization', 'p_street1', 'p_street2', 'p_city','p_state', 'p_country', 'p_code', 'amount', 'lines', 'discount', 'status', 'notes', 'occurrences', 'frequency', 'stopped', 'send_email', 'send_snail_mail'):
            setattr(self, att, None)
        self.lines = []

    
#-----------------------------------------------#
# Project
#-----------------------------------------------#      
class Project(BaseObject):
    '''
    The Project object
    '''
    object_name = 'project'
    TYPE_MAPPINGS = {'project_id' : 'int', 'client_id' : 'int',
        'rate' : 'float'}

    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        for att in ('project_id', 'client_id', 'name', 'bill_method','rate',
            'description', 'tasks'):
            setattr(self, att, None)
        self.tasks = []


#-----------------------------------------------#
# Task
#-----------------------------------------------#      
class Task(BaseObject):
    '''
    The Task object
    '''
    object_name = 'task'
    TYPE_MAPPINGS = {'task_id' : 'int', 'rate' : 'float', 'billable' : 'bool'}

    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        for att in ('task_id', 'name', 'billable', 'rate',
            'description'):
            setattr(self, att, None)


#-----------------------------------------------#
# TimeEntry
#-----------------------------------------------#      
class TimeEntry(BaseObject):
    '''
    The TimeEntry object
    '''
    object_name = 'time_entry'

    TYPE_MAPPINGS = {'time_entry_id' : 'int', 'project_id' : 'int', 'task_id' : 'int', 'hours' : 'float', 'date' : 'datetime'}

    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        for att in ('time_entry_id', 'project_id', 'task_id', 'hours',
            'notes', 'date'):
            setattr(self, att, None)

        
#-----------------------------------------------#
# Estimate
#-----------------------------------------------#      
class Estimate(BaseObject):
    '''
    The Estimate object
    '''
    object_name = 'estimate'
    TYPE_MAPPINGS = {'estimate_id' : 'int', 'client_id' : 'int',
        'po_number' : 'int', 'discount' : 'float', 'amount' : 'float',
        'date' : 'datetime'}

    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        for att in ('estimate_id', 'client_id', 'status', 'date', 'po_number',
      'terms', 'first_name', 'last_name', 'organization', 'p_street1', 'p_street2', 'p_city','p_state', 'p_country', 'p_code', 'lines', 'discount', 'amount', 'notes'):
            setattr(self, att, None)
        self.lines = []


#-----------------------------------------------#
# Expense
#-----------------------------------------------#      
class Expense(BaseObject):
    '''
    The Expense object
    '''
    object_name = 'expense'
    TYPE_MAPPINGS = {'expense_id' : 'int', 'staff_id' : 'int',
     'client_id' : 'int', 'category_id' : 'int', 'project_id' : 'int',
        'amount' : 'float', 'date' : 'datetime'}

    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        for att in ('expense_id', 'staff_id', 'category_id', 'client_id', 'project_id', 'date', 'amount', 'notes', 'status'):
            setattr(self, att, None)


#-----------------------------------------------#
# Category
#-----------------------------------------------#      
class Category(BaseObject):
    '''
    The Category object
    '''

    object_name = 'category'
    TYPE_MAPPINGS = {'category_id' : 'int', 'tax1' : 'float',
        'tax2' : 'float'}

    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        for att in ('category_id', 'name', 'tax1', 'tax2'):
            setattr(self, att, None)

#-----------------------------------------------#
# Staff
#-----------------------------------------------#      
class Staff(BaseObject):
    '''
    The Staff object
    '''
    object_name = 'staff'
    TYPE_MAPPINGS = {'staff_id' : 'int', 'rate' : 'float',
        'last_login' : 'datetime',
        'signup_date' : 'datetime'}

    def __init__(self):
        '''
        The constructor is where we initially create the
        attributes for this class
        '''
        for att in ('staff_id', 'username', 'first_name', 'last_name',
        'email', 'business_phone', 'mobile_phone', 'rate', 'last_login',
        'number_of_logins', 'signup_date', 
        'street1', 'street2', 'city', 'state', 'country', 'code'):
            setattr(self, att, None)

    @classmethod
    def list(cls, options = {}, get_all=False):
        '''  
        Return a list of this object
        '''
        return super(Staff, cls).list(options, element_name='member', get_all=get_all)

