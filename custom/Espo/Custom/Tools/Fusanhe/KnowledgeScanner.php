<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\ORM\EntityManager;
use ZipArchive;

final class KnowledgeScanner
{
    public function __construct(private EntityManager $em) {}
    public function scan(): array
    {
        $root=(string)(getenv('KNOWLEDGE_BASE_PATH')?:'/var/www/html/knowledge'); if(!is_dir($root)) return ['scanned'=>0,'updated'=>0,'errors'=>['Directory not found']];
        $allowed=['pdf'=>'PDF','docx'=>'DOCX','xlsx'=>'XLSX','txt'=>'TXT','md'=>'Markdown'];$scanned=0;$updated=0;$errors=[];
        $it=new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($root,\FilesystemIterator::SKIP_DOTS));
        foreach($it as $file){if(!$file->isFile())continue;$ext=strtolower($file->getExtension());if(!isset($allowed[$ext]))continue;$scanned++;$path=$file->getPathname();$checksum=hash_file('sha256',$path);
            try{$doc=$this->em->getRDBRepository('KnowledgeDocument')->where(['filePath'=>$path])->findOne();if($doc&&$doc->get('checksum')===$checksum)continue;if(!$doc){$doc=$this->em->getNewEntity('KnowledgeDocument');$doc->set(['name'=>$file->getBasename(),'filePath'=>$path,'sourceType'=>$allowed[$ext],'approvalStatus'=>'draft','version'=>'1']);}$doc->set(['checksum'=>$checksum,'indexedAt'=>gmdate('Y-m-d H:i:s'),'extractedText'=>$this->extract($path,$ext)]);$this->em->saveEntity($doc);$updated++;}catch(\Throwable $e){$errors[]=$path.': '.$e->getMessage();}
        }
        return compact('scanned','updated','errors');
    }
    private function extract(string $path,string $ext): string
    {
        if(in_array($ext,['txt','md'],true))return mb_substr((string)file_get_contents($path),0,200000);
        if($ext==='pdf' && trim((string)shell_exec('command -v pdftotext 2>/dev/null'))!=='')return mb_substr((string)shell_exec('pdftotext '.escapeshellarg($path).' - 2>/dev/null'),0,200000);
        if(in_array($ext,['docx','xlsx'],true)&&class_exists(ZipArchive::class)){$zip=new ZipArchive();if($zip->open($path)===true){$names=$ext==='docx'?['word/document.xml']:['xl/sharedStrings.xml'];$text='';foreach($names as $n){$xml=$zip->getFromName($n);if($xml!==false)$text.=' '.strip_tags(str_replace(['</w:p>','</si>'],["\n","\n"],$xml));}$zip->close();return mb_substr(html_entity_decode($text),0,200000);}}
        return '';
    }
}
