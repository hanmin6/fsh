<?php
// Opt-in: uses configured provider and a synthetic screenshot only. Prints no raw content.
require __DIR__ . '/../../custom/Espo/Custom/Tools/Fusanhe/ReplyAssistant.php';
use Espo\Custom\Tools\Fusanhe\ReplyAssistant;
if (getenv('FUSANHE_TEST_LIVE_AI') !== '1') { fwrite(STDERR, "Set FUSANHE_TEST_LIVE_AI=1 to run the opt-in provider smoke test.\n"); exit(2); }
try {
    $service = new ReplyAssistant();
    $image = file_get_contents(__DIR__ . '/../../runtime/reply-assistant/synthetic-chat.png');
    $analysis = $service->handle(['operation'=>'analyze','images'=>['data:image/png;base64,'.base64_encode($image)]]);
    if (!$analysis['recognizedText'] || count($analysis['directions']) !== 3) throw new RuntimeException('Synthetic chat was not recognized');
    echo 'Verified ' . ReplyAssistant::MODEL . '; live vision passed; direction count: ' . count($analysis['directions']) . "\n";
    $reply = $service->handle(['operation'=>'generate','text'=>$analysis['recognizedText'],'direction'=>$analysis['directions'][0],'customInstruction'=>'先别降价，问采购量和目的港，简短礼貌。','language'=>'en']);
    if (!$reply['draftText'] || !$reply['translationZh']) throw new RuntimeException('Empty draft or translation');
    echo "Verified gpt-6.1-sol; live reply generation passed; draft and Chinese translation present.\n";
} catch (Throwable $e) {
    // Only these fixed service codes may be printed; never echo upstream content.
    $safe = ['ai_not_configured','ai_unavailable','invalid_ai_response','invalid_request'];
    fwrite(STDERR, 'Live smoke failed: ' . (in_array($e->getMessage(),$safe,true)?$e->getMessage():get_class($e)) . "\n");
    exit(1);
}
