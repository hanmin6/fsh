package com.fusanhe.crm.data.repository

import com.fusanhe.crm.data.mock.MockData
import com.fusanhe.crm.data.mock.MockModeController
import com.fusanhe.crm.data.mock.now
import com.fusanhe.crm.domain.model.Customer
import com.fusanhe.crm.domain.model.CustomerFilters
import com.fusanhe.crm.domain.model.CustomerHistoryItem
import com.fusanhe.crm.domain.model.CustomerSortOption
import com.fusanhe.crm.domain.model.HistoryStatus
import com.fusanhe.crm.domain.model.HistoryType
import com.fusanhe.crm.domain.model.NewCustomerInput
import com.fusanhe.crm.domain.repository.CustomerRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.io.IOException
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 客户仓库 Mock 实现：数据保存在内存中，后续可无缝替换为真实 API 实现。
 */
@Singleton
class MockCustomerRepository @Inject constructor(
    private val mode: MockModeController,
) : CustomerRepository {

    private val _customers = MutableStateFlow(MockData.customers)
    override fun observeCustomers(): Flow<List<Customer>> = _customers.asStateFlow()

    private val _history = MutableStateFlow(MockData.history)

    private suspend fun guard(): Boolean {
        delay(300)
        val flags = mode.flags.value
        return flags.networkFailure || flags.offline
    }

    override suspend fun searchCustomers(
        query: String,
        filters: CustomerFilters,
        sort: CustomerSortOption,
    ): Result<List<Customer>> {
        if (guard()) return Result.failure(IOException("网络连接失败（演示模式）"))
        val q = query.trim().lowercase()
        val list = _customers.value.asSequence()
            .filter { c ->
                filters.countries.isEmpty() || c.country in filters.countries
            }
            .filter { c -> filters.sources.isEmpty() || c.source in filters.sources }
            .filter { c -> filters.owners.isEmpty() || c.ownerName in filters.owners }
            .filter { c -> filters.levels.isEmpty() || c.level in filters.levels }
            .filter { c ->
                q.isEmpty() ||
                    c.name.lowercase().contains(q) ||
                    c.companyName.lowercase().contains(q) ||
                    (c.email?.lowercase()?.contains(q) == true) ||
                    (c.phone?.contains(q) == true) ||
                    (c.whatsapp?.contains(q) == true)
            }
            .sortedWith(
                when (sort) {
                    CustomerSortOption.LAST_CONTACT_DESC ->
                        compareByDescending<Customer> { it.lastContactAt ?: 0L }
                    CustomerSortOption.CREATED_DESC -> compareByDescending { it.createdAt }
                    CustomerSortOption.LEVEL -> compareBy { it.level.ordinal }
                }
            )
            .toList()
        return Result.success(list)
    }

    override suspend fun getCustomer(id: String): Result<Customer> {
        if (guard()) return Result.failure(IOException("网络连接失败（演示模式）"))
        val customer = _customers.value.firstOrNull { it.id == id }
            ?: return Result.failure(IOException("客户不存在"))
        return Result.success(customer)
    }

    override suspend fun createCustomer(input: NewCustomerInput): Result<Customer> {
        delay(900)
        val flags = mode.flags.value
        if (flags.saveCustomerFailure || flags.offline) {
            return Result.failure(IOException("保存失败，请重试（演示模式）"))
        }
        val customer = Customer(
            id = "cus_${UUID.randomUUID().toString().take(8)}",
            name = input.name.trim(),
            companyName = input.companyName.trim(),
            country = input.country.trim(),
            email = input.email.trim().ifEmpty { null },
            phone = input.phone.trim().ifEmpty { null },
            whatsapp = input.whatsapp.trim().ifEmpty { null },
            alibabaId = input.alibabaId.trim().ifEmpty { null },
            madeInChinaId = input.madeInChinaId.trim().ifEmpty { null },
            jobTitle = input.jobTitle.trim().ifEmpty { null },
            interestedProducts = input.interestedProducts,
            source = input.source ?: return Result.failure(IllegalStateException("缺少客户来源")),
            level = input.level,
            ownerName = input.ownerName.ifBlank { MockData.currentUser.name },
            tags = input.tags,
            notes = input.notes.trim().ifEmpty { null },
            lastContactAt = now(),
            createdAt = now(),
        )
        _customers.update { listOf(customer) + it }
        _history.update {
            listOf(
                CustomerHistoryItem(
                    id = "his_${UUID.randomUUID().toString().take(8)}",
                    customerId = customer.id,
                    type = HistoryType.PROFILE_UPDATE,
                    title = "新增客户",
                    content = "由 ${customer.ownerName} 在移动端创建客户档案。",
                    actorName = customer.ownerName,
                    status = HistoryStatus.INFO,
                    occurredAt = now(),
                )
            ) + it
        }
        return Result.success(customer)
    }

    override suspend fun updateCustomer(customer: Customer): Result<Customer> {
        delay(600)
        val flags = mode.flags.value
        if (flags.saveCustomerFailure || flags.offline) {
            return Result.failure(IOException("保存失败，请重试（演示模式）"))
        }
        var updated = false
        _customers.update { list ->
            list.map { if (it.id == customer.id) { updated = true; customer } else it }
        }
        return if (updated) Result.success(customer)
        else Result.failure(IOException("客户不存在"))
    }

    override suspend fun getCustomerHistory(customerId: String): Result<List<CustomerHistoryItem>> {
        if (guard()) return Result.failure(IOException("网络连接失败（演示模式）"))
        delay(350)
        val list = _history.value
            .filter { it.customerId == customerId }
            .sortedByDescending { it.occurredAt }
        return Result.success(list)
    }

    override suspend fun findPotentialDuplicates(input: NewCustomerInput): List<Customer> {
        delay(400)
        val name = input.name.trim().lowercase()
        val company = input.companyName.trim().lowercase()
        val email = input.email.trim().lowercase()
        val phone = input.phone.trim().replace(" ", "")
        val whatsapp = input.whatsapp.trim().replace(" ", "")
        return _customers.value.filter { c ->
            c.name.lowercase() == name ||
                c.companyName.lowercase() == company ||
                (email.isNotEmpty() && c.email?.lowercase() == email) ||
                (phone.isNotEmpty() && c.phone?.replace(" ", "") == phone) ||
                (whatsapp.isNotEmpty() && c.whatsapp?.replace(" ", "") == whatsapp)
        }
    }

    override suspend fun refresh(): Result<Unit> {
        if (guard()) return Result.failure(IOException("网络连接失败（演示模式）"))
        delay(500)
        return Result.success(Unit)
    }
}
