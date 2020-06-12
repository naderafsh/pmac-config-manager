from dls_pmaclib.dls_pmacremote import PmacEthernetInterface

# from dls_pmaclib.pmacgather import PmacGather
from dls_pmaclib.dls_pmcpreprocessor import ClsPmacParser
import re

# from epmcLib import vxx_rx
from collections import OrderedDict

from getpass import getuser
from datetime import datetime
import os
from pathlib import Path

# import difflib
# from argparse import ArgumentParser
from hashlib import md5, sha1
from time import sleep


freeCodeSuffix = "_tailing"


resevered_words = r"[\>,\<,\!,\(,\),=,+,\-,*,/,\n]"
src_shorthand_replace_list = [
    ("ADDRESS", "ADR"),
    ("AND", "AND"),
    ("CMD ", "CMD"),
    ("COMMAND", "CMD"),
    ("&COMMAND", "CMD"),
    ("DISABLE", "DIS"),
    ("DWELL", "DWE"),
    ("ENABLE", "ENA"),
    ("ENDIF", "ENDI"),
    ("END IF", "ENDI"),
    ("ENDWHILE", "ENDW"),
    ("FRAX\(A,B,C,U,V,W,X,Y,Z\)", "FRAX"),
    ("GOSUB", "GOS"),
    ("GOTO", "GOT"),
    ("LINEAR", "LIN"),
    ("OR", "OR"),
    ("RAPID", "RPD"),
    ("RETURN", "RET "),
    ("WHILE", "WHILE"),
]

cs_module_types = ["INVERSE", "FORWARD"]

EMPTY_MODULE = {
    "code": "",
    "checksum": 0,
    "verified": False,
    "open_cmd": "",
    "close_cmd": "",
    "downloadFailed": False,
    "code_order": 0,
}
errRegExp = re.compile(r"ERR\d{3}")


def stripRgx(text, rgx_to_strip=" +", exclude_quote='"'):
    lst = text.split(exclude_quote)
    for i, item in enumerate(lst):
        if not i % 2:
            lst[i] = re.sub(rgx_to_strip, "", item)
    return '"'.join(lst)


def stripInBrackets(_src, brackets="()", to_strip=" \n\t\r"):
    """removes all ws within brackets"""

    # TODO make this hack code pythonic
    p_count = 0
    _src_out = ""
    for char in _src:
        if char == brackets[0]:
            p_count += 1
        elif char == brackets[1]:
            p_count -= 1
        elif (char in to_strip) and (p_count != 0):
            char = ""
        _src_out += char
    return _src_out


def pmcToBufferSyntax(src, resevered_words=[], shorthand_list=[]):

    # TODO replace all spaces EXCEPT spaces within double quotes: pmac code ignores and won't save space
    # _src = _src.replace(' ','')
    # add a dumy line to ensure regex searches find keywords. remoe it at the end.
    src = "\t" + src
    src = stripRgx(src, rgx_to_strip=" +")

    src = re.sub(r"clear\s", "", src, flags=re.IGNORECASE)
    src = re.sub(r"[\t, ]{2,}", " ", src, flags=re.IGNORECASE)
    src = re.sub(r"(?<=" + resevered_words + ")[\t, ]", "", src, flags=re.IGNORECASE)

    src = re.sub("->I, #", "->I #", src)

    # remove leading zeros
    src = re.sub(r"(?<![\d.])0+(?=\d+)", "", src, flags=re.IGNORECASE)

    for _find, _replace in shorthand_list:
        # replace long forms with shorthands
        src = re.sub(
            r"(?<=[^A-Z])" + _find + r"[\t, ]*", _replace, src, flags=re.IGNORECASE
        )
        # insert a line feed before reserved words, except if they are in paranthesis...
        # so first add line feed to all, and then STRIP ALL linefeeds from within paranthesis
        src = re.sub(
            r"(?<=[^A-Z,^\n])" + _replace, r"\n" + _replace, src, flags=re.IGNORECASE
        )

    src = stripInBrackets(src, brackets="()", to_strip="\n")

    # _src = re.sub(r'\n+', r'\n', _src, flags=re.IGNORECASE)
    src = re.sub(r"[\t, ](?=" + resevered_words + ")", "", src, flags=re.IGNORECASE)

    # swap hex numbers for decimals
    for hex_num in re.findall(r"\$[A-F,0-9]+", src):
        src = src.replace(hex_num, str(int(hex_num[1:], 16)))

    # and add RET at the end of the buffer if there is not one already
    # if not src.endswith('RET\n'):
    #     src = src + 'RET\n'

    return src[1:]


def savePmacModule(
    device_id,
    module_id="",
    save_filename="",
    module_code="",
    user_time_in_header=False,
    source_id="",
):

    uploaded_module_md5 = md5(module_code.encode("utf-8")).hexdigest()
    file_header = (
        ";;\n"
        ";; device: {0}\n"
        ";; module: {2}\n"
        ";; checksum: md5({1})\n"
        ";; source: {3}\n".format(device_id, uploaded_module_md5, module_id, source_id)
    )

    if user_time_in_header:
        file_header = file_header + ";; at {0:%Y-%m-%d %H:%M:%S} by {1}\n".format(
            datetime.now(), getuser()
        )

    file_header = file_header + ";;\n"

    outFile = open(save_filename, "w")
    outFile.write(file_header + module_code)
    outFile.close()

    return uploaded_module_md5


def decodeModuleName(module_full_name):

    _CS = re.findall(r"(?<=&).(?=_)", module_full_name)[0]
    # last one isa the pmac module name, because _trailing is already excluded
    module_first_name = module_full_name.split("_")[-1]

    return _CS, module_first_name


def tpmacModuleFileName(pmac_id="", module_full_name="", suffix="", output_dir_path=""):

    _CS, module_first_name = decodeModuleName(module_full_name)
    return os.path.join(
        output_dir_path,
        f"t_{pmac_id.replace('.','-')}_CS{_CS}-{module_first_name}.{suffix}.PMA".format(),
    )


def pmacCodeModules(code_source="", include_tailing=True):
    module_full_name = None
    _cs_number = 0  # not selected
    code_order = 0
    global_full_name = "XX_&0_GLB" + freeCodeSuffix
    current_global = EMPTY_MODULE.copy()
    for i, code_line in enumerate(code_source):
        if len(code_line) < 1:
            continue

        code_line = code_line.upper()

        # split code_line if it has mupltle instances of buffer or CS control keywords.
        # All these keywords sshould be at the start of the line:
        for _replace in ["OPEN", "CLOSE"]:
            code_line = re.sub(
                r"(?<=[^A-Z,^\n])" + _replace,
                r"\n" + _replace,
                code_line,
                flags=re.IGNORECASE,
            )

        splited_lines = code_line.splitlines()
        if len(splited_lines) > 1:
            for j, added_line in enumerate(splited_lines[1:]):
                code_source.insert(i + j + 1, added_line)  # insert after current line

        code_line = splited_lines[0]
        code_source[i] = code_line

        # find instances of &cc in the command line:
        CS_list = re.findall(r"(?<=&)\d", code_line)

        if len(CS_list) > 0:
            _CS = CS_list[-1]
            _cs_number = int(_CS)

        if len(CS_list) > 1:
            # TODO deal with  multiple modules OPENED in a single line
            print(
                "ERROR: not supported: multiple CS numbers in a single line!", code_line
            )
            exit(1)

        module_types_to_open = re.findall(r"(?<=OPEN)\s+[A-Z]+", code_line)
        module_types_to_close = re.findall(r"OPEN\s+[A-Z]+(?=.*CLOSE)", code_line)
        # code_line has and OPEN statements: OPENNING --------------------
        if len(module_types_to_open) > 0:

            if module_full_name is not None:
                print(
                    f"ERROR trying to open {code_line[5:]} before {module_full_name} is closed"
                )

                exit(1)

            if len(module_types_to_open) > 1:
                # TODO deal with  multiple modules OPENED in a single line
                print(
                    f"ERROR: not supported: multiple modules OPENED in a single line! {code_line}"
                )
                exit(1)

            module_type = module_types_to_open[0].strip()

            # module is not CS defendent
            if module_type not in cs_module_types:
                # need a number to specify the module
                module_sps = re.findall(r"(?<=" + module_type + r")\s*\d+", code_line)
                if len(module_sps) == 1:
                    module_sp = str(int(module_sps[0].strip())).zfill(2)
                    open_cmd = f"OPEN {module_type} {module_sp} CLEAR\n"
                    close_cmd = f"CLOSE\n"
                else:
                    print("ERROR: unspecified module name:", code_line)
                    exit(1)
            # module is CS dependent
            else:
                module_sp = ""
                open_cmd = f"&{_CS}A\n OPEN {module_type} CLEAR\n"
                close_cmd = f"CLOSE\n"

            module_first_name = module_type + module_sp

            # TODO move this and ensure the buffers is closed:
            # if args.download:
            #     pmac1.sendCommand(close_cmd)

            if module_first_name in cs_module_types:
                module_full_name = f"XX_&{str(_cs_number)}_{module_first_name}"
            else:
                module_full_name = f"XX_&{str(0)}_{module_first_name}"

            # reset module and tailings code
            source_module_code = ""
            current_module = EMPTY_MODULE.copy()
            # There is only one global, not a current global
            # global_full_name = module_full_name + freeCodeSuffix
            # current_global = EMPTY_MODULE.copy()
            code_order += 1

        # code_line has and CLOSE statements: CLOSING --------------------
        elif code_line.startswith("CLOSE"):

            # TODO : distinguish CLOSE ALL and CLOSE &cc
            # update module code
            if module_full_name:

                # modify the module code to PMA format to match uploaded code
                source_module_code = pmcToBufferSyntax(
                    source_module_code,
                    resevered_words=resevered_words,
                    shorthand_list=src_shorthand_replace_list,
                )

                current_module["code"] = source_module_code
                current_module["open_cmd"] = open_cmd
                current_module["close_cmd"] = close_cmd
                current_module["code_order"] = code_order

                yield module_full_name, current_module

            module_full_name = None

        # code_line has no OPEN/CLOSE statements: body of moddule --------------------
        else:
            # there is a Named module
            if module_full_name:
                source_module_code += code_line + "\n"
            else:
                # non-module settings all go to
                current_global["code"] += code_line + "\n"
                current_global["code_order"] = code_order

    # return _tailing module if needed
    if include_tailing and global_full_name:
        yield global_full_name, current_global

    return


def downloadParsedCode(pmac=None, code_source=""):

    for code_line in code_source:  # type: str
        if len(code_line) < 1:
            continue
        code_line = code_line.upper()
        (retStr, status) = pmac.sendCommand(code_line)
        if status:
            pass
        else:
            print(retStr, end="\t")
            print("error in communication with pmac")
            break

    return


def downloadCodeLines(pmac=None, module_code=[], section_size=20):

    code_lines = module_code.splitlines(True)
    code_sections = []
    this_code_section = ""
    this_section_lines = 0
    for code_line in code_lines:
        if (this_section_lines < section_size) and (
            len(this_code_section) + len(code_line)
        ) < 255:
            this_code_section = this_code_section + code_line.replace("\n", "\r")
            this_section_lines += 1
        else:
            code_sections.append(this_code_section)
            this_code_section = code_line.replace("\n", "\r")
            this_section_lines = 1

    code_sections.append(this_code_section)

    # code_sections =[''.join(code_lines[i:i+section_size]) for i in range(0, len(code_lines), section_size)]

    for this_code_section in code_sections:
        # while code_section.endswith("\n"):
        #   code_section = code_section[:-1]
        retStr, wasSuccessful = pmac.sendCommand(this_code_section, shouldWait=True)
        if not wasSuccessful or errRegExp.findall(retStr) or len(retStr) < 1:
            return False, f"{this_code_section.splitlines()[-1]} ---> {retStr}"

    return True, str(len(code_lines)).zfill(4)


def downloadCodeLines_not_in_use(pmac=None, module_code=[], section_size=15):

    for r in pmac.sendSeries(module_code.splitlines()):
        wasSuccessful, lineNumber, code_line, retStr = (
            r if len(r) == 4 else False,
            0,
            "",
            "",
        )
        if not wasSuccessful or errRegExp.findall(retStr):
            return False, f" {lineNumber}:{code_line} ---> {retStr}"

    return True, ""


def downloadModule(pmac=None, module_record=EMPTY_MODULE):

    # send open comnmands
    wasSuccessful, return_message = downloadCodeLines(pmac, module_record["open_cmd"])

    if wasSuccessful:
        wasSuccessful, return_message = downloadCodeLines(pmac, module_record["code"])

    # send close comnmands
    closedSuccessfully, close_msg = downloadCodeLines(pmac, module_record["close_cmd"])

    module_record["downloadFailed"] = not (wasSuccessful and closedSuccessfully)

    return wasSuccessful, return_message.strip("\r"), closedSuccessfully, close_msg


def uploadModule(
    pmac, module_full_name, wait_secs=0.15, bunch_size=100, end_code="ERR003"
):

    _CS, module_first_name = decodeModuleName(module_full_name)

    line_no = -1
    this_line_no = 0
    uploaded_module_code = ""
    _code_lines = ""
    status = True
    up_code_list = []
    added_lines = set()
    upload_error = None
    while status and not _code_lines.endswith(end_code):

        # TODO document this: tpmac sometimes sends back the same code line with a different (by 1) line number.
        # I assume at this point that this is related to the starting line, so, try to prevent requesting overlapping
        # ranges
        line_no = max(this_line_no, line_no + 1)
        sleep(wait_secs)
        _command_str = "LIST {},{},{}".format(module_first_name, line_no, bunch_size)

        if int(_CS) > 0:
            _command_str = "&{}".format(_CS) + _command_str

        _code_lines, status = pmac.sendCommand(_command_str)

        if not status:
            upload_error = _code_lines
            break

        _code_lines = _code_lines[:-1]
        _code_lines = re.sub(r"\r", "\n", _code_lines, flags=re.IGNORECASE)
        # and remove the RET at the end of the buffer
        if _code_lines.endswith("RET\n"):
            _code_lines = _code_lines[:-4]

        if _code_lines.endswith(end_code):
            upload_error = None
            break

        if len(_code_lines) > 0:
            for _code_line in _code_lines.splitlines():
                # check if the line starts with a line number
                for s in _code_line.split(":"):
                    if s.isdecimal():
                        this_line_no = int(s)
                    else:
                        if this_line_no not in added_lines and len(s) > 0:
                            up_code_list.append((this_line_no, s))
                            added_lines.add(this_line_no)

                        else:
                            # duplicated line: increase steps
                            pass

        else:
            this_line_no = line_no + 1
            print("empty return, terminating", end="...")
            status = False

    if len(up_code_list) > 0:
        uploaded_module_code = "\n".join(list(zip(*up_code_list))[1]) + "\n"
    else:
        uploaded_module_code = ""

    # catch errors
    if not status:
        print("Comms Error", end="...")

    if upload_error:
        print(f"Error {upload_error}", end="...")

    elif uploaded_module_code[-40:-1].endswith(r"WARNING: response truncated."):
        print(
            "Buffer is truncated, received {} bytes".format(len(uploaded_module_code)),
            end="...",
        )

    return uploaded_module_code


if __name__ == "__main__":
    pass


"""
The source code is assumed to be 

All of the non-modular code will all be augmented in the original order, in one global code buffer.
Currently, I and P and Q variables are NOT cosidered modules (or locals) but they can easily be added
to the model.

The modular code is assumed to be unique per buffer, e.g. the later definition of PLC1 
will overwrite all the preceeding codes. This will generate a warning.



"""
