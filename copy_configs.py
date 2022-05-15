from os import path
import re


src_path = path.abspath(
    r"c:\P4C\opa\int\ctrls\ppmac-baseconfig\ppmac_sln\PMAC Script Language\Global Includes"
)


ref_file_name = f"a1- stepper_no_enc.pmh"
ref_full_name = path.join(src_path,ref_file_name)

print(f"reading from {ref_full_name}")
with open(ref_full_name,"r") as f:
    ref_template = f.read()
    

for i in range(1,8+1):
    out_file_name = f"a{i}- stepper_no_enc.pmh"
    if out_file_name == ref_file_name:
        continue

    out_full_name = path.join(src_path,out_file_name)
    
    
    print(f"writing to {out_full_name}")
    out_script = re.sub("#define xx_ \d+", f"#define xx_ {i}",ref_template)
    with open(out_full_name,"w+") as f:
        f.write(out_script)        
        