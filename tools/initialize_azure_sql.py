"""CD initial setup inside the Discovery image. Never run from a CI test job."""
import os
import re
import time
import pyodbc


class LoginDenied(RuntimeError):
    pass


def connect(database, user, password):
    host = os.environ['SQL_HOST']
    if not re.fullmatch(r'[a-z0-9-]+\.database\.windows\.net', host):
        raise ValueError('Unexpected Azure SQL host.')
    connection = f'DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={host},1433;DATABASE={database};UID={user};PWD={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=10'
    for attempt in range(18):
        try:
            connected = pyodbc.connect(connection, autocommit=True)
            connected.timeout = 30
            return connected
        except pyodbc.Error as error:
            detail = str(error)
            if ('18456' in detail or '4060' in detail or '916' in detail) and '40613' not in detail:
                raise LoginDenied('SQL login/database permission was denied; credential values withheld.') from None
            if attempt == 17:
                raise RuntimeError('Azure SQL connection/resume failed after bounded retries; credentials are withheld.') from None
            time.sleep(min(5+attempt*2, 15))


def run():
    prefix = os.environ['PREFIX']
    if not re.fullmatch(r'[a-z][a-z0-9-]{2,19}', prefix):
        raise ValueError('Invalid own resource prefix.')
    for service in ('discovery', 'groups'):
        password = os.environ[service.upper()+'_DB_PASSWORD']
        admin_password = os.environ['SQL_ADMIN_PASSWORD']
        if not re.fullmatch(r'[A-Za-z0-9_!\-]{20,128}', password) or not re.fullmatch(r'[A-Za-z0-9_!\-]{20,128}', admin_password):
            raise ValueError('Initial SQL credentials must use the generated bounded character set.')
        database, user = f'{prefix}-{service}-db', 'bassline_'+service
        with connect(database, 'bassline_admin', admin_password) as connection:
            cursor = connection.cursor()
            # Bounded validated password alphabet excludes quote/ODBC delimiters.
            # Existing users are preserved; a mismatch fails the subsequent login.
            cursor.execute(f"IF DATABASE_PRINCIPAL_ID('{user}') IS NULL CREATE USER [{user}] WITH PASSWORD = '{password}';")
            for role in ('db_ddladmin', 'db_datareader', 'db_datawriter'):
                cursor.execute(f"IF IS_ROLEMEMBER('{role}', '{user}') <> 1 ALTER ROLE [{role}] ADD MEMBER [{user}];")
        with connect(database, user, password) as own:
            own.execute('SELECT 1').fetchone()
        other = f'{prefix}-'+('groups' if service == 'discovery' else 'discovery')+'-db'
        try:
            with connect(other, user, password):
                raise RuntimeError('Other-domain login unexpectedly succeeded; deployment stopped.')
        except LoginDenied:
            pass
        print(service+': contained identity verified; other-domain database access denied.')


if __name__ == '__main__':
    try:
        run()
    except pyodbc.Error:
        raise RuntimeError('SQL initial setup failed; database diagnostics and credentials are withheld.') from None
