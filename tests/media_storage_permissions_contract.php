<?php
require getcwd().'/custom/Espo/Custom/Tools/Fusanhe/MediaStorage.php';
use Espo\Custom\Tools\Fusanhe\MediaStorage;
$root=getcwd();$tmp=sys_get_temp_dir().'/media-permissions-'.bin2hex(random_bytes(6));mkdir($tmp,0755);mkdir($tmp.'/data',0700);
$web=posix_getpwnam('www-data');if(posix_geteuid()!==0||!$web)throw new RuntimeException('Run isolated ownership contract as root with www-data available');
chown($tmp.'/data',$web['uid']);chgrp($tmp.'/data',$web['gid']);chdir($tmp);
try {
 $storage=new MediaStorage();$storage->locked(fn()=>null);$key=$storage->put('synthetic-result-bytes');$token=$storage->shareSource($key,'image/png',time()+60);
 foreach(['data/fusanhe-media'=>0700,'data/fusanhe-media/'.$key.'.bin'=>0600,'data/fusanhe-media/source-'.hash('sha256',$token).'.json'=>0600,'data/fusanhe-media/submission.lock'=>0600] as $path=>$mode){
  clearstatcache(true,$path);$s=stat($path);
  if($s['uid']!==$web['uid']||$s['gid']!==$web['gid']||($s['mode']&0777)!==$mode)throw new RuntimeException('Worker media file not privately readable by web owner: '.basename($path));
 }
 // Child exercises actual OS access as the web account, rather than relying only on stat assertions.
 $pid=pcntl_fork();if($pid===-1)throw new RuntimeException('Fork failed');
 if($pid===0){posix_setgid($web['gid']);posix_setuid($web['uid']);try{
  $webStorage=new MediaStorage();if($webStorage->get($key)!=='synthetic-result-bytes'||$webStorage->sharedSource($token)['bytes']!=='synthetic-result-bytes')throw new RuntimeException('Original bytes unavailable to web');
  $webStorage->locked(fn()=>null);$webStorage->put('web-created-source');exit(0);
 }catch(Throwable $e){fwrite(STDERR,$e->getMessage()."\n");exit(1);}}
 pcntl_waitpid($pid,$status);if(pcntl_wexitstatus($status)!==0)throw new RuntimeException('Web read/write failed');
 echo "Cross-user private media ownership contract passed\n";
}finally{chdir($root);$it=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($tmp,FilesystemIterator::SKIP_DOTS),RecursiveIteratorIterator::CHILD_FIRST);foreach($it as $p){$p->isDir()?rmdir($p->getPathname()):unlink($p->getPathname());}rmdir($tmp);}
