<?php
$root=$argv[1] ?? dirname(__DIR__) . '/custom/Espo/Custom/Tools/Fusanhe';
require $root.'/AcquisitionRouting.php';
require $root.'/CardProgress.php';
use Espo\Custom\Tools\Fusanhe\CardProgress;
function check(bool $ok,string $name):void {if(!$ok)throw new RuntimeException($name);echo "PASS $name\n";}
$now=new DateTimeImmutable('2026-10-11T10:00:00Z');
$base=['id'=>'one','fusanheSourceSystem'=>'Muse','fusanheSourceId'=>'xpoz:one','createdAt'=>'2026-10-10 01:00:00','rating'=>'B'];
[$start,$end]=CardProgress::bounds($now);
check($start->format('c')==='2026-10-09T16:00:00+00:00'&&$end->format('c')==='2026-10-10T16:00:00+00:00','yesterday uses Shanghai calendar boundaries');
$r=CardProgress::summarize([$base,$base,array_replace($base,['id'=>'old','createdAt'=>'2026-10-09 15:59:59']),array_replace($base,['id'=>'today','createdAt'=>'2026-10-10 16:00:00']),array_replace($base,['id'=>'start','createdAt'=>'2026-10-09 16:00:00'])],$now);
check($r['yesterdayAcquired']===2&&$r['totalAcquired']===4,'count creation once, inclusive yesterday start and exclusive end');
check($r['statisticsDate']==='2026-10-10','statistics label is yesterday');
$leads=[];foreach(['S','A','B','C','D',''] as $i=>$rating)$leads[]=array_replace($base,['id'=>'r'.$i,'rating'=>$rating]);
$r=CardProgress::summarize($leads,$now);
check($r['yesterdayValueCounts']===['high'=>2,'medium'=>1,'low'=>2,'unrated'=>1],'value breakdown uses current rating');
check($r['followUpCounts']['human']===2&&$r['followUpCounts']['pending_rating']===1,'follow-up counts use routing policy');
$r=CardProgress::summarize([array_replace($base,['fusanheSourceSystem'=>'Website']),array_replace($base,['createdAt'=>'invalid']),array_replace($base,['createdAt'=>'2026-10-12 01:00:00']),array_replace($base,['fusanheSourceId'=>''])],$now);
check($r['totalAcquired']===0&&$r['lastAcquiredAt']===null,'exclude non-acquisition, future, invalid and unproven records');
$leads=[];for($i=0;$i<31;$i++)$leads[]=array_replace($base,['id'=>'many'.$i]);
$r=CardProgress::summarize($leads,$now);
check($r['yesterdayAcquired']===31&&!isset($r['dailyTarget'])&&!isset($r['remaining']),'no quota or capped acquisition counts');
$r=CardProgress::summarize([array_replace($base,['createdAt'=>'2026-10-09 09:13:25'])],$now);
check($r['yesterdayAcquired']===0&&$r['totalAcquired']===1,'historical pilot never presented as yesterday acquisition');
