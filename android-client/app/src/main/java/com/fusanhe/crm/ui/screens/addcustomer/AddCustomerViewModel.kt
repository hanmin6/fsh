package com.fusanhe.crm.ui.screens.addcustomer

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fusanhe.crm.data.mock.MockData
import com.fusanhe.crm.domain.model.Customer
import com.fusanhe.crm.domain.model.CustomerField
import com.fusanhe.crm.domain.model.CustomerLevel
import com.fusanhe.crm.domain.model.CustomerSource
import com.fusanhe.crm.domain.model.NewCustomerInput
import com.fusanhe.crm.domain.repository.CustomerRepository
import com.fusanhe.crm.domain.usecase.DetectDuplicateCustomerUseCase
import com.fusanhe.crm.domain.usecase.ValidateNewCustomerUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

/** 新增客户分步表单的步骤 */
enum class AddCustomerStep(val label: String) {
    BASIC("基本信息"),
    CONTACT("联系方式"),
    BUSINESS("商务信息"),
    CONFIRM("确认保存"),
}

data class AddCustomerUiState(
    val step: AddCustomerStep = AddCustomerStep.BASIC,
    // 步骤一：基本信息（必填）
    val name: String = "",
    val companyName: String = "",
    val country: String = "",
    val source: CustomerSource? = null,
    // 步骤二：联系方式（选填）
    val email: String = "",
    val phone: String = "",
    val whatsapp: String = "",
    val alibabaId: String = "",
    val madeInChinaId: String = "",
    val jobTitle: String = "",
    // 步骤三：商务信息（选填）
    val interestedProducts: List<String> = emptyList(),
    val customProduct: String = "",
    val level: CustomerLevel = CustomerLevel.C,
    val ownerName: String = "",
    val tags: List<String> = emptyList(),
    val notes: String = "",
    // 状态
    val fieldErrors: Map<CustomerField, String> = emptyMap(),
    val duplicateDialog: List<Customer> = emptyList(),
    val saving: Boolean = false,
    val errorMessage: String? = null,
    val savedCustomerId: String? = null,
) {
    fun toInput(): NewCustomerInput = NewCustomerInput(
        name = name, companyName = companyName, country = country, source = source,
        email = email, phone = phone, whatsapp = whatsapp,
        alibabaId = alibabaId, madeInChinaId = madeInChinaId, jobTitle = jobTitle,
        interestedProducts = interestedProducts, level = level,
        ownerName = ownerName, tags = tags, notes = notes,
    )
}

@HiltViewModel
class AddCustomerViewModel @Inject constructor(
    private val customerRepository: CustomerRepository,
    private val validate: ValidateNewCustomerUseCase,
    private val detectDuplicates: DetectDuplicateCustomerUseCase,
) : ViewModel() {

    private val _state = MutableStateFlow(AddCustomerUiState())
    val state: StateFlow<AddCustomerUiState> = _state.asStateFlow()

    val countries: List<String> = MockData.countries
    val owners: List<String> = MockData.owners
    val tagPresets: List<String> = MockData.tagPresets
    val productPresets: List<String> = MockData.productPresets

    fun onNameChange(v: String) = _state.update { it.copy(name = v, fieldErrors = it.fieldErrors - CustomerField.NAME) }
    fun onCompanyChange(v: String) = _state.update { it.copy(companyName = v, fieldErrors = it.fieldErrors - CustomerField.COMPANY) }
    fun onCountryChange(v: String) = _state.update { it.copy(country = v, fieldErrors = it.fieldErrors - CustomerField.COUNTRY) }
    fun onSourceChange(v: CustomerSource) = _state.update { it.copy(source = v, fieldErrors = it.fieldErrors - CustomerField.SOURCE) }
    fun onEmailChange(v: String) = _state.update { it.copy(email = v, fieldErrors = it.fieldErrors - CustomerField.EMAIL) }
    fun onPhoneChange(v: String) = _state.update { it.copy(phone = v, fieldErrors = it.fieldErrors - CustomerField.PHONE) }
    fun onWhatsappChange(v: String) = _state.update { it.copy(whatsapp = v, fieldErrors = it.fieldErrors - CustomerField.WHATSAPP) }
    fun onAlibabaIdChange(v: String) = _state.update { it.copy(alibabaId = v) }
    fun onMadeInChinaIdChange(v: String) = _state.update { it.copy(madeInChinaId = v) }
    fun onJobTitleChange(v: String) = _state.update { it.copy(jobTitle = v) }
    fun onLevelChange(v: CustomerLevel) = _state.update { it.copy(level = v) }
    fun onOwnerChange(v: String) = _state.update { it.copy(ownerName = v) }
    fun onNotesChange(v: String) = _state.update { it.copy(notes = v) }
    fun onCustomProductChange(v: String) = _state.update { it.copy(customProduct = v) }

    fun toggleProduct(product: String) = _state.update {
        val list = it.interestedProducts.toMutableList()
        if (!list.remove(product)) list.add(product)
        it.copy(interestedProducts = list)
    }

    fun addCustomProduct() = _state.update {
        val value = it.customProduct.trim()
        if (value.isEmpty() || it.interestedProducts.contains(value)) {
            it.copy(customProduct = "")
        } else {
            it.copy(interestedProducts = it.interestedProducts + value, customProduct = "")
        }
    }

    fun toggleTag(tag: String) = _state.update {
        val list = it.tags.toMutableList()
        if (!list.remove(tag)) list.add(tag)
        it.copy(tags = list)
    }

    fun nextStep() {
        val current = _state.value
        val stepFields: Set<CustomerField> = when (current.step) {
            AddCustomerStep.BASIC -> setOf(CustomerField.NAME, CustomerField.COMPANY, CustomerField.COUNTRY, CustomerField.SOURCE)
            AddCustomerStep.CONTACT -> setOf(CustomerField.EMAIL, CustomerField.PHONE, CustomerField.WHATSAPP)
            AddCustomerStep.BUSINESS -> emptySet()
            AddCustomerStep.CONFIRM -> emptySet()
        }
        val errors = validate(current.toInput()).filterKeys { it in stepFields }
        if (errors.isNotEmpty()) {
            _state.update { it.copy(fieldErrors = errors) }
            return
        }
        if (current.step == AddCustomerStep.CONFIRM) {
            submit()
        } else {
            _state.update {
                it.copy(step = AddCustomerStep.entries[it.step.ordinal + 1], fieldErrors = emptyMap())
            }
        }
    }

    fun previousStep() = _state.update {
        if (it.step == AddCustomerStep.BASIC) {
            it
        } else {
            it.copy(step = AddCustomerStep.entries[it.step.ordinal - 1], fieldErrors = emptyMap())
        }
    }

    fun dismissDuplicateDialog() = _state.update { it.copy(duplicateDialog = emptyList()) }

    fun confirmSaveAnyway() {
        _state.update { it.copy(duplicateDialog = emptyList()) }
        doSave()
    }

    private fun submit() {
        viewModelScope.launch {
            val duplicates = detectDuplicates(_state.value.toInput())
            if (duplicates.isNotEmpty()) {
                _state.update { it.copy(duplicateDialog = duplicates) }
            } else {
                doSave()
            }
        }
    }

    private fun doSave() {
        if (_state.value.saving) return // 防止重复提交
        viewModelScope.launch {
            _state.update { it.copy(saving = true, errorMessage = null) }
            customerRepository.createCustomer(_state.value.toInput())
                .onSuccess { customer ->
                    _state.update { it.copy(saving = false, savedCustomerId = customer.id) }
                }
                .onFailure { e ->
                    _state.update {
                        it.copy(saving = false, errorMessage = e.message ?: "保存失败，请重试")
                    }
                }
        }
    }

    fun consumeError() = _state.update { it.copy(errorMessage = null) }
}
