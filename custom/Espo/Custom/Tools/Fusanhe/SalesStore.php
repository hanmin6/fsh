<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\Core\Exceptions\{BadRequest,Conflict};

/** Only settings and approved public cards live here; customer plans are CRM entities. */
final class SalesStore
{
    public static function directory(): string
    {
        $dir = PHP_SAPI==='cli' && getenv('FUSANHE_SALES_TEST_DIR') ? (string)getenv('FUSANHE_SALES_TEST_DIR') : 'data/fusanhe/sales';
        if (!is_dir($dir) && !mkdir($dir, 0700, true) && !is_dir($dir)) throw new \RuntimeException('sales_storage_unavailable');
        self::secure($dir,true); return $dir;
    }
    /** Espo's container daemon runs as root; files must remain writable by the web worker. */
    public static function secure(string $path,bool $directory=false): void
    {
        if (PHP_SAPI==='cli'&&!getenv('FUSANHE_SALES_TEST_DIR')&&function_exists('posix_geteuid')&&posix_geteuid()===0) {
            if (!chown($path,'www-data')||!chgrp($path,'www-data'))throw new \RuntimeException('sales_storage_unavailable');
        }
        if (!chmod($path,$directory?0700:0600))throw new \RuntimeException('sales_storage_unavailable');
    }
    public static function defaults(): array
    {
        return ['enabled'=>false,'revision'=>0,'emailAccountId'=>'6acc8dd15eba83bfc', 'signature'=>'福三和食品\nfusanhe@fshfoodingredients.com',
            'signatureApproved'=>false,'maxUnansweredFollowups'=>2,'cooldownHours'=>72,'transportIntervalSeconds'=>60,'activationEpoch'=>null,'activatedAt'=>null,'reviewedPlanId'=>null,'reviewedSourceMessageId'=>null];
    }
    public static function read(): array
    {
        $path=self::directory().'/settings.json';
        return is_file($path) ? json_decode(file_get_contents($path),true,512,JSON_THROW_ON_ERROR) + self::defaults() : self::defaults();
    }
    public static function cards(): array
    {
        $path=self::directory().'/cards.json';
        return is_file($path) ? json_decode(file_get_contents($path),true,512,JSON_THROW_ON_ERROR) : [];
    }
    public static function mutate(string $name, \Closure $fn): array
    {
        $path=self::directory().'/'.$name.'.json';$lock=fopen($path.'.lock','c');
        if (!$lock)throw new \RuntimeException('sales_storage_unavailable');self::secure($path.'.lock');
        if (!$lock || !flock($lock,LOCK_EX)) throw new \RuntimeException('sales_storage_locked');
        try {
            $old=$name==='settings'?self::read():self::cards();$new=$fn($old);
            $tmp=tempnam(self::directory(),'sales-');
            try {file_put_contents($tmp,json_encode($new,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR));self::secure($tmp);if (!rename($tmp,$path)) throw new \RuntimeException('sales_commit_failed');}
            finally {if (is_file($tmp)) unlink($tmp);}
            return $new;
        } finally {flock($lock,LOCK_UN);fclose($lock);}
    }
    public static function updateSettings(array $input): array
    {
        return self::mutate('settings',function($old)use($input){
            if (($input['revision']??null)!==$old['revision']) throw new Conflict('设置已更新，请重新读取。');
            if (!is_bool($input['enabled']??null)||!is_bool($input['signatureApproved']??null)) throw new BadRequest('Invalid switches.');
            $new=$old;
            foreach (['signature','signatureApproved','enabled','maxUnansweredFollowups','cooldownHours'] as $key) if (isset($input[$key])) $new[$key]=$input[$key];
            if (!is_string($new['signature'])||mb_strlen($new['signature'])<5||mb_strlen($new['signature'])>1000||!is_int($new['maxUnansweredFollowups'])||$new['maxUnansweredFollowups']<0||$new['maxUnansweredFollowups']>2||!is_int($new['cooldownHours'])||$new['cooldownHours']<24||$new['cooldownHours']>720) throw new BadRequest('Invalid sales settings.');
            if ($new['enabled']&&!$old['enabled']) {
                if (empty($input['reviewedPlanId'])||!$new['signatureApproved']) throw new Conflict('请先核对首批可发送预览和公司署名。');
                $new['reviewedPlanId']=$input['reviewedPlanId'];$new['reviewedSourceMessageId']=$input['reviewedSourceMessageId']??null;$new['activationEpoch']=bin2hex(random_bytes(16));$new['activatedAt']=gmdate('Y-m-d H:i:s');
            }
            $new['revision']=$old['revision']+1;$new['updatedAt']=gmdate('Y-m-d H:i:s');return $new;
        });
    }
    public static function card(string $id,array $input,string $actor): array
    {
        $all=self::mutate('cards',function($old)use($id,$input,$actor){
            $previous=$old[$id]??['revision'=>0];
            if (($input['revision']??null)!==$previous['revision']) throw new Conflict('产品资料已更新，请重新读取。');
            $card=['productId'=>$id];
            foreach (['name','nameEn','applications','publicFacts','source','validUntil'] as $key) {
                $value=trim((string)($input[$key]??''));if (mb_strlen($value)>($key==='publicFacts'?4000:1000)) throw new BadRequest('产品资料过长。');$card[$key]=$value;
            }
            $status=$input['status']??'draft';if (!in_array($status,['draft','approved','retired'],true)) throw new BadRequest('Invalid card status.');
            if ($status==='approved'&&(!$card['name']||!$card['applications']||!$card['publicFacts']||!$card['source']||!preg_match('/^\d{4}-\d{2}-\d{2}$/D',$card['validUntil'])||$card['validUntil']<gmdate('Y-m-d'))) throw new BadRequest('批准前请补齐产品用途、事实、来源及有效期。');
            if (preg_match('/(?:\/home\/|\/Users\/|[A-Z]:\\\\|成本|底价|internalNotes)/i',$card['publicFacts'])) throw new BadRequest('对外事实中含内部内容。');
            $card+=['status'=>$status,'revision'=>$previous['revision']+1,'approvedBy'=>$status==='approved'?$actor:null,'approvedAt'=>$status==='approved'?gmdate('Y-m-d H:i:s'):null];$old[$id]=$card;return $old;
        });return $all[$id];
    }
    public static function approved(): array
    {
        return array_values(array_filter(self::cards(),fn($c)=>$c['status']==='approved'&&($c['validUntil']??'')>=gmdate('Y-m-d')));
    }
}
