<?php
namespace Espo\Custom\Tools\Fusanhe\Connector;
final class MadeInChinaConnector extends AbstractPlaceholderConnector
{
    protected function channel(): string { return 'MadeInChina'; }
}
