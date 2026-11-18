"""Generate credentials once in separate local Compose volumes. Print no values."""
import os
from pathlib import Path
import re
import secrets

for owner, names in {'sqladmin': ['password'], 'discovery': ['password', 'django-secret'],
                     'groups': ['password', 'django-secret']}.items():
    folder = Path('/secrets') / owner
    folder.mkdir(parents=True, exist_ok=True)
    os.chown(folder, 10001, 10001)
    folder.chmod(0o700)
    for name in names:
        path = folder / name
        if not path.exists():
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as output:
                output.write(secrets.token_urlsafe(48))
        if not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', path.read_text()):
            raise ValueError('An existing local credential file is invalid; refusing to replace it.')
        os.chown(path, 10001, 10001)
        path.chmod(0o600)
print('Local credentials are present; existing values retained.')
