<?php
namespace Espo\Custom\Tools\Fusanhe;

/**
 * Minimal server-side HTML rendering for draft quotation / PI documents.
 * Internal-only fields never reach this renderer: the print() payload from
 * QuoteService simply does not contain them.
 */
final class HtmlPrint
{
    private static function esc(?string $value): string
    {
        return htmlspecialchars((string) ($value ?? ''), ENT_QUOTES, 'UTF-8');
    }

    public static function renderQuote(array $d): string
    {
        $rows = '';
        foreach ($d['items'] as $i) {
            $rows .= '<tr>'
                . '<td>' . self::esc((string) $i['position']) . '</td>'
                . '<td>' . self::esc((string) $i['description'])
                . ($i['specVersion'] ? '<br><small>Spec: ' . self::esc((string) $i['specVersion']) . '</small>' : '')
                . ($i['packingSpec'] ? '<br><small>Packing: ' . self::esc((string) $i['packingSpec']) . '</small>' : '')
                . '</td>'
                . '<td class="num">' . number_format((float) $i['quantity'], 2) . ' ' . self::esc((string) $i['unit']) . '</td>'
                . '<td class="num">' . rtrim(rtrim(number_format((float) $i['unitPrice'], 4, '.', ''), '0'), '.') . '</td>'
                . '<td class="num">' . number_format((float) $i['amount'], 2) . '</td>'
                . '</tr>';
        }
        $meta = '';
        foreach ([
            'Trade term' => trim(($d['tradeTerm'] ?? '') . ' ' . ($d['tradeTermPlace'] ?? '')) . (($d['tradeTermVersion'] ?? '') ? ' (' . $d['tradeTermVersion'] . ')' : ''),
            'Payment' => $d['paymentTerms'] ?? '',
            'Delivery' => $d['leadTimeText'] ?? '',
            'Valid until' => $d['validUntil'] ?? '',
        ] as $label => $value) {
            if ((string) $value !== '') {
                $meta .= '<div class="kv"><span>' . self::esc($label) . '</span><b>' . self::esc((string) $value) . '</b></div>';
            }
        }
        $termNote = ($d['tradeTerm'] ?? '') ? '<p class="note">责任划分以 ' . self::esc((string) $d['tradeTerm'])
            . ' 术语及所注明版本为准，本文件不自行扩展解释。</p>' : '';
        $items = $d['items'] ? '' : '<p class="note">No line items yet.</p>';
        return '<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">'
            . '<title>' . self::esc((string) $d['title']) . ' ' . self::esc((string) $d['number']) . '</title>'
            . '<style>'
            . 'body{font-family:-apple-system,Segoe UI,SimHei,sans-serif;margin:40px;color:#1a1a1a}'
            . 'h1{font-size:20px;margin:0 0 4px}.sub{color:#666;margin-bottom:18px}'
            . '.draft{display:inline-block;border:2px solid #b45309;color:#b45309;padding:4px 14px;border-radius:4px;font-weight:700;letter-spacing:2px;margin-bottom:16px}'
            . '.kv{margin:2px 0}.kv span{display:inline-block;width:110px;color:#555}'
            . 'table{border-collapse:collapse;width:100%;margin-top:18px}'
            . 'th,td{border:1px solid #ccc;padding:6px 8px;text-align:left;vertical-align:top;font-size:13px}'
            . 'th{background:#f3f4f6}.num{text-align:right;white-space:nowrap}'
            . 'small{color:#777}.note{color:#92400e;font-size:12px}'
            . '.total{margin-top:12px;text-align:right;font-size:15px}'
            . '</style></head><body>'
            . '<div class="draft">DRAFT 草稿 · 非正式文件 · 未发送</div>'
            . '<h1>' . self::esc((string) $d['title']) . '</h1>'
            . '<div class="sub">' . self::esc((string) $d['number']) . ' · v' . (int) $d['versionNo'] . ' · ' . self::esc((string) $d['date']) . '</div>'
            . '<div class="kv"><span>Seller</span><b>' . self::esc((string) $d['seller']['name']) . '</b></div>'
            . '<div class="kv"><span>Buyer</span><b>' . self::esc((string) $d['buyer']['name']) . '</b>'
            . (($d['buyer']['attn'] ?? '') ? ' · Attn: ' . self::esc((string) $d['buyer']['attn']) : '') . '</div>'
            . $meta
            . $items
            . '<table><thead><tr><th>#</th><th>Description</th><th>Quantity</th><th>Unit price</th><th>Amount</th></tr></thead>'
            . '<tbody>' . $rows . '</tbody></table>'
            . '<div class="total"><b>Total: ' . self::esc((string) $d['currency']) . ' ' . number_format((float) $d['totalAmount'], 2) . '</b></div>'
            . $termNote
            . '<p class="note">本文件为内部草稿，价格与条款在正式确认前不构成承诺；不含内部成本与利润信息。</p>'
            . '</body></html>';
    }
}
