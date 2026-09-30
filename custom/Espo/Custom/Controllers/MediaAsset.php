<?php
namespace Espo\Custom\Controllers;
/** Internal creative records are accessible solely through owner-scoped, sanitized APIs. */
class MediaAsset extends \Espo\Core\Controllers\Record
{
    protected function checkAccess(): bool { return false; }
}
