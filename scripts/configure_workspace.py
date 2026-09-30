#!/usr/bin/env python3
"""Enable the explicitly public, editable workspace; --disable restores native login.

This grants everyone who can reach the site the shared role's business access.
Run on each deployment after rebuilding custom metadata. No account secrets are printed.
"""
import argparse
import base64
import json
import pathlib
import secrets
import subprocess
import urllib.parse
import urllib.request

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--disable', action='store_true')
args = parser.parse_args()
root = pathlib.Path(__file__).resolve().parents[1]
env = {}
for line in (root / '.env').read_text().splitlines():
    if '=' in line and not line.startswith('#'):
        key, value = line.split('=', 1)
        env[key] = value.strip().strip('\"\'')
base = 'http://localhost:' + env.get('ESPOCRM_PORT', '8080') + '/api/v1/'
headers = {
    'Authorization': 'Basic ' + base64.b64encode((env['ESPOCRM_ADMIN_USERNAME'] + ':' + env['ESPOCRM_ADMIN_PASSWORD']).encode()).decode(),
    'Content-Type': 'application/json',
}
def api(path, method='GET', body=None):
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=headers, method=method)
    with urllib.request.urlopen(req) as response:
        payload = response.read()
        return json.loads(payload) if payload else {}

def find(entity, field, value):
    query = urllib.parse.urlencode({'maxSize': 2, 'where[0][type]': 'equals', 'where[0][attribute]': field, 'where[0][value]': value})
    rows = api(entity + '?' + query).get('list', [])
    if len(rows) > 1:
        raise RuntimeError('Ambiguous workspace record: ' + entity)
    return rows[0] if rows else None

username = 'fusanhe-workspace'
if args.disable:
    api('Settings', 'PUT', {'authenticationMethod': 'Espo'})
    user = find('User', 'userName', username)
    if user:
        api('User/' + user['id'], 'PATCH', {'isActive': False})
else:
    metadata = api('Metadata')
    # All installed ACL scopes start denied; allow only explicitly listed business objects.
    acl = {name: False for name, defs in metadata.get('scopes', {}).items() if defs.get('acl')}
    editable = ['Account', 'Contact', 'Lead', 'Opportunity', 'Task', 'Meeting', 'Call',
                'ExternalConversation', 'ExternalIdentity', 'AIReplyDraft', 'KnowledgeDocument',
                'FusanheProduct', 'FusanheProductSpec', 'FusanheCertificate', 'FusanheSample',
                'FusanheInquiry', 'FusanheQuote', 'FusanheQuoteItem', 'FusanheSalesOrder',
                'FusanheOrderLine', 'FusanheOrderShipment', 'FusanheShipmentItem']
    for name in editable:
        if name in acl:
            acl[name] = {'read': 'all', 'create': 'yes', 'edit': 'all', 'delete': 'no', 'stream': 'all'}
    for name in ['ExternalMessage', 'OutboundTask', 'AutomationAgent']:
        if name in acl:
            acl[name] = {'read': 'all', 'create': 'no', 'edit': 'no', 'delete': 'no', 'stream': 'no'}
    role_data = {'name': '公共工作台业务编辑', 'data': acl, 'fieldData': {},
                 'assignmentPermission': 'all', 'userPermission': 'no', 'portalPermission': 'no',
                 'exportPermission': 'no', 'massUpdatePermission': 'no', 'dataPrivacyPermission': 'no'}
    role = find('Role', 'name', role_data['name'])
    role = api('Role/' + role['id'], 'PATCH', role_data) if role else api('Role', 'POST', role_data)
    user = find('User', 'userName', username)
    if user and user.get('type') != 'regular':
        raise RuntimeError('Workspace username belongs to a non-regular account; refusing to alter it.')
    user_data = {'userName': username, 'lastName': '共享工作台', 'type': 'regular', 'isActive': True,
                 'rolesIds': [role['id']], 'teamsIds': [], 'sendAccessInfo': False}
    if not user:
        password = secrets.token_urlsafe(48)
        user_data.update(password=password, passwordConfirm=password)
    user = api('User/' + user['id'], 'PATCH', user_data) if user else api('User', 'POST', user_data)
    api('Settings', 'PUT', {'authenticationMethod': 'FusanheWorkspace'})
    # Store the fixed account id after Settings writes to avoid a stale PHP config snapshot.
    php = 'require "bootstrap.php"; $a=new Espo\\Core\\Application(); $w=$a->getContainer()->get("injectableFactory")->create(\\Espo\\Core\\Utils\\Config\\ConfigWriter::class); $w->set("fusanheWorkspaceUserId", $argv[1]); $w->save();'
    subprocess.run(['docker', 'compose', 'exec', '-T', 'espocrm', 'php', '-r', php, user['id']], cwd=root, check=True)
subprocess.run(['docker', 'compose', 'exec', '-T', 'espocrm', 'php', '-r',
                'require "bootstrap.php"; $a=new Espo\\Core\\Application(); $a->getContainer()->get("dataManager")->updateAppTimestamp();'], cwd=root, check=True)
print('Public workspace disabled; native login restored.' if args.disable else 'Public editable workspace enabled with a regular business account.')
