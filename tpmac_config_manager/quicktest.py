
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
#import difflib
from argparse import ArgumentParser
#from hashlib import md5, sha1
from time import sleep

import pmac_modulars as pm

DEBUGGING = True

parser = ArgumentParser(description='download and analyse pmac code, by modules.')
parser.add_argument('-i', '--pmac_ip', type=str, required=not DEBUGGING, help='pmac ip address')
parser.add_argument('-v', '--verbose', type=int, default=2, help='bluecat verbocity level range 0 to 4')
parser.add_argument('-s', '--src_file', type=str, required=not DEBUGGING, help='source file name')

parser.add_argument('-d', '--download', action='store_true', help='download', default=False)

args = parser.parse_args()

outDumpDir = "pmacio"


# output_basename = "t_{}_CS{}-{}.{}.PMA"

if DEBUGGING:
    
    args.pmac_ip = '10.23.199.230'
    # args.pmac_ip = '10.23.207.9'
    args.download = True
    # fix this before turning it on
    args.download_tailing = False 
    args.download_blank = True
    args.skipFailed = False
    args.src_file = [
        '/beamline/perforce/tec/mc/pmacUtil/trunk/pmc/PLC2_homing.pmc'
        , '/beamline/perforce/tec/mc/pmacUtil/trunk/pmc/PLC6_amplifier_initialize.pmc'
        , '/beamline/perforce/tec/mc/pmacUtil/trunk/pmc/PLC9_auto_cure.pmc'
        , '/beamline/perforce/tec/mc/pmacUtil/trunk/pmc/PLC5_diagnostics.pmc'
        , '/beamline/perforce/tec/mc/pmacUtil/trunk/pmc/BaseConfigNoAxes.pmc'
        , '/beamline/perforce/opa/int/ctrls/WORKSHOP01/Settings/app/WORKSHOP01_CS5_34YX.pmc'
        , '/beamline/perforce/opa/int/ctrls/WORKSHOP01/Settings/app/WORKSHOP01_CS.pmc'
        , '/beamline/perforce/opa/int/ctrls/WORKSHOP01/Settings/app/RaScan_CS_4_X-Y.pmc'
        , '/beamline/perforce/opa/xfm/ctrls/SR05ID01MCS01/Settings/Master.pmc'
        , '/beamline/perforce/opa/xfm/ctrls/SR05ID01MCS01/Settings/RaScan_Master.pmc'

    ][-2]
    args.verbose = 2


pm.args = args

pmac_ip_address = args.pmac_ip
src_full_path = args.src_file

src_path, src_filename = os.path.split(os.path.abspath(src_full_path))
src_path += os.sep
output_dir_path = src_path + outDumpDir

# pmc_test_path = src_path
# pmc_test_file = src_filename

p_line_ = '     '
Path(output_dir_path).mkdir(parents=True, exist_ok=True)

pmc_source_parsed_file = os.path.join(output_dir_path, 'source.parsed.pmc')
pmac_cs = '?'
pmac_module = 'NONE'

if args.verbose > 2:
    print(p_line_ + 'reading from \n {} \n parsing and saving to \n {} ...'.format(src_full_path, pmc_source_parsed_file), end='\n')
pmc_parser = ClsPmacParser()

if pmc_parser.parse(src_full_path):
    pmc_parser.saveOutput(outputFile=pmc_source_parsed_file)
    if args.verbose > 3:
        print(pmc_parser.output)
else:
    exit(1)

if args.verbose > 1:
    print(p_line_ + '\nModularising parsed code', end='...\n\n')

modules_dict = {}
for module_full_name, module_record in pm.pmacCodeModules(code_source=pmc_parser.output, include_tailing=True):
    
    if module_full_name in modules_dict:
        print(f'\nWARNING: module {module_full_name} being overwritten', end='...')

    modules_dict.update({module_full_name: module_record})
    # save sources in PMA files
    source_module_filename = pm.tpmacModuleFileName(suffix="src", pmac_id=pmac_ip_address, module_full_name=module_full_name, output_dir_path=output_dir_path)

    if args.verbose > 3:
        print(f"{p_line_}saving source code to file {source_module_filename} ...", end="\n")

    modules_dict[module_full_name]["md5"] = pm.savePmacModule(
        device_id=pmac_ip_address,
        module_id=module_full_name.split("_", 1)[1],
        save_filename=source_module_filename,
        module_code=module_record['code'],
        source_id=src_full_path,
        user_time_in_header=True,
    )

modules_sorted = OrderedDict(sorted(modules_dict.items()))

if args.verbose > 1:
    print(p_line_ + f'\n{len(modules_sorted)} instances of module code found.', end='------------ \n\n')

if args.verbose > 1:
    print(p_line_ + f'\nConnecting to tpmac at {pmac_ip_address}', end='...\n\n')
pmac1 = PmacEthernetInterface(verbose=False, numAxes=8, timeout=3)
pmac1.setConnectionParams(pmac_ip_address, 1025)
pmac1.connect()
sleep(1)

if args.download:
    print(p_line_ + f'\nDownloading to tpmac...', end='...\n\n')
    for module_full_name, module_record in modules_sorted.items():
        if module_full_name.endswith(pm.freeCodeSuffix) and not args.download_tailing:
            if args.verbose > 1:
                print(p_line_ + f'-- skiped   {module_full_name} (tailings)', end='\n')
            continue

        if not module_record["code"] and not args.download_blank:
            if args.verbose > 1:
                print(p_line_ + f'-- skiped   {module_full_name} (blank)', end='\n')
            continue            

        if args.verbose > 1:
            print(p_line_ + f'downloading {module_full_name}', end='...')
        
        downloadSuccess, returned_msg, closedSuccessfully, close_msg = pm.downloadModule(pmac=pmac1, module_record=module_record)

        if not downloadSuccess:
            print(f'error: {returned_msg}', end='...')
        else:
            print(f'{returned_msg} lines', end='...')

        if not closedSuccessfully:
            print(f'failed to close: {close_msg}', end='\n')
        else:
            print('closed.', end='\n')

# pmac1.getIVars(100, [31, 32, 33])
# pmac1.sendSeries(['ver', 'list plc3'])

if args.verbose > 1:
    print(p_line_ + f'\n\nuploading listed modules from {pmac1.getPmacModel()} at {pmac_ip_address}', end='...\n')

for module_full_name in modules_sorted:
    if module_full_name.endswith(pm.freeCodeSuffix):
        modules_sorted[module_full_name]['verified'] = None
    elif args.skipFailed and modules_sorted[module_full_name]['downloadFailed']:
        if args.verbose > 1:
            print(p_line_ + f'-- skiped {module_full_name} (failed downloads)', end='\n')        
    else:
        # upload module code

        if args.verbose > 1:
            print(p_line_ + f'uploading {module_full_name}', end='...')

        # if this is a PLC or Porgram, and the return of the characters may exceed 1400 bytes, 
        # then list it line by line using this format: LIST {module},{line_no}

        uploaded_module_code = pm.uploadModule(pmac=pmac1, module_full_name=module_full_name, wait_secs=0.025)

        uploaded_module_filename = pm.tpmacModuleFileName(suffix='upl', 
            pmac_id=pmac_ip_address, 
            module_full_name=module_full_name, 
            output_dir_path=output_dir_path
        )

        if args.verbose > 3:
            print(p_line_ + '\n saving uploaded code to file {}'.format(uploaded_module_filename), end='\n')

        uploaded_module_md5 = pm.savePmacModule(device_id=pmac_ip_address,
            module_id=module_full_name.split('_',1)[1], 
            save_filename=uploaded_module_filename, 
            module_code=uploaded_module_code, 
            source_id='uploaded', user_time_in_header=True
        )

        if modules_sorted[module_full_name]['md5'] == uploaded_module_md5:
            # checksums match, hooray!
            modules_sorted[module_full_name]['verified'] = True
            if args.verbose > 0:
                if len(uploaded_module_code) < 1:
                    print('is blank', end='...')
                print('verified.')
        else:
            modules_sorted[module_full_name]['verified'] = False
            _src = modules_sorted[module_full_name]['code']
            _upl = uploaded_module_code

            if args.verbose > -1:
                print('**** not verified ****')
            # if args.verbose > 3:
            #     diff_list = [li for li in difflib.ndiff(_src, _upl) if li[0] != ' ']
            #     print(diff_list)
            if args.verbose > 4:
                print(p_line_ + 'source: \n{} \n\n uploaded: \n{} \n\n'.format(_src, _upl))

exit(0)

