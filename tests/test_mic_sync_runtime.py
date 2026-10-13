#!/usr/bin/env python3
"""Isolated CRM runtime checks for MIC buyer-to-Lead identity behavior."""
import os
import copy
from concurrent.futures import ThreadPoolExecutor
import unittest
import uuid

from tests.test_alibaba_sync_runtime import (
    BASE, admin_api, api, bootstrap_headers, assert_loopback_base_url, sp,
)


class MadeInChinaSyncRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert_loopback_base_url()
        if os.getenv("RUN_MIC_SYNC_RUNTIME") != "1":
            raise unittest.SkipTest("set RUN_MIC_SYNC_RUNTIME=1 to execute isolated MIC runtime tests")
        cls.stamp = uuid.uuid4().hex
        agent_key = f"mic-runtime-{cls.stamp[:18]}"
        _, registration = api("/Fusanhe/agent/register", "POST", {
            "agentKey": agent_key, "mode": "real", "capabilities": ["MadeInChina"],
        }, headers=bootstrap_headers())
        cls.headers = {"X-Agent-Key": agent_key, "X-Agent-Token": registration["agentToken"]}

    def request(self, label, source_id, buyer_id):
        return {
            "jobId": f"job-{self.stamp[:16]}-{label}",
            "requestId": f"mic-{self.stamp[:16]}-{label}",
            "accountHandle": f"fixture-mic-{self.stamp[:16]}",
            "syncMode": "backfill", "batchNo": 1, "finalBatch": True,
            "conversation": {
                "sourceId": source_id, "buyerExternalId": buyer_id,
                "buyerName": "Fictional Buyer", "buyerNameIsPlaceholder": False,
                "subject": "Synthetic inquiry", "country": "Fixtureland", "unreadCount": 9,
            },
            "messages": [{
                "externalId": f"{source_id}:inquiry", "sourceSequence": 1,
                "direction": "inbound", "messageType": "initialInquiry",
                "body": "Sanitized fictional inquiry", "sourceTimestampRaw": "2026-09-23T08:00:00Z",
                "timestampConfidence": "high",
            }, {
                "externalId": f"{source_id}:reply", "sourceSequence": 2,
                "direction": "outbound", "messageType": "chat",
                "body": "Sanitized fictional seller reply", "sourceTimestampRaw": "2026-09-23T08:01:00Z",
                "timestampConfidence": "high",
            }],
        }

    def sync(self, payload, expect_error=False):
        return api("/Fusanhe/mic/sync", "POST", payload, headers=self.headers, expect_error=expect_error)

    def test_same_buyer_id_reuses_lead_but_same_name_different_id_does_not(self):
        account = f"fixture-mic-{self.stamp[:16]}"
        first = self.request("first", f"source-{self.stamp[:12]}-1", f"buyer-{self.stamp[:12]}-A")
        second = self.request("second", f"source-{self.stamp[:12]}-2", f"buyer-{self.stamp[:12]}-A")
        third = self.request("third", f"source-{self.stamp[:12]}-3", f"buyer-{self.stamp[:12]}-B")
        _, result_one = self.sync(first)
        _, result_two = self.sync(second)
        _, result_three = self.sync(third)
        self.assertEqual(result_one["leadId"], result_two["leadId"])
        self.assertNotEqual(result_one["leadId"], result_three["leadId"])
        self.assertEqual(result_one["createdMessages"], 2)
        for payload, result in ((first, result_one), (second, result_two), (third, result_three)):
            _, conversation = admin_api(f"/ExternalConversation/{result['conversationId']}")
            self.assertEqual(conversation["externalId"], payload["conversation"]["sourceId"])
            self.assertEqual(conversation["unreadCount"], 0, "historical import must not alter unread count")
            _, lead = admin_api(f"/Lead/{result['leadId']}")
            self.assertTrue(lead["name"])
            messages = admin_api("/ExternalMessage?" + sp(where=[
                {"type": "equals", "attribute": "conversationId", "value": result["conversationId"]},
            ]))[1]
            self.assertEqual({row["direction"] for row in messages["list"]}, {"inbound", "outbound"})
            for entity in ("AIReplyDraft", "OutboundTask"):
                effects = admin_api("/" + entity + "?" + sp(where=[
                    {"type": "equals", "attribute": "conversationId", "value": result["conversationId"]},
                ]))[1]
                self.assertEqual(effects["total"], 0)
            self.assertTrue(conversation.get("backfillCompletedAt"))
        channels = admin_api("/ExternalChannel?" + sp(where=[
            {"type": "equals", "attribute": "type", "value": "MadeInChina"},
            {"type": "equals", "attribute": "accountHandle", "value": account},
        ]))[1]
        self.assertEqual(channels["total"], 1)

    def test_only_generated_mic_placeholder_name_is_upgraded(self):
        buyer_id = f"buyer-{self.stamp[:12]}-placeholder"
        first_payload = self.request("placeholder", f"placeholder-{self.stamp[:12]}-1", buyer_id)
        first_payload["conversation"]["buyerName"] = f"MIC 买家 {buyer_id}"
        first_payload["conversation"]["buyerNameIsPlaceholder"] = True
        _, first = self.sync(first_payload)
        _, before = admin_api(f"/Lead/{first['leadId']}")
        self.assertEqual(before["name"], f"MIC 买家 {buyer_id}")

        second_payload = self.request("real-name", f"placeholder-{self.stamp[:12]}-2", buyer_id)
        second_payload["conversation"]["buyerName"] = "Fictional Trading Group"
        second_payload["conversation"]["buyerNameIsPlaceholder"] = False
        _, second = self.sync(second_payload)
        _, after = admin_api(f"/Lead/{second['leadId']}")
        self.assertEqual(second["leadId"], first["leadId"])
        self.assertEqual(after["name"], "Fictional Trading Group")

    def test_missing_buyer_id_fallback_keeps_existing_binding_and_real_change_conflicts(self):
        source_id = f"fallback-{self.stamp[:12]}-source"
        buyer_id = f"buyer-{self.stamp[:12]}-known"
        original = self.request("fallback-original", source_id, buyer_id)
        _, first = self.sync(original)
        fallback = self.request("fallback-replay", source_id, source_id)
        _, second = self.sync(fallback)
        self.assertTrue(second["accepted"])
        self.assertEqual(second["conversationId"], first["conversationId"])
        self.assertEqual(second["identityId"], first["identityId"])
        self.assertEqual(second["leadId"], first["leadId"])
        self.assertEqual(second["createdMessages"], 0)
        _, conversation = admin_api(f"/ExternalConversation/{first['conversationId']}")
        _, identity = admin_api(f"/ExternalIdentity/{first['identityId']}")
        self.assertEqual(conversation["externalUserId"], buyer_id)
        self.assertEqual(identity["externalUserId"], buyer_id)
        changed = self.request("fallback-changed", source_id, f"buyer-{self.stamp[:12]}-different")
        status, _ = self.sync(changed, expect_error=True)
        self.assertEqual(status, 409)
        _, after = admin_api(f"/ExternalConversation/{first['conversationId']}")
        self.assertEqual(after["identityId"], first["identityId"])
        self.assertEqual(after["externalUserId"], buyer_id)

    def test_repeat_import_refreshes_source_metadata_without_duplicate_records(self):
        buyer_id = f"buyer-{self.stamp[:12]}-refresh"
        source_id = f"refresh-{self.stamp[:12]}-source"
        first_payload = self.request("refresh-first", source_id, buyer_id)
        first_payload["conversation"]["buyerName"] = f"MIC 买家 {buyer_id}"
        first_payload["conversation"]["buyerNameIsPlaceholder"] = True
        first_payload["conversation"]["subject"] = "Initial synthetic subject"
        first_payload["conversation"]["country"] = "Old Fixtureland"
        _, first = self.sync(first_payload)

        second_payload = self.request("refresh-second", source_id, buyer_id)
        second_payload["conversation"]["buyerName"] = "Updated Fictional Buyer"
        second_payload["conversation"]["buyerNameIsPlaceholder"] = False
        second_payload["conversation"]["subject"] = "Updated synthetic subject"
        second_payload["conversation"]["country"] = "New Fixtureland"
        _, second = self.sync(second_payload)
        self.assertTrue(second["accepted"])
        _, replay = self.sync(second_payload)
        self.assertEqual(replay, second)

        self.assertEqual(second["conversationId"], first["conversationId"])
        self.assertEqual(second["leadId"], first["leadId"])
        self.assertEqual(second["createdMessages"], 0)
        self.assertEqual(second["deduplicatedMessages"], 2)
        _, conversation = admin_api(f"/ExternalConversation/{first['conversationId']}")
        self.assertEqual(conversation["externalUserId"], buyer_id)
        self.assertEqual(conversation["subject"], "Updated synthetic subject")
        self.assertEqual(conversation["country"], "New Fixtureland")
        messages = admin_api("/ExternalMessage?" + sp(where=[
            {"type": "equals", "attribute": "conversationId", "value": first["conversationId"]},
        ]))[1]
        self.assertEqual(messages["total"], 2)

        sparse_payload = copy.deepcopy(second_payload)
        sparse_payload["requestId"] += "-sparse"
        sparse_payload["jobId"] += "-sparse"
        sparse_payload["conversation"].pop("subject")
        sparse_payload["conversation"].pop("country")
        _, sparse = self.sync(sparse_payload)
        _, after_sparse = admin_api(f"/ExternalConversation/{first['conversationId']}")
        self.assertEqual(after_sparse["subject"], "Updated synthetic subject")
        self.assertEqual(after_sparse["country"], "New Fixtureland")

        clear_payload = copy.deepcopy(second_payload)
        clear_payload["requestId"] += "-clear"
        clear_payload["jobId"] += "-clear"
        clear_payload["conversation"]["subject"] = ""
        clear_payload["conversation"]["country"] = ""
        _, cleared = self.sync(clear_payload)
        _, after_clear = admin_api(f"/ExternalConversation/{first['conversationId']}")
        self.assertEqual(after_clear.get("subject") or "", "")
        self.assertEqual(after_clear.get("country") or "", "")
        self.assertTrue(sparse["accepted"])
        self.assertTrue(cleared["accepted"])

    def test_message_content_hash_does_not_collide_on_delimiters(self):
        buyer_id = f"buyer-{self.stamp[:12]}-hash"
        payload = self.request("hash-collision", f"hash-{self.stamp[:12]}-source", buyer_id)
        payload["messages"] = [{
            "externalId": "prefix|a", "sourceSequence": 1, "direction": "inbound",
            "messageType": "chat", "body": "bc", "sourceTimestampRaw": "2026-09-23T08:00:00Z",
            "timestampConfidence": "high",
        }, {
            "externalId": "prefix", "sourceSequence": 2, "direction": "inbound",
            "messageType": "chat", "body": "a|bc", "sourceTimestampRaw": "2026-09-23T08:01:00Z",
            "timestampConfidence": "high",
        }]
        _, result = self.sync(payload)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["createdMessages"], 2)
        self.assertEqual(result["deduplicatedMessages"], 0)
        messages = admin_api("/ExternalMessage?" + sp(where=[
            {"type": "equals", "attribute": "conversationId", "value": result["conversationId"]},
        ]))[1]
        self.assertEqual(messages["total"], 2)

    def test_sender_and_safe_attachment_metadata_roundtrip_and_reject_unsafe_keys(self):
        buyer_id = f"buyer-{self.stamp[:12]}-attachments"
        payload = self.request("attachments", f"attachments-{self.stamp[:12]}-source", buyer_id)
        safe_items = [
            {"name": "catalog-page.png", "mediaType": "image/png", "size": 2048},
            {"name": "drawing.pdf", "mediaType": None, "size": None},
        ]
        payload["messages"][0]["senderName"] = "Synthetic MIC Buyer"
        payload["messages"][0]["attachmentMetadata"] = {"items": safe_items}
        _, result = self.sync(payload)
        rows = admin_api("/ExternalMessage?" + sp(where=[
            {"type": "equals", "attribute": "conversationId", "value": result["conversationId"]},
        ]))[1]["list"]
        inquiry = next(row for row in rows if row["externalId"] == payload["messages"][0]["externalId"])
        self.assertEqual(inquiry["senderName"], "Synthetic MIC Buyer")
        self.assertEqual(inquiry["attachmentMetadata"], {"items": safe_items})

        unsafe_values = [
            {"items": [{"name": "catalog.png", "mediaType": "image/png", "size": 1, "url": "https://fixture.invalid/a"}]},
            {"items": [{"name": "catalog.png", "mediaType": "image/png", "size": 1, "token": "synthetic-token"}]},
            {"items": safe_items, "url": "https://fixture.invalid/a"},
            {"items": [{"name": "https://fixture.invalid/catalog.png", "mediaType": "image/png", "size": 1}]},
            {"items": [{"name": "www.example.com/file", "mediaType": "image/png", "size": 1}]},
            {"items": [{"name": "//example.com/file", "mediaType": "image/png", "size": 1}]},
            {"items": [{"name": "api_key=synthetic-secret", "mediaType": "image/png", "size": 1}]},
            {"items": [{"name": "Bearer synthetic-token", "mediaType": "image/png", "size": 1}]},
            {"items": [{"name": "x" * 256, "mediaType": "image/png", "size": 1}]},
            {"items": [{"name": "catalog.png", "mediaType": "m" * 128, "size": 1}]},
            {"items": [{"name": "catalog.png", "mediaType": "image/png", "size": -1}]},
            {"items": [{"name": f"file-{index}.png", "mediaType": "image/png", "size": index} for index in range(21)]},
        ]
        for index, metadata in enumerate(unsafe_values):
            with self.subTest(index=index):
                invalid = self.request(f"unsafe-attachment-{index}", f"unsafe-{self.stamp[:12]}-{index}", buyer_id)
                invalid["messages"][0]["attachmentMetadata"] = metadata
                status, error = self.sync(invalid, expect_error=True)
                self.assertEqual(status, 400)
                self.assertTrue(any(error.get(key) for key in ("error", "message", "errors", "raw")))

    def test_duplicate_source_message_enriches_sender_and_attachments_in_place(self):
        buyer_id = f"buyer-{self.stamp[:12]}-enrichment"
        source_id = f"enrichment-{self.stamp[:12]}-source"
        first_payload = self.request("enrichment-first", source_id, buyer_id)
        first_payload["messages"][0]["senderName"] = "Unknown sender"
        _, first_result = self.sync(first_payload)
        first_rows = admin_api("/ExternalMessage?" + sp(where=[
            {"type": "equals", "attribute": "conversationId", "value": first_result["conversationId"]},
        ]))[1]["list"]
        first_message = next(row for row in first_rows if row["externalId"] == first_payload["messages"][0]["externalId"])
        self.assertFalse(first_message.get("attachmentMetadata"))

        second_payload = copy.deepcopy(first_payload)
        second_payload["requestId"] += "-enriched"
        second_payload["jobId"] += "-enriched"
        second_payload["messages"][0]["senderName"] = "Synthetic MIC Buyer"
        second_payload["messages"][0]["attachmentMetadata"] = {"items": [
            {"name": "updated-catalog.png", "mediaType": "image/png", "size": 4096},
        ]}
        _, second_result = self.sync(second_payload)
        second_rows = admin_api("/ExternalMessage?" + sp(where=[
            {"type": "equals", "attribute": "conversationId", "value": first_result["conversationId"]},
        ]))[1]["list"]
        updated_message = next(row for row in second_rows if row["externalId"] == first_payload["messages"][0]["externalId"])

        self.assertEqual(second_result["conversationId"], first_result["conversationId"])
        self.assertEqual(second_result["leadId"], first_result["leadId"])
        self.assertEqual(second_result["createdMessages"], 0)
        self.assertEqual(second_result["deduplicatedMessages"], 2)
        self.assertEqual(len(second_rows), len(first_rows))
        self.assertEqual(updated_message["id"], first_message["id"])
        self.assertEqual(updated_message["senderName"], "Synthetic MIC Buyer")
        self.assertEqual(updated_message["attachmentMetadata"], {"items": [
            {"name": "updated-catalog.png", "mediaType": "image/png", "size": 4096},
        ]})

        sparse_source = copy.deepcopy(second_payload)
        sparse_source["requestId"] = f"mic-{self.stamp[:16]}-attach-sparse"
        sparse_source["jobId"] = f"job-{self.stamp[:16]}-attach-sparse"
        sparse_source["messages"][0].pop("attachmentMetadata")
        _, sparse_result = self.sync(sparse_source)
        after_sparse_source = admin_api(f"/ExternalMessage/{updated_message['id']}")[1]
        self.assertEqual(sparse_result["createdMessages"], 0)
        self.assertEqual(after_sparse_source["attachmentMetadata"], {"items": [
            {"name": "updated-catalog.png", "mediaType": "image/png", "size": 4096},
        ]})

        empty_source = copy.deepcopy(second_payload)
        empty_source["requestId"] = f"mic-{self.stamp[:16]}-attach-empty"
        empty_source["jobId"] = f"job-{self.stamp[:16]}-attach-empty"
        empty_source["messages"][0]["senderName"] = "Second synthetic buyer name"
        empty_source["messages"][0]["attachmentMetadata"] = {"items": []}
        _, empty_result = self.sync(empty_source)
        after_empty_source = admin_api(f"/ExternalMessage/{updated_message['id']}")[1]
        self.assertEqual(empty_result["createdMessages"], 0)
        self.assertEqual(after_empty_source["senderName"], "Second synthetic buyer name")
        self.assertEqual(after_empty_source["attachmentMetadata"], {"items": [
            {"name": "updated-catalog.png", "mediaType": "image/png", "size": 4096},
        ]})

        admin_api(f"/ExternalMessage/{updated_message['id']}", "PATCH", {"senderName": "Human maintained sender"})
        third_payload = copy.deepcopy(empty_source)
        third_payload["requestId"] = f"mic-{self.stamp[:16]}-attach-human"
        third_payload["jobId"] = f"job-{self.stamp[:16]}-attach-human"
        third_payload["messages"][0]["senderName"] = "Another source correction"
        _, third_result = self.sync(third_payload)
        after_human_edit = admin_api(f"/ExternalMessage/{updated_message['id']}")[1]
        self.assertEqual(third_result["createdMessages"], 0)
        self.assertEqual(after_human_edit["senderName"], "Human maintained sender")

        admin_api(f"/ExternalMessage/{updated_message['id']}", "PATCH", {"attachmentMetadata": {"items": [
            {"name": "human-added-reference.txt", "mediaType": "text/plain", "size": 24},
        ]}})
        fourth_payload = copy.deepcopy(third_payload)
        fourth_payload["requestId"] = f"mic-{self.stamp[:16]}-attach-human-file"
        fourth_payload["jobId"] = f"job-{self.stamp[:16]}-attach-human-file"
        fourth_payload["messages"][0]["attachmentMetadata"] = {"items": [
            {"name": "another-source-file.png", "mediaType": "image/png", "size": 2048},
        ]}
        _, fourth_result = self.sync(fourth_payload)
        after_attachment_edit = admin_api(f"/ExternalMessage/{updated_message['id']}")[1]
        self.assertEqual(fourth_result["createdMessages"], 0)
        self.assertEqual(after_attachment_edit["attachmentMetadata"], {"items": [
            {"name": "human-added-reference.txt", "mediaType": "text/plain", "size": 24},
        ]})

    def test_human_cleared_attachment_metadata_stays_empty_after_source_replay(self):
        buyer_id = f"buyer-{self.stamp[:12]}-clear-attachments"
        source_id = f"clear-{self.stamp[:12]}-source"
        payload = self.request("clear-attachments", source_id, buyer_id)
        payload["messages"][0]["attachmentMetadata"] = {"items": [
            {"name": "source-catalog.png", "mediaType": "image/png", "size": 1024},
        ]}
        _, imported = self.sync(payload)
        rows = admin_api("/ExternalMessage?" + sp(where=[
            {"type": "equals", "attribute": "conversationId", "value": imported["conversationId"]},
        ]))[1]["list"]
        message = next(row for row in rows if row["externalId"] == payload["messages"][0]["externalId"])
        admin_api(f"/ExternalMessage/{message['id']}", "PATCH", {"attachmentMetadata": {"items": []}})

        replay = copy.deepcopy(payload)
        replay["requestId"] = f"mic-{self.stamp[:16]}-clear-replay"
        replay["jobId"] = f"job-{self.stamp[:16]}-clear-replay"
        replay["messages"][0]["attachmentMetadata"] = {"items": [
            {"name": "refreshed-source-catalog.png", "mediaType": "image/png", "size": 2048},
        ]}
        _, replay_result = self.sync(replay)
        after = admin_api(f"/ExternalMessage/{message['id']}")[1]
        self.assertEqual(replay_result["createdMessages"], 0)
        self.assertEqual(after["attachmentMetadata"], {"items": []})

    def test_same_id_replay_refreshes_chronology_without_body_change(self):
        buyer_id = f"buyer-{self.stamp[:12]}-chronology"
        source_id = f"chronology-{self.stamp[:12]}-source"
        first_payload = self.request("chronology-first", source_id, buyer_id)
        first_payload["messages"][0].update({
            "senderExternalId": "source-sender-old",
            "sentAt": "2026-09-23T08:00:00Z",
            "sourceTimestampRaw": "2026-09-23T08:00:00Z",
            "timestampConfidence": "medium",
        })
        _, first_result = self.sync(first_payload)
        first_rows = admin_api("/ExternalMessage?" + sp(where=[
            {"type": "equals", "attribute": "conversationId", "value": first_result["conversationId"]},
        ]))[1]["list"]
        message_id = next(row["id"] for row in first_rows if row["externalId"] == first_payload["messages"][0]["externalId"])

        corrected = copy.deepcopy(first_payload)
        corrected["requestId"] += "-corrected"
        corrected["jobId"] += "-corrected"
        corrected["messages"][0].update({
            "senderExternalId": "source-sender-corrected",
            "sentAt": "2026-09-23T08:07:00Z",
            "sourceTimestampRaw": "2026-09-23T08:07:00Z",
            "timestampConfidence": "high",
            "sourceSequence": 4,
            "messageType": "chat",
        })
        _, corrected_result = self.sync(corrected)
        stored = admin_api(f"/ExternalMessage/{message_id}")[1]
        self.assertEqual(corrected_result["createdMessages"], 0)
        self.assertEqual(stored["id"], message_id)
        self.assertEqual(stored["senderExternalId"], "source-sender-corrected")
        self.assertEqual(stored["sourceTimestampRaw"], "2026-09-23T08:07:00Z")
        self.assertEqual(stored["timestampConfidence"], "high")
        self.assertEqual(stored["sourceSequence"], 4)
        self.assertEqual(stored["messageType"], "chat")
        self.assertEqual(stored["sentAt"], "2026-09-23 08:07:00")

        lower_confidence = copy.deepcopy(corrected)
        lower_confidence["requestId"] += "-lower-confidence"
        lower_confidence["jobId"] += "-lower-confidence"
        lower_confidence["messages"][0]["sourceTimestampRaw"] = "2026-09-23T09:30:00Z"
        lower_confidence["messages"][0]["sentAt"] = "2026-09-23T09:30:00Z"
        lower_confidence["messages"][0]["timestampConfidence"] = "low"
        _, lower_result = self.sync(lower_confidence)
        after_lower_confidence = admin_api(f"/ExternalMessage/{message_id}")[1]
        self.assertEqual(lower_result["createdMessages"], 0)
        self.assertEqual(after_lower_confidence["sentAt"], "2026-09-23 08:07:00")
        self.assertEqual(after_lower_confidence["sourceTimestampRaw"], "2026-09-23T08:07:00Z")
        self.assertEqual(after_lower_confidence["timestampConfidence"], "high")

    def test_concurrent_first_imports_serialize_by_account_channel(self):
        buyer_id = f"buyer-{self.stamp[:12]}-concurrent"
        account_handle = f"fixture-concurrent-{self.stamp[:16]}"
        source_id = f"concurrent-{self.stamp[:12]}-source"
        same_source = [
            self.request(f"same-source-{index}", source_id, buyer_id)
            for index in range(2)
        ]
        different_sources = [
            self.request(f"same-buyer-{index}", f"concurrent-{self.stamp[:12]}-{index}", buyer_id)
            for index in range(2)
        ]
        for payload in same_source + different_sources:
            payload["accountHandle"] = account_handle

        with ThreadPoolExecutor(max_workers=2) as pool:
            same_results = list(pool.map(self.sync, same_source))
        self.assertTrue(all(result[1]["accepted"] for result in same_results))
        self.assertEqual(same_results[0][1]["conversationId"], same_results[1][1]["conversationId"])
        self.assertEqual(same_results[0][1]["identityId"], same_results[1][1]["identityId"])
        self.assertEqual(
            same_results[0][1]["leadId"], same_results[1][1]["leadId"],
            msg=(
                "same-source race IDs only: "
                f"conversation={same_results[0][1]['conversationId']}, "
                f"identity={same_results[0][1]['identityId']}, "
                f"leads={same_results[0][1]['leadId']},{same_results[1][1]['leadId']}"
            ),
        )
        same_conversations = admin_api("/ExternalConversation?" + sp(where=[
            {"type": "equals", "attribute": "externalId", "value": source_id},
        ]))[1]
        self.assertEqual(same_conversations["total"], 1)

        with ThreadPoolExecutor(max_workers=2) as pool:
            buyer_results = list(pool.map(self.sync, different_sources))
        self.assertTrue(all(result[1]["accepted"] for result in buyer_results))
        self.assertEqual(buyer_results[0][1]["leadId"], buyer_results[1][1]["leadId"])
        self.assertNotEqual(buyer_results[0][1]["conversationId"], buyer_results[1][1]["conversationId"])


if __name__ == "__main__":
    unittest.main()
