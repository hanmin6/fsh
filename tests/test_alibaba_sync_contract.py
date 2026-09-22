import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AgentCredentialContract(unittest.TestCase):
    def test_agent_credential_metadata_contract(self):
        metadata = json.loads(
            (
                ROOT
                / "custom/Espo/Custom/Resources/metadata/entityDefs/AutomationAgent.json"
            ).read_text(encoding="utf-8")
        )
        fields = metadata["fields"]

        self.assertEqual(fields["credentialHash"]["type"], "varchar")
        self.assertEqual(fields["credentialHash"]["maxLength"], 255)
        self.assertTrue(fields["credentialHash"]["readOnly"])
        self.assertTrue(fields["credentialHash"]["layoutListDisabled"])
        self.assertTrue(fields["credentialHash"]["layoutMassUpdateDisabled"])
        self.assertEqual(fields["credentialStatus"]["type"], "enum")
        self.assertEqual(fields["credentialStatus"]["options"], ["active", "revoked"])
        self.assertEqual(fields["credentialStatus"]["default"], "active")
        self.assertTrue(fields["credentialStatus"]["displayAsLabel"])
        self.assertEqual(fields["lastCredentialUsedAt"]["type"], "datetime")
        self.assertTrue(fields["lastCredentialUsedAt"]["readOnly"])
        self.assertEqual(fields["clientVersion"]["type"], "varchar")
        self.assertEqual(fields["clientVersion"]["maxLength"], 100)

    def test_agent_authentication_contract(self):
        source = (
            ROOT / "custom/Espo/Custom/Tools/Fusanhe/AutomationAuth.php"
        ).read_text(encoding="utf-8")

        for expected in (
            "assertBootstrap",
            "assertAgent",
            "X-Agent-Key",
            "X-Agent-Token",
            "password_verify",
            "DateTimeImmutable",
            "PT5M",
        ):
            self.assertIn(expected, source)

    def test_registration_is_atomic_and_hash_failures_do_not_persist_agents(self):
        source = (
            ROOT / "custom/Espo/Custom/Tools/Fusanhe/WorkflowService.php"
        ).read_text(encoding="utf-8")
        registration = source.split("public function registerAgent", 1)[1].split(
            "public function heartbeat", 1
        )[0]

        for expected in (
            "getTransactionManager",
            "->forUpdate()",
            "password_hash",
            "$credentialHash === false",
            "$tx->rollback()",
            "Unable to issue agent credential.",
        ):
            self.assertIn(expected, registration)

    def test_agent_actions_require_json_objects(self):
        action_files = (
            "PostAgentRegister.php",
            "PostAgentHeartbeat.php",
            "PostAgentClaim.php",
            "PostTaskSending.php",
            "PostTaskResult.php",
        )
        for filename in action_files:
            source = (
                ROOT / "custom/Espo/Custom/Tools/Fusanhe/Api" / filename
            ).read_text(encoding="utf-8")
            self.assertIn("instanceof \\stdClass", source)
            self.assertIn("BadRequest", source)

    def test_agent_clients_document_bootstrap_and_agent_headers(self):
        script = (ROOT / "scripts/mock-agent.py").read_text(encoding="utf-8")
        runtime_tests = (ROOT / "tests/test_phase1_runtime.py").read_text(encoding="utf-8")
        document = (ROOT / "docs/API_AGENT_HANDOFF.md").read_text(encoding="utf-8")

        for source in (script, runtime_tests, document):
            self.assertIn("X-Automation-Token", source)
            self.assertIn("X-Agent-Key", source)
            self.assertIn("X-Agent-Token", source)
        self.assertIn("agentToken", script)
        self.assertIn("credentialIssued", runtime_tests)
        self.assertIn("最后一次成功轮换", document)

    def test_mock_agent_reuses_environment_credential_or_requires_explicit_rotation(self):
        script = (ROOT / "scripts/mock-agent.py").read_text(encoding="utf-8")
        document = (ROOT / "docs/API_AGENT_HANDOFF.md").read_text(encoding="utf-8")

        for expected in (
            "FUSANHE_AGENT_TOKEN",
            "FUSANHE_ROTATE_AGENT_TOKEN",
            '"rotateCredential": True',
            'post("/Fusanhe/agent/heartbeat", {}, agent_headers)',
            "Configure FUSANHE_AGENT_TOKEN",
        ):
            self.assertIn(expected, script)
        self.assertIn("FUSANHE_AGENT_TOKEN", document)
        self.assertIn("FUSANHE_ROTATE_AGENT_TOKEN=1", document)


class AlibabaSyncMetadataContract(unittest.TestCase):
    def _entity(self, name):
        return json.loads(
            (
                ROOT
                / "custom/Espo/Custom/Resources/metadata/entityDefs"
                / f"{name}.json"
            ).read_text(encoding="utf-8")
        )

    def test_external_conversation_sync_metadata(self):
        fields = self._entity("ExternalConversation")["fields"]

        for field_name in ("sourceCreatedAtRaw", "sourceUpdatedAtRaw"):
            self.assertEqual(fields[field_name]["type"], "varchar")
            self.assertGreaterEqual(fields[field_name]["maxLength"], 64)

        for field_name in ("lastSourceSyncAt", "backfillCompletedAt"):
            self.assertEqual(fields[field_name]["type"], "datetime")
            self.assertTrue(fields[field_name]["readOnly"])

        self.assertEqual(fields["syncError"]["type"], "text")
        self.assertTrue(fields["syncError"]["readOnly"])
        self.assertTrue(fields["syncError"]["layoutListDisabled"])
        self.assertTrue(fields["syncError"]["layoutMassUpdateDisabled"])

    def test_external_message_sync_metadata(self):
        fields = self._entity("ExternalMessage")["fields"]

        self.assertEqual(fields["sourceTimestampRaw"]["type"], "varchar")
        self.assertGreaterEqual(fields["sourceTimestampRaw"]["maxLength"], 64)
        self.assertTrue(fields["sourceTimestampRaw"]["readOnly"])
        self.assertEqual(
            fields["timestampConfidence"],
            {
                "type": "enum",
                "options": ["high", "medium", "low"],
                "default": "low",
                "readOnly": True,
                "layoutListDisabled": True,
                "layoutMassUpdateDisabled": True,
            },
        )
        self.assertEqual(fields["sourceSequence"]["type"], "int")
        self.assertEqual(fields["sourceSequence"]["min"], 1)
        self.assertTrue(fields["sourceSequence"]["readOnly"])
        self.assertEqual(
            fields["messageType"],
            {
                "type": "enum",
                "options": ["initialInquiry", "chat"],
                "default": "chat",
                "readOnly": True,
                "layoutListDisabled": True,
                "layoutMassUpdateDisabled": True,
            },
        )

    def test_automation_audit_request_id_is_nullable_and_unique(self):
        metadata = self._entity("AutomationAudit")
        self.assertEqual(
            metadata["fields"]["requestId"],
            {
                "type": "varchar",
                "maxLength": 64,
                "readOnly": True,
            },
        )
        self.assertTrue(metadata["indexes"]["requestId"]["unique"])

    def test_external_channel_account_is_unique_per_type(self):
        indexes = self._entity("ExternalChannel")["indexes"]
        self.assertEqual(indexes["type"]["columns"], ["type"])
        self.assertEqual(
            indexes["typeAccountHandle"],
            {"columns": ["type", "accountHandle"], "unique": True},
        )

    def test_alibaba_sync_route_is_unauthenticated_post_action(self):
        routes = json.loads(
            (ROOT / "custom/Espo/Custom/Resources/routes.json").read_text(
                encoding="utf-8"
            )
        )
        matching = [route for route in routes if route["route"] == "/Fusanhe/alibaba/sync"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["method"], "post")
        self.assertTrue(matching[0]["noAuth"])
        self.assertEqual(
            matching[0]["actionClassName"],
            "Espo\\Custom\\Tools\\Fusanhe\\Api\\PostAlibabaSync",
        )

    def test_alibaba_sync_action_authenticates_and_validates_json_object(self):
        source = (
            ROOT
            / "custom/Espo/Custom/Tools/Fusanhe/Api/PostAlibabaSync.php"
        ).read_text(encoding="utf-8")
        self.assertIn("AlibabaSyncService", source)
        self.assertIn("assertAgent", source)
        self.assertIn("instanceof \\stdClass", source)
        self.assertIn("BadRequest", source)
        self.assertIn("->sync($body, $agent)", source)


class AlibabaSyncServiceContract(unittest.TestCase):
    def test_sync_service_has_bounded_transactional_import_contract(self):
        source = (
            ROOT / "custom/Espo/Custom/Tools/Fusanhe/AlibabaSyncService.php"
        ).read_text(encoding="utf-8")
        for expected in (
            "syncMode",
            "backfill",
            "incremental",
            "requestId",
            "finalBatch",
            "sourceSequence",
            "timestampConfidence",
            "resolveAutomaticCustomer",
            "AutomationAudit",
            "getTransactionManager",
            "MAX_MESSAGES",
            "MAX_BODY",
            "MAX_BATCH",
        ):
            self.assertIn(expected, source)
        self.assertNotIn("generateDraft", source)
        self.assertNotIn("OutboundTask", source)

    def test_conversation_state_converts_entity_collection_before_sorting(self):
        source = (
            ROOT / "custom/Espo/Custom/Tools/Fusanhe/AlibabaSyncService.php"
        ).read_text(encoding="utf-8")
        self.assertIn("iterator_to_array", source)
        self.assertLess(source.index("iterator_to_array"), source.index("usort("))

    def test_identity_automatic_linking_is_strong_evidence_or_alibaba_lead(self):
        source = (
            ROOT / "custom/Espo/Custom/Tools/Fusanhe/IdentityService.php"
        ).read_text(encoding="utf-8")
        for expected in (
            "resolveAutomaticCustomer",
            "ensureLeadForIdentity",
            "uniqueEmail",
            "uniquePhone",
            "ambiguousNewLead",
            "来源：Alibaba；询价单；身份key",
            "'source' => 'Web Site'",
        ):
            self.assertIn(expected, source)
        self.assertNotIn("createCustomer($identity", source)

    def test_alibaba_payload_uses_canonical_source_fields_and_strict_values(self):
        source = (
            ROOT / "custom/Espo/Custom/Tools/Fusanhe/AlibabaSyncService.php"
        ).read_text(encoding="utf-8")
        for expected in (
            "$conversationInput->country",
            "$conversationInput->createdAtRaw",
            "$conversationInput->updatedAtRaw",
            "$messageInput->sourceTimestampRaw",
            "trim((string) $messageInput->body)",
            "trim((string) ($message->body ?? '')) === ''",
            "is_int($message->sourceSequence)",
            "$identityEmail = $buyerExternalId === '' ? ''",
            "$identityPhone = $buyerExternalId === '' ? ''",
        ):
            self.assertIn(expected, source)
        for forbidden in (
            "$conversationInput->buyerCountry",
            "$conversationInput->sourceCreatedAt",
            "$conversationInput->sourceUpdatedAt",
            "'sourceTimestampRaw' => $rawTimestamp",
        ):
            self.assertNotIn(forbidden, source)

    def test_final_sync_marks_source_even_when_message_batch_is_empty(self):
        source = (
            ROOT / "custom/Espo/Custom/Tools/Fusanhe/AlibabaSyncService.php"
        ).read_text(encoding="utf-8")
        refresh = source.split("private function refreshConversationState", 1)[1]
        self.assertLess(refresh.index("lastSourceSyncAt"), refresh.index("if (!$messages)"))
        self.assertIn("backfillCompletedAt", source)

    def test_sync_replay_is_payload_bound_and_channel_creation_is_locked(self):
        source = (
            ROOT / "custom/Espo/Custom/Tools/Fusanhe/AlibabaSyncService.php"
        ).read_text(encoding="utf-8")
        for expected in (
            "canonicalPayloadHash",
            "payloadHash",
            "'jobId' => $jobId",
            "replayResponse",
            "sameReplay",
            "->forUpdate()->findOne()",
            "is_bool($input->finalBatch)",
            "assertMaxLength",
            "system integration boundary",
        ):
            self.assertIn(expected, source)

    def test_existing_conversation_identity_is_continuous_and_phone_queries_both_forms(self):
        sync_source = (
            ROOT / "custom/Espo/Custom/Tools/Fusanhe/AlibabaSyncService.php"
        ).read_text(encoding="utf-8")
        identity_source = (
            ROOT / "custom/Espo/Custom/Tools/Fusanhe/IdentityService.php"
        ).read_text(encoding="utf-8")
        for expected in (
            "existingConversationIdentity",
            "refreshIntegrationProfile",
            "if ($identity === null)",
        ):
            self.assertIn(expected, sync_source)
        for expected in (
            "phoneCandidates",
            "array_unique([$rawPhone, $normalisedPhone])",
            "normalisePhone",
        ):
            self.assertIn(expected, identity_source)

    def test_sync_validates_profile_and_sender_varchar_character_limits(self):
        source = (
            ROOT / "custom/Espo/Custom/Tools/Fusanhe/AlibabaSyncService.php"
        ).read_text(encoding="utf-8")
        for expected in (
            "'buyerExternalId', 191",
            "'subject', 255",
            "'buyerName', 255",
            "'buyerEmail', 255",
            "'buyerPhone', 100",
            "'country', 100",
            "'senderName', 255",
            "'senderExternalId', 191",
            "mb_strlen($value)",
            "strlen((string) $message->body)",
        ):
            self.assertIn(expected, source)

    def test_sync_requires_nonempty_buyer_name_before_lead_resolution(self):
        source = (
            ROOT / "custom/Espo/Custom/Tools/Fusanhe/AlibabaSyncService.php"
        ).read_text(encoding="utf-8")
        self.assertIn("requiredString($input->conversation, 'buyerName', 255", source)


if __name__ == "__main__":
    unittest.main()
