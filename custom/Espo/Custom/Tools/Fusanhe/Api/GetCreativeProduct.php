<?php
namespace Espo\Custom\Tools\Fusanhe\Api;
use Espo\Core\Api\{Request, Response};
use Espo\Core\Acl;
use Espo\Entities\User;
use Espo\ORM\EntityManager;
use Espo\Core\FileStorage\Manager;
use Espo\Custom\Tools\Fusanhe\MediaPolicy;
use Espo\Custom\Tools\Fusanhe\MediaStorage;
/** Product facts and ACL-checked candidate originals; suggestions never assert an association. */
final class GetCreativeProduct extends AbstractFusanheAction
{
    public function __construct(User $user, Acl $acl, EntityManager $em, private Manager $storage, private MediaStorage $mediaStorage)
    {parent::__construct($user, $acl, $em);}
    public function process(Request $request): Response
    {
        $product = $this->requireEntityScope('FusanheProduct', (string) $request->getRouteParam('id'), 'read');
        $images = []; $seen = []; $specs = [];
        $maxImages = $request->getQueryParam('thumbnail') === '1' ? 1 : 8;
        $append = function ($attachment, bool $linked) use (&$images, &$seen, $maxImages) {
            if (count($images) >= $maxImages) return;
            if (!$this->user->isAdmin()) {
                if (!$this->acl->checkEntity($attachment, 'read')) return;
                $parentType = $attachment->get('parentType');$parentId = $attachment->get('parentId');
                if ($parentType && $parentId) {
                    $parent = $this->em->getEntityById($parentType, $parentId);
                    if (!$parent || !$this->acl->checkEntity($parent, 'read')) return;
                } elseif ($attachment->get('createdById') !== $this->user->getId() && !$attachment->get('global')) return;
            }
            if (!in_array($attachment->get('type'), ['image/png', 'image/jpeg', 'image/webp'], true) || $attachment->get('size') > 2097152 || $attachment->get('isBeingUploaded')) return;
            try {
                $path = $this->storage->getLocalFilePath($attachment);
                if (!is_file($path) || filesize($path) > 2097152) return;
                $dataUrl = 'data:' . $attachment->get('type') . ';base64,' . base64_encode(file_get_contents($path));
                $data = MediaPolicy::image($dataUrl);
                if (isset($seen[$data['sha256']])) return;
                $seen[$data['sha256']] = true;
                $images[] = ['id' => $attachment->getId(), 'name' => $attachment->get('name'), 'dataUrl' => $dataUrl, 'sha256' => $data['sha256'], 'linked' => $linked];
            } catch (\Throwable) {return;}
        };
        $collect = function ($record, string $type, bool $linked) use ($append) {
            foreach ($this->em->getRDBRepository($type)->getRelation($record, 'files')->find() as $attachment) $append($attachment, $linked);
        };
        $collect($product, 'FusanheProduct', true);
        if ($this->user->isAdmin() || $this->acl->checkScope('FusanheProductSpec', 'read')) {
            foreach ($this->em->getRDBRepository('FusanheProductSpec')->where(['productId' => $product->getId(), 'status' => 'approved'])->limit(0, 3)->find() as $spec) {
                if (!$this->user->isAdmin() && !$this->acl->checkEntity($spec, 'read')) continue;
                $row = ['id' => $spec->getId(), 'status' => 'approved'];
                foreach (['packingSpec', 'ingredients', 'shelfLife', 'storageConditions', 'customerVisibleNotes'] as $field) {
                    if ($this->user->isAdmin() || $this->acl->checkField('FusanheProductSpec', $field, 'read')) $row[$field] = $spec->get($field);
                }
                $specs[] = $row;
            }
        }
        // A previously confirmed/uploaded image remains linked to this user's product.
        if (count($images) < $maxImages && ($this->user->isAdmin() || $this->acl->checkScope('MediaAsset', 'read'))) {
            foreach ($this->em->getRDBRepository('MediaAsset')->where(['productId' => $product->getId(), 'assignedUserId' => $this->user->getId(), 'kind' => 'source'])->order('createdAt', 'DESC')->limit(0, 8)->find() as $asset) {
                if (count($images) >= $maxImages) break;
                if (isset($seen[$asset->get('sha256')])) continue;
                try {
                    $url = 'data:' . $asset->get('mime') . ';base64,' . base64_encode($this->mediaStorage->get((string) $asset->get('fileKey')));
                    $data = MediaPolicy::image($url);$seen[$data['sha256']] = true;
                    $images[] = ['id' => $asset->getId(), 'name' => $asset->get('name'), 'sha256' => $data['sha256'], 'dataUrl' => $url, 'linked' => true];
                } catch (\Throwable) {continue;}
            }
        }
        if (count($images) < $maxImages && ($this->user->isAdmin() || $this->acl->checkScope('KnowledgeDocument', 'read'))) {
            $name = (string) $product->get('name');
            if ($name !== '') foreach ($this->em->getRDBRepository('KnowledgeDocument')->where(['OR' => [['product' => $name], ['name*' => '%' . $name . '%'], ['name*' => '%' . ((string) $product->get('nameEn') ?: $name) . '%']]])->limit(0, 12)->find() as $doc) {
                if (!$this->user->isAdmin() && !$this->acl->checkEntity($doc, 'read')) continue;
                $collect($doc, 'KnowledgeDocument', false);
            }
        }
        // Imported image folders need not have a product link yet. Filename matches are candidates only.
        if (count($images) < $maxImages && ($this->user->isAdmin() || $this->acl->checkScope('Attachment', 'read'))) {
            $terms = array_filter([(string) $product->get('name'), (string) $product->get('nameEn'), preg_replace('/^(?:冻干|冷冻|速冻|IQF\s*)/u', '', (string) $product->get('name'))]);
            $conditions = array_map(fn ($term) => ['name*' => '%' . $term . '%'], array_unique($terms));
            if ($conditions) foreach ($this->em->getRDBRepository('Attachment')->where(['OR' => $conditions, 'type' => ['image/png', 'image/jpeg', 'image/webp']])->limit(0, 24)->find() as $attachment) $append($attachment, false);
        }
        $facts = ['id' => $product->getId()];
        foreach (['name', 'nameEn', 'code', 'category'] as $field) {
            if ($this->user->isAdmin() || $this->acl->checkField('FusanheProduct', $field, 'read')) $facts[$field] = $product->get($field);
        }
        if ($this->user->isAdmin() || $this->acl->checkField('FusanheProduct', 'description', 'read')) $facts['description'] = trim(preg_split('/(?:来源|原始来源|SHA-256)[：:]/u', (string) $product->get('description'))[0]);
        return $this->json($request, ['product' => $facts, 'specs' => $specs, 'images' => $images]);
    }
}
