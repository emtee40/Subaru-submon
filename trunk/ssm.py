import time
import re
import serial
import random

class Port():
    re_reserved = r'.^$*+?{[]\|()}'
    
    def __init__(self, device='/dev/ttyUSB0'):
        self.port = serial.Serial(port=device, baudrate=1953, \
                                  parity='E', timeout=0)

    def read(self, length=None):
        if length is None:
            length = self.port.inWaiting()
        return self.port.read(length)

    def write(self, data):
        return self.port.write(data)

    def stop(self):
        return self.port.write('\x12\x00\x00\x00')

    def close(self):
        return self.port.close()

    def flush(self):
        return self.port.flush()

    def ask_ecu(self, adh, adl, length):
        self.write('%c' * 4 % (0x78, adh, adl, chr(length - 1)))

    def get_ecu_data(self, address, length, single=True):       
        adh = chr(address / 256)
        adl = chr(address % 256)

        self.flush()
        
        self.ask_ecu(adh, adl, length)
        
        returned_data = self.read_ecu_data(adh, adl, length)

        if single:
            self.stop()

        return returned_data

    def read_ecu_data(self, adh, adl, length):
        if adh in self.re_reserved:
            adh = '\\' + adh
        if adl in self.re_reserved:
            self[key]=value 
            adl = '\\' + adl

        pattern = '{ah}{al}.{num}{ah}{al}'.format(ah=adh, al=adl, \
                                                  num=('{' + repr(length) + '}'))
        data = self.read()
        start_time = time.time()
        
        matches = re.findall(pattern, data, re.DOTALL)            
        while len(matches) == 0 and (time.time() - start_time) < 5:
            data += self.read()
            matches = re.findall(pattern, data, re.DOTALL)

        if len(matches) is 0:
            return None
        else:
            return matches[-1][2:-2]

class Parameter():
    def __init__(self, desc, format, units, address, equation, parent_list=None):
        # Set the description
        self.desc = desc
        
        # Set up the format
        self.format_decimals = format
        self.format = '{{0:.{decs}f}}'.format(decs=self.format_decimals)
        # Set the units and units_str
        self.units = units.replace(u'%deg%', u'\u00b0')
        self.units_str = self.units.replace(u'\u00b0', 'deg')
        
        # Set the address and address_str
        self.address = address
        if self.address is None:
            self.address_str = 'None'
        else:
            try:
                self.address_str = '{0:04x}'.format(self.address)
            except ValueError:
                self.address_str = '$ValueError$'
        
        # Set the equation
        var = []
        for match in re.finditer('(?P<var>%[a-zA-Z ]+%)', equation):
            var.append(match.group('var'))
        for sub in var:
            equation = equation.replace(sub, 'self.parent_list[\'' + sub[1:-1] + '\'].get_value()')
        self.equation = lambda self,b: eval(equation)
        
        # Set the parent list
        self.parent_list = parent_list
        
        # See if the equation has some problems
        try:
            self.equation(self, 0)
        except KeyError:
            print 'Error: Invalid key passed to {0}\'s equation.'.format(self.desc)
            print '       Calc set to return original value.'
            self.equation = lambda self,b: b
        except AttributeError as ae:
            if 'has no attribute \'parent_list\'' in ae.__str__():
                print 'Error: {0} was passed a parameter but not a parent list.'.format(self.desc)
            else:
                print 'Error: {0}\'s equation contains an unknown parameter.'.format(self.desc)
            print '        Calc set to return original value.'
            self.equation = lambda self,b: b
        
        # Initialize? textvar
        self.textvar = None
        # Set a default to a random value
        self.value = random.random()

    def calc(self, value):
        try:
            return self.equation(self, value)
        except:
            return None

    def __repr__(self):
        return 'Name: {0.desc:30s} Format: {0.format:10s} Units: {0.units_str:10s} Address: {0.address_str:4s}'.format(self)
        
    def set_textvar(self, textvar):
        self.textvar = textvar
        
    def set_value(self, b):
        self.value = self.calc(b)
        if self.textvar is not None:
            if self.value is None:
                self.textvar.set('Error')
            else:
                self.textvar.set(self.format.format(self.value))            
    
    def get_value(self):
        return self.value

    def get_fvalue(self):
        if self.value is None:
            return repr(None)
        else:
            return self.format.format(self.value)  

class ParameterList():
    def __init__(self):
        self.dict = dict()
        self.set = []
    
    def __repr__(self):
        buf = ''
        for tag in self.set:
            buf += '\n' + 'tag: {0:15s} '.format(tag) + repr(self.dict[tag])
        return buf[1:]
        
    def __iter__(self):
        for name in self.set:
            yield self.dict[name]
    
    def add(self, key, value):
        self.set.append(key)
        self.dict[key] = value
        
    def get(self, key):
        return self.dict[key]
        
    def __getitem__(self, key):
        return self.get(key)
        
    def get_lowest_address(self):
        low_address = 0xffff
        for param in self.dict.values():
            if type(param.address) is int and param.address < low_address:
                low_address = param.address
        return low_address
    
    def get_highest_address(self):
        high_address = 0x0000
        for param in self.dict.values():
            if type(param.address) is int and param.address > high_address:
                high_address = param.address
        return high_address

def load_param_file(f, offset=0, whence=0):
    """Loads SSM paramters from file f.  Parameters should be tab separated.  \
This function returns an ssm.ParameterList containing the parameters read from \
the file."""
    f.seek(offset, whence)
    
    raw_params = []
    param_list = ParameterList()
    
    for line in f.readlines():
        # Check for comment
        if line[0] == '#':
            continue
        raw_params.append(line[:-1].split(':'))
#        print raw_params[-1]

    # Start the line counter at 1 for user readability.
    i = 1;
    for param in raw_params:
       # Make sure there's a complete parameter to read.
        if len(param) < 6:
            print 'Error: Invalid parameter: Line {0}.'.format(i)
            continue

        # To enhance readability in file, allow for multiple tabs between
        # parameter fields.  Remove empty spaces.
        #blank_indicies = {};
        #for i in range(len(param)-1, 0, -1):
        #    if param[i] == "":
        #       blank_indicies.append(i)

        #for index in blank_indicies:
        #    del param[i]

        # Make sure we still have 6 fields...
        #if len(param) < 6:
        #    print 'Error: Invalid parameter: Line {0}.'.format(i)
        #    continue

        # Parse our address.
        if param[4] == 'None':
            address = None
        else:
            try:
                address = int(param[4], 16)
            except ValueError:
                address = '$ValueError$'

        # Add the parameter and increase our line counter.
        param_list.add(param[0], Parameter(param[1], int(param[2], 10), param[3], address, param[5].replace('B','b'), param_list))
        i += 1

    return param_list

def load_list_file(f, master_list):
    # Start at beginning of file.
    f.seek(0)
    
    # Create the dictionary of ParamterLists.
    lists = dict()
    
    # Marker for whether we're working on a list.
    have_list = False
    
    # Keep track of line numbers
    lines = 0
    for line in f.readlines():
        # Increase line number.
        lines += 1
        
        # Skip blank lines and lines consisting of a newline character.
        if len(line) <= 1:
            continue
        
        # Ignore comments
        if line[0] == '#':
            continue
            
        # If we have not-comments, strip off the newline.
        line = line[:-1]
        
        # If we don't already have a list, try to get one.  Lists MUST begin with "+".
        if have_list is False:
            if line[0] == '+':
                list_name = line[1:]
                current_list = ParameterList()
                have_list = True
            # If this isn't the start of a new list, ignore it.
            else:
                continue
        else:
            # If we got the ending line for a list, create the list and store it.
            if line[0] == '-':
                lists[list_name] = current_list
                have_list = False
            # Otherwise, we need to add a parameter to the current list.
            else:
                try:
                    current_list.add(line, master_list[line])
                except AttributeError:
                    print 'Error: Parameter {0} not found in the master list: Line {1}.'.format(master_list, lines)
    
    return lists
        
    
        
