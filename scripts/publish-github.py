"""Publish this standalone repository after GitHub CLI authentication.

Default visibility is private. Existing unrelated remote repositories are never overwritten.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', default='kindle-dashboard')
    parser.add_argument('--visibility', choices=['private', 'public'], default='private')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9._-]+', args.name): parser.error('Invalid repository name')
    gh = shutil.which('gh')
    portable = ROOT / '.tools/gh/gh.exe'
    if not gh and portable.is_file(): gh = str(portable)
    if not gh: parser.error('Install GitHub CLI and run gh auth login --scopes workflow first')
    def command(parts, **kwargs): return subprocess.run(parts, cwd=ROOT, check=True, text=True, **kwargs)
    command([gh, 'auth', 'status'])
    top = command(['git', 'rev-parse', '--show-toplevel'], capture_output=True).stdout.strip()
    if Path(top).resolve() != ROOT: parser.error('Refusing to publish the parent workspace')
    if command(['git', 'status', '--porcelain'], capture_output=True).stdout:
        parser.error('Commit the reviewed project first; working tree must be clean')
    login = json.loads(command([gh, 'api', 'user'], capture_output=True).stdout)['login']
    repository = f'{login}/{args.name}'
    remote = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=ROOT, capture_output=True, text=True)
    expected = f'https://github.com/{repository}.git'
    if remote.returncode == 0:
        if remote.stdout.strip() not in (expected, expected[:-4]): parser.error('Existing origin differs from requested destination')
        command(['git', 'push', '-u', 'origin', 'main'])
    else:
        command([gh, 'repo', 'create', repository, '--'+args.visibility, '--source', str(ROOT), '--remote', 'origin', '--push',
                 '--description', 'A customizable e-ink dashboard for jailbroken Kindles: NAS rendering, widgets, Markdown and offline pages'])
    print(f'https://github.com/{repository}')
    print(f'Watch checks and container publication: {gh} run list --repo {repository}')


if __name__ == '__main__': main()
