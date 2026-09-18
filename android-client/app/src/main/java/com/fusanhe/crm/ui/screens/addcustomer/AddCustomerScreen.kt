package com.fusanhe.crm.ui.screens.addcustomer

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Check
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.fusanhe.crm.domain.model.CustomerField
import com.fusanhe.crm.domain.model.CustomerLevel
import com.fusanhe.crm.domain.model.CustomerSource
import com.fusanhe.crm.ui.components.ConfirmDialog
import com.fusanhe.crm.ui.components.InfoRow
import com.fusanhe.crm.ui.theme.FusanheTheme

/**
 * 新增客户：四步表单（基本信息 → 联系方式 → 商务信息 → 确认保存），
 * 必填校验 + 格式校验 + 疑似重复提示 + 保存状态反馈。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddCustomerScreen(
    onSaved: (String) -> Unit,
    onBack: () -> Unit,
    viewModel: AddCustomerViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(state.errorMessage) {
        state.errorMessage?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.consumeError()
        }
    }
    LaunchedEffect(state.savedCustomerId) {
        state.savedCustomerId?.let(onSaved)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("新增客户") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = "返回")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .imePadding(),
        ) {
            StepperHeader(state.step)
            Column(
                Modifier
                    .weight(1f)
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 16.dp),
            ) {
                when (state.step) {
                    AddCustomerStep.BASIC -> BasicStep(viewModel, state)
                    AddCustomerStep.CONTACT -> ContactStep(viewModel, state)
                    AddCustomerStep.BUSINESS -> BusinessStep(viewModel, state)
                    AddCustomerStep.CONFIRM -> ConfirmStep(state)
                }
                Spacer(Modifier.height(24.dp))
            }
            BottomActions(
                state = state,
                onPrevious = viewModel::previousStep,
                onNext = viewModel::nextStep,
            )
        }
    }

    if (state.duplicateDialog.isNotEmpty()) {
        ConfirmDialog(
            title = "发现疑似重复客户",
            text = "以下客户信息与当前填写内容相似，可能为同一客户：\n" +
                state.duplicateDialog.joinToString("\n") { "· ${it.name}（${it.companyName}，${it.country}）" } +
                "\n\n是否仍然保存为新的客户？",
            confirmText = "仍要保存",
            dismissText = "返回修改",
            onConfirm = viewModel::confirmSaveAnyway,
            onDismiss = viewModel::dismissDuplicateDialog,
        )
    }
}

@Composable
private fun StepperHeader(step: AddCustomerStep) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        AddCustomerStep.entries.forEachIndexed { index, s ->
            if (index > 0) {
                Box(
                    Modifier
                        .weight(1f)
                        .height(2.dp)
                        .background(
                            if (index <= step.ordinal) MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.surfaceVariant
                        ),
                )
            }
            val reached = index <= step.ordinal
            val isCurrent = index == step.ordinal
            Box(
                modifier = Modifier
                    .size(if (isCurrent) 26.dp else 22.dp)
                    .clip(CircleShape)
                    .background(
                        when {
                            index < step.ordinal -> MaterialTheme.colorScheme.primaryContainer
                            reached -> MaterialTheme.colorScheme.primary
                            else -> MaterialTheme.colorScheme.surfaceVariant
                        }
                    ),
                contentAlignment = Alignment.Center,
            ) {
                if (index < step.ordinal) {
                    Icon(
                        Icons.Outlined.Check,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.onPrimaryContainer,
                        modifier = Modifier.size(14.dp),
                    )
                } else {
                    Text(
                        "${index + 1}",
                        style = MaterialTheme.typography.labelSmall,
                        color = if (reached) Color.White else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Spacer(Modifier.width(4.dp))
            Text(
                s.label,
                style = MaterialTheme.typography.labelSmall,
                fontWeight = if (isCurrent) FontWeight.SemiBold else FontWeight.Normal,
                color = if (reached) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun BottomActions(
    state: AddCustomerUiState,
    onPrevious: () -> Unit,
    onNext: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surface)
            .padding(horizontal = 16.dp, vertical = 10.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (state.step != AddCustomerStep.BASIC) {
            TextButton(onClick = onPrevious, enabled = !state.saving) { Text("上一步") }
        }
        Spacer(Modifier.weight(1f))
        Button(onClick = onNext, enabled = !state.saving) {
            if (state.saving) {
                CircularProgressIndicator(
                    modifier = Modifier.size(18.dp),
                    strokeWidth = 2.dp,
                    color = MaterialTheme.colorScheme.onPrimary,
                )
                Spacer(Modifier.width(8.dp))
            }
            Text(if (state.step == AddCustomerStep.CONFIRM) "确认保存" else "下一步")
        }
    }
}

// ---------- 步骤一：基本信息 ----------

@Composable
private fun BasicStep(viewModel: AddCustomerViewModel, state: AddCustomerUiState) {
    FormTextField(
        label = "客户姓名 *",
        value = state.name,
        onValueChange = viewModel::onNameChange,
        error = state.fieldErrors[CustomerField.NAME],
    )
    FormTextField(
        label = "公司名称 *",
        value = state.companyName,
        onValueChange = viewModel::onCompanyChange,
        error = state.fieldErrors[CustomerField.COMPANY],
    )
    DropdownField(
        label = "国家或地区 *",
        options = viewModel.countries,
        selected = state.country.ifEmpty { null },
        onSelected = viewModel::onCountryChange,
        error = state.fieldErrors[CustomerField.COUNTRY],
    )
    DropdownField(
        label = "客户来源 *",
        options = CustomerSource.entries.toList(),
        selected = state.source,
        optionLabel = { it.label },
        onSelected = viewModel::onSourceChange,
        error = state.fieldErrors[CustomerField.SOURCE],
    )
}

// ---------- 步骤二：联系方式 ----------

@Composable
private fun ContactStep(viewModel: AddCustomerViewModel, state: AddCustomerUiState) {
    Text(
        "以下字段均为选填，但填写后有助于AI更精准地回复客户",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    Spacer(Modifier.height(8.dp))
    FormTextField(
        label = "邮箱",
        value = state.email,
        onValueChange = viewModel::onEmailChange,
        error = state.fieldErrors[CustomerField.EMAIL],
        keyboardType = KeyboardType.Email,
    )
    FormTextField(
        label = "手机号",
        value = state.phone,
        onValueChange = viewModel::onPhoneChange,
        error = state.fieldErrors[CustomerField.PHONE],
        keyboardType = KeyboardType.Phone,
    )
    FormTextField(
        label = "WhatsApp",
        value = state.whatsapp,
        onValueChange = viewModel::onWhatsappChange,
        error = state.fieldErrors[CustomerField.WHATSAPP],
        keyboardType = KeyboardType.Phone,
    )
    FormTextField(
        label = "阿里国际站账号",
        value = state.alibabaId,
        onValueChange = viewModel::onAlibabaIdChange,
    )
    FormTextField(
        label = "Made-in-China 账号",
        value = state.madeInChinaId,
        onValueChange = viewModel::onMadeInChinaIdChange,
    )
    FormTextField(
        label = "职位",
        value = state.jobTitle,
        onValueChange = viewModel::onJobTitleChange,
    )
}

// ---------- 步骤三：商务信息 ----------

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun BusinessStep(viewModel: AddCustomerViewModel, state: AddCustomerUiState) {
    Text("感兴趣的产品", style = MaterialTheme.typography.bodyMedium)
    Spacer(Modifier.height(6.dp))
    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        viewModel.productPresets.forEach { product ->
            FilterChip(
                selected = product in state.interestedProducts,
                onClick = { viewModel.toggleProduct(product) },
                label = { Text(product) },
            )
        }
    }
    if (state.interestedProducts.isNotEmpty()) {
        Spacer(Modifier.height(6.dp))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            state.interestedProducts.forEach {
                com.fusanhe.crm.ui.components.LabelChip(it)
            }
        }
    }
    Spacer(Modifier.height(8.dp))
    OutlinedTextField(
        value = state.customProduct,
        onValueChange = viewModel::onCustomProductChange,
        label = { Text("添加自定义产品") },
        singleLine = true,
        trailingIcon = {
            TextButton(onClick = viewModel::addCustomProduct, enabled = state.customProduct.isNotBlank()) {
                Text("添加")
            }
        },
        modifier = Modifier.fillMaxWidth(),
    )

    Spacer(Modifier.height(12.dp))
    DropdownField(
        label = "客户等级",
        options = CustomerLevel.entries.toList(),
        selected = state.level,
        optionLabel = { it.label },
        onSelected = viewModel::onLevelChange,
    )
    DropdownField(
        label = "负责人",
        options = viewModel.owners,
        selected = state.ownerName.ifEmpty { null },
        onSelected = viewModel::onOwnerChange,
    )

    Spacer(Modifier.height(12.dp))
    Text("标签", style = MaterialTheme.typography.bodyMedium)
    Spacer(Modifier.height(6.dp))
    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        viewModel.tagPresets.forEach { tag ->
            FilterChip(
                selected = tag in state.tags,
                onClick = { viewModel.toggleTag(tag) },
                label = { Text(tag) },
            )
        }
    }

    Spacer(Modifier.height(12.dp))
    OutlinedTextField(
        value = state.notes,
        onValueChange = viewModel::onNotesChange,
        label = { Text("备注") },
        minLines = 3,
        modifier = Modifier.fillMaxWidth(),
    )
}

// ---------- 步骤四：确认摘要 ----------

@Composable
private fun ConfirmStep(state: AddCustomerUiState) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(Modifier.padding(16.dp)) {
            Text("基本信息", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(6.dp))
            InfoRow("客户姓名", state.name)
            InfoRow("公司名称", state.companyName)
            InfoRow("国家/地区", state.country)
            InfoRow("客户来源", state.source?.label ?: "—")
            Spacer(Modifier.height(10.dp))
            Text("联系方式", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(6.dp))
            InfoRow("邮箱", state.email.ifBlank { "—" })
            InfoRow("手机号", state.phone.ifBlank { "—" })
            InfoRow("WhatsApp", state.whatsapp.ifBlank { "—" })
            InfoRow("阿里账号", state.alibabaId.ifBlank { "—" })
            InfoRow("MIC 账号", state.madeInChinaId.ifBlank { "—" })
            Spacer(Modifier.height(10.dp))
            Text("商务信息", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(6.dp))
            InfoRow("感兴趣产品", state.interestedProducts.joinToString("、").ifEmpty { "—" })
            InfoRow("客户等级", state.level.label)
            InfoRow("负责人", state.ownerName.ifBlank { "默认（当前登录人）" })
            InfoRow("标签", state.tags.joinToString("、").ifEmpty { "—" })
            if (state.notes.isNotBlank()) {
                InfoRow("备注", state.notes)
            }
        }
    }
    Spacer(Modifier.height(10.dp))
    Text(
        "保存后可在客户详情中继续完善资料；当前为演示模式，数据仅保存在本机内存中。",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

// ---------- 通用表单控件 ----------

@Composable
private fun FormTextField(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    error: String? = null,
    keyboardType: KeyboardType = KeyboardType.Text,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = { Text(label) },
        isError = error != null,
        supportingText = error?.let { { Text(it) } },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = keyboardType),
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun <T> DropdownField(
    label: String,
    options: List<T>,
    selected: T?,
    onSelected: (T) -> Unit,
    error: String? = null,
    optionLabel: (T) -> String = { it.toString() },
) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = it },
        modifier = Modifier.padding(vertical = 4.dp),
    ) {
        OutlinedTextField(
            value = selected?.let(optionLabel) ?: "",
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            isError = error != null,
            supportingText = error?.let { { Text(it) } },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier
                .fillMaxWidth()
                .menuAnchor(MenuAnchorType.PrimaryNotEditable),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { option ->
                DropdownMenuItem(
                    text = { Text(optionLabel(option)) },
                    onClick = {
                        onSelected(option)
                        expanded = false
                    },
                )
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun AddCustomerPreview() {
    FusanheTheme {
        Text("AddCustomerScreen preview", Modifier.padding(16.dp))
    }
}
