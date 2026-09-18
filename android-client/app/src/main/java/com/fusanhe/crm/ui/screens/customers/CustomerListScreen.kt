package com.fusanhe.crm.ui.screens.customers

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.FilterList
import androidx.compose.material.icons.outlined.People
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.fusanhe.crm.domain.model.Customer
import com.fusanhe.crm.ui.components.AvatarInitials
import com.fusanhe.crm.ui.components.EmptyState
import com.fusanhe.crm.ui.components.ErrorState
import com.fusanhe.crm.ui.components.LabelChip
import com.fusanhe.crm.ui.components.ListSkeleton
import com.fusanhe.crm.ui.components.OfflineBanner
import com.fusanhe.crm.ui.components.SortFilterChipsRow
import com.fusanhe.crm.ui.theme.FusanheTheme
import com.fusanhe.crm.util.TimeFormat

/**
 * 客户列表：搜索、筛选入口、最近联系排序、下拉刷新、骨架屏、分页加载、空状态。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CustomerListScreen(
    onAddCustomer: () -> Unit,
    onCustomerClick: (String) -> Unit,
    onOpenSearch: () -> Unit,
    viewModel: CustomerListViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = onAddCustomer,
                icon = { Icon(Icons.Outlined.Add, contentDescription = null) },
                text = { Text("新增客户") },
            )
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "客户",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                IconButton(onClick = onOpenSearch) {
                    Icon(Icons.Outlined.FilterList, contentDescription = "搜索和筛选")
                }
            }
            Text(
                if (state.totalCount > 0) "共 ${state.totalCount} 个客户" else "",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp),
            )
            Spacer(Modifier.height(8.dp))

            OutlinedTextField(
                value = state.query,
                onValueChange = viewModel::onQueryChange,
                placeholder = { Text("搜索姓名 / 公司 / 邮箱 / 手机号") },
                leadingIcon = { Icon(Icons.Outlined.Search, contentDescription = null) },
                trailingIcon = {
                    if (state.query.isNotEmpty()) {
                        IconButton(onClick = { viewModel.onQueryChange("") }) {
                            Icon(Icons.Outlined.Close, contentDescription = "清除")
                        }
                    }
                },
                singleLine = true,
                shape = MaterialTheme.shapes.medium,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
            )

            Spacer(Modifier.height(8.dp))
            SortFilterChipsRow(
                currentSort = state.sort,
                filterCount = with(state.filters) { countries.size + sources.size + owners.size + levels.size },
                onSortChange = viewModel::setSort,
                onOpenSearch = onOpenSearch,
            )

            if (state.offline) {
                OfflineBanner("当前处于离线演示模式")
            }

            Box(Modifier.fillMaxSize()) {
                when {
                    state.initialLoading -> ListSkeleton(rows = 6)
                    state.error != null && state.customers.isEmpty() ->
                        ErrorState(message = state.error!!, onRetry = viewModel::refresh)
                    state.customers.isEmpty() -> EmptyState(
                        icon = Icons.Outlined.People,
                        title = "未找到客户",
                        description = "调整搜索条件，或点击右下角新增客户",
                        actionText = "新增客户",
                        onAction = onAddCustomer,
                    )
                    else -> CustomerListView(
                        state = state,
                        onCustomerClick = onCustomerClick,
                        onLoadMore = viewModel::loadMore,
                    )
                }
            }
        }
    }
}

@Composable
private fun CustomerListView(
    state: CustomerListUiState,
    onCustomerClick: (String) -> Unit,
    onLoadMore: () -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 96.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(state.customers, key = { it.id }) { customer ->
            CustomerCard(customer, onCustomerClick)
        }
        item(key = "footer") {
            Box(Modifier.fillMaxWidth().padding(vertical = 12.dp), contentAlignment = Alignment.Center) {
                when {
                    state.loadingMore -> Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                        Spacer(Modifier.width(8.dp))
                        Text("加载中…", style = MaterialTheme.typography.labelMedium)
                    }
                    state.endReached && state.customers.size > 4 ->
                        Text(
                            "已加载全部 ${state.totalCount} 个客户",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.outline,
                        )
                    else -> Spacer(Modifier.height(1.dp))
                }
                // 滚动到列表底部时触发加载下一页
                androidx.compose.runtime.LaunchedEffect(state.customers.size) {
                    if (!state.endReached && !state.loadingMore) onLoadMore()
                }
            }
        }
    }
}

@Composable
fun CustomerCard(customer: Customer, onClick: (String) -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick(customer.id) },
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            AvatarInitials(customer.name)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        customer.name,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f, fill = false),
                    )
                    Spacer(Modifier.width(6.dp))
                    LabelChip(customer.level.label.split(" ").first())
                }
                Spacer(Modifier.height(2.dp))
                Text(
                    customer.companyName,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Spacer(Modifier.height(4.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    LabelChip(customer.country)
                    LabelChip(customer.source.label)
                }
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    "最近联系",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.outline,
                )
                Text(
                    customer.lastContactAt?.let { TimeFormat.formatRelative(it) } ?: "—",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun CustomerCardPreview() {
    FusanheTheme {
        CustomerCard(
            customer = Customer(
                id = "p1", name = "John Smith", companyName = "Summit Foods LLC", country = "美国",
                source = com.fusanhe.crm.domain.model.CustomerSource.ALIBABA,
                level = com.fusanhe.crm.domain.model.CustomerLevel.A,
                ownerName = "张伟", lastContactAt = System.currentTimeMillis() - 3600_000L,
            ),
            onClick = {},
        )
    }
}
