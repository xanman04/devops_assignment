"""Validate the system manifest against the unmodified course schema and API paths."""
import ast
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import yaml


ROOT = Path(__file__).resolve().parents[1]


def check():
    schema = json.loads((ROOT / 'system.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    manifest = yaml.safe_load((ROOT / 'system.yaml').read_text(encoding='utf-8'))
    Draft202012Validator(schema).validate(manifest)
    services = manifest['services']
    assert set(manifest['ui']['calls']) == set(services), 'UI must call both services'
    for name, service in services.items():
        for field in ('path', 'openapi', 'migrations'):
            assert (ROOT / service[field]).exists(), f'{name}: missing {field}'
        observed = set()
        for source in (ROOT / service['path']).rglob('*.py'):
            if source.name.startswith('test') or 'migrations' in source.parts:
                continue
            for node in ast.walk(ast.parse(source.read_text(encoding='utf-8'))):
                key = None
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if ast.unparse(node.func.value) == 'os.environ' and node.func.attr in {'get', 'setdefault'} and node.args:
                        key = node.args[0]
                elif isinstance(node, ast.Subscript) and ast.unparse(node.value) == 'os.environ':
                    key = node.slice
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    observed.add(key.value)
        assert not observed - service['env'].keys(), f'{name}: undocumented environment variables: {sorted(observed - service["env"].keys())}'
        for call in service.get('calls', []):
            assert call['service'] in services, 'Unknown peer service'
            assert call['url_env'] in service['env'], 'Undocumented peer URL variable'
            peer = json.loads((ROOT / services[call['service']]['openapi']).read_text(encoding='utf-8'))
            for endpoint in call['endpoints']:
                method, path = endpoint.split(' ', 1)
                assert method.lower() in peer['paths'].get(path, {}), f'Undocumented peer endpoint: {endpoint}'
    print('system.yaml matches the official schema, repository paths, environment reads and peer API operations.')


if __name__ == '__main__':
    check()
