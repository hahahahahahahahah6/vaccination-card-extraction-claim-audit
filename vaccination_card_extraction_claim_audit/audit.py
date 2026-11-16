"""Offline phrase matching and module-local source evidence."""
import ast
import os
from pathlib import Path
import re
import tokenize

from .phrases import VACCINATIONCARDEXTRACTION, NOVACCINATIONCARDEXTRACTION, GENERIC_NAMES


def normalize(text):
    return ' '.join(text.lower().replace("n't", ' not').replace('-', ' ').split())


def _matches(text, phrases):
    occupied = set()
    found = []
    for phrase in sorted(phrases, key=lambda p: (-len(p), p)):
        for match in re.finditer(r'\b' + re.escape(phrase) + r'\b', text):
            span = set(range(match.start(), match.end()))
            if not occupied.intersection(span):
                occupied.update(span)
                found.append((phrase, match.start(), match.end()))
    return found


def match_phrases(text):
    text = normalize(text)
    denials = _matches(text, NOVACCINATIONCARDEXTRACTION)
    chars = list(text)
    for _, start, end in denials:
        chars[start:end] = ' ' * (end - start)
    return _matches(''.join(chars), VACCINATIONCARDEXTRACTION), denials


def paragraphs(text):
    fence = None
    lines = []
    start = 1
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        if marker:
            if lines:
                yield start, '\n'.join(lines)
                lines = []
            fence = marker[1]
        elif not line.strip():
            if lines:
                yield start, '\n'.join(lines)
                lines = []
        else:
            if not lines:
                start = number
            lines.append(line)
    if lines:
        yield start, '\n'.join(lines)


def source_evidence(text):
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []
    nodes = list(ast.walk(tree))
    imports = {}
    gate = False
    shadow = set()
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            shadow.add(node.name)
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
                gate |= alias.name.startswith(('azure.ai.formrecognizer', 'azure.ai.documentintelligence'))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            gate |= any((module + '.' + x.name).startswith(('azure.ai.formrecognizer', 'azure.ai.documentintelligence')) for x in node.names)
            for alias in node.names:
                imports[alias.asname or alias.name] = module + '.' + alias.name
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            targets = [item.optional_vars for item in node.items if item.optional_vars]
        for target in targets:
            for child in ast.walk(target):
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                    shadow.add(child.id)
    def resolved(name):
        return imports.get(name, '') if name not in shadow else ''
    calls = [node for node in nodes if isinstance(node, ast.Call)]
    clients, analyzes, evidence = [], [], []
    for call in calls:
        func = call.func
        if isinstance(func, ast.Name):
            route = resolved(func.id).rsplit('.', 1)[-1]
            if route in GENERIC_NAMES and route not in shadow:
                evidence.append({'route': 'generic-vaccination-card', 'line': call.lineno})
            if resolved(func.id) in {'azure.ai.formrecognizer.DocumentAnalysisClient', 'azure.ai.documentintelligence.DocumentIntelligenceClient'} and route not in shadow:
                clients.append(call)
        elif isinstance(func, ast.Attribute):
            if func.attr in GENERIC_NAMES and func.attr not in shadow:
                evidence.append({'route': 'generic-vaccination-card', 'line': call.lineno})
            base = func.value
            while isinstance(base, ast.Attribute):
                base = base.value
            if func.attr in {'DocumentAnalysisClient', 'DocumentIntelligenceClient'} and func.attr not in shadow and isinstance(base, ast.Name) and resolved(base.id).split('.')[0] == 'azure':
                clients.append(call)
            if func.attr in {'begin_analyze_document', 'begin_analyze_document_from_url'} and func.attr not in shadow:
                args = call.args[:1] + [kw.value for kw in call.keywords if kw.arg == 'model_id']
                if any(isinstance(arg, ast.Constant) and arg.value == 'prebuilt-vaccinationCard' for arg in args):
                    analyzes.append(call)
    if gate and clients:
        evidence.extend({'route': 'azure-vaccination-card', 'line': call.lineno} for call in analyzes)
    return sorted(evidence, key=lambda item: (item['line'], item['route']))


def audit(repo='.', ignore=(), fail_on='high'):
    root = Path(repo)
    if not root.is_dir() or not root.stat().st_mode & 0o444 or not root.stat().st_mode & 0o111:
        raise OSError('Root must be a readable directory: ' + str(root))
    positive, negative, production, tests = [], [], [], []
    prefixes = []
    for prefix in ignore:
        parts = Path(prefix).parts
        if Path(prefix).is_absolute() or '..' in parts:
            raise ValueError('Ignore prefixes must be relative paths without parent traversal')
        prefixes.append(parts)

    def ignored(parts):
        return any(parts[:len(prefix)] == prefix for prefix in prefixes)

    def walk_error(error):
        raise error
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        base = Path(directory)
        dirs[:] = sorted(d for d in dirs if not (base / d).is_symlink() and not ignored((base / d).relative_to(root).parts))
        for filename in sorted(files):
            path = base / filename
            relative = path.relative_to(root)
            label = relative.as_posix()
            if path.is_symlink() or ignored(relative.parts):
                continue
            if label == 'README.md' or (path.suffix == '.md' and 'docs' in relative.parts):
                for line, paragraph in paragraphs(path.read_text(encoding='utf-8')):
                    yes, no = match_phrases(paragraph)
                    positive.extend({'path': label, 'line': line, 'phrase': p[0]} for p in yes)
                    negative.extend({'path': label, 'line': line, 'phrase': p[0]} for p in no)
            if path.suffix != '.py' or set(relative.parts[:-1]) & {'fixtures', 'docs', 'examples'}:
                continue
            try:
                with tokenize.open(path) as stream:
                    evidence = source_evidence(stream.read())
            except SyntaxError:
                evidence = []
            target = tests if ('tests' in relative.parts[:-1] or filename.startswith('test_') or filename.endswith('_test.py')) else production
            target.extend(dict(item, path=label) for item in evidence)
    findings = []
    if positive and not production:
        findings.append({'rule': 'documented-vaccination-card-extraction-claim-false', 'severity': 'MEDIUM' if tests else 'HIGH', 'message': 'Documented capability lacks production source evidence.', 'locations': positive})
    if negative and production:
        findings.append({'rule': 'documented-no-vaccination-card-extraction-claim-false', 'severity': 'HIGH', 'message': 'Documented denial conflicts with production source evidence.', 'locations': negative})
    failed = any(f['severity'] == 'HIGH' or fail_on.lower() == 'medium' for f in findings)
    return {'verdict': 'FAIL' if failed else 'PASS', 'findings': findings, 'production_evidence': production, 'test_evidence': tests}
