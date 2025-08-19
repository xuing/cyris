# CyRIS: Cyber Range Instantiation System

CyRIS is a tool for facilitating cybersecurity training by automating
the creation and management of the corresponding training environments
(a.k.a., cyber ranges) based on a description in YAML format. CyRIS is
being developed by the Cyber Range Organization and Design (CROND)
NEC-endowed chair at the Japan Advanced Institute of Science and
Technology (JAIST).

An overview of the CyRIS workflow is provided below. Based on the
input cyber range description, and a collection of virtual machine
base images, CyRIS performs preparation, content installation and
cloning in order to deploy the cyber range on a given server
infrastructure.

![CyRIS workflow](https://github.com/crond-jaist/cyris/blob/master/cyris_workflow.png "CyRIS workflow")

CyRIS is written in Python, and has various features, including system
configuration, tool installation, incident emulation, content
management, and clone management. If interested, please download the
[latest release](https://github.com/crond-jaist/cyris/releases/) and
let us know if you have any issues; a sample virtual machine base
image and a user guide are also provided for your convenience.

The procedure for installing and configuring CyRIS is rather complex,
therefore you should refer to the User Guide. In particular, the
following issues are to be considered:

* _Hardware requirements_: Hardware vrtualization support, Internet
  connection (optional) -- See Section 3.1 of the User Guide.
* _Software installation_: Host preparation, base image preparation,
  CyRIS configuration -- See Section 3.2 of the User Guide.


## Quick Start

This section provides some basic instructions on how to run a basic
test in order to make sure CyRIS operates correctly. In what follows
we assume that the installation procedure mentioned above was
conducted successfully, and the current directory is the directory
where CyRIS was installed. Please refer to the accompanying User Guide
for details.

### Preliminary checks

Some key issues that must not be forgotten before proceeding to
running CyRIS are:

* The configuration file `CONFIG` needs to reflect your actual CyRIS
  installation, in particular paying attention to the constants below:

  `cyris_path = ...`
  
  `cyber_range_dir = ...`

* The sample KVM base image must be present on the CyRIS host, and the
  content of the file `basevm_small.xml` must reflect the actual
  location of the base image:

  `<source file ='...'/>`

* The content of sample file `examples/basic.yml` should reflect the
  actual host properties, and the actual location of the file
  `basevm_small.xml` in the corresponding sections:

  `mgmt_addr: ...`

  `account: ...`

  `basevm_config_file: ...`

### Basic operation

A typical sequence of operations is as follows:

* Create a cyber range using the basic description edited above:

  `$ main/cyris.py examples/basic.yml CONFIG`

* Check the details regarding the created cyber range:

  `$ cat cyber_range/123/range_details-cr123.yml`

* Check the notification about how to login to the cyber range:

  `$ cat cyber_range/123/range_notification-cr123.txt`

* Try to login into the cyber range:

  `$ ssh trainee01@... -p ...`

* Destroy the cyber range:

  `$ main/range_cleanup.sh 123 CONFIG`

### Recovery from errors

Occasionally an error such as `No route to host` appears. We are
currently investigating its exact cause, but for the moment you should
just destroy the partially created cyber range and repeat the creation
process.

In case you encounter subsequent errors due to mis-configurations, and
the range cleanup command above is insufficient to restore correct
operation, you can also clean up the temporary files via a special
cleanup script (two arguments are required):

  `$ ./destroy_all_cr.sh CYRIS_PATH CYBER_RANGE_PATH`


## References

For a research background about CyRIS, please consult the following
paper:

* R. Beuran, C. Pham, D. Tang, K. Chinen, Y. Tan, Y. Shinoda,
  "Cybersecurity Education and Training Support System: CyRIS", IEICE
  Transactions on Information and Systems, vol. E101-D, no. 3, March
  2018, pp. 740-749.

For the list of contributors, please check the file CONTRIBUTORS.

## Explain by Codex 
Codebase Structure

The repository contains the CyRIS tool which automates cyber‑range creation and management. The introduction in README.md explains that CyRIS takes a YAML description and a set of VM images to perform preparation, content installation and cloning, ultimately deploying ranges on servers.

At the repository root are configuration files and directories for logs and ranges:

CHANGES
CONFIG
CONTRIBUTORS
HOST-PREPARE.sh
README.md
cleanup/
cyber_range/
destroy_all_cr.sh
examples/
instantiation/
logs/
main/
settings/

CONFIG – template configuration for CyRIS paths and gateway settings.

examples/ – sample YAML range descriptions including basic.yml, basic-aws.yml, etc.

cyber_range/, logs/, settings/ – directories that must exist for correct operation

cleanup/ – helper scripts (e.g., downbridges.py) for bridge removal.

destroy_all_cr.sh – removes all created ranges and temporary settings

instantiation/ – shell and Python utilities for tasks such as attack emulation, malware creation and VM cloning

main/ – core Python modules used by the CyRIS command-line interface

Essential Concepts

Main program (main/cyris.py)

Starts by importing modules and AWS support libraries

The CyberRangeCreation class parses command-line arguments and configuration, printing a banner with the current version from CHANGES

Reads the YAML description, instantiates Host, Guest and CloneSetting objects, then orchestrates cloning and configuration tasks.

Configuration Parsing

parse_config.py reads the [config] section of CONFIG, returning paths and gateway options so that cyris.py can locate its directories and know whether to use a gateway host

Entities and Task Modules

entities.py defines classes for hosts, guests, network bridges and instances, allowing the description file to be represented in Python objects

modules.py contains feature classes executed during range creation, such as SSH key setup, user management, package installation, malware deployment and traffic capture generation. Each exposes a command() method used by the orchestrator

Cloning Environment

clone_environment.py implements the VMClone class which generates scripts to create network bridges, clone VMs and configure entry points. It constructs management files for each range instance and provides destruction commands

Range Cleanup

range_cleanup.py performs cleanup of instantiated ranges by executing generated scripts and removing residual KVM domains and network bridges

destroy_all_cr.sh can forcibly remove all range directories and temporary settings if needed.

Quick Start Workflow

The README outlines initial steps: adjust CONFIG, provide the sample base VM, edit examples/basic.yml, then run main/cyris.py with the YAML file and config. After creation you can inspect the range details, log in as the generated trainee account, and clean up with main/range_cleanup.py

Version History

The CHANGES file lists release notes, showing the current version as v1.4 with updates for Ubuntu 24.04 LTS compatibility and previous conversion to Python 3

Overall, CyRIS combines Python scripts and shell utilities to parse a YAML range description, configure virtual machines (either KVM or AWS), deploy custom content, optionally simulate attacks or malware, and manage network settings. The modular design lets tasks be extended via classes under main/modules.py, while clone_environment.py automates cloning and connectivity for multiple hosts and instances. The provided examples and configuration files illustrate how to define a cyber range and execute the creation workflow.
