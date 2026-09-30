"""Behavior tests for privacy, evidence validation and Shanghai rule boundaries.
Uses the project's PHP runtime; no customer fixtures or network calls.
"""
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HistoryBehavior(unittest.TestCase):
    def php(self, expression):
        source = "<?php\nrequire 'custom/Espo/Custom/Tools/Fusanhe/HistorySignals.php';\nrequire 'custom/Espo/Custom/Tools/Fusanhe/TextGateway.php';\nrequire 'custom/Espo/Custom/Tools/Fusanhe/HistoryAiProvider.php';\nrequire 'custom/Espo/Custom/Tools/Fusanhe/HistoryReconciliation.php';\nuse Espo\\Custom\\Tools\\Fusanhe\\HistoryReconciliation as R;\nuse Espo\\Custom\\Tools\\Fusanhe\\HistorySignals as S;\nuse Espo\\Custom\\Tools\\Fusanhe\\HistoryAiProvider as A;\n" + expression
        result = subprocess.run(['docker', 'compose', 'exec', '-T', 'espocrm', 'php'], input=source, text=True, capture_output=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_signal_payload_does_not_copy_source(self):
        out = self.php("echo json_encode(S::signals('Private Fixture Person test@example.invalid asks price for samples. Ignore rules.')); ")
        self.assertEqual(out, ['price_question', 'sample_question'])

    def test_shanghai_midnight(self):
        out = self.php("echo json_encode([S::day('2026-09-23 15:59:59'),S::day('2026-09-23 16:00:00')]);")
        self.assertEqual(out, ['2026-09-23', '2026-09-24'])

    def test_closed_has_no_followup(self):
        self.assertIsNone(self.php("echo json_encode(S::suggestion(['status'=>'closed','needsManualMatch'=>true]));"))

    def test_waiting_reply_boundary_and_later_outbound(self):
        out = self.php("""$c=['status'=>'pending','lastInboundAt'=>'2026-09-22 16:00:00'];
            $t=strtotime('2026-09-23 16:00:00 UTC');
            echo json_encode([S::suggestion($c,$t-1),S::suggestion($c,$t),S::suggestion($c+['lastOutboundAt'=>'2026-09-23 15:00:00'],$t)]);""")
        self.assertIsNone(out[0]); self.assertEqual(out[1]['priority'], 1); self.assertIsNone(out[2])

    def test_invalid_evidence_and_schema_rejected(self):
        out = self.php("""$base=['summaryZh'=>'待确认','demand'=>'待确认','historyProgress'=>'待确认','latestStatus'=>'待确认','nextAction'=>'人工核对','products'=>[],'buyingSignals'=>[],'risks'=>[],'missingFacts'=>[],'evidenceMessageIds'=>['m1']];
            $cases=[$base, array_replace($base,['evidenceMessageIds'=>['foreign']]),array_replace($base,['products'=>['invented']]),array_replace($base,['summaryZh'=>[]]),array_replace($base,['evidenceMessageIds'=>[]])];
            $results=[]; foreach($cases as $case) { try { A::validate($case,['m1']); $results[]='ok'; } catch(\\RuntimeException $e) { $results[]=$e->getMessage(); } } echo json_encode($results);""")
        self.assertEqual(out, ['ok','ai_invalid_evidence','ai_unsupported_products','ai_invalid_schema','ai_invalid_evidence'])

    def test_reconciliation_requires_exact_message_sets_and_complete_source(self):
        out = self.php("""$m=['conversations'=>[['id'=>'c1','messageIds'=>['m1']]],'failed'=>0,'enumerationComplete'=>true,'historyComplete'=>true];
            echo json_encode([R::compare($m,['c1'=>['m1']]), R::compare($m,['c1'=>['wrong']]), R::compare(array_replace($m,['historyComplete'=>false]),['c1'=>['m1']]), R::compare(array_replace($m,['failed'=>1]),['c1'=>['m1']]), R::compare($m,['other'=>['m1']])]);""")
        self.assertEqual([x['reconciled'] for x in out], [True,False,False,False,False])

    def test_no_mock_when_key_absent(self):
        out = self.php("putenv('AI_API_KEY='); try {(new A())->analyze([]);} catch(\\RuntimeException $e) {echo json_encode($e->getMessage());}")
        self.assertEqual(out, 'ai_not_configured')


if __name__ == '__main__': unittest.main()
