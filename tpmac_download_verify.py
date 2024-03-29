from re import A
from typing import IO
from dls_pmaclib.dls_pmacremote import PmacEthernetInterface
from dls_pmaclib.dls_pmcpreprocessor import ClsPmacParser
from collections import OrderedDict
import os
from pathlib import Path
from argparse import ArgumentParser
from time import sleep
from pmac_config_manager import pmac_modulars as pm
import yaml as ym
import time

"""
A proof of concept for a base-overlay model to manage configuration of pmac controllers.

baseConfig is a default and common configuration that enables basic functions (mainly via pmacUtil)
and also provides some tools for managing overlay configurations.
This is mainly download_attempt and maintained via IDE.

Idea is to put all overlay configs into pmac modules, e.g. PLCs, PROGs, and kinematics. Axis
overlay configs are also done via dedicated configurator PLC's.

PLC1 calls the configratur PLC's at startup.

A checksum can be applied to verifyu the integrity of the configurator PLC's to add to reliability.

"""


def yaml_dump():
    """construct a string only dict off modules_sorted
    as a report, then dumps it into a yaml file.
    """
    yaml_dump_file = os.path.join(output_dir_base, "config_check_log.yaml")

    if os.path.exists(yaml_dump_file):

        with open(yaml_dump_file, "r") as yamlfile:
            report_dict = ym.safe_load(yamlfile)  # Note the safe_load
    else:
        report_dict = {}

    if not isinstance(report_dict, dict):
        # wrong or empty yaml record
        report_dict = {}

    if pmac_ip_address in report_dict:
        verify_dict = report_dict[pmac_ip_address]
        if "modules" in verify_dict:
            module_dict = verify_dict["modules"]
        else:
            module_dict = {}
    else:
        verify_dict = {}
        module_dict = {}

    any_errors = False
    for module_full_name in modules_sorted:
        report_module = {}
        code_module = modules_sorted[module_full_name]
        assert isinstance(code_module, pm.codeModule)

        report_module["download_attempt"] = code_module.download_attempt
        report_module["download_msg"] = code_module.download_msg
        report_module["download_failed"] = code_module.download_failed
        report_module["checksum"] = code_module.checksum
        report_module["type"] = code_module.module_type
        report_module["verified"] = code_module.verified

        report_module["last_update"] = time.strftime("%y%m%d_%H%M", time.localtime())
        report_module["source"] = src_full_path

        report_module["saved"] = pmac_saved
        report_module["reset"] = pmac_reset

        any_errors = (
            any_errors or (not code_module.verified) or code_module.download_failed
        )

        # overwrite the module record
        module_dict[module_full_name] = report_module

    verify_dict["modules"] = module_dict
    verify_dict["last_update"] = time.strftime("%y%m%d_%H%M", time.localtime())
    if pmac_saved:
        verify_dict["last_saved"] = verify_dict["last_update"]
    if pmac_reset:
        verify_dict["last_reset"] = verify_dict["last_update"]

    verify_dict["last_errors"] = any_errors

    verify_dict["last_source"] = src_full_path

    source_dict = {os.path.basename(src_full_path): verify_dict}

    report_dict[pmac_ip_address] = verify_dict

    with open(yaml_dump_file, "w+") as yamlfile:
        ym.safe_dump(report_dict, yamlfile, default_flow_style=False)


def download(module_full_name, code_module, default_download_choice=""):

    reason_for_skip = ""

    if module_full_name.endswith("globals") and not args.download_globals:
        reason_for_skip = "globals"

    if not code_module.body and not args.download_blank:
        reason_for_skip = "blank"

    if download.skip_all:
        reason_for_skip = "user-all"

    if not reason_for_skip:
        userinp = (
            input(f"{module_full_name} ... [S]kip/skip[A]ll/download ")
            if not default_download_choice
            else default_download_choice
        )

        if userinp == "A":
            download.skip_all = True
            reason_for_skip = "user-all"
        elif userinp == "S":
            reason_for_skip = "user"

    if reason_for_skip:
        stager.stage(
            f"-- skipped  {module_full_name} ({reason_for_skip}) \n",
            this_verbose_level=2,
            laps_time=False,
        )
        code_module.download_msg = f"skipped - {reason_for_skip}"
        code_module.download_attempt = False
        return

    stager.stage(
        f"Downloading {module_full_name}", this_verbose_level=2, laps_time=False,
    )

    (returned_msg, downloadSuccess, close_msg, closeSuccess,) = pm.downloadModule(
        pmac=pmac1, code_module=code_module
    )

    if not downloadSuccess:
        print(f"error: {returned_msg}", end="...")
        code_module.download_msg = f"failed: - {returned_msg}"
        code_module.download_attempt = True
    else:
        print(f"{returned_msg}", end="...")
        code_module.download_msg = f"success: - {returned_msg}"
        code_module.download_attempt = True

    if not closeSuccess:
        print(f"failed to close: {close_msg}", end="\n")
    else:
        print("closed.", end="\n")


def parsing():

    if pmc_parser.parse(src_full_path):

        stager.stage(
            f"Saving to {pmc_source_parsed_file}", this_verbose_level=2, laps_time=False
        )

        pmc_parser.saveOutput(outputFile=pmc_source_parsed_file)
        # print(pmc_parser.output) if args.verbose > 3 else ()
    else:
        raise RuntimeError("parser returned error.")


def readYamlArgs(yaml_args_path):
    """read setup parameters and run arguments from yaml file

    """

    if os.path.exists(yaml_args_path):
        with open(yaml_args_path, "r") as yamlfile:
            run_args = ym.safe_load(yamlfile)  # Note the safe_load
    else:
        run_args = {}
        raise FileNotFoundError(f"{yaml_args_path}")

    if not isinstance(run_args, dict):
        # wrong or empty yaml record
        run_args = {}

    args.out_dir = run_args["out_dir"]
    args.pmac_ip = run_args["pmac_ip"]
    args.download = run_args["download"]
    args.download_globals = run_args["download_globals"]
    args.download_blank = run_args["download_blank"]
    args.skip_failed_modules = run_args["skip_failed_modules"]
    args.src_file = run_args["src_file"]
    args.verbose = run_args["verbose"]
    args.default_download_choice = run_args["default_download_choice"]


parser = ArgumentParser(description="download and analyse pmac code, by modules.")

parser.add_argument(
    "-y",
    "--yaml_args",
    type=str,
    default="_local/default_args.yaml",
    required=False,
    help="yaml args file name",
)

parser.add_argument("-i", "--pmac_ip", type=str, required=False, help="pmac ip address")
parser.add_argument(
    "-v", "--verbose", type=int, default=2, help="verbocity level range 0 to 4"
)
parser.add_argument(
    "-s", "--src_file", type=str, required=False, help="source file name"
)

parser.add_argument(
    "-o", "--out_dir", type=str, required=False, help="output directory"
)

parser.add_argument(
    "-d", "--download", action="store_true", help="download", default=False
)

args = parser.parse_args()

readYamlArgs(args.yaml_args)


pmac_ip_address = args.pmac_ip
src_full_path = args.src_file

src_path, src_filename = os.path.split(os.path.abspath(src_full_path))

output_dir_base = args.out_dir

Path(output_dir_base).mkdir(parents=True, exist_ok=True)

pmc_source_parsed_file = os.path.join(output_dir_base, "source.parsed.PMA")
pmac_cs = "?"
pmac_module = "NONE"

pmc_parser = ClsPmacParser()

stager = pm.stager(verbose_level=args.verbose, default_end=" > ")

stager.stage(f"Parsing {src_full_path}", this_verbose_level=1)
parsing()


stager.stage("Modularising parsed code", this_verbose_level=2)

modules_dict = {}
for module_full_name, code_module in pm.tpmacExtractModules(
    code_source=pmc_parser.output, include_globals=True
):

    if module_full_name in modules_dict:
        print(f"\nWARNING: module {module_full_name} re-defined", end="...")

    modules_dict.update({module_full_name: code_module})
    # save sources in PMA files
    source_module_filename = pm.tpmacModuleFullPath(
        suffix="src",
        pmac_id=pmac_ip_address,
        module_full_name=module_full_name,
        output_dir_path=output_dir_base,
    )

    stager.stage(
        f"Saving source code to file {source_module_filename}",
        this_verbose_level=4,
        laps_time=False,
    )

    saved_md5 = pm.savePmacModule(
        device_id=pmac_ip_address,
        module_id=module_full_name.split("_", 1)[1],
        save_filename=source_module_filename,
        code_module=code_module,
        source_id=src_full_path,
        user_time_in_header=True,
    )

modules_sorted = OrderedDict(sorted(modules_dict.items()))

stager.stage(
    f"\n{len(modules_sorted)} instances of module code found.------------ \n\n",
    this_verbose_level=2,
    laps_time=False,
)

stager.stage(f"Connecting to tpmac at {pmac_ip_address}", this_verbose_level=0)

pmac1 = PmacEthernetInterface(verbose=False, numAxes=8, timeout=3)
pmac1.setConnectionParams(pmac_ip_address, 1025)
pmac1.connect()

stager.stage("Waiting", this_verbose_level=4)

sleep(1)

# pmac1.getIVars(100, [31, 32, 33])
# pmac1.sendSeries(['ver', 'list plc3'])

userinp = input("[R]est / [S]ave or continue...")

if userinp == "R":
    print(f"resetting {pmac_ip_address} ...")
    pmac1.sendCommand("$$$", shouldWait=False)
    pmac_reset = True
    sleep(5)

if args.download:
    download.skip_all = False
    stager.stage("Downloading to tpmac...", this_verbose_level=0)
    for module_full_name, code_module in modules_sorted.items():
        download(
            module_full_name,
            code_module,
            default_download_choice=args.default_download_choice,
        )

stager.stage(
    f"Uploading listed modules from {pmac1.getPmacModel()} at {pmac_ip_address}\n",
    this_verbose_level=2,
)

for module_full_name in modules_sorted:
    if modules_sorted[module_full_name].module_type == "globals":
        # how to upload free code:
        modules_sorted[module_full_name].verified = False
        stager.stage(
            f"Uploading {module_full_name}", this_verbose_level=2, laps_time=False,
        )
        upl_code_module = pm.uploadGlobals(
            pmac=pmac1,
            #     module_full_name=module_full_name,
            wait_secs=0.025,
            global_module=modules_sorted[module_full_name],
        )

    elif args.skip_failed_modules and modules_sorted[module_full_name].download_failed:
        print(f"-- skiped {module_full_name} (failed downloads)", end="\n") if (
            args.verbose > 1
        ) else ()
        continue
    else:
        # upload module code

        stager.stage(
            f"Uploading {module_full_name}", this_verbose_level=2, laps_time=False,
        )

        # if this is a PLC or Porgram, and the return of the characters may exceed 1400 bytes,
        # then list it line by line using this format: LIST {module},{line_no}

        upl_code_module = pm.uploadModule(
            pmac=pmac1, module_full_name=module_full_name, wait_secs=0.025
        )

        # code_module.__init__(body=uploaded_module_code)

    uploaded_module_filename = pm.tpmacModuleFullPath(
        suffix="upl",
        pmac_id=pmac_ip_address,
        module_full_name=module_full_name,
        output_dir_path=output_dir_base,
    )

    stager.stage(
        f"Saving uploaded code to file {uploaded_module_filename}",
        this_verbose_level=4,
        laps_time=False,
    )

    uploaded_module_md5 = pm.savePmacModule(
        device_id=pmac_ip_address,
        module_id=module_full_name.split("_", 1)[1],
        save_filename=uploaded_module_filename,
        code_module=upl_code_module,
        source_id="uploaded",
        user_time_in_header=True,
    )

    # TODO: save a catalog in the dump directory

    # report dict structure:
    # module name
    #  .

    if modules_sorted[module_full_name].checksum == uploaded_module_md5:
        # checksums match, hooray!
        modules_sorted[module_full_name].verified = True
        if args.verbose > 0:
            if len(upl_code_module.body) < 1:
                print("blank", end="...")
            else:
                print("code found", end="...")
            print("verified.")
    else:
        modules_sorted[module_full_name].verified = False
        _src = modules_sorted[module_full_name].body
        _upl = upl_code_module.body

        print("**** code mistmatch ****") if (args.verbose > -1) else ()

        stager.stage(
            f"source: \n{_src} \n\n uploaded: \n{_upl} \n\n",
            this_verbose_level=5,
            laps_time=False,
        )

print(f"\noutput dumped in {output_dir_base}")

stager.stage("\nRecording report", this_verbose_level=0)

stager.stage("Done.", this_verbose_level=0)

print(f"\n\ntime lapses in seconds: {stager.time_laps}")


pmac_reset = False
pmac_saved = False
userinp = input("[R]est / [S]ave or continue...")

if userinp == "R":
    print(f"resetting {pmac_ip_address} ...")
    pmac1.sendCommand("$$$", shouldWait=False)
    pmac_reset = True
    sleep(5)
elif userinp == "S":
    print(f"saving {pmac_ip_address} ...")
    pmac1.sendCommand("sav", shouldWait=False)
    pmac_saved = True
    sleep(5)
elif userinp == "$$$***":
    print(f"erasing {pmac_ip_address} ...")
    pmac1.sendCommand(userinp, shouldWait=False)
    pmac_reset = True
    sleep(5)


yaml_dump()
