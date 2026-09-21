There are 5 top level directories in this repository


- flow_simulator:
    Contains code for generating network, flow traces
    via custom simulator written in Python

- localization:
    Contains inference algorithms for various fault localization systems

- ns3:
    Contains code for generating network/flow traces
    via ns3 simulations

- hw_traces:
    Contains traces for failure scenarios created in a testbed

- flow_probe:
    Contains code for agent that collects flow statistics at end-host


Windows / VS Code setup
-----------------------

The C++ and ns-3 components require a Linux toolchain. On Windows, install
WSL2 with Ubuntu, then open this folder using "Remote-WSL: Reopen Folder in
WSL" in VS Code. Run the task "FaultLocalization: setup WSL" once. It installs
GCC, GDB, sparsehash, Python, and the Python dependencies.

After setup, use these VS Code tasks:

    - FaultLocalization: build C++ localization
    - FaultLocalization: build ns-3

The C++ debugger configuration is named "C++: reproduce_results". The ns-3
sample can be started with the task "FaultLocalization: run ns-3 example".



