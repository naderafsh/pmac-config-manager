from ast import Break
from os import path
import re
import shutil
import xml.etree.ElementTree as ET

# this shall point to the abs path of the root
src_path = path.abspath(r"c:\P4C\tec\mc\ppmac\trunk\firmware\baseConfig")

# r"c:\P4C\opa\int\ctrls\ppmac-baseconfig\ppmac_sln"

dest_path = path.abspath(r"c:\P4C\opa\mct\ctrls\Powerbrick01")
                         
# r"c:\P4C\tec\mc\ppmac\trunk\firmware\baseConfig")

des_ppproj_file = r"PB_MCTPPMAC01.ppproj" #r"template_base.ppproj"




updated_des_ppproj_file = "updated_" + des_ppproj_file

des_ppproj_full = path.join(dest_path,des_ppproj_file)
updated_des_ppproj_full = path.join(dest_path,updated_des_ppproj_file)

# \ppmac_sln\PMAC Script Language\Global Includes
userinput = ""

for ref_file_name in ["Configuration/pp_disable.txt", 
                      "Configuration/pp_startup.txt", 
                      "Configuration/pp_inc_disable.txt", 
                      "Configuration/pp_inc_startup.txt", 
                      
                      "Database/_placeholder.txt",
                      
                      "Log/_placeholder.txt",
                      
                      "PMAC Script Language/Global Includes/00- system gates.pmh",
                      "PMAC Script Language/Global Includes/01- global definitions.pmh",
                      "PMAC Script Language/Global Includes/02- io n flags.pmh",
                      "PMAC Script Language/Global Includes/03- enc conversion table.pmh",
                      
                      "PMAC Script Language/Kinematic Routines/_placeholder.txt",
                      
                      "PMAC Script Language/Motion Programs/dls_prog_10_cs_motion.pmc",
                       
                      "PMAC Script Language/Libraries/abs_encloss_sub.pmc",
                      "PMAC Script Language/Libraries/config_bricklv_sub.pmc",
                      "PMAC Script Language/Libraries/config_check_sub.pmc",
                      "PMAC Script Language/Libraries/config_lock_sub.pmc",
                      "PMAC Script Language/Libraries/fine_phase_sub.pmc",
                      "PMAC Script Language/Libraries/home_sub.pmc",
                      "PMAC Script Language/Libraries/idle_strategy_sub.pmc",
                      "PMAC Script Language/Libraries/mu_to_egu.pmc",
                      "PMAC Script Language/Libraries/protection_sub.pmc",
                      "PMAC Script Language/Libraries/refresh_io_sub.pmc",
                      "PMAC Script Language/Libraries/set_bissc_sub.pmc",
                      "PMAC Script Language/Libraries/set_brushed_sub.pmc",
                      "PMAC Script Language/Libraries/set_companion_sub.pmc",
                      "PMAC Script Language/Libraries/set_encloss_sub.pmc",
                      "PMAC Script Language/Libraries/set_inc_sub.pmc",
                      "PMAC Script Language/Libraries/set_phase_enc_sub.pmc",
                      "PMAC Script Language/Libraries/set_powon_sub.pmc",
                      "PMAC Script Language/Libraries/set_stepper_sub.pmc",
                      "PMAC Script Language/Libraries/updates_sub.pmc",
                      "PMAC Script Language/Libraries/timer.pmc",
                       
                      "PMAC Script Language/PLC Programs/config.plc",
                      "PMAC Script Language/PLC Programs/ConfigLockReset.plc",
                      "PMAC Script Language/PLC Programs/dls_cs_readback.plc",
                      "PMAC Script Language/PLC Programs/idle_strategy.plc",
                      "PMAC Script Language/PLC Programs/PowerOnReset.plc",
                      "PMAC Script Language/PLC Programs/Protection.plc",
                      "PMAC Script Language/PLC Programs/RefreshIO.plc",
                      "PMAC Script Language/PLC Programs/motor1_home.plc",
                      "PMAC Script Language/PLC Programs/motor2_home.plc",
                      "PMAC Script Language/PLC Programs/motor3_home.plc",
                      "PMAC Script Language/PLC Programs/motor4_home.plc",
                      "PMAC Script Language/PLC Programs/motor5_home.plc",
                      "PMAC Script Language/PLC Programs/motor6_home.plc",
                      "PMAC Script Language/PLC Programs/motor7_home.plc",
                      "PMAC Script Language/PLC Programs/motor8_home.plc",
 
                      ]:
    ref_full_name = path.join(src_path,ref_file_name)
    dest_full_name = path.join(dest_path,ref_file_name)
    

    print(f"\n\ngoing to overwrite \n{dest_full_name} \nwith \n{ref_full_name}")

    if userinput != "a":
        input("[S]kip, Confirm (a)ll or ctrl-c to abort > ")  #userinput = ""
    if (userinput.lower() == "s"):
        continue

    # make sure this file exists in the pproj file
    # with open(des_ppproj_full,"r") as f:
    #     des_ppproj_xml = f.read()    
    
    ET.register_namespace('', "http://schemas.microsoft.com/developer/msbuild/2003")
    
    proj_tree = ET.parse(des_ppproj_full)
    root = proj_tree.getroot()
    
    attrib_text = ref_file_name.replace(r"/", "\\")
    
    # check if the file is already ioncluded
    ref_is_in_ppproj = True if "_place" in attrib_text else False
    target_group = None
    for group in root:
        if ref_is_in_ppproj or target_group: 
            break
        # print(group.tag)
        for subgr in group:
            
            if "Content" in subgr.tag:
                target_group = group 
            
            if subgr.get('Include') == attrib_text:
                # already included
                ref_is_in_ppproj = True
                break
    
    
    if not ref_is_in_ppproj:
        print(f"adding {attrib_text} to project")
        new_include = ET.Element("Content")
        new_include.attrib["Include"] = ref_file_name
        
        target_group.append(new_include)      
        
        proj_tree.write(updated_des_ppproj_full)
        
    else:
        print(f"{attrib_text} is already included")
    
    # mm = re.match(ref_file_name.replace(r"\\", r"\\"), root)
    
    # then copy 
    copied_path = shutil.copy2(ref_full_name,dest_full_name)
    
    print(f"returned: {copied_path}")

