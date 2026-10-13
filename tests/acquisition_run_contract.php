<?php
$root = getcwd();
foreach (['ReceptionSettings','MorningReportStore','AcquisitionRouting','AcquisitionRunStore','MorningReportBusiness','MorningReport'] as $name) require "$root/custom/Espo/Custom/Tools/Fusanhe/$name.php";
use Espo\Custom\Tools\Fusanhe\AcquisitionRunStore as Runs;
function ckRun(bool $ok, string $message): void { if (!$ok) throw new RuntimeException($message); }
$dir = sys_get_temp_dir() . '/fsh-acquisition-' . bin2hex(random_bytes(6)); mkdir($dir); chdir($dir); mkdir('data/fusanhe',0700,true);
try {
    $store = new Runs(); $settings = $store->configure('2026-10-13');
    $asOf = new DateTimeImmutable('2026-10-14T01:00:00Z');
    $run = ['date'=>'2026-10-13','trigger'=>'scheduled','status'=>'completed','startedAt'=>'2026-10-13T14:00:01Z',
        'finishedAt'=>'2026-10-13T14:09:00Z','stats'=>['candidates'=>14,'qualified'=>5,'created'=>3,'deduplicated'=>2],
        'errors'=>[],'createdLeadIds'=>['a','b','c']];
    $store->save($run); ckRun(($store->read('2026-10-13')['stats']['created'] ?? -1)===3,'durable native counts');
    ckRun((fileperms($store->directory().'/2026-10-13.json')&0777)===0600,'private journal');
    $leads=[['id'=>'a','rating'=>'A'],['id'=>'b','rating'=>'B'],['id'=>'c'],['id'=>'a','rating'=>'A'],['id'=>'not-created','rating'=>'A']];
    $s=Runs::summary('2026-10-14',$settings,$run,$asOf,$leads);
    ckRun($s['routes']===['human'=>1,'ai'=>1,'pending_rating'=>1,'blocked'=>0],'live routing, duplicate ids and only new records');
    ckRun(!$s['warnings']&&str_contains(Runs::text($s),'新增入库 3 条'),'successful run with actual count');
    $zero=$run;$zero['stats']=['candidates'=>0,'qualified'=>0,'created'=>0,'deduplicated'=>0];
    ckRun(!Runs::summary('2026-10-14',$settings,$zero,$asOf)['warnings'],'valid zero discovery');
    $partial=$run;$partial['status']='partial';$partial['errors']=['b2b_timeout','b2b_timeout'];
    $p=Runs::summary('2026-10-14',$settings,$partial,$asOf);
    ckRun(count($p['warnings'])===1&&str_contains($p['warnings'][0],'企业联系人搜索超时')&&str_contains(Runs::text($p),'新增入库 3 条'),'partial failure preserves imported count and reports source error');
    $report=Espo\Custom\Tools\Fusanhe\MorningReport::build('2026-10-14',[],[],[],[],[],['enabled'=>true],$asOf,['acquisitionRun'=>$p]);
    ckRun(str_contains($report['text'],'新增入库 3 条')&&str_contains($report['text'],'运行提醒：昨晚获客异常：企业联系人搜索超时'),'real morning template includes both run counts and abnormalities');
    ckRun(Runs::summary('2026-10-14',$settings,null,$asOf)['status']==='missing','silent timer miss is visible');
    $running=$run;$running['status']='running';
    ckRun(Runs::summary('2026-10-14',$settings,$running,$asOf)['status']==='stalled','interrupted server execution is visible');
    ckRun(Runs::summary('2026-10-13',$settings,null,new DateTimeImmutable('2026-10-13T01:00:00Z'))['status']==='not_started','no alarm before first scheduled date');
    ckRun(Runs::summary('2026-10-14',$settings,null,new DateTimeImmutable('2026-10-13T13:00:00Z'))['status']==='scheduled','future report preview does not claim a missed run');
    ckRun(Runs::summary('2026-10-14',$settings+[],null,new DateTimeImmutable('2026-10-13T16:01:00Z'))['date']==='2026-10-13','cross-midnight report attribution stays on scheduled date');
    try{$store->read('../../settings');throw new RuntimeException('path accepted');}catch(InvalidArgumentException $e){}
    echo "PASS acquisition runs: private durable counts, live routing, partial/empty/missing/crash outcomes and Beijing schedule attribution\n";
} finally {
    chdir($root);$it=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($dir,FilesystemIterator::SKIP_DOTS),RecursiveIteratorIterator::CHILD_FIRST);
    foreach($it as $p){$p->isDir()?rmdir($p->getPathname()):unlink($p->getPathname());}rmdir($dir);
}
