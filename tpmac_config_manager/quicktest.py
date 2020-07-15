from dls_pmaclib.dls_pmacremote import PmacEthernetInterface
from dls_pmaclib.dls_pmcpreprocessor import ClsPmacParser
from collections import OrderedDict
import os
from pathlib import Path
from argparse import ArgumentParser
from time import sleep
from tpmac_config_manager import pmac_modulars as pm

"""
A proof of concept for a base-overlay model to manage configuration of pmac controllers.

baseConfig is a default and common configuration that enables basic functions (mainly via pmacUtil)
and also provides some tools for managing overlay configurations.
This is mainly downloaded and maintained via IDE.

Idea is to put all overlay configs into pmac modules, e.g. PLCs, PROGs, and kinematics. Axis
overlay configs are also done via dedicated configurator PLC's.

PLC1 calls the configratur PLC's at startup.

A checksum can be applied to verifyu the integrity of the configurator PLC's to add to reliability.

"""


DEBUGGING = True

parser = ArgumentParser(description="download and analyse pmac code, by modules.")
parser.add_argument(
    "-i", "--pmac_ip", type=str, required=not DEBUGGING, help="pmac ip address"
)
parser.add_argument(
    "-v", "--verbose", type=int, default=2, help="bluecat verbocity level range 0 to 4"
)
parser.add_argument(
    "-s", "--src_file", type=str, required=not DEBUGGING, help="source file name"
)

parser.add_argument(
    "-o", "--out_dir", type=str, required=not DEBUGGING, help="output directory"
)

parser.add_argument(
    "-d", "--download", action="store_true", help="download", default=False
)

args = parser.parse_args()


if DEBUGGING:
    args.out_dir = str(Path.home()) + "/tcm_dump"  # use source dir

    args.pmac_ip = "10.23.199.230"
    # args.pmac_ip = '10.23.207.9'
    args.download = True  # For this test file, False means just verify
    # fix this before turning it on
    args.download_tailing = False
    args.download_blank = True
    args.skip_failed_modules = True
    args.src_file = [
        "/beamline/perforce/tec/mc/pmacUtil/trunk/pmc/PLC2_homing.pmc",
        "/beamline/perforce/tec/mc/pmacUtil/trunk/pmc/PLC6_amplifier_initialize.pmc",
        "/beamline/perforce/tec/mc/pmacUtil/trunk/pmc/PLC9_auto_cure.pmc",
        "/beamline/perforce/tec/mc/pmacUtil/trunk/pmc/PLC5_diagnostics.pmc",
        "/beamline/perforce/tec/mc/pmacUtil/trunk/pmc/BaseConfigNoAxes.pmc",
        "/beamline/perforce/opa/int/ctrls/WORKSHOP01/Settings/app/WORKSHOP01_CS5_34YX.pmc",
        "/beamline/perforce/opa/int/ctrls/WORKSHOP01/Settings/app/WORKSHOP01_CS.pmc",
        "/beamline/perforce/opa/int/ctrls/WORKSHOP01/Settings/app/RaScan_CS_4_X-Y.pmc",
        "tests/tpmac-code-sample/Master.pmc",
        "tests/tpmac-code-sample/RaScan_Master.pmc",
    ][-2]
    args.verbose = 2


pm.args = args

pmac_ip_address = args.pmac_ip
src_full_path = args.src_file

src_path, src_filename = os.path.split(os.path.abspath(src_full_path))

# os.path.join(src_path, outDumpDir)

output_dir_base = args.out_dir

# pmc_test_path = src_path
# pmc_test_file = src_filename

Path(output_dir_base).mkdir(parents=True, exist_ok=True)

pmc_source_parsed_file = os.path.join(output_dir_base, "source.parsed.pmc")
pmac_cs = "?"
pmac_module = "NONE"

print(
    "reading from \n {} \n parsing and saving to \n {} ...".format(
        src_full_path, pmc_source_parsed_file
    ),
    end="\n",
) if (args.verbose > 2) else ()
pmc_parser = ClsPmacParser()

if pmc_parser.parse(src_full_path):
    pmc_parser.saveOutput(outputFile=pmc_source_parsed_file)
    if args.verbose > 3:
        print(pmc_parser.output)
else:
    exit(1)

print("\nModularising parsed code", end="...\n\n") if args.verbose > 1 else ()

modules_dict = {}
for module_full_name, module_record in pm.tpmacExtractModules(
    code_source=pmc_parser.output, include_tailing=True
):

    if module_full_name in modules_dict:
        print(f"\nWARNING: module {module_full_name} re-defined", end="...")

    modules_dict.update({module_full_name: module_record})
    # save sources in PMA files
    source_module_filename = pm.tpmacModuleFullPath(
        suffix="src",
        pmac_id=pmac_ip_address,
        module_full_name=module_full_name,
        output_dir_path=output_dir_base,
    )

    print(f"saving source code to file {source_module_filename} ...", end="\n") if (
        args.verbose > 3
    ) else ()

    saved_md5 = pm.savePmacModule(
        device_id=pmac_ip_address,
        module_id=module_full_name.split("_", 1)[1],
        save_filename=source_module_filename,
        module_code=module_record.body,
        source_id=src_full_path,
        user_time_in_header=True,
    )

modules_sorted = OrderedDict(sorted(modules_dict.items()))

if args.verbose > 1:
    print(
        f"\n{len(modules_sorted)} instances of module code found.",
        end="------------ \n\n",
    )

# # Now, see if you can further breakdown the globals:
# _old_rx = tpmac.vxx_rx("[iI]", 1, mode="find")
# _matches = re.findall(_old_rx, modules_sorted["XX_&0_GLOBAL_tailing"].body)
# print("  {} instances of {} found".format(len(_matches), _old_rx))

# _matches = re.findall(
#     tpmac.vmn_stats(tpmac.Ivar_mn_rx, "1", "2", "3"),
#     modules_sorted["XX_&0_GLOBAL_tailing"].body,
# )
# print("  {} instances of {} found".format(len(_matches), _old_rx))


if args.verbose > 1:
    print(f"\nConnecting to tpmac at {pmac_ip_address}", end="...\n\n")
pmac1 = PmacEthernetInterface(verbose=False, numAxes=8, timeout=3)
pmac1.setConnectionParams(pmac_ip_address, 1025)
pmac1.connect()
sleep(1)

if args.download:
    print("\nDownloading to tpmac...", end="...\n\n")
    for module_full_name, module_record in modules_sorted.items():
        if module_full_name.endswith(pm.freeCodeSuffix) and not args.download_tailing:
            print(f"-- skiped   {module_full_name} (tailings)", end="\n") if (
                args.verbose > 1
            ) else ()
            continue

        if not module_record.body and not args.download_blank:
            print(f"-- skiped   {module_full_name} (blank)", end="\n") if (
                args.verbose > 1
            ) else ()
            continue

        print(f"downloading {module_full_name}", end="...") if (
            args.verbose > 1
        ) else ()

        (returned_msg, downloadSuccess, close_msg, closeSuccess,) = pm.downloadModule(
            pmac=pmac1, code_module=module_record
        )

        if not downloadSuccess:
            print(f"error: {returned_msg}", end="...")
        else:
            print(f"{returned_msg}", end="...")

        if not closeSuccess:
            print(f"failed to close: {close_msg}", end="\n")
        else:
            print("closed.", end="\n")

# pmac1.getIVars(100, [31, 32, 33])
# pmac1.sendSeries(['ver', 'list plc3'])

print(
    f"\n\nuploading listed modules from {pmac1.getPmacModel()} at {pmac_ip_address}",
    end="...\n",
) if (args.verbose > 1) else ()

for module_full_name in modules_sorted:
    if module_full_name.endswith(pm.freeCodeSuffix):
        modules_sorted[module_full_name].verified = False
    elif args.skip_failed_modules and modules_sorted[module_full_name].download_failed:
        print(f"-- skiped {module_full_name} (failed downloads)", end="\n") if (
            args.verbose > 1
        ) else ()
    else:
        # upload module code

        print(f"uploading {module_full_name}", end="...") if (args.verbose > 1) else ()

        # if this is a PLC or Porgram, and the return of the characters may exceed 1400 bytes,
        # then list it line by line using this format: LIST {module},{line_no}

        uploaded_module_code = pm.uploadModule(
            pmac=pmac1, module_full_name=module_full_name, wait_secs=0.025
        )

        uploaded_module_filename = pm.tpmacModuleFullPath(
            suffix="upl",
            pmac_id=pmac_ip_address,
            module_full_name=module_full_name,
            output_dir_path=output_dir_base,
        )

        print(
            "\n saving uploaded code to file {}".format(uploaded_module_filename),
            end="\n",
        ) if (args.verbose > 3) else ()

        uploaded_module_md5 = pm.savePmacModule(
            device_id=pmac_ip_address,
            module_id=module_full_name.split("_", 1)[1],
            save_filename=uploaded_module_filename,
            module_code=uploaded_module_code,
            source_id="uploaded",
            user_time_in_header=True,
        )

        if modules_sorted[module_full_name].checksum == uploaded_module_md5:
            # checksums match, hooray!
            modules_sorted[module_full_name].verified = True
            if args.verbose > 0:
                if len(uploaded_module_code) < 1:
                    print("is cleared", end="...")
                print("verified.")
        else:
            modules_sorted[module_full_name].verified = False
            _src = modules_sorted[module_full_name].body
            _upl = uploaded_module_code

            print("**** ERROR: not verified ****") if (args.verbose > -1) else ()
            # if args.verbose > 3:
            #     diff_list = [li for li in difflib.ndiff(_src, _upl) if li[0] != ' ']
            #     print(diff_list)
            if args.verbose > 4:
                print("source: \n{} \n\n uploaded: \n{} \n\n".format(_src, _upl))


print(f"\noutput dumped in {output_dir_base}")
print("program terminated.")

exit(0)
