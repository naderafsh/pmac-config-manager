
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

DEBUGGING = True

output_basename = 't_{}_CS{}-{}.{}.PMA'

resevered_words = r'[\>,\<,\!,\(,\),=,+,\-,*,/,\n]'
src_shorthand_replace_list = [
                ('ADDRESS', 'ADR'), ('ENDIF', 'ENDI'), ('ENDWHILE', 'ENDW'), ('GOTO', 'GOT')
                , ('GOSUB', 'GOS'), ('RAPID', 'RPD'), ('RETURN', 'RET ')
                , ('CMD ', 'CMD'), ('END IF', 'ENDI'), ('&COMMAND','CMD')
                ,('ENABLE','ENA'), ('DISABLE', 'DIS'), ('COMMAND','CMD')
                ,('WHILE', 'WHILE'), ('AND', 'AND'), ('OR', 'OR')
                #, (r'\)AND',r')\nAND'),(r'\)OR',r')\nOR'), (r'\)ENDW',r')\nENDW'), (r'(?<=\d)WHILE',r'\nWHILE')
                ]

cs_modules =[
    'INVERSE'
    , 'FORWARD'
    ]

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

    return src


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

    ][-2]
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


if args.verbose > 0:
    print(p_line_ + 'downloading & ' if args.download else '' + f'comparing output of the parser to {pmac1.getPmacModel()} at {pmac_ip_address}...', end='\n')
module_full_name = None
_cs_number = 0 # not selected
code_order = 0
module_global = '_tailing'
EMPTY_MODULE = {'code': '', 'checksum': 0, 'verified': False}
downloaded_code_unsorted = {module_global: EMPTY_MODULE.copy()}

modules_dict = OrderedDict(sorted(downloaded_code_unsorted.items()))

# _pmac_orphan_code = ''
for code_line in pmc_parser.output:  # type: str
    if len(code_line) > 0:
        code_line = code_line.upper()

        # find instances of &cc in the command line:
        CS_list = re.findall(r'(?<=&)\d', code_line)

        if len(CS_list)==1:
            _CS=CS_list[0]
            _cs_number = int(_CS)
            if args.verbose > 1:
                print(p_line_ + 'switched to CS no {}'.format(_cs_number))
        elif len(CS_list) > 1:
            # TODO deal with  multiple modules OPENED in a single line
            print('ERROR: not supported: multiple CS numbers in a single line!', code_line)
            exit(1)            

        if code_line.startswith('OPEN'):

            if module_full_name is None:
                # identify the new module
                
                module_types = re.findall('(?<=OPEN)\s+[A-Z]+', code_line)
                if len(module_types) == 1 :
                    module_type = module_types[0].strip() 
                else:
                    # TODO deal with  multiple modules OPENED in a single line
                    print('ERROR: not supported: multiple modules OPENED in a single line!',module_type)
                    exit(1)                    
 
                if module_type not in cs_modules :
                    # need a number to specify the module
                    module_sps = re.findall('(?<='+module_type+')\s*\d+', code_line)
                    if len(module_sps)==1 :
                        module_sp = module_sps[0].strip()
                        close_cmd = 'CLOSE'
                    else:
                        # TODO deal with  multiple modules OPENED in a single line
                        print('ERROR: wrong numbers after module name',module_sps)
                        exit(1)                         
                else:
                    module_sp = ''
                    close_cmd = 'CLOSE &' + _CS
                
                module_first_name = module_type + module_sp
                
                # and close
                if args.download:
                    pmac1.sendCommand(close_cmd)

                if module_first_name in cs_modules:
                    module_full_name = '{}_&{}_{}'.format(str(code_order), str(_cs_number), module_first_name)
                else:
                    module_full_name = '{}_&{}_{}'.format(str(code_order), str(0), module_first_name)
                code_order += 1

                #reset module code holder
                source_module_code = ''
                # add module
                modules_dict[module_full_name] = EMPTY_MODULE.copy()

                # add non-module code section, named after module
                module_global = module_full_name + '_tailing'
                modules_dict[module_global] = EMPTY_MODULE.copy()

                if args.verbose > 1:
                    print(p_line_ + 'opening {}'.format(module_full_name))
            else:
                if args.verbose > -1:
                    print(p_line_ + 'ERROR trying to open {} before {} is closed'.format(code_line[5:], module_full_name))

        elif code_line.startswith('CLOSE'):

            # TODO : distinguish CLOSE ALL and CLOSE &cc

            if args.verbose > 1:
                print(p_line_ + 'closing {}'.format(module_full_name))
            # update module code
            if module_full_name:

                # modify the module code to PMA format to match uploaded code
                source_module_code = hack_src_to_buffer_syntax(source_module_code, \
                    resevered_words=resevered_words, shorthand_list=src_shorthand_replace_list)

                source_module_md5 = md5(source_module_code.encode('utf-8')).hexdigest()
                modules_dict[module_full_name]['code'] = source_module_code
                modules_dict[module_full_name]['md5'] = source_module_md5

                _CS = re.findall(r'(?<=&).(?=_)', module_full_name)[0]
                source_module_filename = os.path.join(output_dir_path, \
                    output_basename.format(pmac_ip_address.replace('.','-'), _CS, module_first_name, 'src'))
                
                if args.verbose > 0:
                    print(p_line_ + 'saving source code to file {} ...'.format(source_module_filename), end='\n')

                outFile = open(source_module_filename, 'w')
                file_header = ';;\n;; This code is sourced from:\n;; {0} \n;; ' \
                      '{2:%Y-%m-%d %H:%M:%S} user {1}\n;; checksum: md5({3}) \n;;\n\n'\
                              .format(src_full_path, getpass.getuser(), datetime.datetime.now(), source_module_md5)

                outFile.write(file_header + source_module_code)
                outFile.close()

            module_full_name = None

        else:
            if module_full_name:
                source_module_code += code_line + '\n'
            else:
                # non-module settings all go to
                modules_dict[module_global]['code'] += code_line + '\n'
                pass

        # TODO save global code here

        if args.download:
            (retStr, status) = pmac1.sendCommand(code_line)
        else:
            (retStr, status) = '', True

        if status:
            pass
        else:
            if args.verbose > -1:
                print(retStr, end='\t')
                print('error in communication with pmac')
            break



# pmac1.getIVars(100, [31, 32, 33])
# pmac1.sendSeries(['ver', 'list plc3'])

if args.verbose > 0:
    print(p_line_ + 'uploading listed modules from pmac...')


for module_full_name in modules_dict:
    if module_full_name.endswith('_tailing'):
        modules_dict[module_full_name]['verified'] = None

    else:
        # upload module code
        _CS = re.findall(r'(?<=&).(?=_)', module_full_name)[0]
        # last one isa the pmac module name, because _trailing is already excluded
        module_first_name = module_full_name.split('_')[-1]

        if args.verbose > 0:
            print(p_line_ + 'uploading CS {} module {} ... '.format(_CS, module_first_name), end='')

        # if this is a PLC or Porgram, and the return of the characters may exceed 1400 bytes, 
        # then list it line by line using this format: LIST {module},{line_no}
        
        lines_each_read = 200
        line_no = -1
        this_line_no = 0
        uploaded_module_code = ''
        _code_lines = ''
        status = True
        up_code_list = []
        added_lines = set()
        while status and not _code_lines.endswith('ERR003'): 
            
            # TODO document this: tpmac sometimes sends back the same code line with a different (by 1) kline number.
            # I assume at this point that this is related to the starting line, so, try to prevent requesting overlapping
            # ranges
            line_no = max(this_line_no, line_no + 1)
            _command_str = 'LIST {},{},{}'.format(module_first_name, line_no, lines_each_read)
            
            if (int(_CS) > 0):
                _command_str = '&{} '.format(_CS) + _command_str

            _code_lines, status = pmac1.sendCommand(_command_str)

            if not status:
                upload_error = _code_lines
                break

            _code_lines = _code_lines[:-1]
            _code_lines = re.sub(r'\r', '\n', _code_lines, flags=re.IGNORECASE)

            if _code_lines.endswith('ERR003'):
                upload_error = 'ERR003'
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
                    
            # now fine the lines and put them together until it ids finished.
            #_upl = repr(_code_line)[1:-1].replace(r'\r', '\n')
            # remove line numbers
            #_upl = re.sub(r'\r\d*:', '\n', _upl, flags=re.IGNORECASE)
            # and the first one
            #_upl = re.sub(r'\d*:', '', _upl, flags=re.IGNORECASE)

        if len(up_code_list) > 0:
            uploaded_module_code = "\n".join(list(zip(*up_code_list))[1]) + "\n"
        else:
            print('Buffer is empty')
            continue

        
        # catch errors
        if not status:
            print(uploaded_module_code)
            continue
        # elif len(uploaded_module_code) > 2310:
        #     print('Reciving buffer is probably truncated, received {} bytes'.format(len(uploaded_module_code)))
        #     continue
        elif uploaded_module_code[-40:-1].endswith(r'WARNING: response truncated.'):
            print('Buffer is truncated, received {} bytes'.format(len(uploaded_module_code)))
            continue            
        
        #uploaded_module_lines = repr(uploaded_module_code)[1:-1].replace(r'\r', '\n')
        uploaded_module_code = re.sub(r'RET\s.*', '', uploaded_module_code, flags=re.IGNORECASE)
        uploaded_module_md5 = md5(uploaded_module_code.encode('utf-8')).hexdigest()
        uploaded_module_filename = os.path.join(output_dir_path, \
            output_basename.format(pmac_ip_address.replace('.','-'),_CS, module_first_name, 'upl'))

        if args.verbose > 3:
            print(p_line_ + '\n saving uploaded code to file {} ...'.format(uploaded_module_filename), end='\n')

        outFile = open(uploaded_module_filename, 'w')
        file_header = ';;\n;; This code is sourced from:\n;; {0} \n;; ' \
                    '{2:%Y-%m-%d %H:%M:%S} user {1}\n;; checksum: md5({3}) \n;;\n\n'\
                    .format(pmac_ip_address, getpass.getuser(), datetime.datetime.now(), uploaded_module_md5)
        
        outFile.write(file_header + uploaded_module_code)
        outFile.close()

        if args.verbose > 4:
            print(p_line_ + '\n verifying module code from tpmac...', end='')

        if modules_dict[module_full_name]['md5'] == uploaded_module_md5:
            # checksums match, hooray!
            modules_dict[module_full_name]['verified'] = True
            if args.verbose > 0:
                print('success: verified.')
        else:
            modules_dict[module_full_name]['verified'] = False
            _src = modules_dict[module_full_name]['code']
            _upl = uploaded_module_code

            if args.verbose > -1:
                print('!! error: not verified !!')
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

