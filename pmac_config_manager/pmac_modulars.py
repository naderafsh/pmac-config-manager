import re

from getpass import getuser
from datetime import datetime
import os
from pathlib import Path

from hashlib import md5
from time import sleep, time


freeCodeSuffix = "_globals"

cs_module_types = ["INVERSE", "FORWARD"]

prog_module_types = ["PROG"]

errRegExp = re.compile(r"ERR\d{3}")


class codeModule:
    body = ...  # type: str
    checksum = ...  # type: str
    open_cmd = ...  # type: str
    close_cmd = ...  # type: str
    code_order = ...  # type: int
    download_failed = ...  # type: bool
    verified = ...  # type: bool
    module_type = ...  # type: str
    download_attempt = ...  # type: bool
    download_msg = ...  # type: str

    def __init__(
        self,
        open_line="",
        first_name="",
        cs_id=None,
        module_sp=None,
        open_cmd="",
        close_cmd="",
        code_order=None,
        body="",
    ):

        if open_line:
            self.setFromCodeLine(code_line=open_line, _CS=cs_id)
        elif first_name:
            self.setFromFirstName(first_name=first_name, cs_id=cs_id)

        if open_cmd:
            self.open_cmd = open_cmd

        if close_cmd:
            self.close_cmd = close_cmd

        if code_order:
            self.code_order = code_order

        self.verified = False
        self.download_failed = False
        self.download_attempt = False
        self.download_msg = ""

        self.setBody(body)

    def setFromFirstName(self, first_name="", cs_id="0"):

        if not first_name:
            return False

        if first_name in cs_module_types:
            self.first_name = first_name
            self.module_type = self.first_name
            self.module_sp = ""
            self.open_cmd = f"&{cs_id}A OPEN {self.module_type} CLEAR\n"
            self.close_cmd = "CLOSE\n"
        else:
            self.setFromCodeLine(code_line="OPEN " + first_name, _CS=cs_id)

        return True

    def setFromCodeLine(self, code_line="", _CS="0"):

        module_types_to_open = re.findall(r"(?<=OPEN)\s+[A-Z]+", code_line)
        self.module_type = module_types_to_open[0].strip()

        if self.module_type in cs_module_types:
            self.module_sp = ""
            self.open_cmd = f"&{_CS}A OPEN {self.module_type} CLEAR\n"
            self.close_cmd = "CLOSE\n"
        # module is not CS dependent
        else:
            # need a number to specify the module
            module_sps = re.findall(r"(?<=" + self.module_type + r")\s*\d+", code_line)
            if len(module_sps) == 1:
                self.module_sp = str(int(module_sps[0].strip())).zfill(2)
                if self.module_type in prog_module_types:
                    self.open_cmd = (
                        f"A OPEN {self.module_type} {self.module_sp} CLEAR\n"
                    )
                    self.close_cmd = "CLOSE\n"
                else:
                    self.open_cmd = f"DISABLE {self.module_type} {self.module_sp} OPEN {self.module_type} {self.module_sp} CLEAR\n"
                    self.close_cmd = "CLOSE\n"
            else:
                raise RuntimeError(f"ERROR: unspecified module name: {code_line}")

        self.first_name = self.module_type + self.module_sp

        return True

    def setBody(self, body="", checksum="", code_order=None):

        self.body = body
        self.verify(checksum)

        if code_order:
            self.code_order = code_order

        return True

    def verify(self, checksum=""):
        self.checksum = md5(self.body.encode("utf-8")).hexdigest()
        self.verified = checksum == self.checksum

        return True


def removeLeadingZeros(src):
    """    
    removes all leading zeros from constants, including hex numbers e.g. P0050->P50
    BUT dose't remove zeros from within hex numbers e.g. $000C0800 -> $C0800

    Args:
        src ([type]): [description]

    Returns:
        [type]: [description]
    """

    rgx_dec_leading_zeros = r"(?<![\dA-F.])0+(?=[\d+])"
    src = re.sub(rgx_dec_leading_zeros, "", src, flags=re.IGNORECASE)

    rgx_hex_leading_zeros = (
        r"(?<=[$])((?<![\dA-F.])0+(?=[\dA-F+]))"  # r"[$]((?<![\dA-F.])0+(?=[\dA-F+]))"
    )
    src = re.sub(rgx_hex_leading_zeros, "", src, flags=re.IGNORECASE)

    return src


def stripRgx(text, rgx_to_strip=" +", exclude_quote='"'):
    """
    strips what specified as rgx_to_strip, leaving intances inside quotes intact
    """

    lst = text.split(exclude_quote)
    for i, item in enumerate(lst):
        if not i % 2:
            lst[i] = re.sub(rgx_to_strip, "", item)
    return '"'.join(lst)


def stripInBrackets(_src, brackets="()", to_strip=" \n\t\r"):
    """
    removes all white-spaces within brackets
    """

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


def tpmcBufferSyntax(src):
    """
    modifies syntax of the script to match the tpmac stored code as retreives using List command
    """

    resevered_words = r"[\>,\<,\!,\(,\),=,+,\-,*,/,\n]"
    src_move_shorthands = [("LINEAR", "LIN"), ("RAPID", "RPD")]
    src_whole_shorthands = [
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
        (r"FRAX\(A,B,C,U,V,W,X,Y,Z\)", "FRAX"),
        ("GOSUB", "GOS"),
        ("GOTO", "GOT"),
        ("OR", "OR"),
        ("RETURN", "RET"),
        ("WHILE", "WHILE"),
    ]
    # remove buffer commands from source
    src = re.sub(r"clear\s", "", src, flags=re.IGNORECASE)

    # trim extra tabs and spaces

    # add a dumy line to ensure regex searches find keywords. remoe it at the end.
    src = "\t" + src
    # replace all spaces except spaces within double quotes: pmac code ignores and won't save space
    src = stripRgx(src, rgx_to_strip=" +")
    # reduce repeated tabs and spaces to single spaces
    src = re.sub(r"[\t, ]{2,}", " ", src, flags=re.IGNORECASE)
    # remove tabs and spaces globals reserved words
    src = re.sub(r"(?<=" + resevered_words + ")[\t, ]", "", src, flags=re.IGNORECASE)
    # remove tabs and spaces leading reserved words
    src = re.sub(r"[\t, ](?=" + resevered_words + ")", "", src, flags=re.IGNORECASE)

    # remove extra comma in coordinate axis assignment
    src = re.sub("->I, #", "->I #", src)

    # remove line feeds after N labels (goto labels)
    src = re.sub(r"(?<=\WN\d{1})\s+", "", src)
    src = re.sub(r"(?<=\WN\d{2})\s+", "", src)
    src = re.sub(r"(?<=\WN\d{3})\s+", "", src)

    src = removeLeadingZeros(src)

    # replace long forms with shorthands
    for _find, _replace in src_whole_shorthands:

        src = re.sub(
            r"(?<=[^A-Z])" + _find + r"[\t, ]*", _replace, src, flags=re.IGNORECASE
        )

        # insert a line feed before reserved words, except if they are in paranthesis...
        # so first add line feed to all, and then strip all linefeeds from within paranthesis
        src = re.sub(
            r"(?<=[^A-Z,^\n])" + _replace, r"\n" + _replace, src, flags=re.IGNORECASE
        )

    # replace move command shorthands with
    for _find, _replace in src_move_shorthands:

        src = re.sub(
            r"(?<=ABS|INC)" + _find + r"(?=[ABCUVWXYZ])",
            _replace,
            src,
            flags=re.IGNORECASE,
        )

    # strip line feeds within brackets
    src = stripInBrackets(src, brackets="()", to_strip="\n")

    # _src = re.sub(r'\n+', r'\n', _src, flags=re.IGNORECASE)

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
    code_module=None,
    user_time_in_header=False,
    source_id="",
):

    file_header = (
        ";;\n"
        ";; device: {0}\n"
        ";; module: {2}\n"
        ";; checksum: md5({1})\n"
        ";; source: {3}\n".format(device_id, code_module.checksum, module_id, source_id)
    )

    if user_time_in_header:
        file_header = file_header + ";; at {0:%Y-%m-%d %H:%M:%S} by {1}\n".format(
            datetime.now(), getuser()
        )

    file_header = file_header + ";;\n"

    Path(save_filename).parent.mkdir(parents=True, exist_ok=True)

    outFile = open(save_filename, "w")
    outFile.write(file_header + code_module.body)
    outFile.close()

    return code_module.checksum


def pmacModuleName(module_full_name):

    _CS = re.findall(r"(?<=CS).(?=_)", module_full_name)[0]
    # last one isa the pmac module name, because _trailing is already excluded
    module_first_name = module_full_name.split("_")[-1]

    return _CS, module_first_name


def tpmacModuleFullPath(
    pmac_id="", module_full_name="", suffix="", ext="PMA", output_dir_path=""
):

    _CS, module_first_name = pmacModuleName(module_full_name)

    return os.path.join(
        output_dir_path,
        f"{pmac_id.replace('.','-').replace(':','_')}",
        f"CS{_CS}_{module_first_name}.{suffix}.{ext}".format(),
    )


def tpmacExtractModules(code_source="", include_globals=True):
    module_full_name = None
    _cs_number = 0  # not selected
    code_order = 0
    _CS = None
    global_full_name = "CS0" + "_" + "globals"
    current_globals = codeModule()
    current_globals.module_type = "globals"
    current_globals.open_cmd = ""
    current_globals.close_cmd = ""

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

        # In case code_source includes multi-line segments
        splited_lines = code_line.splitlines()
        if len(splited_lines) > 1:
            for j, added_line in enumerate(splited_lines[1:]):
                code_source.insert(i + j + 1, added_line)  # insert after current line

        code_line = splited_lines[0]
        code_source[i] = code_line

        # if not already in a buffer (LISTable module) then
        if not module_full_name:
            # find instances of &cc in the command line:
            CS_list = re.findall(r"(?<=&)\d+", code_line)

            if len(CS_list) > 0:
                _CS = CS_list[-1]
                _cs_number = int(_CS)

            if len(CS_list) > 1:
                # TODO deal with multiple CS changes in a single line
                # also deal with syntax mix that binary & creates: (10&30) is NOT
                # defining a cs number. Inside buffered modules, & only works inside cmd
                # So...
                # for the moment, we will IGNORE the multiple ones and   .
                raise RuntimeError(
                    f"unsupported syntax, multiple CS numbers in a single line : {code_line}"
                )

        module_types_to_open = re.findall(r"(?<=OPEN)\s+[A-Z]+", code_line)
        # module_types_to_close = re.findall(r"OPEN\s+[A-Z]+(?=.*CLOSE)", code_line)
        # code_line has and OPEN statements: OPENNING --------------------
        if len(module_types_to_open) > 0:

            if module_full_name is not None:
                raise RuntimeError(
                    f"ERROR trying to open {code_line[5:]} before {module_full_name} is closed"
                )

            if len(module_types_to_open) > 1:
                # multiple modules OPENED in a single line should have been dealt with before
                raise RuntimeError(
                    f"unsupported syntax, multiple modules OPEN statements in a single line: {code_line}"
                )

            # there is a single module type identified here

            current_module = codeModule(
                open_line=code_line, cs_id=_CS
            )  # type = codeModule

            if current_module.module_type in cs_module_types:
                module_full_name = f"CS{str(_cs_number)}_{current_module.first_name}"
            else:
                module_full_name = f"CS{str(0)}_{current_module.first_name}"

            # reset module and globals code
            source_module_code = ""

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
                source_module_code = tpmcBufferSyntax(source_module_code)

                current_module.setBody(
                    body=source_module_code, code_order=code_order,
                )

                yield module_full_name, current_module

            module_full_name = None

        # code_line has no OPEN/CLOSE statements: body of moddule --------------------
        else:
            # there is a named module
            if module_full_name:
                source_module_code += code_line + "\n"
            else:
                # non-module settings all go to
                # check if this is a setting
                # simplest check is if it contains "="  .
                if "=" in code_line:
                    current_globals.body += code_line + "\n"
                    current_globals.code_order = code_order
                else:
                    pass
                    # all other code are ignored!!!
                    # e.g. -> definitions, etc   .

    # return _globals module if needed
    if include_globals and global_full_name:
        # now extract gloabal modules
        # from within globals, like I1xx and Pxxx.

        global_modules = {}

        for _code_line in current_globals.body.splitlines():
            _left_side = _code_line.split("=")[0]
            myset = re.findall(r"([A-Z])(\d+)", _left_side)[0]
            family_char = myset[0]
            index_int = int(int(myset[1]) / 100)

            # if index_int > 49:
            #     # these are I5sx, I7mnx and I8mxx
            #     # collate all of them under 50, 60, 70, 80 and 90
            #     index_int =  * 10int(index_int / 10)

            first_name = (
                f"{family_char}{index_int}xx"
                if (index_int < 50) or (family_char != "I")
                else f"{family_char}{int(index_int/10)}mnx"
            )

            gmodule_full_name = f"CS0_{first_name}"

            # now see if this gmodule exists in global_moduls

            if gmodule_full_name not in global_modules:
                _gmodule = codeModule()
                _gmodule.close_cmd = ""
                _gmodule.open_cmd = ""
                _gmodule.first_name = first_name
                _gmodule.module_type = "globals"
                _gmodule.body = ""
                _gmodule.code_order = current_globals.code_order
                global_modules[gmodule_full_name] = _gmodule

            # gmodule exists, add the codeline

            # clean up
            _code_line = _code_line.replace(" ", "").strip() + "\n"
            # process is to resolve crange syntax
            # e.g. P745..760=0

            if ".." in _code_line:
                myset = re.findall(
                    r"([A-Z])(\d+)(?:\.\.)(\d+)\s*(?:=)\s*(.*)", _code_line
                )[0]
                _start = int(myset[1])
                _end = int(myset[2]) + 1
                if (_start > _end) or (_start < 1):
                    raise SyntaxError(f"{_code_line}")

                _dum = ""
                for elem in range(_start, _end):
                    _dum += (myset[0] + str(elem) + "=" + myset[3]) + "\n"

                # replace the shorthand range ".." command
                # with expanded version in source code
                _code_line = _dum

            global_modules[gmodule_full_name].body += _code_line

        # 2nd pass: verify and yield global modules one by one
        for _gmodule_name in global_modules:
            _gmodule = global_modules[_gmodule_name]  # type: codeModule
            # remove leading zeros
            _gmodule.setBody(removeLeadingZeros(_gmodule.body))
            # verify so that the checksum is added
            _gmodule.verify()
            yield _gmodule_name, _gmodule

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


def downloadCodeLines(pmac=None, module_code=[], section_size=1):
    """
    downloads pmac script to pmac

    the script is devided into sections of section_size and sent to the pmac using sendCommand

    this was an attempt to use sendSeries. It frequently fails to write into buffers returning ERR005,
    indicating buffer gets closed while downloading.
    """
    code_lines = module_code.splitlines(True)
    code_sections = []
    this_code_section = ""
    this_section_lines = 0
    secion_counter = 0
    for code_line in code_lines:
        if (this_section_lines < section_size) and (
            len(this_code_section) + len(code_line)
        ) < 255:
            this_code_section = this_code_section + code_line.replace("\n", "\r")
            this_section_lines += 1
        else:
            secion_counter += 1
            code_sections.append((secion_counter, this_code_section))
            this_code_section = code_line.replace("\n", "\r")
            this_section_lines = 1

    # append the last section
    secion_counter += 1
    code_sections.append((secion_counter, this_code_section))

    for (success, section_number, this_code_section, retStr) in pmac.sendSeries(
        code_sections
    ):
        if not success:
            return (
                f"section{section_number}: {this_code_section.splitlines()[-1]} ---> {retStr}",
                False,
            )

    n = len(code_lines)

    return f" {n} lines" if n > 0 else "cleared", True


def downloadCodeLinesOBS(pmac=None, module_code=[], section_size=20):
    """
    downloads pmac script to pmac

    the script is devided into sections of section_size and sent to the pmac using sendCommand

    using sendCommand for sections, its 3x faster but sometimes code chunks get missing from download

    """
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

    for this_code_section in code_sections:
        retStr, success = pmac.sendCommand(this_code_section, shouldWait=True)
        if not success or errRegExp.findall(retStr) or len(retStr) < 1:
            return f"{this_code_section.splitlines()[-1]} ---> {retStr}", False

    n = len(code_lines)

    return f" {n} lines" if n > 0 else "cleared", True


def downloadModule(pmac=None, code_module=codeModule()):
    """downloads a code module body.
    for non LIST able free settings code_module.open_cmd and code_module.close_cmd shall be blank
    """

    # send open commands
    return_message, success = downloadCodeLines(pmac, code_module.open_cmd)

    if success:
        # download code body
        return_message, success = downloadCodeLines(pmac, code_module.body)

    # send close commands
    closedSuccessfully, close_msg = downloadCodeLines(pmac, code_module.close_cmd)

    code_module.download_failed = not (success and closedSuccessfully)

    return return_message.strip("\r"), success, close_msg, closedSuccessfully


def uploadGlobals(
    pmac,
    # module_full_name,
    global_module: codeModule,
    wait_secs=0.15,
    bunch_size=10,
    end_code="ERR003",
):

    """uploads LIST able module using full name"""

    # _CS, module_first_name = pmacModuleName(module_full_name)

    global_module_lines = global_module.body.splitlines()

    this_line_no = 0
    uploaded_module_code = ""
    _code_lines = ""
    success = True
    up_code_list = []
    added_lines = set()
    upload_error = None

    code_cmd_lines = []
    for src_line in global_module_lines:
        # use left hand side of statements as commands
        code_cmd_lines.append(src_line.split("=")[0])

    while success and this_line_no < len(global_module_lines):

        # TODO document this: tpmac sometimes sends back the same code line with a different (by 1) line number.
        # I assume at this point that this is related to the starting line, so, try to prevent requesting overlapping
        # ranges

        sleep(wait_secs)

        last_line_no = min(this_line_no + bunch_size, len(global_module_lines))

        # if last_line_no == len(global_module_lines):
        #     print("debug")

        _command_str = "\n".join(code_cmd_lines[this_line_no:last_line_no]) + "\n"

        _code_lines, success = pmac.sendCommand(_command_str)

        if not success:
            upload_error = _code_lines
            break

        # TODO: check if uppercase for all
        # uplpoaded code is not problematic
        _code_lines = _code_lines.upper()
        _code_lines = re.sub(r"\r", "\n", _code_lines, flags=re.IGNORECASE)

        # and remove the RET at the end of the buffer
        if _code_lines.endswith("\x06"):
            _code_lines = _code_lines[:-1]

        if _code_lines.endswith("\n"):
            _code_lines = _code_lines[:-1]
        # if _code_lines.endswith(end_code):
        #     upload_error = None
        #     break

        _up_code_list = list(
            zip(code_cmd_lines[this_line_no:last_line_no], _code_lines.splitlines(),)
        )

        if len(_code_lines) > 0:
            for (_query, _answer) in _up_code_list:
                # check if the line starts with a line number
                this_line_code = f"{_query}={_answer}"

                up_code_list.append((this_line_no, this_line_code))
                added_lines.add(this_line_no)
                this_line_no += 1

        else:
            this_line_no += 1
            print("empty return, terminating", end="...")
            success = False

    # remove empty lines
    up_code_list = [item for item in up_code_list if len(item[1]) > 0]

    if len(up_code_list) > 0:
        uploaded_module_code = "\n".join(list(zip(*up_code_list))[1]) + "\n"
    else:
        uploaded_module_code = ""

    # catch errors
    if not success:
        print("Comms Error", end="...")

    if upload_error:
        print(f"Error {upload_error}", end="...")

    elif uploaded_module_code[-40:-1].endswith(r"WARNING: response truncated."):
        print(
            "Buffer is truncated, received {} bytes".format(len(uploaded_module_code)),
            end="...",
        )

    # now put the loaded code into a code module
    code_module = codeModule(body=uploaded_module_code)
    code_module.module_type = "globals"
    code_module.open_cmd = ""
    code_module.close_cmd = ""

    return code_module


def uploadModule(
    pmac, module_full_name, wait_secs=0.15, bunch_size=100, end_code="ERR003"
):

    """uploads LIST able module using full name"""

    _CS, module_first_name = pmacModuleName(module_full_name)

    line_no = -1
    this_line_no = 0
    uploaded_module_code = ""
    _code_lines = ""
    success = True
    up_code_list = []
    added_lines = set()
    upload_error = None
    while success and not _code_lines.endswith(end_code):

        # TODO document this: tpmac sometimes sends back the same code line with a different (by 1) line number.
        # I assume at this point that this is related to the starting line, so, try to prevent requesting overlapping
        # ranges
        line_no = max(this_line_no, line_no + 1)
        sleep(wait_secs)
        _command_str = "LIST {},{},{}".format(module_first_name, line_no, bunch_size)

        if int(_CS) > 0:
            _command_str = "&{}".format(_CS) + _command_str

        _code_lines, success = pmac.sendCommand(_command_str)

        if not success:
            upload_error = _code_lines
            break

        # TODO: check if uppercase for all
        # uplpoaded code is not problematic
        _code_lines = _code_lines[:-1].upper()
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

                code_line_splited = _code_line.split(":", 1)

                assert len(code_line_splited) == 2 and code_line_splited[0].isdecimal
                # found a line number
                this_line_no = int(code_line_splited[0])
                this_line_code = code_line_splited[1]

                if this_line_no not in added_lines:
                    up_code_list.append((this_line_no, this_line_code))
                    added_lines.add(this_line_no)
                else:
                    # duplicated line: it is possible that this line was truncated the last time
                    # ovewrite last one!
                    assert up_code_list[-1][0] == this_line_no
                    up_code_list[-1] = (this_line_no, this_line_code)

        else:
            this_line_no = line_no + 1
            print("empty return, terminating", end="...")
            success = False

    # remove empty lines
    up_code_list = [item for item in up_code_list if len(item[1]) > 0]

    if len(up_code_list) > 0:
        uploaded_module_code = "\n".join(list(zip(*up_code_list))[1]) + "\n"
    else:
        uploaded_module_code = ""

    # catch errors
    if not success:
        print("Comms Error", end="...")

    if upload_error:
        print(f"Error {upload_error}", end="...")

    elif uploaded_module_code[-40:-1].endswith(r"WARNING: response truncated."):
        print(
            "Buffer is truncated, received {} bytes".format(len(uploaded_module_code)),
            end="...",
        )

    # now put the loaded code into a code module
    code_module = codeModule(body=uploaded_module_code)
    code_module.setFromFirstName(first_name=module_first_name, cs_id=_CS)

    return code_module


class stager:
    times = ...  # type: list
    time_laps = ...  # type: list
    verbose_levels = ...  # type: list
    verbose_level = ...  # type: int
    print_end = ...  # type: str

    print_close = ...  # type: str

    def __init__(self, verbose_level=0, default_end=": ", default_close="*\n"):
        self.times = []
        self.verbose_level = verbose_level
        self.print_end = default_end
        self.verbose_levels = []
        self.print_close = default_close

    def stage(self, fstring=None, this_verbose_level=1, times=None, laps_time=True):

        # new stage

        if not fstring:
            return False

        if laps_time:
            abbr_str = fstring.split()[0]
            self.times.append([abbr_str, time(), this_verbose_level])
            self.verbose_levels.append(this_verbose_level)

            if len(self.times) > 1:

                self.time_laps.append(
                    (self.times[-2][0], round(self.times[-1][1] - self.times[-2][1], 3))
                )

                # close the last stage
                if self.verbose_levels[-2] <= self.verbose_level:
                    print(self.print_close, end="")

            else:
                self.time_laps = []

        if this_verbose_level <= self.verbose_level:
            print(fstring, end=self.print_end)

        return True


if __name__ == "__main__":
    pass


"""
All of the non-modular code will all be augmented in the original order, in one global code buffer.
Currently, I and P and Q variables are NOT cosidered modules (or locals) but they can easily be added
to the model.

The modular code is assumed to be unique per buffer, e.g. the later definition of PLC1
will overwrite all the preceeding codes. This will generate a warning.

"""
