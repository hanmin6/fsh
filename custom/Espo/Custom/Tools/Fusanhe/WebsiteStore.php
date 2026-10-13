<?php
namespace Espo\Custom\Tools\Fusanhe;

final class WebsiteStore
{
    public static function directory(): string
    {
        $dir=PHP_SAPI==='cli'&&getenv('FUSANHE_WEBSITE_TEST_DIR')?getenv('FUSANHE_WEBSITE_TEST_DIR'):'data/fusanhe/website';
        if(!is_dir($dir)&&!mkdir($dir,0700,true)&&!is_dir($dir))throw new \RuntimeException('website_storage_unavailable');
        SalesStore::secure($dir,true);return $dir;
    }
    public static function receipt(string $sourceId,?array $value=null): ?array
    {
        $file=self::directory().'/reply-'.hash('sha256',$sourceId).'.json';
        if($value===null)return is_file($file)?json_decode(file_get_contents($file),true,512,JSON_THROW_ON_ERROR):null;
        $tmp=tempnam(self::directory(),'reply-');try{file_put_contents($tmp,json_encode($value,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR));SalesStore::secure($tmp);rename($tmp,$file);}finally{if(is_file($tmp))unlink($tmp);}return $value;
    }
    public static function lock(): mixed
    {
        $file=self::directory().'/sync.lock';$lock=fopen($file,'c');if(!$lock)throw new \RuntimeException('website_storage_unavailable');SalesStore::secure($file);
        if(!flock($lock,LOCK_EX|LOCK_NB)){fclose($lock);throw new \Espo\Core\Exceptions\Conflict('Website sync busy.');}return $lock;
    }
    public static function status(?array $value=null): array
    {
        $file=self::directory().'/status.json';if($value===null)return is_file($file)?json_decode(file_get_contents($file),true):['configured'=>false];
        $tmp=tempnam(self::directory(),'status-');file_put_contents($tmp,json_encode($value,JSON_THROW_ON_ERROR));SalesStore::secure($tmp);rename($tmp,$file);return $value;
    }
}
