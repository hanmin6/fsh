#!/usr/bin/env python3
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ApiContract(unittest.TestCase):
    def test_shared_action_has_acl_and_record_guards(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/Api/AbstractFusanheAction.php").read_text()
        self.assertIn("checkScope", source)
        self.assertIn("checkEntity", source)
        self.assertIn("requireEntityScope", source)

    def test_request_id_is_validated_and_returned(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/Api/AbstractFusanheAction.php").read_text()
        self.assertIn("X-Request-Id", source)
        self.assertIn("random_bytes", source)
        self.assertIn("'requestId' => $requestId", source)

    def test_error_codes_are_stable_and_do_not_expose_exception_messages(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/Api/AbstractFusanheAction.php").read_text()
        for code in ("invalid_request", "forbidden", "not_found", "internal_error"):
            self.assertIn(code, source)
        self.assertNotIn("$error->getMessage()", source)

    def test_global_fusanhe_middleware_correlates_success_errors_and_audit(self):
        middleware = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/Api/FusanheApiMiddleware.php").read_text()
        metadata = (ROOT / "custom/Espo/Custom/Resources/metadata/app/api.json").read_text()
        kernel = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/ServiceKernel.php").read_text()
        self.assertIn("FusanheApiMiddleware", metadata)
        self.assertIn("/Fusanhe/", middleware)
        self.assertIn("withHeader('X-Request-Id'", middleware)
        self.assertIn("RequestContext::set", middleware)
        self.assertIn("RequestContext::requestId", kernel)
        self.assertNotIn("$error->getMessage()", middleware)


if __name__ == "__main__":
    unittest.main()
