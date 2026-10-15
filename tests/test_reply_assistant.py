import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class ReplyAssistantContract(unittest.TestCase):
    def test_route_is_authenticated_and_acl_precedes_provider(self):
        routes = json.loads((ROOT / 'custom/Espo/Custom/Resources/routes.json').read_text())
        route = next(r for r in routes if r['route'] == '/Fusanhe/reply-assistant')
        self.assertEqual(route['method'], 'post')
        self.assertFalse(route.get('noAuth', False))
        action = (ROOT / 'custom/Espo/Custom/Tools/Fusanhe/Api/PostReplyAssistant.php').read_text()
        self.assertLess(action.index("requireScope('AIReplyDraft', 'create')"), action.index('->handle('))
        self.assertNotIn("$error->getMessage()", action)

    def test_provider_is_ephemeral_and_never_sends(self):
        code = (ROOT / 'custom/Espo/Custom/Tools/Fusanhe/ReplyAssistant.php').read_text()
        for forbidden in ('file_put_contents', 'error_log(', 'OutboundTask', 'createEntity', '->mock('):
            self.assertNotIn(forbidden, code)
        self.assertIn('getimagesizefromstring', code)
        self.assertIn('base64_decode', code)
        self.assertIn('CURLOPT_FOLLOWLOCATION => false', code)

    def test_ui_does_not_persist_materials(self):
        code = (ROOT / 'client/custom/ui/src/reply-assistant.tsx').read_text()
        for forbidden in ('localStorage', 'sessionStorage', 'useStored', '/approve'):
            self.assertNotIn(forbidden, code)
        self.assertIn('manual-draft', code)

if __name__ == '__main__':
    unittest.main()
