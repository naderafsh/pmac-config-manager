import re
from collections import OrderedDict


def isPmacNumber(s: str):

    if s.startswith("$"):
        # check if it is a valid hex
        try:
            int(s[1:], 16)
        except ValueError:
            return False
        else:
            return True
    else:
        # check if it is a valid decimal
        return (
            s.replace("e-", "")
            .replace("e+", "")
            .lstrip("+-")
            .replace(".", "", 1)
            .isdigit()
        )


def ppmacFindAssociates(module_settings, exclusions=[]):
    assert isinstance(module_settings, set)
    # assert isinstance(module_settings[0], tuple)
    # assert len(module_setting) == 2) for module_settings in module_settings

    # alternatively, all non-numerical right-hands are assocites
    return set(
        [
            (
                # ("".join(inst[-1].rsplit("]", 1)[0]) + "]")
                inst[-1][0 : inst[-1].rfind("]") + 1]
                if inst[-1].find("]") > 0
                else inst[-1]
            )
            for inst in module_settings
            if not isPmacNumber(inst[-1])
        ]
    ) - set(exclusions)


def ppmacFindSettings(modules: set, code_source="", deindex=True):

    # add associate settings:
    module_settings = set([])
    for module in modules:
        module = module.replace("[", r"\[").replace("]", r"\]")

        reg_str = rf"(?:\n)({module}\.\S*)(?:\s*=\s*)(.*)"
        module_settings.update(
            set(re.findall(reg_str, code_source, flags=re.IGNORECASE))
        )

    return module_settings


def ppmacExtractModules(
    code_source="", include_tailing=True, motor_index=None, deindex=True
):

    linecomment_prefix = "//"

    # start by extracting direct Motor[i] settings
    reg_str = rf"(?:\s*)(Motor\[{motor_index}\]\.\S*)(?:\s*=\s*)(.*)"
    motor_settings = set(re.findall(reg_str, code_source, flags=re.IGNORECASE))

    # then look for its correspondends, via right-hand associations
    # reg_str = rf"(?:Motor\[{motor_index}\])(?:\.)(?:\S*)(?:\s*=\s*)(.*\[.*)"
    # associate_instances = re.findall(reg_str, code_source, flags=re.IGNORECASE)
    #

    associates = ppmacFindAssociates(
        motor_settings, exclusions=["Sys.pushm", f"Motor[{motor_index}]"]
    )

    # extract the associate settings
    associate_settings = ppmacFindSettings(modules=associates, code_source=code_source)

    # check second hand dependencies
    associates_of_associates = ppmacFindAssociates(
        associate_settings, exclusions=["Sys.pushm", f"Motor[{motor_index}]"]
    )

    if len(associates_of_associates) > 0:
        # this is problematic. There might be some circular references

        if not associates_of_associates.issubset(associates):

            raise RuntimeWarning(f"Unexpected dependency: {associates_of_associates}")

    axis_settings = motor_settings
    axis_settings.update(associate_settings)

    # if deindex, then set
    if deindex:
        gate_index = 0 if motor_index < 5 else 1
        chan_index = motor_index - gate_index * 4 - 1
        companion_index = motor_index + 8
        enctable_index = motor_index
        # find L1 as Motor index

        index_settings = [
            ("L1", f"{motor_index} //Motor[{motor_index}]"),
            ("L2", f"{gate_index} //PowerBrick[{gate_index}]"),
            ("L3", f"{chan_index} //Chan[{chan_index}]"),
            ("L4", "L2 // 2nd gate"),
            ("L5", "L3 // 2nd chan"),
            ("L6", "L1 - 1 // motor addressed from 0"),
            ("L7", f"{companion_index} // companion axis bla bla"),
            ("L8", f"{enctable_index} //EncTable[{enctable_index}]"),
        ]

        # replace instances of Motor[]

        for index_setting in index_settings:
            _find = index_setting[1].split(linecomment_prefix)[1]
            _replace = _find.replace(
                f"[{index_setting[1].split(linecomment_prefix)[0].strip()}]",
                f"[{index_setting[0]}]",
            )

            axis_settings = [
                (
                    axis_setting[0].replace(_find, _replace),
                    axis_setting[1].replace(_find, _replace),
                )
                for axis_setting in axis_settings
            ]

    axis_settings_dict = OrderedDict(sorted(axis_settings))

    return axis_settings_dict
