package com.fusanhe.crm.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.fusanhe.crm.ui.theme.ForestGreen

/** 福三和品牌标志：森林绿圆角方块 + "福"字 */
@Composable
fun FusanheLogoMark(size: Dp = 56.dp) {
    Box(
        modifier = Modifier
            .size(size)
            .background(ForestGreen, RoundedCornerShape(size / 4)),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = "福",
            color = Color.White,
            fontSize = (size.value * 0.5f).sp,
            fontWeight = FontWeight.SemiBold,
        )
    }
}
