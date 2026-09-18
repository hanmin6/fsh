<?php
namespace Espo\Custom\Tools\Fusanhe\Connector;
final class EmailConnector extends AbstractPlaceholderConnector
{
    protected function channel(): string { return 'Email'; }
}
