"""Command line entry point."""
import argparse
import json
import sys
from . import __version__
from .audit import audit


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, self.prog + ': error: ' + message + '\n')


def main(argv=None):
    parser = Parser()
    parser.add_argument('--version', action='version', version=__version__)
    sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('audit')
    command.add_argument('repo', nargs='?', default='.')
    command.add_argument('--fail-on', choices=('high', 'medium'), default='high')
    command.add_argument('--ignore', action='append', default=[])
    command.add_argument('--json', action='store_true')
    command.add_argument('--verbose', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = audit(args.repo, args.ignore, args.fail_on)
    except (OSError, UnicodeError, ValueError, SyntaxError) as error:
        print(str(error), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result['verdict'])
        for finding in result['findings']:
            print(f"{finding['severity']} {finding['rule']}: {finding['message']}")
        if args.verbose:
            for category in ('production_evidence', 'test_evidence'):
                for item in result[category]:
                    print(f"{category}: {item['path']}:{item['line']} {item['route']}")
    return 2 if result['verdict'] == 'FAIL' else 0


if __name__ == '__main__':
    sys.exit(main())
