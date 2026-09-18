package com.fusanhe.crm.domain.usecase

import com.fusanhe.crm.domain.model.CustomerField
import com.fusanhe.crm.domain.model.NewCustomerInput
import javax.inject.Inject

/**
 * 新增客户表单校验。
 * 返回字段 -> 错误提示；为空表示全部通过。
 */
class ValidateNewCustomerUseCase @Inject constructor() {

    operator fun invoke(input: NewCustomerInput): Map<CustomerField, String> {
        val errors = mutableMapOf<CustomerField, String>()
        if (input.name.isBlank()) errors[CustomerField.NAME] = "请填写客户姓名"
        if (input.companyName.isBlank()) errors[CustomerField.COMPANY] = "请填写公司名称"
        if (input.country.isBlank()) errors[CustomerField.COUNTRY] = "请选择国家或地区"
        if (input.source == null) errors[CustomerField.SOURCE] = "请选择客户来源"
        input.email.takeIf { it.isNotBlank() }?.let {
            if (!EMAIL_REGEX.matches(it.trim())) errors[CustomerField.EMAIL] = "邮箱格式不正确"
        }
        input.phone.takeIf { it.isNotBlank() }?.let {
            if (!PHONE_REGEX.matches(it.trim())) errors[CustomerField.PHONE] = "手机号格式不正确（6-15 位数字，可带 + 和 -）"
        }
        input.whatsapp.takeIf { it.isNotBlank() }?.let {
            if (!PHONE_REGEX.matches(it.trim())) errors[CustomerField.WHATSAPP] = "WhatsApp 号码格式不正确"
        }
        return errors
    }

    companion object {
        private val EMAIL_REGEX = Regex("^[A-Za-z0-9+_.\\-]+@[A-Za-z0-9\\-]+(\\.[A-Za-z0-9\\-]+)+$")
        private val PHONE_REGEX = Regex("^\\+?[0-9][0-9\\-]{5,17}$")
    }
}
