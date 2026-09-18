package com.fusanhe.crm.domain.repository

import com.fusanhe.crm.domain.model.Customer
import com.fusanhe.crm.domain.model.CustomerFilters
import com.fusanhe.crm.domain.model.CustomerHistoryItem
import com.fusanhe.crm.domain.model.CustomerSortOption
import com.fusanhe.crm.domain.model.NewCustomerInput
import kotlinx.coroutines.flow.Flow

interface CustomerRepository {
    fun observeCustomers(): Flow<List<Customer>>

    suspend fun searchCustomers(
        query: String,
        filters: CustomerFilters,
        sort: CustomerSortOption,
    ): Result<List<Customer>>

    suspend fun getCustomer(id: String): Result<Customer>

    suspend fun createCustomer(input: NewCustomerInput): Result<Customer>

    suspend fun updateCustomer(customer: Customer): Result<Customer>

    suspend fun getCustomerHistory(customerId: String): Result<List<CustomerHistoryItem>>

    /** 疑似重复客户检测（姓名/公司/邮箱/手机号相似） */
    suspend fun findPotentialDuplicates(input: NewCustomerInput): List<Customer>

    /** 手动刷新（演示模式可模拟网络失败） */
    suspend fun refresh(): Result<Unit>
}
