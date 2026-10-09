<?php
namespace Espo\Custom\Hooks\Contact;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;
use Espo\Custom\Tools\Fusanhe\CustomerRatingGuard;
class RecordRating implements BeforeSave
{
    public function __construct(private CustomerRatingGuard $guard) {}
    public function beforeSave(Entity $entity, SaveOptions $options): void { $this->guard->beforeSave($entity, $options); }
}
