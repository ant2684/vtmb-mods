"""Read-only UP KeyValues inspection; duplicate mappings/sections are preserved."""
import argparse
import json
import re
from pathlib import Path


def parse(text):
    # Consume comments as tokens, without removing // inside quoted values.
    pattern = r'//[^\r\n]*|"([^"\r\n]*)"|([{}])|([^\s{}"]+)'
    tokens = []
    for match in re.finditer(pattern, text):
        groups = match.groups()
        if any(value is not None for value in groups):
            tokens.append(next(value for value in groups if value is not None))
    def block(index, nested=False):
        rows = []
        while index < len(tokens):
            key = tokens[index]
            index += 1
            if key == '{':
                raise ValueError('Unexpected opening brace')
            if key == '}':
                if not nested:
                    raise ValueError('Unexpected closing brace')
                return rows, index
            if index >= len(tokens):
                raise ValueError('Missing value')
            if tokens[index] == '{':
                value, index = block(index + 1, True)
            else:
                value = tokens[index]
                if value == '}':
                    raise ValueError('Missing value before closing brace')
                index += 1
            rows.append((key, value))
        if nested:
            raise ValueError('Missing closing brace')
        return rows, index
    return block(0)[0]


def children(rows, name):
    return [value for key, value in rows if key == name and isinstance(value, list)]


def values(rows):
    return {key: value for key, value in rows if isinstance(value, str)}


def descendants(rows, name):
    for key, value in rows:
        if isinstance(value, list):
            if key == name:
                yield value
            yield from descendants(value, name)


def templates(system):
    found = {}
    for path in sorted(system.glob('npctemplate*.txt')):
        for body in descendants(parse(path.read_text(encoding='cp1252')), 'ClanData'):
            text = children(body, 'Text')
            if not text:
                continue
            identity = values(text[0])
            name = identity.get('TemplateName')
            if name in ['Werewolf', 'SheriffMan', 'ManBat', 'MingXiao', 'MingXiaoProxy']:
                found[name] = {'file': path.name, **identity,
                               'sections': {key: values(value) for key, value in body
                                            if isinstance(value, list)}}
    return found


def disciplines(system):
    found = []
    for path in sorted(system.glob('disciplinetgt_00[0-4].txt')):
        for body in descendants(parse(path.read_text(encoding='cp1252')), 'DisciplineTgt'):
            direct = values(body)
            hits = {key: value for key, value in body
                    if key.startswith('Hit_') and isinstance(value, list)}
            # Keep all mapping rules: explicit CharTemplate rules can precede
            # and override a strata selection; don't flatten to a global flag.
            mappings = list(descendants(body, 'Affects_Table'))
            found.append({'file': path.name, **direct, 'mappings': mappings,
                          'hit_tables': hits})
    return found


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('system', type=Path)
    args = parser.parse_args()
    print(json.dumps({'templates': templates(args.system),
                      'disciplines': disciplines(args.system)}, indent=2))
