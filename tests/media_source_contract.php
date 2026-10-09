<?php
require getcwd().'/custom/Espo/Custom/Tools/Fusanhe/MediaStorage.php';
use Espo\Custom\Tools\Fusanhe\MediaStorage;
function checkSource(bool $ok,string $message):void {if(!$ok)throw new RuntimeException($message);}
$root=getcwd();$tmp=sys_get_temp_dir().'/source-contract-'.bin2hex(random_bytes(6));mkdir($tmp,0700);chdir($tmp);
try {
 $storage=new MediaStorage();$key=$storage->put('fictional-image');
 $token=$storage->shareSource($key,'image/png',time()+60);
 checkSource((bool)preg_match('/^[a-f0-9]{64}$/D',$token),'Unpredictable token');
 checkSource($storage->sharedSource($token)['bytes']==='fictional-image','Provider receives selected bytes');
 foreach (['../'.$token,str_repeat('a',64)] as $invalid) {
  try {$storage->sharedSource($invalid);throw new LogicException('Invalid token accepted');}catch(RuntimeException $e){}
 }
 $expired=$storage->shareSource($key,'image/png',time()-1);
 try {$storage->sharedSource($expired);throw new LogicException('Expired token accepted');}catch(RuntimeException $e){}
 try {$storage->shareSource($key,'video/mp4',time()+60);throw new LogicException('Video exposed as source');}catch(RuntimeException $e){}
 echo "Source transfer contracts passed\n";
} finally {chdir($root);$it=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($tmp,FilesystemIterator::SKIP_DOTS),RecursiveIteratorIterator::CHILD_FIRST);foreach($it as $p){$p->isDir()?rmdir($p->getPathname()):unlink($p->getPathname());}rmdir($tmp);}
