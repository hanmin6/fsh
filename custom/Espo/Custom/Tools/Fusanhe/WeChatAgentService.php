<?php
namespace Espo\Custom\Tools\Fusanhe;
final class WeChatAgentService
{
    public function __construct(private WeChatAgentStore $store,private WeChatAgentPlanner $planner,private WeChatCrmTools $tools) {}
    public static function help(): string
    {
        return "福三和 CRM 微信助手\n你可以这样说：\n• 列出客户\n• 找德国的 A 级客户\n• 调出某公司的资料和最近沟通\n• 查看第 2 个 / 下一页\n• 添加客户：姓名张三，公司某贸易公司，邮箱 zhang@example.com，电话 13800138000\n也可以一次粘贴最多 10 位客户。添加前会展示预览和确认码，回复‘确认添加 六位码’才会录入；回复‘取消添加’放弃。\n新录入默认是潜在客户，可在 CRM 中继续评级和跟进。";
    }
    public function execute(string $account,string $source,array $plan,array &$session,array $config): string
    {
        $actor=$config['actorUserId'];$action=$plan['action'];
        if(($session['expiresAt']??0)<time())$session=[];
        $session['expiresAt']=time()+1800;
        if($action==='help')return self::help();
        if($action==='cancel'){unset($session['draft']);return '已取消待添加的客户资料，没有写入 CRM。';}
        if($action==='confirm'){
            $draft=$session['draft']??null;
            if(!$draft||($draft['expiresAt']??0)<time()||($draft['revision']??-1)!==$config['revision']||!hash_equals($draft['code'],$plan['code']))return '确认码不存在或已过期，请重新发送要添加的客户资料。';
            $rows=$this->tools->create($actor,$account,$draft['operation'],$draft['customers']);unset($session['draft']);
            $session['selected']=end($rows);$text='已添加 '.count($rows)." 位潜在客户：\n";foreach($rows as $r)$text.=$r['name']."\n".WeChatCrmTools::url($r)."\n";return $text;
        }
        if($action==='add'){
            $customers=WeChatAgentPlanner::customers($plan['customers']);$seen=[];
            foreach($customers as $c){
                foreach(array_filter(['name:'.mb_strtolower($c['name']),$c['email']?'email:'.mb_strtolower($c['email']):'',$c['phone']?'phone:'.preg_replace('/\D/','',$c['phone']):'']) as $key){if(isset($seen[$key]))return '名单里有重复的客户姓名或联系方式，请整理后再发送；本次没有录入。';$seen[$key]=true;}
                $duplicates=$this->tools->duplicates($actor,$c);if($duplicates){$session['selected']=$duplicates[0];return '发现已有客户与‘'.$c['name'].'’的姓名或联系方式相同，本次没有新增。请先核对：'."\n".WeChatCrmTools::url($duplicates[0]);}
            }
            $code=(string)random_int(100000,999999);$session['draft']=['code'=>$code,'customers'=>$customers,'operation'=>$source,'revision'=>$config['revision'],'expiresAt'=>time()+600];
            $text='待添加 '.count($customers)." 位潜在客户（尚未录入）：\n";
            foreach($customers as $i=>$c){$text.=($i+1).'. '.$c['name']."\n";foreach(['company'=>'公司','email'=>'邮箱','phone'=>'电话','country'=>'国家/地区','note'=>'备注'] as $k=>$label)if($c[$k]!=='')$text.=$label.'：'.$c[$k]."\n";}
            if(mb_strlen($text)>3200){unset($session['draft']);return '这份客户名单较长，请分成更小的几份发送；本次没有录入。';}
            return $text."\n资料正确请回复：确认添加 {$code}\n确认码 10 分钟有效；取消请回复：取消添加。";
        }
        if($action==='select'){
            $ref=$session['results'][$plan['index']-1]??null;if(!$ref)return '请先查询客户，再回复“查看第 1 个”到“查看第 5 个”。';$session['selected']=$ref;return $this->tools->detail($actor,$ref);
        }
        if($action==='current'||$action==='detail'&&($plan['query']??'')===''){
            if(empty($session['selected']))return '请先说客户名称，或查询后回复“查看第 2 个”，我再调出对应资料和沟通记录。';return $this->tools->detail($actor,$session['selected']);
        }
        if($action==='next'){
            if(empty($session['search'])||empty($session['more']))return '当前没有下一页；可以换客户名称、国家或评级继续查询。';
            $plan=$session['search'];$offset=($session['offset']??0)+5;if($offset>100)return '已查看较多客户，请增加名称、国家或评级条件后继续查询。';
        }else $offset=0;
        if(in_array($action,['search','detail','next'],true)){
            $result=$this->tools->search($actor,$plan,$offset);$rows=$result['rows'];$session['search']=$plan;$session['offset']=$offset;$session['more']=$result['more'];$session['results']=array_map(fn($r)=>['id'=>$r['id'],'type'=>$r['type']],$rows);
            if(!$rows)return 'CRM 中没有符合条件的客户。可以换一个名称、国家或评级，或发送客户资料让我添加。';
            if($action==='detail'&&count($rows)===1&&!$result['more']){$session['selected']=$session['results'][0];return $this->tools->detail($actor,$session['selected']);}
            $text="找到这些客户：\n";foreach($rows as $i=>$r){$text.=($i+1).'. '.($r['name']??'未命名').' · '.['Lead'=>'潜在客户','Account'=>'客户公司','Contact'=>'联系人'][$r['type']];$rating=AcquisitionRouting::effectiveRating($r);if($rating)$text.=' · '.$rating.'级';if(!empty($r['accountName']))$text.=' · '.$r['accountName'];$text.="\n";}
            return mb_substr($text,0,3000)."\n回复“查看第 2 个”调出资料和最近沟通。".($result['more']?'还有更多，回复“下一页”。':'');
        }
        return self::help();
    }
    public function tick(?WeChatAccounts $accounts=null): array
    {
        $cfg=$this->store->settings();if(!$cfg['enabled'])return ['enabled'=>false];
        $dir=ReceptionSettings::directory();$path=$dir.'/wechat-agent-worker.lock';$lock=fopen($path,'c');if(!$lock)throw new \RuntimeException('agent_storage_unavailable');ReceptionSettings::protect($path,0600);
        if(!flock($lock,LOCK_EX|LOCK_NB)){fclose($lock);return ['busy'=>true];}
        $accounts??=new WeChatAccounts(new WeChatApi());$processed=0;$errors=0;
        try{foreach($accounts->listing()['accounts'] as $a){
            if($a['status']!=='bound'||!$a['agentEnabled'])continue;
            try{$accounts->pollInbox($a['id']);}catch(\Throwable $e){if($e->getMessage()!=='wechat_timeout')$errors++;}
            for($i=0;$i<3;$i++){
                $m=$accounts->claimAgentMessage($a['id']);if(!$m)break;
                // Backfilled/historical messages can never trigger customer entry.
                if($m['at']<($cfg['activatedAt']??PHP_INT_MAX))continue;
                try{$plan=$this->planner->plan($m['text']);}catch(\Throwable $e){$plan=['action'=>'error'];}
                try{
                    $ready=$accounts->prepareAgentReply($a['id'],$m['key'],$m['lease'],function(array &$session)use($a,$m,$plan,$cfg){
                        $current=$this->store->settings();if(!$current['enabled']||$current['revision']!==$cfg['revision'])throw new \RuntimeException('agent_cancelled');
                        if($plan['action']==='error')return '暂时无法理解这条消息，没有执行新增操作。可回复“帮助”，或稍后重试。';
                        try{return $this->execute($a['id'],$m['key'],$plan,$session,$cfg);}catch(\Throwable $e){return $e->getMessage()==='agent_duplicate'?'客户已存在，本次没有重复添加，请重新查询。':'本次 CRM 操作未完成，请检查资料或稍后重试；可回复“帮助”查看支持的用法。';}
                    });
                    if($ready)$accounts->sendAgentReply($a['id'],$m['key'],$m['lease'],function()use($cfg){$s=$this->store->settings();return $s['enabled']&&$s['revision']===$cfg['revision'];});$processed++;
                }catch(\Throwable $e){$errors++;}
            }
        }return ['enabled'=>true,'processed'=>$processed,'errors'=>$errors];}finally{flock($lock,LOCK_UN);fclose($lock);}
    }
}
