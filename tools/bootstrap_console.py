#!/usr/bin/env python3
# tools/bootstrap_console.py
#
# Première connexion à la console telnet d'un MikroTik CHR sous GNS3, pour le
# préparer à une prise en main Ansible (SSH). C'est l'étape "phase 1 / bootstrap".
#
# Pourquoi un script dédié (et pas le module ansible.builtin.expect) ?
#   - On doit gérer le séquencement du boot (réveiller la console, réessayer).
#   - CHR 7.x FORCE un changement de mot de passe au 1er login : sans ça, SSH
#     refuse la connexion. Il faut donc poser un mot de passe ici.
#   - RouterOS pollue le flux avec des séquences ANSI ; pexpect avec des motifs
#     tolérants et un log de session complet est bien plus robuste et débogable.
#
# Deux modes :
#   observe    -> te branche sur la console en interactif pour CAPTURER la
#                 séquence exacte de TON image (à faire en premier, une fois).
#   bootstrap  -> joue la séquence automatiquement : login, mot de passe,
#                 licence, IP de management, activation SSH.
#
# Prérequis :  pip install pexpect   +   le binaire `telnet`
#
# Exemples :
#   python3 tools/bootstrap_console.py observe   --port 5000
#   python3 tools/bootstrap_console.py bootstrap --port 5000 \
#           --mgmt-ip 192.168.100.11 --prefix 24 --new-password 'Lab123!'

import argparse
import sys
import time

try:
    import pexpect
except ImportError:
    sys.exit("pexpect manquant -> pip install pexpect")


def spawn_console(host: str, port: int, logfile=None):
    """Ouvre la console telnet et réveille le prompt."""
    child = pexpect.spawn(f"telnet {host} {port}", encoding="utf-8", timeout=15)
    if logfile:
        child.logfile_read = logfile          # tout ce qu'on REÇOIT est tracé
    time.sleep(1)
    child.send("\r")                          # réveiller la console
    return child


# ---------------------------------------------------------------------------
# Mode OBSERVE — à lancer EN PREMIER pour voir la vraie séquence de ton image.
# ---------------------------------------------------------------------------

def mode_observe(args):
    print(f"[observe] Connexion console -> {args.host}:{args.port}")
    print("[observe] Tu es en interactif. Loggue-toi À LA MAIN et note :")
    print("          - le prompt exact de login / mot de passe")
    print("          - si un changement de mot de passe est exigé (7.x)")
    print("          - la bannière de licence éventuelle")
    print("          - le prompt final (ex: '[admin@MikroTik] >')")
    print("[observe] Ctrl-] puis 'quit' (ou Ctrl-\\) pour sortir de telnet.\n")
    child = spawn_console(args.host, args.port)
    child.interact()                          # te rend la main, clavier <-> console


# ---------------------------------------------------------------------------
# Mode BOOTSTRAP — séquence automatique.
# Les motifs sont volontairement TOLÉRANTS (sous-chaînes, casse souple) pour
# résister aux séquences ANSI. Ajuste-les avec ce que `observe` t'a montré.
# ---------------------------------------------------------------------------

PROMPT = r"\]\s*>"          # prompt RouterOS loggué : "[admin@nom] >"


def expect_any(child, patterns, timeout):
    """expect() tolérant qui retourne l'index du motif vu, ou -1 sur timeout."""
    try:
        return child.expect(patterns, timeout=timeout)
    except pexpect.TIMEOUT:
        return -1
    except pexpect.EOF:
        sys.exit("[bootstrap] Connexion fermée par l'hôte (EOF). Nœud démarré ?")


def do_login(child, user, old_password, new_password):
    """Gère login + changement de mot de passe forcé + bannière licence."""
    # Réessaie de réveiller le login tant qu'on ne l'a pas (boot pas fini).
    for attempt in range(6):
        idx = expect_any(child, [r"[Ll]ogin:", PROMPT], timeout=15)
        if idx == 0:
            break
        if idx == 1:
            print("[bootstrap] Déjà loggué.")
            return
        print(f"[bootstrap] Pas encore de prompt login (essai {attempt+1})...")
        child.send("\r")
    else:
        sys.exit("[bootstrap] Aucun prompt de login : le nœud a-t-il fini de booter ?")

    child.sendline(user)
    expect_any(child, [r"[Pp]assword:"], timeout=10)
    child.sendline(old_password)

    # Après le mot de passe, plusieurs chemins possibles. On boucle sur les
    # invites connues jusqu'à atteindre le prompt loggué.
    for _ in range(8):
        idx = expect_any(child, [
            r"new password",          # 0 : changement de mot de passe forcé
            r"repeat new password",   # 1
            r"license\? \[Y/n\]",     # 2 : bannière licence
            r"[Pp]assword:",          # 3 : redemande (mauvais mot de passe ?)
            PROMPT,                   # 4 : on est arrivé
        ], timeout=12)

        if idx == 0:
            child.sendline(new_password)
        elif idx == 1:
            child.sendline(new_password)
        elif idx == 2:
            child.sendline("n")
        elif idx == 3:
            child.sendline(old_password)
        elif idx == 4:
            print("[bootstrap] Login OK, prompt atteint.")
            return
        else:
            sys.exit("[bootstrap] Bloqué après le mot de passe (voir le log de session).")
    sys.exit("[bootstrap] Trop d'invites inattendues au login.")


def push_config(child, mgmt_ip, prefix, iface, new_password):
    """Pose l'IP de management, active SSH, fige le mot de passe."""
    cmds = [
        f"/ip address add address={mgmt_ip}/{prefix} interface={iface}",
        "/ip service enable ssh",
        f"/user set admin password={new_password}",
        "/ip address print",
    ]
    for cmd in cmds:
        child.sendline(cmd)
        idx = expect_any(child, [PROMPT], timeout=10)
        if idx != 0:
            print(f"[bootstrap] Pas de retour au prompt après : {cmd}")
    print(f"[bootstrap] Config posée : {mgmt_ip}/{prefix} sur {iface}, SSH actif.")


def mode_bootstrap(args):
    print(f"[bootstrap] Console -> {args.host}:{args.port}")
    # Log complet de la session : indispensable pour déboguer une séquence ANSI.
    logfile = open(args.log, "w", encoding="utf-8") if args.log else sys.stdout
    child = spawn_console(args.host, args.port, logfile=logfile)

    do_login(child, args.user, args.old_password, args.new_password)
    push_config(child, args.mgmt_ip, args.prefix, args.iface, args.new_password)

    child.sendline("/quit")
    print("[bootstrap] Terminé. Teste maintenant :")
    print(f"            ssh {args.user}@{args.mgmt_ip}")


def main():
    p = argparse.ArgumentParser(description="Bootstrap console MikroTik pour Ansible")
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--host", default="localhost", help="hôte console GNS3")
    common.add_argument("--port", type=int, required=True, help="port console GNS3")

    po = sub.add_parser("observe", parents=[common], help="capturer la séquence à la main")
    po.set_defaults(func=mode_observe)

    pb = sub.add_parser("bootstrap", parents=[common], help="jouer la séquence auto")
    pb.add_argument("--mgmt-ip", dest="mgmt_ip", required=True)
    pb.add_argument("--prefix", type=int, default=24)
    pb.add_argument("--iface", default="ether1")
    pb.add_argument("--user", default="admin")
    pb.add_argument("--old-password", dest="old_password", default="")
    pb.add_argument("--new-password", dest="new_password", required=True)
    pb.add_argument("--log", default=None, help="fichier de log de session (debug)")
    pb.set_defaults(func=mode_bootstrap)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
