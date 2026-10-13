<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\Core\InjectableFactory;
use Espo\Core\Mail\Account\PersonalAccount\AccountFactory;
use Espo\Core\Mail\Sender;
use Espo\Entities\Email;
use Espo\ORM\{Entity,EntityManager};

/** Native encrypted EmailAccount credentials, native mail record, stable RFC identity. */
final class SalesMailSender
{
    public function __construct(private EntityManager $em,private InjectableFactory $factory,private ServiceKernel $kernel,private ?\Closure $testTransport=null) {}
    public function prepare(Entity $row,array $context,array $plan,array $settings): Email
    {
        $account=$this->factory->create(AccountFactory::class)->create($settings['emailAccountId']);
        if (!$account->getEntity()->isActive()||!$account->isAvailableForSending()) throw new \RuntimeException('sales_mailbox_unavailable');
        $channel=$this->em->getRDBRepository('ExternalChannel')->where(['type'=>'Email','accountHandle'=>$account->getEmailAddress(),'enabled'=>true])->findOne();
        if (!$channel) throw new \RuntimeException('sales_mail_channel_disabled');
        $rfc='<sales.'.$row->getId().'.'.$row->get('generation').'@fshfoodingredients.com>';
        $email=$this->em->getRDBRepository('Email')->where(['messageId'=>$rfc])->findOne();
        if ($email) throw new \RuntimeException('sales_email_already_prepared');
        $email=$this->em->getNewEntity('Email');
        $email->set(['name'=>$plan['subject'],'subject'=>$plan['subject'],'from'=>$account->getEmailAddress(),'to'=>$context['profile']['email'],
            'body'=>$plan['body']."\n\n".$settings['signature'],'bodyPlain'=>$plan['body']."\n\n".$settings['signature'],'isHtml'=>false,'status'=>'Draft',
            'messageId'=>$rfc,'assignedUserId'=>$account->getUser()->getId(),'parentType'=>$row->get('targetType'),'parentId'=>$row->get('targetId')]);
        $latest=end($context['messages']);
        if (($latest['direction']??'')==='inbound') {
            $message=$this->em->getEntityById('ExternalMessage',$latest['id']);$raw=(array)($message?->get('rawPayload')??[]);
            if (!empty($raw['nativeEmailId'])) $email->setRepliedId($raw['nativeEmailId']);
        }
        $this->kernel->save($email);$account->relateEmail($email);return $email;
    }
    public function submit(Email $email,array $settings,array $context=[]): void
    {
        if ($this->testTransport) {($this->testTransport)($email,$settings);$this->kernel->save($email);return;}
        $account=$this->factory->create(AccountFactory::class)->create($settings['emailAccountId']);
        if (!$account->getEntity()->isActive()||!$account->isAvailableForSending()) throw new \RuntimeException('sales_mailbox_unavailable');
        $sender=$this->factory->create(Sender::class)->withSmtpParams($account->getSmtpParams())->withParams(['fromAddress'=>$account->getEmailAddress(),'fromName'=>'福三和食品']);
        $email->getToAddressList();$email->getFromAddress(); // hydrate native address relations before the sender reads them.
        if ($email->get('repliedId')) {
            $reply=$this->em->getEntityById('Email',$email->get('repliedId'));$rfc=$reply?->getMessageId();
            if ($rfc) {
                $latest=end($context['messages']);$m=$latest?$this->em->getEntityById('ExternalMessage',$latest['id']):null;$raw=SalesPolicy::data($m?->get('rawPayload'));
                preg_match_all('/<[^<>]+>/',($raw['references']??'').' '.$rfc,$refs);$references=implode(' ',array_unique($refs[0]));
                $sender->withAddedHeader('In-Reply-To',$rfc);$sender->withAddedHeader('References',$references);
            }
        }
        $sender->send($email);$this->kernel->save($email);
    }
    public function record(Entity $row,Email $email,array $context): void
    {
        $channel=$this->em->getRDBRepository('ExternalChannel')->where(['type'=>'Email','accountHandle'=>$email->getFromAddress()])->findOne();
        $conv=null;$latest=end($context['messages']);
        if (($latest['direction']??'')==='inbound') {
            $m=$this->em->getEntityById('ExternalMessage',$latest['id']);$candidate=$m?$this->em->getEntityById('ExternalConversation',$m->get('conversationId')):null;
            if ($candidate&&$candidate->get('channelId')===$channel->getId())$conv=$candidate;
        }
        if (!$conv) {
            $thread='zoho-thread:'.hash('sha256',strtolower($email->getFromAddress()).'|'.strtolower(trim($email->getMessageId())));
            $conv=$this->kernel->create('ExternalConversation',['name'=>$email->getSubject(),'subject'=>$email->getSubject(),'channelId'=>$channel->getId(),'externalId'=>$thread,'externalUserId'=>$context['profile']['email'],
                lcfirst($row->get('targetType')).'Id'=>$row->get('targetId'),'assignedUserId'=>$row->get('assignedUserId'),'controlMode'=>'aiAssist','controlOrigin'=>'','status'=>'sent','needsManualMatch'=>false]);
        }
        $externalId='sales-email:'.$email->getId();
        $message=$this->em->getRDBRepository('ExternalMessage')->where(['externalId'=>$externalId])->findOne();
        if (!$message) $message=$this->kernel->create('ExternalMessage',['name'=>'OUT '.$externalId,'externalId'=>$externalId,'conversationId'=>$conv->getId(),'direction'=>'outbound','senderName'=>'福三和食品','senderExternalId'=>$email->getFromAddress(),
            'sentAt'=>$email->get('dateSent'),'body'=>$email->getBodyPlain(),'deliveryStatus'=>'sent','timestampConfidence'=>'high','automationKind'=>'aiSales','contentHash'=>hash('sha256',$externalId.'|'.$email->getBodyPlain()),
            'rawPayload'=>['source'=>'Zoho SMTP','nativeEmailId'=>$email->getId(),'salesPlanId'=>$row->getId(),'rfcMessageId'=>$email->getMessageId(),
                'salesPlanSnapshot'=>(array)$row->get('plan'),'customerEvidence'=>$context['profile'],'approvedProducts'=>$context['products'],'generation'=>$row->get('generation')]]);
        $row->set(['ownMessageId'=>$message->getId(),'lastMessageId'=>$message->getId()]);
        $conv->set(['lastOutboundAt'=>$email->get('dateSent'),'lastMessageAt'=>$email->get('dateSent'),'lastMessagePreview'=>mb_substr($email->getBodyPlain(),0,200)]);$this->kernel->save($conv);
    }
}
