"""Offline contract checks for the Made-in-China CRM import boundary."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MadeInChinaSyncContract(unittest.TestCase):
    def test_route_uses_agent_auth_and_dedicated_service(self):
        routes = json.loads((ROOT / "custom/Espo/Custom/Resources/routes.json").read_text(encoding="utf-8"))
        route = [row for row in routes if row.get("route") == "/Fusanhe/mic/sync"]
        self.assertEqual(len(route), 1)
        self.assertEqual(route[0]["method"], "post")
        self.assertTrue(route[0]["noAuth"])
        self.assertEqual(route[0]["actionClassName"], "Espo\\Custom\\Tools\\Fusanhe\\Api\\PostMadeInChinaSync")
        action = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/Api/PostMadeInChinaSync.php").read_text(encoding="utf-8")
        self.assertIn("assertAgent", action)
        self.assertIn("MadeInChinaSyncService", action)

    def test_contract_is_account_scoped_and_bounded(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/MadeInChinaSyncService.php").read_text(encoding="utf-8")
        for expected in (
            "MadeInChina", "accountHandle", "sourceId", "buyerExternalId",
            "MAX_MESSAGES", "MAX_BATCH", "requestId", "canonicalPayloadHash",
            "finalBatch", "backfillCompletedAt", "AutomationAudit",
            "requestId was already used with different job or payload.",
            "MIC source message ID was replayed with different content.",
            "Unsupported synchronization field:",
        ):
            self.assertIn(expected, source)
        self.assertIn("public const MAX_MESSAGES = 100", source)
        self.assertIn("->sync($body, $agent)", (ROOT / "custom/Espo/Custom/Tools/Fusanhe/Api/PostMadeInChinaSync.php").read_text(encoding="utf-8"))
        self.assertIn("in_array('MadeInChina', (array) ($agent->get('capabilities')", source)
        self.assertIn("throw new Forbidden", source)

    def test_identity_uses_stable_buyer_id_and_only_upgrades_generated_name(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/IdentityService.php").read_text(encoding="utf-8")
        self.assertIn("resolveMadeInChinaCustomer", source)
        self.assertIn("buyerExternalId", source)
        self.assertIn("MadeInChina", source)
        self.assertIn("MIC 买家 ", source)

    def test_confirmed_mic_lead_upgrades_placeholder_before_early_return(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/IdentityService.php").read_text(encoding="utf-8")
        branch = source.split("public function resolveMadeInChinaCustomer", 1)[1].split("$leadId =", 1)[0]
        self.assertLess(branch.index("upgradeMadeInChinaLeadPlaceholder"), branch.index("return ['targetType' => $type"))
        self.assertIn("$lead->get('name') !== $placeholderName", source)

    def test_mic_customer_resolution_locks_identity_before_lead_reuse_or_creation(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/IdentityService.php").read_text(encoding="utf-8")
        resolver = source.split("public function resolveMadeInChinaCustomer", 1)[1].split("private function upgradeMadeInChinaLeadPlaceholder", 1)[0]
        self.assertIn("where(['id' => $identity->getId()])->forUpdate()->findOne()", resolver)
        self.assertIn("$identity = $lockedIdentity", resolver)

    def test_mic_confirmed_and_fallback_leads_use_current_reads(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/IdentityService.php").read_text(encoding="utf-8")
        resolver = source.split("public function resolveMadeInChinaCustomer", 1)[1].split("private function upgradeMadeInChinaLeadPlaceholder", 1)[0]
        self.assertGreaterEqual(resolver.count("$this->repo('Lead')->where(['id' => $id])->forUpdate()->findOne()"), 1)
        self.assertIn("$this->repo('Lead')->where(['id' => $leadId])->forUpdate()->findOne()", resolver)

    def test_import_has_no_draft_task_or_unread_side_effect(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/MadeInChinaSyncService.php").read_text(encoding="utf-8")
        self.assertNotIn("generateDraft", source)
        self.assertNotIn("OutboundTask", source)
        self.assertIn("'unreadCount' => 0", source)
        self.assertNotIn("$conversationInput->unreadCount", source)

    def test_payload_fields_and_source_channel_are_explicit(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/MadeInChinaSyncService.php").read_text(encoding="utf-8")
        self.assertIn("'type' => 'MadeInChina'", source)
        self.assertIn("$conversationInput->sourceId", source)
        self.assertIn("'externalId' => $sourceId", source)
        self.assertIn("'MadeInChina', $accountHandle", source)
        self.assertNotIn("gatewayUuid", source)
        self.assertNotIn("rawPayload' => $input", source)
        self.assertIn("allowOnly($input", source)
        self.assertIn("allowOnly($input->conversation", source)
        self.assertIn("allowOnly($message", source)

    def test_conversation_source_metadata_refreshes_on_repeated_import(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/MadeInChinaSyncService.php").read_text(encoding="utf-8")
        self.assertIn("refreshConversationSourceMetadata($conversation, $conversationInput, $buyerId)", source)
        self.assertIn("'externalUserId' => $buyerId", source)
        self.assertIn("'subject' => (string) ($conversationInput->subject ?? '')", source)
        self.assertIn("'country' => (string) ($conversationInput->country ?? '')", source)

    def test_success_ack_and_message_hash_are_unambiguous(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/MadeInChinaSyncService.php").read_text(encoding="utf-8")
        self.assertIn("'accepted' => true", source)
        self.assertIn("$response['accepted'] = true", source)
        self.assertIn("['MadeInChina', $accountHandle, $sourceId, $direction, $externalId, $body]", source)
        self.assertNotIn("implode('|', [", source)

    def test_rollback_replay_fallback_uses_success_ack_normalizer(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/MadeInChinaSyncService.php").read_text(encoding="utf-8")
        rollback_path = source.split("$tx->rollback();", 1)[1]
        self.assertIn("normalizeAcceptedResponse($response)", rollback_path)
        self.assertIn("return $this->normalizeAcceptedResponse($response)", source)

    def test_sparse_source_metadata_updates_preserve_omitted_values(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/MadeInChinaSyncService.php").read_text(encoding="utf-8")
        self.assertIn("foreach (['subject', 'country'] as $field)", source)
        self.assertIn("property_exists($conversationInput, $field)", source)

    def test_attachment_contract_is_bounded_and_strict(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/MadeInChinaSyncService.php").read_text(encoding="utf-8")
        self.assertIn("MAX_ATTACHMENTS = 20", source)
        self.assertIn("'attachmentMetadata'", source)
        self.assertIn("'attachmentMetadata' => $attachmentMetadata", source)
        self.assertIn("allowOnly($value, ['items'])", source)
        self.assertIn("allowOnly($item", source)
        self.assertIn("mediaType", source)
        self.assertIn("size", source)
        self.assertIn("www", source)
        self.assertIn(r"\/\/", source)
        self.assertIn("api[_-]?key", source)

    def test_duplicate_message_refreshes_only_present_source_metadata(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/MadeInChinaSyncService.php").read_text(encoding="utf-8")
        self.assertIn("refreshExistingMessageSourceMetadata($existing, $messageInput, $messageIndex)", source)
        self.assertIn("refreshExistingMessageSourceMetadata($sameContent, $messageInput, $messageIndex)", source)
        self.assertIn("property_exists($input, 'senderName')", source)
        self.assertIn("property_exists($input, 'attachmentMetadata')", source)

    def test_channel_lock_serializes_imports_and_only_duplicate_key_races_retry(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/MadeInChinaSyncService.php").read_text(encoding="utf-8")
        find_channel = source.split("private function findChannel", 1)[1].split("private function attachCustomer", 1)[0]
        self.assertIn("->forUpdate()->findOne()", find_channel)
        self.assertIn("if (!$this->isDuplicateKeyViolation($e))", find_channel)
        self.assertIn("private function isDuplicateKeyViolation(\\Throwable $error)", source)

    def test_identity_unique_key_race_rereads_only_the_expected_mic_identity(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/MadeInChinaSyncService.php").read_text(encoding="utf-8")
        identity_race = source.split("if ($identity === null)", 1)[1].split("} else {", 1)[0]
        self.assertIn("buildIdentityKey(", identity_race)
        self.assertIn("identityKey' => $identityKey", source)
        self.assertIn("->forUpdate()->findOne()", source)
        self.assertIn("MIC buyer identity race did not resolve to the expected account.", source)

    def test_replay_refreshes_source_chronology_when_confidence_is_not_downgraded(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/MadeInChinaSyncService.php").read_text(encoding="utf-8")
        helper = source.split("private function refreshExistingMessageSourceMetadata", 1)[1].split("private function refreshConversationState", 1)[0]
        for field in ("sentAt", "sourceTimestampRaw", "timestampConfidence", "sourceSequence", "messageType", "senderExternalId"):
            self.assertIn("'" + field + "'", helper)
        self.assertIn("confidenceRank", helper)

    def test_attachment_replay_uses_provenance_and_ignores_empty_downgrades(self):
        source = (ROOT / "custom/Espo/Custom/Tools/Fusanhe/MadeInChinaSyncService.php").read_text(encoding="utf-8")
        self.assertIn("attachmentMetadataHash", source)
        self.assertIn("sourceAttachmentHash", source)
        self.assertIn("Empty source observations never downgrade known attachment data.", source)
        self.assertIn("hash_equals($sourceAttachmentHash", source)
        self.assertIn("$currentItems === [] && !is_string($sourceAttachmentHash)", source)


if __name__ == "__main__":
    unittest.main()
