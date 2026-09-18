<?php
namespace Espo\Custom\Tools\Fusanhe\Connector;
final class WebsiteConnector extends AbstractPlaceholderConnector
{
    protected function channel(): string { return 'Website'; }
}
