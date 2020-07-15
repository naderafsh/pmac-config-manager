TOP = ../..
ifdef EPICS_HOST_ARCH
include $(TOP)/configure/CONFIG
#----------------------------------------
#  ADD MACRO DEFINITIONS AFTER THIS LINE

# Copy all pmc files into data directory
#Not sure how to get the following rule to work so have created another one below
#DATA += $(patsubst ../%, %, $(wildcard ../*.pmc))

include $(TOP)/configure/RULES

pmcs:
	-@$(INSTALL_PRODUCT) -d -m 555 ../*.pmc $(TOP)/data

buildInstall: pmcs

endif



