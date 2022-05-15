pmac-config-manager
A collection of tools for useful forppmac and tpmac configuration management.

for tpmac: download/verify config code directly, without using IDE. With tpmac, the actual config can be saved and will be retained after restart. Therefore these download/verify tools can be fully utilised for a central configuration managrment.

for ppmac: 
Some tools to maintain and autogenerate IDE files, and some capability to directly download PLC codes. 
PowerPmac configuration is fully maintained by the IDE and actual config will reset to last downloaded project, therefore changed PLC codes will be lost after restart. So the only way to makemanage configuration is to make it dynamic, as apply the "application" layer of the config everytime the brick restarts. This is feasible, provided BaseConfig is arranged in a modular arrangement to suppoirt this.