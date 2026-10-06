"""Explicit per-file recovery decision; does not perform restoration."""
import argparse
from infra.core import Blocked, need, read_json
from infra.gameplay import windows
from infra.session import Transaction


def reconcile(config, relative, sha256, action, reason):
    transaction = Transaction(need(config, 'game_root'), need(config, 'state_root'))
    if not transaction.data:
        raise Blocked('Missing recovery journal')
    transaction.acquire_installation()
    folder = transaction.state / transaction.data['id']
    windows(config, 'Inspect', folder)
    if read_json(folder / 'settings-current.json')['Processes']:
        raise Blocked('Game process present or unverified; no reconciliation')
    transaction.reconcile_file(relative, sha256.upper(), action, reason)
    return {'status': 'RECORDED', 'path': relative, 'action': action, 'next': 'python -m infra.recover --config local.json'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--file', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--action', choices=['keep-current', 'restore-recorded'], required=True)
    parser.add_argument('--reason', required=True)
    args = parser.parse_args()
    print(reconcile(read_json(args.config), args.file, args.sha256, args.action, args.reason))
