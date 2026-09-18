package com.fusanhe.crm.domain.usecase

import com.fusanhe.crm.domain.model.Customer
import com.fusanhe.crm.domain.model.NewCustomerInput
import com.fusanhe.crm.domain.repository.CustomerRepository
import javax.inject.Inject

/**
 * 疑似重复客户检测：
 * 公司名或姓名完全一致、或邮箱/手机号/WhatsApp 一致即视为疑似重复。
 */
class DetectDuplicateCustomerUseCase @Inject constructor(
    private val customerRepository: CustomerRepository,
) {
    suspend operator fun invoke(input: NewCustomerInput): List<Customer> =
        customerRepository.findPotentialDuplicates(input)
}
