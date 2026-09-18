<?php
namespace Espo\Custom\Tools\Fusanhe\Connector;
final class AlibabaConnector extends AbstractPlaceholderConnector
{
    protected function channel(): string { return 'Alibaba'; }
}
