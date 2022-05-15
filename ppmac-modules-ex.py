#!
from collections import defaultdict
from os import path
from pmac_config_manager import ppmac_config as pm
from pmac_config_manager import stager as st

"""

example loading and modularising ppmac code

"""


stager = st.stager(verbose_level=2)

src_full_path = path.abspath(
    r"C:\Users\afsharn\gitdir\ppmac-baseconfig\ppmac_sln\Configuration\pp_save.cfg"
)

src_path, src_filename = path.split(path.abspath(src_full_path))

stager.stage(
    f"Loading ppmac native code from file {src_full_path}", this_verbose_level=1
)


with open(src_full_path, "r") as f:
    ppmac_script = f.read()


for i in range(16):

    stager.stage(
        f"\nmotor_{i} settings",
        this_verbose_level=2,
        laps_time=True, print_end=":\n"
    )

    axis_settings_list = pm.ppmacExtractModules(
        code_source=ppmac_script, include_tailing=True, motor_index=i, deindex=True,
    )

    axis_config_script = "\n".join(
        f"{line[0]}={line[1]}" for line in axis_settings_list
    )

    out_full_name = path.join(src_path, f"{src_filename.rsplit('.')[0]}.motor_{i}.cfg")

    print(f"saving in {out_full_name}")
    with open(out_full_name, "w+") as f:
        f.write(axis_config_script)


stager.stage(f"Done.", this_verbose_level=0)

print(f"\n\ntime lapses in seconds: {stager.time_laps}")

input("press a key to terminate...")

exit(0)
