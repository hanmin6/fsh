#!/usr/bin/env python3
"""Dependency-free MCP stdio adapter for the narrow Muse CRM HTTP gateway.

Run with --config /private/path/muse-crm.json, or CRM_API_URL,
FUSANHE_AGENT_KEY and FUSANHE_AGENT_TOKEN environment variables.
Only JSON-RPC messages go to stdout. Tokens never appear in tool results.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


def string(maximum=255, **kwargs):
    return {'type': 'string', 'maxLength': maximum, **kwargs}


def schema(properties, required=(), **kwargs):
    return {'type': 'object', 'properties': properties, 'required': list(required),
            'additionalProperties': False, **kwargs}


TOOLS = [
    {'name': 'crm_search_prospects', 'description': 'Search CRM prospects by stable source ID, email, phone or name.',
     'annotations': {'readOnlyHint': True, 'openWorldHint': False},
     'inputSchema': schema({'sourceId': string(191), 'email': string(), 'phone': string(100),
                            'name': string(), 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 25}},
                           anyOf=[{'required': [k]} for k in ['sourceId', 'email', 'phone', 'name']])},
    {'name': 'crm_upsert_prospect', 'description': 'Create or update a prospect with source provenance. Use a stable sourceId; never invent customers.',
     'annotations': {'readOnlyHint': False, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False},
     'inputSchema': schema({'sourceId': string(191), 'sourceAccount': string(191),
                            'sourceUrl': string(), 'campaignKey': string(191),
                            'displayName': string(), 'company': string(), 'email': string(),
                            'phone': string(100), 'country': string(100), 'notes': string(10000),
                            'contactPolicy': string(enum=['unknown', 'allowed', 'optedOut', 'restricted'])},
                           ['sourceId'], anyOf=[{'required': [k]} for k in ['displayName', 'company', 'email']])},
    {'name': 'crm_record_activity', 'description': 'Record supplied outreach content or inbound activity in CRM. This does not send messages; deliveryStatus must reflect the actual result.',
     'annotations': {'readOnlyHint': False, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False},
     'inputSchema': schema({'sourceId': string(191), 'sourceAccount': string(191),
                            'messageExternalId': string(191), 'conversationExternalId': string(191),
                            'body': string(20000), 'subject': string(), 'senderName': string(),
                            'channelAccountId': string(191),
                            'channelType': string(enum=['Alibaba', 'MadeInChina', 'Website', 'Email', 'WhatsApp', 'Other']),
                            'direction': string(enum=['inbound', 'outbound']),
                            'deliveryStatus': string(enum=['queued', 'sending', 'sent', 'delivered', 'failed', 'mockSent', 'received']),
                            'sentAt': string(40), 'language': string(20),
                            'contactPolicy': string(enum=['unknown', 'allowed', 'optedOut', 'restricted'])},
                           ['sourceId', 'messageExternalId', 'body'])},
]
ROUTES = {'crm_search_prospects': ('GET', 'muse/prospects'),
          'crm_upsert_prospect': ('POST', 'muse/prospect'),
          'crm_record_activity': ('POST', 'muse/activity')}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Agent headers must never follow a redirect to a different endpoint.
        return None


class Gateway:
    def __init__(self, config):
        self.base = config.get('CRM_API_URL', 'https://gzfusanhesp.com/api/v1').rstrip('/')
        parsed = urllib.parse.urlsplit(self.base)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('CRM URL must not contain credentials, query or fragment')
        if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost', '::1')):
            raise ValueError('CRM requires HTTPS or loopback HTTP')
        self.key = config.get('FUSANHE_AGENT_KEY', '')
        self.token = config.get('FUSANHE_AGENT_TOKEN', '')
        if not self.key or not self.token:
            raise ValueError('Agent credential configuration is missing')
        self.http = urllib.request.build_opener(NoRedirect())

    def call(self, name, arguments):
        method, route = ROUTES[name]
        specification = next(t['inputSchema'] for t in TOOLS if t['name'] == name)
        if not isinstance(arguments, dict) or set(arguments) - set(specification['properties']):
            raise ValueError('Unsupported tool arguments')
        for field in specification['required']:
            if not isinstance(arguments.get(field), str) or not arguments[field].strip():
                raise ValueError('Required tool field missing: ' + field)
        for key, value in arguments.items():
            rule = specification['properties'][key]
            if rule['type'] == 'string':
                if not isinstance(value, str) or len(value) > rule['maxLength'] or ('enum' in rule and value not in rule['enum']):
                    raise ValueError('Invalid tool field: ' + key)
            elif type(value) is not int or not rule['minimum'] <= value <= rule['maximum']:
                raise ValueError('Invalid tool field: ' + key)
        if 'anyOf' in specification and not any(arguments.get(x['required'][0], '').strip() for x in specification['anyOf']):
            raise ValueError('At least one search or profile field is required')
        url = self.base + '/Fusanhe/' + route
        data = None
        if method == 'GET':
            url += '?' + urllib.parse.urlencode(arguments)
        else:
            data = json.dumps(arguments, ensure_ascii=False).encode()
        request = urllib.request.Request(url, data, {
            'X-Agent-Key': self.key, 'X-Agent-Token': self.token,
            'X-Request-Id': 'mcp-' + uuid.uuid4().hex, 'Content-Type': 'application/json'}, method=method)
        try:
            with self.http.open(request, timeout=45) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise ValueError('CRM rejected request (HTTP %s); check credential, permissions and fields' % exc.code) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ValueError('CRM connection failed; no automatic retry was performed') from None


def dispatch(message, gateway):
    method, params = message.get('method'), message.get('params') or {}
    if method == 'initialize':
        supported = ['2024-11-05', '2025-03-26', '2025-06-18', '2025-11-25']
        version = params.get('protocolVersion')
        return {'protocolVersion': version if version in supported else supported[-1],
                'capabilities': {'tools': {}}, 'serverInfo': {'name': 'fusanhe-crm', 'version': '1.0.0'},
                'instructions': 'CRM tools store customer data and activity only. Never report queued content as delivered.'}
    if method == 'ping':
        return {}
    if method == 'tools/list':
        return {'tools': TOOLS}
    if method == 'tools/call':
        name = params.get('name')
        if name not in ROUTES:
            return {'content': [{'type': 'text', 'text': 'Unknown CRM tool'}], 'isError': True}
        try:
            result = gateway.call(name, params.get('arguments', {}))
            return {'content': [{'type': 'text', 'text': json.dumps(result, ensure_ascii=False)}], 'isError': False}
        except ValueError as exc:
            return {'content': [{'type': 'text', 'text': str(exc)}], 'isError': True}
    raise LookupError('Method not found')


def main():
    if hasattr(sys.stdin, 'reconfigure'):
        sys.stdin.reconfigure(encoding='utf-8')
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path)
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text()) if args.config else os.environ
        gateway = Gateway(config)
    except (ValueError, OSError, AttributeError):
        print('CRM MCP configuration is invalid or missing', file=sys.stderr)
        return 1
    for line in sys.stdin:
        ident = None
        try:
            if len(line.encode()) > 131072:
                raise ValueError('Message exceeds limit')
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError('Expected JSON-RPC object')
            if 'id' not in message:
                continue
            ident = message['id']
            result = dispatch(message, gateway)
            response = {'jsonrpc': '2.0', 'id': ident, 'result': result}
        except LookupError:
            response = {'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32601, 'message': 'Method not found'}}
        except (ValueError, TypeError, AttributeError):
            response = {'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32600, 'message': 'Invalid request'}}
        print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
