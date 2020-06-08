
from dls_pmaclib.dls_pmacremote import PmacEthernetInterface
# from dls_pmaclib.pmacgather import PmacGather
from dls_pmaclib.dls_pmcpreprocessor import ClsPmacParser
import re
#from epmcLib import vxx_rx
from collections import OrderedDict

import getpass
import datetime
import os
from pathlib import Path
import difflib
from argparse import ArgumentParser
from hashlib import md5, sha1
from time import sleep

DEBUGGING = True

output_basename = 't_{}_CS{}-{}.{}.PMA'

resevered_words = r'[\>,\<,\!,\(,\),=,+,\-,*,/,\n]'
src_shorthand_replace_list = [
                ('ADDRESS', 'ADR'), ('ENDIF', 'ENDI'), ('ENDWHILE', 'ENDW'), ('GOTO', 'GOT')
                ,('GOSUB', 'GOS'), ('RAPID', 'RPD'), ('RETURN', 'RET '), ('DWELL', 'DWE')
                ,('CMD ', 'CMD'), ('END IF', 'ENDI'), ('&COMMAND','CMD'), ('LINEAR', 'LIN')
                ,('ENABLE','ENA'), ('DISABLE', 'DIS'), ('COMMAND','CMD')
                ,('WHILE', 'WHILE'), ('AND', 'AND'), ('OR', 'OR')
                #, (r'\)AND',r')\nAND'),(r'\)OR',r')\nOR'), (r'\)ENDW',r')\nENDW'), (r'(?<=\d)WHILE',r'\nWHILE')
                ]

cs_modules =[
    'INVERSE'
    , 'FORWARD'
    ]

EMPTY_MODULE = {'code': '', 'checksum': 0, 'verified': False, 'open_cmd': '', 'close_cmd': ''}
errRegExp = re.compile(r'ERR\d{3}')

def strip_rgx(text, rgx_to_strip=" +", exclude_quote='"'):
    lst = text.split(exclude_quote)
    for i, item in enumerate(lst):
        if not i % 2:
            lst[i] = re.sub(rgx_to_strip, "", item)
    return '"'.join(lst)

def strip_in_brackets(_src, brackets='()', to_strip=' \n\t\r'):
    """removes all ws within brackets"""

    # TODO make this hack code pythonic
    p_count = 0
    _src_out = ''
    for char in _src:
        if char==brackets[0]:
            p_count += 1
        elif char==brackets[1]:
            p_count -= 1
        elif (char in to_strip) and (p_count != 0):
            char = ''
        _src_out += char
    return _src_out

def hack_src_to_buffer_syntax(src, resevered_words=[], shorthand_list=[]):

    # TODO replace all spaces EXCEPT spaces within double quotes: pmac code ignores and won't save space
    #_src = _src.replace(' ','')
    src = strip_rgx(src, rgx_to_strip=" +")

    src = re.sub(r'clear\s', '', src, flags=re.IGNORECASE)
    src = re.sub(r'[\t, ]{2,}', ' ', src, flags=re.IGNORECASE)
    src = re.sub(r'(?<=' + resevered_words + ')[\t, ]', '', src, flags=re.IGNORECASE)

    src = re.sub('->I, #', '->I #', src)

    # remove leading zeros
    src = re.sub(r'(?<![\d.])0+(?=\d+)', '', src, flags=re.IGNORECASE)

    for _find, _replace in shorthand_list:
        # replace long forms with shorthands
        src = re.sub(r'(?<=[^A-Z])'+_find + r'[\t, ]*', _replace, src, flags=re.IGNORECASE)
        # insert a line feed before reserved words, except if they are in paranthesis...
        # so first add line feed to all, and then STRIP ALL linefeeds from within paranthesis
        src = re.sub(r'(?<=[^A-Z,^\n])'+_replace, r'\n' + _replace, src, flags=re.IGNORECASE)

    src = strip_in_brackets(src, brackets='()', to_strip='\n')    

    # _src = re.sub(r'\n+', r'\n', _src, flags=re.IGNORECASE)
    src = re.sub(r'[\t, ](?=' + resevered_words + ')', '', src, flags=re.IGNORECASE)

    # swap hex numbers for decimals
    for hex_num in re.findall(r'\$[A-F,0-9]+',src):
        src = src.replace(hex_num, str(int(hex_num[1:], 16)) )

    # and add RET at the end of the buffer if there is not one already
    # if not src.endswith('RET\n'):
    #     src = src + 'RET\n'

    return src

def saveModule(device_id, module_id='', save_filename='', module_code='', user_time_in_header=False, \
    source_id=''):
    uploaded_module_md5 = md5(module_code.encode('utf-8')).hexdigest()
    file_header = \
        ';;\n' \
        ';; device: {0}\n' \
        ';; module: {2}\n' \
        ';; checksum: md5({1})\n'\
        ';; source: {3}\n' \
        .format(device_id, uploaded_module_md5, module_id, source_id)

    if user_time_in_header:
        file_header = file_header + ';; at {0:%Y-%m-%d %H:%M:%S} by {1}\n'.format(datetime.datetime.now(),getpass.getuser())

    file_header = file_header + ';;\n'

    outFile = open(save_filename, 'w')
    outFile.write(file_header + module_code)
    outFile.close()
    
    return uploaded_module_md5

def decodeModuleName(module_full_name):
    
    _CS = re.findall(r'(?<=&).(?=_)', module_full_name)[0]
    # last one isa the pmac module name, because _trailing is already excluded
    module_first_name = module_full_name.split('_')[-1]

    return _CS, module_first_name   

def uploadModule(pmac, module_full_name, wait_secs=0.15, lines_each_read=100, error_code='ERR003'):

    _CS, module_first_name = decodeModuleName(module_full_name)

    line_no = -1
    this_line_no = 0
    uploaded_module_code = ''
    _code_lines = ''
    status = True
    up_code_list = []
    added_lines = set()
    while status and not _code_lines.endswith(error_code): 
        
        # TODO document this: tpmac sometimes sends back the same code line with a different (by 1) line number.
        # I assume at this point that this is related to the starting line, so, try to prevent requesting overlapping
        # ranges
        line_no = max(this_line_no, line_no + 1)
        sleep(wait_secs)
        _command_str = 'LIST {},{},{}'.format(module_first_name, line_no, lines_each_read)
        
        if (int(_CS) > 0):
            _command_str = '&{}'.format(_CS) + _command_str

        _code_lines, status = pmac.sendCommand(_command_str)

        if not status:
            upload_error = _code_lines
            break

        _code_lines = _code_lines[:-1]
        _code_lines = re.sub(r'\r', '\n', _code_lines, flags=re.IGNORECASE)
        # and remove the RET at the end of the buffer
        if _code_lines.endswith('RET\n'):
             _code_lines = _code_lines[:-4]

        if _code_lines.endswith(error_code):
            upload_error = error_code
            break

        if len(_code_lines) > 0:
            for _code_line in _code_lines.splitlines():
                #check if the line starts with a line number
                for s in _code_line.split(':'):
                    if s.isdecimal():
                        this_line_no = int(s)
                    else:
                        if this_line_no not in added_lines and len(s)>0:
                            up_code_list.append((this_line_no,s))
                            added_lines.add(this_line_no)

                        else:
                            # duplicated line: increase steps
                            pass
        
        else:
            this_line_no = line_no + 1
            print('unexpected ')
                
    if len(up_code_list) > 0:
        uploaded_module_code = "\n".join(list(zip(*up_code_list))[1]) + "\n"
    else:
        uploaded_module_code = f'{_command_str} returned empty' 
        print(uploaded_module_code, end='...')
    
    # catch errors
    if not status:
        print('Comms Error', end='...')

    elif uploaded_module_code[-40:-1].endswith(r'WARNING: response truncated.'):
        print('Buffer is truncated, received {} bytes'.format(len(uploaded_module_code)), end='...')

    return uploaded_module_code

def breakCodeInModules(code_source=''):
    module_full_name = None
    _cs_number = 0 # not selected
    code_order = 0
    module_global = '_tailing'
    EMPTY_MODULE = {'code': '', 'md5': '', 'verified': False, 'open_cmd': '', 'close_cmd': ''}
    downloaded_code_unsorted = {module_global: EMPTY_MODULE.copy()}

    modules_dict = OrderedDict(sorted(downloaded_code_unsorted.items()))

    for code_line in pmc_parser.output:  # type: str
        if len(code_line)<1:
            continue


        code_line = code_line.upper()

        # find instances of &cc in the command line:
        CS_list = re.findall(r'(?<=&)\d', code_line)

        if len(CS_list) > 0:
            _CS=CS_list[-1]
            _cs_number = int(_CS)
            if args.verbose > 3:
                print(p_line_ + 'switched to CS no {}'.format(_cs_number))
        
        # if len(CS_list) > 1:
        #     # TODO deal with  multiple modules OPENED in a single line
        #     print('ERROR: not supported: multiple CS numbers in a single line!', code_line)
        #     exit(1)            

        module_types = re.findall(r'(?<=OPEN)\s+[A-Z]+', code_line)

        # code_line has and OPEN statements: OPENNING --------------------
        if len(module_types) > 0:
        
            if module_full_name is not None:
                print(p_line_ + 'ERROR trying to open {} before {} is closed'.format(code_line[5:], module_full_name))
                exit(1)

            if len(module_types) > 1 :
                # TODO deal with  multiple modules OPENED in a single line
                print(f'ERROR: not supported: multiple modules OPENED in a single line! {code_line}')
                exit(1)                    

            module_type = module_types[0].strip() 

            # module is not CS defendent
            if module_type not in cs_modules :
                # need a number to specify the module
                module_sps = re.findall('(?<='+module_type+')\s*\d+', code_line)
                if len(module_sps)==1 :
                    module_sp = module_sps[0].strip()
                    open_cmd = f'OPEN {module_type} {module_sp} CLEAR\n'
                    close_cmd = f'CLOSE\n'
                else:
                    print('ERROR: unspecified module name:', code_line)
                    exit(1) 
            # module is CS dependent                       
            else:
                module_sp = ''
                open_cmd = f'&{_CS}A\n OPEN {module_type} CLEAR\n'
                close_cmd = f'CLOSE\n'  
            
            module_first_name = module_type + module_sp
            
            # TODO move this and ensure the buffers is closed:
            # if args.download:
            #     pmac1.sendCommand(close_cmd)

            if module_first_name in cs_modules:
                module_full_name = '{}_&{}_{}'.format(str(code_order), str(_cs_number), module_first_name)
            else:
                module_full_name = '{}_&{}_{}'.format(str(code_order), str(0), module_first_name)

            if args.verbose > 3:
                print(p_line_ + 'opening {}'.format(module_full_name))

            # reset module and tailings code 
            source_module_code = ''
            modules_dict[module_full_name] = EMPTY_MODULE.copy()
            module_global = module_full_name + '_tailing'
            modules_dict[module_global] = EMPTY_MODULE.copy()
            code_order += 1

        # code_line has and CLOSE statements: CLOSING --------------------
        elif code_line.startswith('CLOSE'):

            # TODO : distinguish CLOSE ALL and CLOSE &cc

            if args.verbose > 3:
                print(p_line_ + 'closing {}'.format(module_full_name))
            # update module code
            if module_full_name:

                # modify the module code to PMA format to match uploaded code
                source_module_code = hack_src_to_buffer_syntax(source_module_code, \
                    resevered_words=resevered_words, shorthand_list=src_shorthand_replace_list)

                _CS = re.findall(r'(?<=&).(?=_)', module_full_name)[0]
                source_module_filename = os.path.join(output_dir_path, \
                    output_basename.format(pmac_ip_address.replace('.','-'), _CS, module_first_name, 'src'))
                
                if args.verbose > 3:
                    print(p_line_ + 'saving source code to file {} ...'.format(source_module_filename), end='\n')

                source_module_md5 = saveModule(device_id=pmac_ip_address, \
                    module_id=module_full_name.split('_',1)[1], \
                    save_filename=source_module_filename, \
                    module_code=source_module_code,
                    source_id=src_full_path, user_time_in_header=True)

                modules_dict[module_full_name]['code'] = source_module_code
                modules_dict[module_full_name]['md5'] = source_module_md5
                modules_dict[module_full_name]['open_cmd'] = open_cmd 
                modules_dict[module_full_name]['close_cmd'] = close_cmd 

            module_full_name = None

        # code_line has no OPEN/CLOSE statements: body of moddule --------------------
        else:
            # there is a Named module
            if module_full_name:
                source_module_code += code_line + '\n'
            else:
                # non-module settings all go to
                modules_dict[module_global]['code'] += code_line + '\n'
                pass

    return modules_dict

def downloadParsedCode(pmac=None, code_source=''):

    for code_line in pmc_parser.output:  # type: str
        if len(code_line)<1:
            continue
        code_line = code_line.upper()
        (retStr, status) = pmac.sendCommand(code_line)
        if status:
            pass
        else:
            if args.verbose > -1:
                print(retStr, end='\t')
                print('error in communication with pmac')
            break
    
    return

def downloadCodeLines(pmac=None, code_lines=[]):
    
    for code_line in code_lines.splitlines():
        retStr, wasSuccessful = pmac.sendCommand(code_line, shouldWait=True)
        if not wasSuccessful or errRegExp.findall(retStr):
            return False, f'{code_line} ---> {retStr}'   
        
    return True, ''  

def downloadModule(pmac=None, module_record=EMPTY_MODULE):

    # send open comnmands
    wasSuccessful, return_message = downloadCodeLines(pmac, module_record['open_cmd'])

    if wasSuccessful:
        wasSuccessful, return_message = downloadCodeLines(pmac, module_record['code'])

    # send close comnmands
    closedSuccessfully, close_msg  = downloadCodeLines(pmac, module_record['close_cmd'])

    return wasSuccessful, return_message, closedSuccessfully, close_msg 


parser = ArgumentParser(description='Set positions of DynAp motors on the trajectory.')
parser.add_argument('-i', '--pmac_ip', type=str, required=not DEBUGGING, help='pmac ip address')
parser.add_argument('-v', '--verbose', type=int, default=2, help='bluecat verbocity level range 0 to 4')
parser.add_argument('-s', '--src_file', type=str, required=not DEBUGGING, help='source file name')

parser.add_argument('-d', '--download', action='store_true', help='download', default=False)

args = parser.parse_args()

if DEBUGGING:
    args.pmac_ip = '10.23.199.230'
    # args.pmac_ip = '10.23.207.9'
    args.download = True
    args.src_file = [
        '/beamline/perforce/tec/mc/pmacUtil/trunk/pmc/PLC2_homing.pmc'
        , '/beamline/perforce/tec/mc/pmacUtil/trunk/pmc/PLC5_diagnostics.pmc'
        , '/beamline/perforce/tec/mc/pmacUtil/trunk/pmc/BaseConfigNoAxes.pmc'
        , '/beamline/perforce/opa/int/ctrls/WORKSHOP01/Settings/app/WORKSHOP01_CS5_34YX.pmc'
        , '/beamline/perforce/opa/int/ctrls/WORKSHOP01/Settings/app/WORKSHOP01_CS.pmc'
        , '/beamline/perforce/opa/int/ctrls/WORKSHOP01/Settings/app/RaScan_CS_4_X-Y.pmc'
        , '/beamline/perforce/opa/xfm/ctrls/SR05ID01MCS01/Settings/Master.pmc'
        , '/beamline/perforce/opa/xfm/ctrls/SR05ID01MCS01/Settings/RaScan_Master.pmc'

    ][-1]
    args.verbose = 2

pmac_ip_address = args.pmac_ip
src_full_path = args.src_file

src_path, src_filename = os.path.split(os.path.abspath(src_full_path))
src_path += os.sep
output_dir_path = src_path + 'pmacio'

# pmc_test_path = src_path
# pmc_test_file = src_filename

p_line_ = '     '
Path(output_dir_path).mkdir(parents=True, exist_ok=True)

pmc_source_parsed_file = os.path.join(output_dir_path, 'source.parsed.pmc')
pmac_cs = '?'
pmac_module = 'NONE'

if args.verbose > 0:
    print(p_line_ + 'reading from \n {} \n parsing and saving to \n {} ...'.format(src_full_path, pmc_source_parsed_file), end='\n')
pmc_parser = ClsPmacParser()

if pmc_parser.parse(src_full_path):
    pmc_parser.saveOutput(outputFile=pmc_source_parsed_file)
    if args.verbose > 3:
        print(pmc_parser.output)
else:
    exit(1)

if args.verbose > 0:
    print(p_line_ + f'Connecting to tpmac at {pmac_ip_address}...', end='\n')

pmac1 = PmacEthernetInterface(verbose=False, numAxes=8, timeout=3)

pmac1.setConnectionParams(pmac_ip_address, 1025)
pmac1.connect()

# pmac1.runTests()

# _pmac_orphan_code = ''
if args.verbose > 0:
    print(p_line_ + 'compiling parsed code...', end='\n')

modules_dict = breakCodeInModules(code_source=pmc_parser)
if args.download:
    # if args.verbose > 0:
    #     print(p_line_ + f'downloading output of the parser to {pmac1.getPmacModel()} at {pmac_ip_address}...', end='\n')
    # downloadPaesedCode(pmac=pmac1, code_source=pmc_parser)

    module_full_name = '1_&5_FORWARD'
    if args.verbose > 0:
        print(p_line_ + f'downloading {module_full_name} to {pmac1.getPmacModel()} at {pmac_ip_address}...', end='\n')
    
    downloadSuccess, returned_msg, closedSuccessfully, close_msg = downloadModule(pmac=pmac1, module_record=modules_dict[module_full_name])

if not downloadSuccess:
    print(f'Error: {returned_msg}')

if not closedSuccessfully:
    print(f'Failed to close: {close_msg}')

# pmac1.getIVars(100, [31, 32, 33])
# pmac1.sendSeries(['ver', 'list plc3'])

if args.verbose > 0:
    print(p_line_ + f'uploading listed modules from {pmac1.getPmacModel()} at {pmac_ip_address}...')

for module_full_name in modules_dict:
    if module_full_name.endswith('_tailing'):
        modules_dict[module_full_name]['verified'] = None

    else:
        # upload module code


        if args.verbose > 0:
            print(p_line_ + 'uploading ' + module_full_name, end='...')

        # if this is a PLC or Porgram, and the return of the characters may exceed 1400 bytes, 
        # then list it line by line using this format: LIST {module},{line_no}

 
        uploaded_module_code = uploadModule(pmac=pmac1, module_full_name=module_full_name)

        _CS, module_first_name = decodeModuleName(module_full_name)
        uploaded_module_filename = os.path.join(output_dir_path, \
            output_basename.format(pmac_ip_address.replace('.','-'),_CS, module_first_name, 'upl'))
        
        if args.verbose > 3:
            print(p_line_ + '\n saving uploaded code to file {} ...'.format(uploaded_module_filename), end='\n')

        uploaded_module_md5 = saveModule(device_id=pmac_ip_address, \
            module_id=module_full_name.split('_',1)[1], \
            save_filename=uploaded_module_filename, \
            module_code=uploaded_module_code, \
            source_id='uploaded', user_time_in_header=True)

        if args.verbose > 4:
            print(p_line_ + '\n verifying module code from tpmac...', end='')

        if modules_dict[module_full_name]['md5'] == uploaded_module_md5:
            # checksums match, hooray!
            modules_dict[module_full_name]['verified'] = True
            if args.verbose > 0:
                print('verified.')
        else:
            modules_dict[module_full_name]['verified'] = False
            _src = modules_dict[module_full_name]['code']
            _upl = uploaded_module_code

            if args.verbose > -1:
                print('!! not verified !!')
            if args.verbose > 3:
                diff_list = [li for li in difflib.ndiff(_src, _upl) if li[0] != ' ']
                print(diff_list)
            if args.verbose > 2:
                print(p_line_ + 'source: \n{} \n\n uploaded: \n{} \n\n'.format(_src, _upl))

exit(0)
# g = PmacGather(pmac1)
# axes = [3, 2]
# g.gatherConfig(axes, 400, 10)
# g.gatherTrigger()
# data = g.collectData()
# g.parseData(data)
# for c in g.channels:
#     print(c.scaledData)

