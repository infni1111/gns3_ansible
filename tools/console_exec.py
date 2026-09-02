#!/usr/bin/env python3
# console_exec.py — petit client console GNS3 (telnet brut) sans pexpect.
# Se connecte à localhost:<port>, envoie une liste de commandes shell, lit la sortie.
# Usage : console_exec.py <port> "cmd1" "cmd2" ...
# Conçu pour les nœuds Docker (console = shell). Best-effort : on lit ce qui vient.

import socket, sys, time

def main():
    port = int(sys.argv[1])
    cmds = sys.argv[2:]
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
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
    for c in cmds:
        s.sendall(c.encode() + b"\n")
        time.sleep(1.2)
        data = drain()
        sys.stdout.write(data.decode(errors="replace"))
        sys.stdout.flush()
    s.close()

if __name__ == "__main__":
    main()
