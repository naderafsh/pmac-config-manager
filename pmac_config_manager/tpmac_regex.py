#!/usr/bin/env python
#
# $File: //ASP/Personal/afsharn/tpmac-config-manager/tpmac_config_manager/epmcLib.py $
# $Revision: #1 $
# $DateTime: 2020/06/24 22:15:13 $
# Last checked in by: $Author: afsharn $
#
# Description
# <description text>
#
# Copyright (c) 2019 Australian Synchrotron
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# Licence as published by the Free Software Foundation; either
# version 2.1 of the Licence, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public Licence for more details.
#
# You should have received a copy of the GNU Lesser General Public
# Licence along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Contact details:
# nadera@ansto.gov.au
# 800 Blackburn Road, Clayton, Victoria 3168, Australia.
#

import re
import datetime
import getpass

pre_rx = r"^(\s*)"
eq_rx = r"[\s,=].*"
trail_rx = eq_rx + r"[; ? \w]"

xx_rx = r"_XX_"
mn_rx = r"_M__N__L_"
sx_rx = r"_S__X_"

first_in_line_only_rx = "^(\s*)"
Ivar_xx_rx = "[iI]" + xx_rx
Pvar_xx_rx = "[pP]" + xx_rx
Ivar_mn_rx = "[iI]" + "7" + mn_rx
Ivar_s5x_rx = "[iI]" + "5" + mn_rx
Ivar_s6x_rx = "[iI]" + "6" + mn_rx


statement_whole_rx = r"[0-9a-zA-Z_.\[\]]+[ \t]*=[ \t]*[\+\-0-9a-zA-Z_$.\[\]]*"
statement_varref_rx = r"[0-9a-zA-Z_.\[\]]+(?=[ \t]*=)"
statement_val_rx = r"(?<=[= \t])[\+\-0-9a-zA-Z_$.\[\]]*"


def vxx_rx(vstr, dumstr, mode="find", tail_rx=r"\d{2}\D", fold_digits=2):

    # global _rx
    dumstr = str(dumstr)
    if not vstr:
        mode = "raw"
    elif vstr == "&":
        tail_rx = r"\D"
        if mode != "raw":
            dumstr = r"[ \t]*" + dumstr
    elif vstr == "#":
        tail_rx = r"\D"
    elif vstr == "plc":
        vstr = r"((plc|PLC))"
        tail_rx = r"\D"
        if mode != "raw":
            dumstr = r"[ \t]*" + dumstr
    else:
        tail_rx = r"\d{" + str(fold_digits) + "}\D"

    dumstr = str(dumstr)
    if mode == "find":
        _rx = vstr + dumstr + tail_rx + ".*"
    elif mode == "sub":
        _rx = "(?<=" + vstr + ")" + dumstr + "(?=" + tail_rx + ")"
    elif mode == "raw":
        _rx = dumstr
    return _rx


def isx_vars(old_xx, mode="find"):
    if old_xx > 9:
        x = old_xx - 10
        s = 6
    else:
        x = old_xx
        s = 5

    dumstr = str(s) + str(x)

    _dum_rx = vxx_rx("[iI]", dumstr, mode)

    return _dum_rx


def rxit(m):
    if m:
        m = str(m)
    else:
        m = r"\d"
    return m


# find Ivars, belonging to amp #xx, and include channel (IC channel)
def vxx_stats(_Stats_rx, xx, pre_rx=r"^(\s*)", trail_rx=r"[\s,=].*[; ? \w]"):

    dum_rx = _Stats_rx

    if xx:
        if xx == "0":
            xx_sub = r"\d"
        elif xx == "00":
            xx_sub = r"\d{2}"
        else:
            xx_sub = str(xx) + r"\d{2}"
    else:
        xx_sub = r"\d{1,4}"

    dum_rx = re.sub("_XX_", xx_sub, dum_rx)
    dum_rx = pre_rx + dum_rx + trail_rx

    dum_pattern = re.compile(dum_rx, re.MULTILINE)

    return dum_pattern


# find Ivars, belonging to amp #xx, and include channel (IC channel)
def vmn_stats(
    _Stats_rx, m="", n="", l="", pre_rx=r"^(\s*)", trail_rx=r"[\s,=].*[; ? \w]"
):

    dum_rx = _Stats_rx
    m = rxit(m)
    n = rxit(n)
    l = rxit(l)

    dum_rx = re.sub("_M_", m, dum_rx)
    dum_rx = re.sub("_N_", n, dum_rx)
    dum_rx = re.sub("_L_", l, dum_rx)
    dum_rx = pre_rx + dum_rx + trail_rx

    dum_pattern = re.compile(dum_rx, re.MULTILINE)
    return dum_pattern


class Epmc:
    file_full_name = ""
    epmc_file = ""

    actionLog = (
        "\n\n;;; epmcLib AuroConvert end pointer ;;;\n\n;;;;;;;;;;;;;;; epmc action log ;;;;;;;;;;;;;;;;;;;\n;; Log started at "
        + "{0:%Y-%m-%d %H:%M:%S} \n".format(datetime.datetime.now())
    )

    # take in a script, apply it to an existing script by finding and updating variable referemnces
    def apply_script(self, pmc_script):
        if not pmc_script:
            return 1
        # find varref's in script
        varref_rx = statement_varref_rx  # r'[0-9a-zA-Z_.\[\]]+(?=[ \t]*=)'
        varstat_rx = statement_whole_rx  # r'[0-9a-zA-Z_.\[\]]+[ \t]*=[ \t]*[+-0-9a-zA-Z_$.\[\]]*'
        varref_val_rx = statement_val_rx  # r'(?<=[= \t])[+-0-9a-zA-Z_$.\[\]]+'
        patrx = re.compile(varstat_rx)
        for _match in patrx.finditer(pmc_script):
            dum = re.findall(varref_rx, _match.group(0))
            if len(dum) > 0:
                dum = dum[0]
            else:
                dum = ""
            varref = dum
            dum = re.findall(varref_val_rx, _match.group(0))
            if len(dum) > 0:
                dum = dum[len(dum) - 1]
            else:
                dum = ""
            varref_val = dum
            print(" {} will be updated with value {}".format(varref, varref_val))
            self.update_var(varref, varref_val)

    # this function can be used to update a known variable in code
    def update_var(self, varref="boolboolA", new_val="boombA_oldval_"):

        # this routine assumes that there is only 1 instance of the varref in the script
        varref_escaped = re.escape(varref)
        varstat_old_rx = varref_escaped + r"[ \t]*=[ \t]*[\+\-0-9a-zA-Z_$.\[\]]*"
        varstat_new_sub = varref + "=" + new_val
        _matches = re.findall(varstat_old_rx, self.script)

        self.log_action("   ...{} instances of {} found".format(len(_matches), varref))

        if len(_matches) < 1:
            old_val = "none"
            # doit = True
            # # Add to the end of the script now:
            # # replace at ;;; epmcLib AuroConvert end pointer ;;;
            # varstat_old_rx = ';;; epmcLib AuroConvert end pointer ;;;'
            # varstat_new_sub = varstat_new_sub + '\n\n;;; epmcLib AuroConvert end pointer ;;;'
            doit = False

        elif len(_matches) == 1:
            doit = True
            old_val = _matches[0]
        else:
            old_val = "multiple values"
            self.log_action(
                "   !!! multiple {} instances of variable {} are found".format(
                    len(_matches), varref
                )
            )
            patrx = re.compile(varstat_old_rx)
            for _match in patrx.finditer(self.script):
                self.log_action("{}".format(_match))

            doit = (
                input(
                    "... confirm updating all {} instances with {} [y]?".format(
                        len(_matches), new_val
                    )
                )
                == "y"
            )
        if doit:

            self.log_action("... updating {} to {}".format(old_val, new_val))
            self.script = re.sub(varstat_old_rx, varstat_new_sub, self.script)
            self.log_action("done.")
            return True
        else:
            self.log_action("skipped.")
            return False

        self.tpmcSubxx(varref_escaped + "\s{0,1}=", old_val, new_val)

    def swap_motors(self, old_xx, new_xx, dum_xx=99):
        self.move_motor(new_xx, dum_xx)
        self.move_motor(old_xx, new_xx)
        self.move_motor(dum_xx, old_xx)

    def log_action(self, text):
        textlines = text.split("\n")
        for line in textlines:
            s = ";; "
            # s += ' {0:%H:%M:%S} '.format(datetime.datetime.now())
            s += line + "\n"
            print(s)
            self.actionLog += s

    def move_cs(self, old_xx, new_xx):
        self.log_action("moving CS {} to {}".format(old_xx, new_xx))
        self.tpmcSubxx("&", old_xx, new_xx)
        # and move Isx settings with that:
        _old_sx = isx_vars(old_xx, mode="raw")
        _new_sx = isx_vars(new_xx, mode="raw")
        self.tpmcSubxx("[iI]", _old_sx, _new_sx)

    def move_motor(self, old_xx, new_xx):
        self.log_action("moving motor {} to {}".format(old_xx, new_xx))
        self.tpmcSubxx(
            "[iI]", old_xx, new_xx
        )  # move I-variables corresponding to axis xx : I3xx <-> #3
        self.tpmcSubxx(
            "[mM]", old_xx, new_xx
        )  # move M-variables corresponding to axis xx : M3xx <-> #3
        self.tpmcSubxx(
            "#", old_xx, new_xx
        )  # move Commands corresponding to axis xx    :
        self.tpmcSubxx(
            "[pP]", old_xx, new_xx, fold_digits=0
        )  # move P-variables corresponding to axis xx : P3 <-> #3

    def move_plc(self, old_xx, new_xx):
        self.log_action("moving plc {} to {}".format(old_xx, new_xx))
        self.tpmcSubxx("plc", old_xx, new_xx)
        self.tpmcSubxx("[pP]", old_xx, new_xx)

    def tpmcSubxx(self, vstr, old_xx, new_xx, fold_digits=2):

        _old_rx = vxx_rx(vstr, old_xx, mode="find", fold_digits=fold_digits)
        _matches = re.findall(_old_rx, self.script)

        self.log_action("  {} instances of {} found".format(len(_matches), _old_rx))

        if not _matches:
            return

        # check if there are instances of new
        _new_rx = vxx_rx(vstr, new_xx, mode="find", fold_digits=fold_digits)

        _matches = re.findall(_new_rx, self.script)

        if _matches:
            self.log_action(
                "  !!! {} instances of destination {} already existed".format(
                    len(_matches), _new_rx
                )
            )
            patrx = re.compile(_new_rx)
            for _match in patrx.finditer(self.script):
                self.log_action("{}".format(_match))

            doit = (
                input("   confirm replacing {} with {} [y]?".format(_old_rx, _new_rx))
                == "y"
            )
        else:
            doit = True

        _old_rx = vxx_rx(vstr, old_xx, mode="sub", fold_digits=fold_digits)
        _new_rx = vxx_rx(vstr, new_xx, mode="raw", fold_digits=fold_digits)

        if doit:
            self.script = re.sub(_old_rx, _new_rx, self.script)
            self.log_action('    replaced with "{}"'.format(_new_rx))
            return True
        else:
            self.log_action("    skipped.")
            return False

    def reSub(self, _old_rx, _new_rx):
        self.script = re.sub(_old_rx, _new_rx, self.script)

    def Load(self, _epmc_file):
        self.epmc_file = _epmc_file
        self.script = self.epmc_file.read()


# end
