<?php
namespace Espo\Custom\Tools\Fusanhe;
/** The model selects a finite tool schema; it never receives CRM records or runs SQL/code. */
final class WeChatAgentPlanner
{
    public function __construct(private TextGateway $gateway) {}
    public static function customers(mixed $rows): array
    {
        if(!is_array($rows)||!array_is_list($rows)||count($rows)<1||count($rows)>10)throw new \InvalidArgumentException('invalid_customers');
        $out=[];
        foreach($rows as $row){
            if(!is_array($row))throw new \InvalidArgumentException('invalid_customer');$v=[];
            foreach(['name'=>100,'company'=>150,'email'=>200,'phone'=>40,'country'=>80,'note'=>800] as $k=>$limit){$text=$row[$k]??'';if(!is_string($text)||mb_strlen($text)>$limit||preg_match('/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/',$text))throw new \InvalidArgumentException('invalid_customer');$v[$k]=trim($text);}
            if($v['name']==='')throw new \InvalidArgumentException('missing_name');
            if($v['email']!==''&&!filter_var($v['email'],FILTER_VALIDATE_EMAIL))throw new \InvalidArgumentException('invalid_email');
            if($v['phone']!==''&&!preg_match('/^\+?[0-9 ()\-.]{7,40}$/D',$v['phone']))throw new \InvalidArgumentException('invalid_phone');
            $out[]=$v;
        }
        return $out;
    }
    public function plan(string $text): array
    {
        $text=trim($text);
        if(preg_match('/^确认添加\s*([0-9]{6})$/u',$text,$m))return ['action'=>'confirm','code'=>$m[1]];
        if(preg_match('/^(取消|取消添加|帮助|菜单|help|晨报测试|连接测试)$/iu',$text))return ['action'=>str_starts_with($text,'取消')?'cancel':'help'];
        if(preg_match('/^(?:查看|调出|看看|打开)?\s*第?\s*([1-5一二三四五])\s*(?:个|条|位)?(?:客户|的资料)?$/u',$text,$m))return ['action'=>'select','index'=>is_numeric($m[1])?(int)$m[1]:array_search($m[1],['一','二','三','四','五'],true)+1];
        if(preg_match('/^(下一页|更多客户|更多)$/u',$text))return ['action'=>'next'];
        if(preg_match('/^(?:他|她|这个客户|这位客户)(?:的)?(?:资料|详情|电话|邮箱|联系方式|最近沟通|聊天记录|跟进情况)(?:呢|是什么|怎么样|多少)?[？?]?$/u',$text))return ['action'=>'current'];
        if(preg_match('/^(?:列出|查看|看看|有哪些|有什么)?\s*(?:全部|所有)?(?:客户|客户名单|客户列表)[？?]?$/u',$text))return ['action'=>'search','query'=>'','type'=>'all','rating'=>'','country'=>''];
        $contacts=[];
        $masked=preg_replace_callback('/[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}|\+?\d[\d ()\-]{5,}\d/iu',function($m)use(&$contacts){$key='CONTACT_'.count($contacts);$contacts[$key]=$m[0];return $key;},$text);
        $response=$this->gateway->complete([
            ['role'=>'system','content'=>'你是福三和微信CRM助手的意图解析器。只输出JSON，不执行操作。用户可查询或添加客户。允许action=search/detail/add/help；type只允许all/Lead/Account/Contact。search/detail输出query(客户或公司名称，不能带操作动词)、rating(空或S/A/B/C/D)、country。只指定国家、评级或客户类型时query必须为空；例如找德国的A级客户应query空、country德国、rating A。添加始终新建潜在客户Lead，输出customers数组(最多10条)，每条仅name/company/email/phone/country/note。不确定客户名称时action=help，不猜造任何字段。CONTACT_N是已遮蔽的联系方式占位符，按原样保留在对应email/phone。不能返回确认、删除、修改、发送客户消息、权限修改、SQL、脚本等操作。用户说查询是search；问具体客户详情/最近沟通是detail；无指定客户的代词请返回detail且query为空。'],
            ['role'=>'user','content'=>mb_substr($masked,0,4000)],
        ],null,true,1600);
        $p=json_decode($response['content'],true,128,JSON_THROW_ON_ERROR);
        if(!in_array($p['action']??'', ['search','detail','add','help'],true))throw new \RuntimeException('agent_invalid_plan');
        if($p['action']==='add'){
            $customers=$p['customers']??[];
            foreach($customers as &$r)foreach(['email','phone'] as $k)if(isset($contacts[$r[$k]??'']))$r[$k]=$contacts[$r[$k]];unset($r);
            return ['action'=>'add','customers'=>self::customers($customers)];
        }
        $query=$p['query']??'';$country=$p['country']??'';$rating=$p['rating']??'';$type=$p['type']??'all';
        if(!is_string($query)||mb_strlen($query)>100||!is_string($country)||mb_strlen($country)>80||!in_array($rating,['','S','A','B','C','D'],true)||!in_array($type,['all','Lead','Account','Contact'],true))throw new \RuntimeException('agent_invalid_plan');
        return ['action'=>$p['action'],'query'=>trim($query),'country'=>trim($country),'rating'=>$rating,'type'=>$type];
    }
}
