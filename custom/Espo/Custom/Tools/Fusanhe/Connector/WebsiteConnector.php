<?php
namespace Espo\Custom\Tools\Fusanhe\Connector;
final class WebsiteConnector extends AbstractPlaceholderConnector
{
    protected function channel(): string { return 'Website'; }
    public function healthCheck(): array
    {
        $s=\Espo\Custom\Tools\Fusanhe\WebsiteStore::status();$fresh=!empty($s['checkedAt'])&&strtotime($s['checkedAt'].' UTC')>=time()-300;
        return ['channel'=>'Website','configured'=>!empty($s['configured']),'status'=>!empty($s['configured'])?($fresh?'healthy':'sync_pending'):'unavailable',
            'transport'=>'authenticated-push','checkedAt'=>$s['checkedAt']??null];
    }
}
