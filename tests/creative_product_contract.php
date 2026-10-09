<?php
namespace Espo\Core\Exceptions {class BadRequest extends \RuntimeException{} class NotFound extends \RuntimeException{} class Forbidden extends \RuntimeException{}}
namespace Espo\Core\Api {interface Action {public function process(Request $r):Response;} class Request {public function getRouteParam($name){return 'p';}public function getQueryParam($name){return null;}public function getHeader($name){return null;}} class Response {public function __construct(public array $payload){}public function setHeader(...$x){}public function setStatus(...$x){}}class ResponseComposer {public static function json($p){return new Response($p);}}}
namespace Espo\Core {class Acl {public function checkScope(...$x){return true;}public function checkEntity(...$x){return true;}public function checkField($type,$field,$action){return !in_array($field,['description','ingredients']);}}}
namespace Espo\Core\FileStorage {class Manager {public function getLocalFilePath($a){return $a->get('path');}}}
namespace Espo\ORM {
 class Entity {public function __construct(public string $id,public array $data){}public function getId(){return $this->id;}public function get($key){return $this->data[$key]??null;}}
 class EntityManager {public array $rows=[];public function getEntityById($t,$id){return $this->rows[$t][$id]??null;}public function getRDBRepository($t){return new Repo($this->rows[$t]??[]);}}
 class Repo {public function __construct(public array $rows){}public function where($w){foreach($w as $k=>$v)if(!in_array($k,['OR']))$this->rows=array_filter($this->rows,fn($r)=>is_array($v)?in_array($r->get($k),$v):$r->get($k)===$v);return $this;}public function order(...$x){return $this;}public function limit(...$x){return $this;}public function find(){return array_values($this->rows);}public function getRelation($record,$field){return new self($record->get('files')??[]);}}
}
namespace Espo\Entities {class User extends \Espo\ORM\Entity {public function isAdmin(){return false;}}}
namespace {
$root=getcwd();foreach(['MediaStorage','MediaPolicy'] as $name)require "$root/custom/Espo/Custom/Tools/Fusanhe/$name.php";
require "$root/custom/Espo/Custom/Tools/Fusanhe/Api/AbstractFusanheAction.php";require "$root/custom/Espo/Custom/Tools/Fusanhe/Api/GetCreativeProduct.php";
$em=new Espo\ORM\EntityManager();$em->rows['FusanheProduct']['p']=new Espo\ORM\Entity('p',['name'=>'Product','description'=>'restricted product secret']);$em->rows['FusanheProductSpec']['s']=new Espo\ORM\Entity('s',['productId'=>'p','status'=>'approved','ingredients'=>'restricted ingredients secret','packingSpec'=>'10kg']);
$tmp=sys_get_temp_dir().'/creative-product-'.bin2hex(random_bytes(5));mkdir($tmp);chdir($tmp);
try {
 $action=new Espo\Custom\Tools\Fusanhe\Api\GetCreativeProduct(new Espo\Entities\User('u',[]),new Espo\Core\Acl(),$em,new Espo\Core\FileStorage\Manager(),new Espo\Custom\Tools\Fusanhe\MediaStorage());
 $data=$action->process(new Espo\Core\Api\Request())->payload;
 if(str_contains(json_encode($data),'restricted'))throw new RuntimeException('Field ACL bypass leaked restricted product data');
 if($data['product']['name']!=='Product'||$data['specs'][0]['packingSpec']!=='10kg')throw new RuntimeException('Permitted product facts missing');
 echo "Creative product field ACL contract passed\n";
}finally {chdir($root);$it=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($tmp,FilesystemIterator::SKIP_DOTS),RecursiveIteratorIterator::CHILD_FIRST);foreach($it as $p){$p->isDir()?rmdir($p->getPathname()):unlink($p->getPathname());}rmdir($tmp);}
}
