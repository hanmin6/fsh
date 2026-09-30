<?php
namespace Espo\Custom\Controllers;
/** Internal creative records are accessible solely through owner-scoped, sanitized APIs. */
class CreativePlan extends \Espo\Core\Controllers\Record
{
    protected function checkAccess(): bool { return false; }
}
