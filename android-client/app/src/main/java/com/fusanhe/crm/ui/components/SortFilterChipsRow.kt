package com.fusanhe.crm.ui.components

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.FilterList
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.fusanhe.crm.domain.model.CustomerSortOption

/** 排序 + 筛选入口横排（客户列表与搜索页共用） */
@Composable
fun SortFilterChipsRow(
    currentSort: CustomerSortOption,
    filterCount: Int,
    onSortChange: (CustomerSortOption) -> Unit,
    onOpenSearch: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState())
            .padding(horizontal = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        CustomerSortOption.entries.forEach { option ->
            FilterChip(
                selected = currentSort == option,
                onClick = { onSortChange(option) },
                label = { Text(option.label) },
            )
        }
        FilterChip(
            selected = filterCount > 0,
            onClick = onOpenSearch,
            label = {
                BadgedBox(badge = {
                    if (filterCount > 0) { Badge { Text("$filterCount") } }
                }) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Outlined.FilterList, contentDescription = null)
                        Spacer(Modifier.width(4.dp))
                        Text("筛选")
                    }
                }
            },
        )
    }
}
