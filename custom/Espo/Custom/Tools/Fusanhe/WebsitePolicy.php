<?php
namespace Espo\Custom\Tools\Fusanhe;
use Espo\Core\Exceptions\BadRequest;

/** Website-owned records only. Visitor text cannot choose channel, direction, identity or model. */
final class WebsitePolicy
{
    public const SITE='https://fshfoodingredients.com';
    public const AGENT='website-fshfoodingredients';
    public static function event(array $v): array
    {
        $kind=$v['kind']??'';$role=$v['role']??'';
        if(!in_array($kind,['form','chat'],true)||!in_array($role,['user','ai','human','system'],true)||($kind==='form'&&$role!=='user'))throw new BadRequest('Invalid website record type.');
        foreach(['id','conversation'] as $key)if(!is_string($v[$key]??null)||!preg_match('/^[a-zA-Z0-9:_-]{8,120}$/D',$v[$key]))throw new BadRequest('Stable website IDs required.');
        $ts=$v['timestamp']??null;if(!is_int($ts)||$ts<1577836800||$ts>time()+300)throw new BadRequest('Invalid source timestamp.');
        $body=trim((string)($v['body']??''));if(!$body||mb_strlen($body)>12000)throw new BadRequest('Invalid message.');
        $data=$v['data']??[];if(!is_array($data))throw new BadRequest('Invalid profile.');$safe=[];
        foreach(['name','company','email','phone','country','product','pack','reqtype','doc_type','oem_brand','oem_market','oem_volume','oem_pack','landing_page','source_channel','language'] as $key) {
            $value=$data[$key]??'';if(!is_scalar($value)&&$value!==null)throw new BadRequest('Profile must contain text.');$value=trim(strip_tags((string)$value));
            if(mb_strlen($value)>2000)throw new BadRequest('Profile too long.');if($value!=='')$safe[$key]=$value;
        }
        if(!empty($safe['email'])&&!filter_var($safe['email'],FILTER_VALIDATE_EMAIL))throw new BadRequest('Invalid customer email.');
        if(!empty($safe['landing_page'])&&(!str_starts_with($safe['landing_page'],self::SITE.'/')||parse_url($safe['landing_page'],PHP_URL_HOST)!=='fshfoodingredients.com'))unset($safe['landing_page']);
        if(isset($v['sequence'])&&(!is_int($v['sequence'])||$v['sequence']<0||$v['sequence']>1000000))throw new BadRequest('Invalid source sequence.');
        $sequence=isset($v['sequence'])?['sequence'=>$v['sequence']]:[];
        return ['id'=>$v['id'],'conversation'=>$v['conversation'],'kind'=>$kind,'role'=>$role,'timestamp'=>$ts,'body'=>$body,'data'=>$safe,
            'humanTakeover'=>($v['humanTakeover']??false)===true,'receiptId'=>is_string($v['receiptId']??null)?$v['receiptId']:null]+$sequence;
    }
    public static function language(array $event): string {return ($event['data']['language']??'')==='zh'||preg_match('/[\x{4e00}-\x{9fff}]/u',$event['body'])?'zh':'en';}
}
