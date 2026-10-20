<?php
// Local CLI boundary only. No public route and no credentials in the journal.
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
require 'bootstrap.php';
$app = new Espo\Core\Application(); $app->setupSystemUser();
$em = $app->getContainer()->get('entityManager');
$store = new Espo\Custom\Tools\Fusanhe\AcquisitionRunStore();
$action = $argv[1] ?? '';
function publicSource(string $url): string {
    $p = parse_url(trim($url));
    if (!$p || !in_array($p['scheme'] ?? '', ['https','http'], true) || empty($p['host']) || isset($p['user']) || isset($p['pass'])) return '';
    $host = preg_replace('/^www\./', '', strtolower($p['host']));
    if ($host === 'twitter.com') $host = 'x.com';
    $path = rtrim($p['path'] ?? '', '/');
    if (in_array($host, ['linkedin.com','x.com','instagram.com'], true)) $path = strtolower($path);
    return 'https://' . $host . $path;
}
if ($action === 'snapshot') {
    $keys = []; $sources = []; $linkedIn = [];
    foreach (['Lead','Account','Contact'] as $type) foreach ($em->getRDBRepository($type)->find() as $e) {
        $source = trim((string) $e->get('fusanheSourceId'));
        if ($source !== '') { $sources[$source] = true; $keys[hash('sha256', 'source:' . $source)] = true; }
        $url = publicSource((string) $e->get('fusanheSourceUrl'));
        if ($url !== '') {
            $keys[hash('sha256', 'url:' . $url)] = true;
            if (str_starts_with($url, 'https://linkedin.com/')) $linkedIn[$url] = true;
        }
        $email = strtolower(trim((string) $e->get('emailAddress')));
        if (filter_var($email, FILTER_VALIDATE_EMAIL)) $keys[hash('sha256', 'email:' . $email)] = true;
    }
    $job = $em->getRDBRepository('ScheduledJob')->where(['job' => 'FusanheCustomerRating', 'status' => 'Active'])->findOne();
    echo json_encode(['keys' => array_keys($keys), 'sourceIds' => array_keys($sources), 'linkedIn' => array_keys($linkedIn),
        'ratingActive' => (bool) $job, 'settings' => $store->settings()], JSON_THROW_ON_ERROR);
} elseif ($action === 'configure') {
    echo json_encode($store->configure($argv[2] ?? ''), JSON_THROW_ON_ERROR);
} elseif ($action === 'write') {
    $input = stream_get_contents(STDIN, 2097153);
    if (strlen($input) > 2097152) throw new RuntimeException('acquisition_journal_too_large');
    $store->save(json_decode($input, true, 64, JSON_THROW_ON_ERROR)); echo "{\"saved\":true}\n";
} elseif ($action === 'verify') {
    $ids = json_decode(stream_get_contents(STDIN), true, 16, JSON_THROW_ON_ERROR);
    $routes = array_fill_keys(['human','ai','pending_rating','blocked'], 0); $ratings = []; $missing = 0;
    foreach (array_unique($ids) as $id) {
        $lead = $em->getEntityById('Lead', (string) $id);
        if (!$lead) { $missing++; continue; }
        $row = (array) $lead->getValueMap();
        $route = Espo\Custom\Tools\Fusanhe\AcquisitionRouting::route($row); $routes[$route]++;
        if ($lead->get('fusanheFollowUpRoute') !== $route) throw new RuntimeException('acquisition_route_not_persisted');
        $ratings[(string) ($lead->get('aiRatingStatus') ?: 'pending')] = ($ratings[(string) ($lead->get('aiRatingStatus') ?: 'pending')] ?? 0) + 1;
    }
    echo json_encode(['routes' => $routes, 'ratings' => $ratings, 'missing' => $missing], JSON_THROW_ON_ERROR);
} else throw new InvalidArgumentException('invalid_bridge_action');
