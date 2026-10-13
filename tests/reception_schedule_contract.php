<?php
require 'custom/Espo/Custom/Tools/Fusanhe/ReceptionSchedule.php';
use Espo\Custom\Tools\Fusanhe\ReceptionSchedule as S;
function check(bool $ok,string $name):void { if(!$ok) throw new RuntimeException($name); }
$c=S::defaults();$c['enabled']=true;
function at(string $t,array $c):array { return S::state($c,new DateTimeImmutable($t,new DateTimeZone('Asia/Shanghai'))); }
foreach ([['2026-10-10 08:59',true,'work'],['2026-10-10 09:00',false,'work'],['2026-10-10 18:59',false,'work'],['2026-10-10 19:00',true,'work'],['2026-10-11 12:00',true,'rest'],['2026-10-01 12:00',true,'rest'],['2026-09-20 12:00',false,'work'],['2026-02-14 12:00',false,'work'],['2026-02-16 12:00',true,'rest'],['2026-01-04 12:00',false,'work'],['2026-10-12 08:59',true,'work'],['2026-10-12 09:00',false,'work']] as [$t,$expected,$kind]) {
 $s=at($t,$c);check($s['active']===$expected&&$s['dayKind']===$kind,$t);
}
$c['dateOverrides']=['2026-10-11'=>'work','2026-10-12'=>'rest'];check(!at('2026-10-11 12:00',$c)['active'],'override work');check(at('2026-10-12 12:00',$c)['active'],'override rest');
check(!at('2027-01-01 22:00',$c)['active']&&!at('2027-01-01 22:00',$c)['calendarCovered'],'unknown year is not silently treated as correct calendar');
$c['dateOverrides']['2027-01-01']='rest';check(at('2027-01-01 22:00',$c)['active'],'explicit future exception');
$c['restdayAllDay']=false;check(!at('2026-10-01 12:00',$c)['active']&&at('2026-10-01 23:00',$c)['active'],'rest day night-only');
$c['workdayStart']='08:00';$c['workdayEnd']='18:00';check(at('2026-10-10 08:00',$c)['active']&&!at('2026-10-10 18:00',$c)['active'],'same-day hours');
$c=S::defaults();$c['enabled']=true;$now=new DateTimeImmutable('2026-10-11 12:00',new DateTimeZone('Asia/Shanghai'));
check(S::allows(['controlMode'=>'human','controlOrigin'=>'valueRouting'],['rating'=>'S'],$c,$now),'high value offhours');
check(!S::allows(['controlMode'=>'human','controlOrigin'=>'manual'],['rating'=>'S'],$c,$now),'manual takeover wins');
check(!S::allows(['controlMode'=>'human'],null,$c,$now),'unknown historical human origin is protected');
check(!S::allows(['controlMode'=>'aiAssist'],['fusanheContactPolicy'=>'optedOut'],$c,$now),'opt-out');
check(!S::allows(['status'=>'closed'],null,$c,$now),'closed');
$c['enabled']=false;check(!S::allows([],null,$c,$now),'disabled');
foreach (['24:00','19:60','9:00','garbage'] as $bad) { $v=S::defaults();$v['workdayStart']=$bad;try{S::validate($v);throw new RuntimeException('accepted invalid');}catch(InvalidArgumentException $e){} }
$v=S::defaults();$v['dateOverrides']=['2026-02-30'=>'rest'];try{S::validate($v);throw new RuntimeException('accepted invalid date');}catch(InvalidArgumentException $e){}
echo "PASS schedule: boundaries, official adjustments, exceptions, unknown year, takeover and validation\n";
