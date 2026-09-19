# GNS3 + Ansible Lab Automation

Tooling to build a GNS3 network lab from code and then configure its devices with Ansible. A small Python SDK wraps the GNS3 REST API (v2) to create projects, nodes and links. An interactive CLI turns a short topology description (`r1`, `s1`, `g1`, ...) into a deployed GNS3 project and writes a matching Ansible inventory. Ansible playbooks then configure the MikroTik CHR routers in two phases: first over the GNS3 telnet console, because a new node has no IP address yet, and then over SSH with the `community.routeros` collection.

## Features

- **Python SDK for the GNS3 API** (`gns3/`): `GNS3Client` (a `requests` session with typed exceptions for 404/409/other HTTP errors and connection failures), plus `GNS3Project`, `GNS3Node`, `GNS3Link` and `GNS3Template`. These cover create/load/delete, start/stop/reload/suspend of nodes, project duplicate/stats, link packet capture, and template search.
- **Topology model and deployer**: `Topology → NodeTopology → Link → Endpoint`. `GNS3Deployer` maps name prefixes to GNS3 templates, resolves template IDs by name (cached), places nodes on a grid, de-duplicates links (A–B equals B–A), and returns a `DeployResult` listing what succeeded and what failed.
- **Dynamic Ansible inventory**: `AnsibleInventory` groups the deployed nodes by prefix (`routers`, `switches`, `firewalls`, `guests`, `clouds`) and exports their GNS3 console host, port and type.
- **Interactive CLI** (`cli/shell.py`): menus to create and deploy a project, inspect an existing project, or delete one.
- **Console bootstrap** (`tools/bootstrap_console.py`): a `pexpect` script that logs into a new CHR over telnet. It handles the forced password change and the licence prompt on RouterOS 7, sets a management IP, enables SSH, and logs the full session. An `observe` mode lets you walk through the login sequence of a new image by hand.
- **Two-phase Ansible configuration**: `site.yml` runs the console bootstrap, then the SSH configuration (sets the system identity and applies optional per-host `router_config_commands`).

## Architecture

```
 cli/shell.py ──► GNS3Deployer ──► GNS3Client ──► GNS3 REST API (:3080/v2)
      │                │                               │
      │                └─ DeployResult                 └─ nodes / links / consoles
      ▼
 AnsibleInventory ──► inventory/gns3_dynamic.yml
                              │
                   ansible-playbook site.yml
            ┌─────────────────┴──────────────────┐
  phase 1: bootstrap_routers.yml       phase 2: configure_routers.yml
  telnet console (pexpect)             SSH, community.routeros
  -> mgmt IP + SSH + password          -> identity + per-host commands
```

The Prefix → template mapping lives in `gns3/deploy.py`: `r` → MikroTik CHR 7.22.1, `s` → Ethernet switch, `f` → FortiGate VM 7.6.6, `g` → VPCS, `c` → Cloud. The templates must exist on the GNS3 server under these exact names.

## Tech stack

Python 3.10+ (`requests`, `PyYAML`, `pexpect`), Ansible (`ansible.netcommon`, `community.routeros`), GNS3 REST API v2, MikroTik RouterOS 7 (CHR).

## Getting started

Prerequisites: a reachable GNS3 server on `http://localhost:3080` with the templates listed above, plus `telnet` on the host.

```bash
pip install requests pyyaml pexpect
ansible-galaxy collection install ansible.netcommon community.routeros
```

1. **Deploy a topology** and generate the inventory:

   ```bash
   python3 cli/shell.py
   ```

   Choose "create a project", enter nodes (e.g. `r1`, `s1`, `g1`) and links (adapter `e`, port number), then confirm. The CLI writes `inventory/gns3_dynamic.yml`, which is the default inventory in `ansible.cfg`.

2. **Start the nodes** in GNS3 (the deployer creates them but does not start them).

3. **Configure the routers**. Change the default lab credentials in `group_vars` first.

   ```bash
   ansible-playbook site.yml                          # both phases
   ansible-playbook playbooks/bootstrap_routers.yml   # phase 1 only (console)
   ansible-playbook playbooks/configure_routers.yml   # phase 2 only (SSH)
   ```

   Management IPs follow a convention: `rN` gets `192.168.100.(10+N)/24` on `ether1` (see `group_vars/all.yml`).

Other entry points:

```bash
python3 tools/bootstrap_console.py observe --port <console-port>     # step through the login by hand
ansible-playbook playbooks/create_project.yml -i inventory/hosts.yml   # create a project via the uri module
ansible-playbook -i inventory/lab_dhcp.yml playbooks/configure_r1_dhcp.yml  # SSH to a CHR that got its IP from DHCP
python3 test_deploy.py                                                # unit + integration checks against a live server
```

## Project layout

```
gns3/            SDK: client, project, node, link, template, deploy, inventory, topology_builder, exceptions
cli/shell.py     interactive CLI (create / open / delete projects)
tools/           bootstrap_console.py (pexpect), console_exec.py (raw-socket console client)
playbooks/       bootstrap_routers, configure_routers, configure_r1_dhcp, create_project
group_vars/      global lab settings, RouterOS connection settings
inventory/       static inventories (the dynamic one is generated)
site.yml         two-phase orchestration
test_*.py        script-style tests and a DHCP lab builder
```

## Status and known limitations

This is a working lab prototype, not a packaged library.

- No `requirements.txt` / packaging. Imports rely on running from the repository root.
- `playbooks/create_nodes.yml` and `playbooks/create_links.yml` are empty placeholders. Nodes and links are created by the Python deployer.
- Running `configure_routers.yml` on its own needs `ansible_host` for each router. `group_vars/routers.yml` does not set it. In `site.yml` it comes from the phase-1 `set_fact`.
- The management network must be reachable from the Ansible host (e.g. through a GNS3 Cloud node). This is not automated.
- Redeploying into an existing project adds nodes again instead of reconciling them.
- The `w` adapter prefix just maps to adapter index 1.
- `test_*.py` are standalone scripts, not a pytest suite. `test_dhcp_lab.py` creates resources when imported and hard-codes template UUIDs from one specific server.
- The FortiGate template has to be provided separately.
- Code comments and CLI messages are in French.
