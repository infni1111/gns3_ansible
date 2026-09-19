#!/usr/bin/env python3
# console_exec.py — petit client console GNS3 (telnet brut) sans pexpect.
# Se connecte à <hôte>:<port>, envoie une liste de commandes, lit la sortie.
# Usage : console_exec.py [--host H] [--wait S] <port> "cmd1" "cmd2" ...
#   --host : hôte qui expose les consoles GNS3 (défaut 127.0.0.1)
#   --wait : secondes d'attente après chaque commande (défaut 1.2) — à monter
#            pour les commandes lentes (ip dhcp, ping…)
# Conçu pour les consoles "shell" (nœuds Docker, VPCS). Best-effort : on lit ce qui vient.

import argparse, socket, sys, time

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--wait", type=float, default=1.2)
    p.add_argument("port", type=int)
    p.add_argument("cmds", nargs="*")
    args = p.parse_args()

    s = socket.create_connection((args.host, args.port), timeout=5)
    s.settimeout(2.0)

    def drain():
        out = b""
        try:
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                out += chunk
        except socket.timeout:
            pass
        return out

    # réveiller le shell
    s.sendall(b"\n")
    time.sleep(0.5)
    drain()
    for c in args.cmds:
        s.sendall(c.encode() + b"\n")
        time.sleep(args.wait)
        data = drain()
        sys.stdout.write(data.decode(errors="replace"))
        sys.stdout.flush()
    s.close()

if __name__ == "__main__":
    main()
