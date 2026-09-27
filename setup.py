"""Generate local-only credentials; never overwrite an existing environment."""
from pathlib import Path
import secrets

if __name__ == '__main__':
    target = Path(__file__).resolve().parent / '.env'
    template = target.with_name('.env.example').read_text(encoding='utf-8')
    for name in ['POSTGRES_PASSWORD', 'ADMIN_TOKEN', 'READER_TOKEN']:
        template = template.replace(f'{name}=\n', f'{name}={secrets.token_urlsafe(36)}\n')
    with target.open('x', encoding='utf-8') as file:
        file.write(template)
    print('Created .env. Use ADMIN_TOKEN or READER_TOKEN from that file to sign in locally.')
