<?php
namespace Espo\Custom\Tools\Fusanhe;
final class WeChatAgentStore
{
    public function settings(): array
    {
        $path=ReceptionSettings::directory().'/wechat-agent.json';
        return (is_file($path)?json_decode(file_get_contents($path),true,128,JSON_THROW_ON_ERROR):[])+['enabled'=>false,'actorUserId'=>null,'activatedAt'=>null,'revision'=>0,'scope'=>'all'];
    }
    public function configure(bool $enabled,string $actor): array
    {
        $dir=ReceptionSettings::directory();$path=$dir.'/wechat-agent.json';$lock=fopen($path.'.lock','c');if(!$lock)throw new \RuntimeException('agent_storage_unavailable');ReceptionSettings::protect($path.'.lock',0600);flock($lock,LOCK_EX);
        try{$s=$this->settings();$s['enabled']=$enabled;$s['actorUserId']=$actor;$s['revision']++;$s['activatedAt']=time();$tmp=tempnam($dir,'agent-');try{ReceptionSettings::protect($tmp,0600);if(file_put_contents($tmp,json_encode($s,JSON_THROW_ON_ERROR))===false||!rename($tmp,$path))throw new \RuntimeException('agent_storage_unavailable');}finally{if(is_file($tmp))unlink($tmp);}return $s;}finally{flock($lock,LOCK_UN);fclose($lock);}
    }
}
