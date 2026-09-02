# test_shell.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gns3.topology_builder import run_shell

if __name__ == "__main__":
    topo = run_shell()
    topo.summary()
