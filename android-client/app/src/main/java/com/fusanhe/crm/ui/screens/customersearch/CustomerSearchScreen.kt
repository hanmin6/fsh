package com.fusanhe.crm.ui.screens.customersearch

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.fusanhe.crm.data.mock.MockData
import com.fusanhe.crm.domain.model.CustomerLevel
import com.fusanhe.crm.domain.model.CustomerSortOption
import com.fusanhe.crm.domain.model.CustomerSource
import com.fusanhe.crm.ui.components.EmptyState
import com.fusanhe.crm.ui.components.ErrorState
import com.fusanhe.crm.ui.screens.customers.CustomerCard

/**
 * 搜索和筛选页：按国家、来源、负责人、客户等级筛选 + 排序 + 实时结果。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CustomerSearchScreen(
    onBack: () -> Unit,
    onCustomerClick: (String) -> Unit,
    viewModel: CustomerSearchViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("搜索和筛选") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    TextButton(onClick = viewModel::clearAll) { Text("重置") }
                },
            )
        },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            Column(
                Modifier
                    .weight(0.52f)
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 16.dp),
            ) {
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
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))

                FilterSection("国家或地区") {
                    listOf("美国", "德国", "英国", "西班牙", "墨西哥", "澳大利亚", "日本", "阿联酋", "加拿大", "法国", "荷兰").forEach { country ->
                        FilterChip(
                            selected = country in state.filters.countries,
                            onClick = { viewModel.toggleCountry(country) },
                            label = { Text(country) },
                        )
                    }
                }
                FilterSection("客户来源") {
                    CustomerSource.entries.forEach { source ->
                        FilterChip(
                            selected = source in state.filters.sources,
                            onClick = { viewModel.toggleSource(source) },
                            label = { Text(source.label) },
                        )
                    }
                }
                FilterSection("负责人") {
                    MockData.owners.forEach { owner ->
                        FilterChip(
                            selected = owner in state.filters.owners,
                            onClick = { viewModel.toggleOwner(owner) },
                            label = { Text(owner) },
                        )
                    }
                }
                FilterSection("客户等级") {
                    CustomerLevel.entries.forEach { level ->
                        FilterChip(
                            selected = level in state.filters.levels,
                            onClick = { viewModel.toggleLevel(level) },
                            label = { Text(level.label.split(" ").first()) },
                        )
                    }
                }
                FilterSection("排序") {
                    CustomerSortOption.entries.forEach { option ->
                        FilterChip(
                            selected = state.sort == option,
                            onClick = { viewModel.setSort(option) },
                            label = { Text(option.label) },
                        )
                    }
                }
                Spacer(Modifier.height(8.dp))
            }

            // 搜索结果
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    if (state.searching) "搜索中…" else "找到 ${state.results.size} 个客户",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                if (state.searching) {
                    CircularProgressIndicator(modifier = Modifier.height(16.dp), strokeWidth = 2.dp)
                }
            }
            Column(Modifier.weight(0.48f)) {
                when {
                    state.error != null -> ErrorState(message = state.error!!, onRetry = viewModel::retry)
                    !state.searching && state.results.isEmpty() -> EmptyState(
                        icon = Icons.Outlined.Search,
                        title = "没有匹配的客户",
                        description = "尝试调整关键词或筛选条件",
                    )
                    else -> LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(
                            start = 16.dp, end = 16.dp, bottom = 16.dp,
                        ),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        items(state.results, key = { it.id }) { customer ->
                            CustomerCard(customer, onCustomerClick)
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun FilterSection(
    title: String,
    content: @Composable () -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth().padding(bottom = 10.dp),
    ) {
        Column(Modifier.padding(12.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(6.dp))
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                content()
            }
        }
    }
}
