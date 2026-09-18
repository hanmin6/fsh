package com.fusanhe.crm.ui.components

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Call
import androidx.compose.material.icons.outlined.Chat
import androidx.compose.material.icons.outlined.Email
import androidx.compose.material.icons.outlined.Language
import androidx.compose.material.icons.outlined.Store
import androidx.compose.material.icons.outlined.Storefront
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import com.fusanhe.crm.domain.model.Channel

fun channelIcon(channel: Channel): ImageVector = when (channel) {
    Channel.EMAIL -> Icons.Outlined.Email
    Channel.WHATSAPP -> Icons.Outlined.Chat
    Channel.ALIBABA -> Icons.Outlined.Storefront
    Channel.MADE_IN_CHINA -> Icons.Outlined.Store
    Channel.WEBSITE -> Icons.Outlined.Language
    Channel.PHONE -> Icons.Outlined.Call
}

/** 渠道图标 */
@Composable
fun ChannelIcon(channel: Channel, modifier: Modifier = Modifier) {
    Icon(
        channelIcon(channel),
        contentDescription = channel.label,
        tint = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = modifier,
    )
}
