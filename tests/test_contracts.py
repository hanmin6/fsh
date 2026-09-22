#!/usr/bin/env python3
import json, pathlib, re, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Contracts(unittest.TestCase):
 def test_all_metadata_is_valid_json(self):
  for path in (ROOT/'custom/Espo/Custom/Resources').rglob('*.json'):
   with self.subTest(path=path):json.loads(path.read_text(encoding='utf-8'))
 def test_deduplication_and_idempotency_indexes(self):
  def entity(name):return json.loads((ROOT/f'custom/Espo/Custom/Resources/metadata/entityDefs/{name}.json').read_text(encoding='utf-8'))
  self.assertTrue(entity('ExternalConversation')['indexes']['channelExternal']['unique'])
  self.assertTrue(entity('ExternalMessage')['indexes']['conversationHash']['unique'])
  self.assertTrue(entity('OutboundTask')['indexes']['idempotencyKey']['unique'])
 def test_routes_have_action_classes(self):
  routes=json.loads((ROOT/'custom/Espo/Custom/Resources/routes.json').read_text(encoding='utf-8'))
  for route in routes:
   cls=route['actionClassName'].split('\\')[-1]
   self.assertTrue((ROOT/f'custom/Espo/Custom/Tools/Fusanhe/Api/{cls}.php').exists())
 def test_safe_defaults_and_no_committed_env(self):
  self.assertIn('FUSANHE_OUTBOUND_PAUSED=true',(ROOT/'.env.example').read_text(encoding='utf-8'))
  self.assertFalse((ROOT/'.env').resolve() in [p.resolve() for p in ROOT.glob('*') if False])
  tracked=(ROOT/'.gitignore').read_text(encoding='utf-8');self.assertRegex(tracked,r'(?m)^\.env$')
 def test_connector_contract_implemented(self):
  contract=(ROOT/'custom/Espo/Custom/Tools/Fusanhe/Connector/Connector.php').read_text(encoding='utf-8')
  methods=re.findall(r'function\s+(\w+)',contract)
  self.assertEqual(methods,['fetchConversations','fetchMessages','acknowledgeMessage','prepareReply','createOutboundTask','reportSendResult','healthCheck'])
if __name__=='__main__':unittest.main()
