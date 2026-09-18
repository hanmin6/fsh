package com.fusanhe.crm.ui.screens.customers

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fusanhe.crm.data.mock.MockModeController
import com.fusanhe.crm.domain.model.Customer
import com.fusanhe.crm.domain.model.CustomerFilters
import com.fusanhe.crm.domain.model.CustomerSortOption
import com.fusanhe.crm.domain.repository.CustomerRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class CustomerListUiState(
    val customers: List<Customer> = emptyList(),
    val totalCount: Int = 0,
    val query: String = "",
    val filters: CustomerFilters = CustomerFilters(),
    val sort: CustomerSortOption = CustomerSortOption.LAST_CONTACT_DESC,
    val initialLoading: Boolean = true,
    val refreshing: Boolean = false,
    val loadingMore: Boolean = false,
    val endReached: Boolean = false,
    val error: String? = null,
    val offline: Boolean = false,
)

@HiltViewModel
class CustomerListViewModel @Inject constructor(
    private val customerRepository: CustomerRepository,
    private val mode: MockModeController,
) : ViewModel() {

    private val _state = MutableStateFlow(CustomerListUiState())
    val state: StateFlow<CustomerListUiState> = _state.asStateFlow()

    private var allCache: List<Customer> = emptyList()
    private var page = 0
    private var searchJob: Job? = null

    init {
        viewModelScope.launch {
            delay(800) // 模拟首次加载
            customerRepository.observeCustomers().collect { all ->
                allCache = all
                applyAndPaginate()
                _state.update {
                    it.copy(initialLoading = false, error = null, offline = mode.flags.value.offline)
                }
            }
        }
    }

    fun refresh() {
        if (_state.value.refreshing) return
        viewModelScope.launch {
            _state.update { it.copy(refreshing = true, error = null) }
            customerRepository.refresh()
                .onFailure { e ->
                    _state.update {
                        it.copy(
                            refreshing = false,
                            error = e.message ?: "刷新失败",
                            offline = mode.flags.value.offline,
                        )
                    }
                }
                .onSuccess {
                    _state.update { it.copy(refreshing = false, offline = mode.flags.value.offline) }
                }
        }
    }

    fun onQueryChange(query: String) {
        _state.update { it.copy(query = query) }
        searchJob?.cancel()
        searchJob = viewModelScope.launch {
            delay(300)
            applyAndPaginate()
        }
    }

    fun applyFilters(filters: CustomerFilters) {
        _state.update { it.copy(filters = filters) }
        applyAndPaginate()
    }

    fun setSort(sort: CustomerSortOption) {
        _state.update { it.copy(sort = sort) }
        applyAndPaginate()
    }

    fun loadMore() {
        val current = _state.value
        if (current.loadingMore || current.endReached || current.initialLoading) return
        viewModelScope.launch {
            _state.update { it.copy(loadingMore = true) }
            delay(500) // 模拟分页请求
            page += 1
            val filteredList = filtered()
            val nextVisible = filteredList.take((page + 1) * PAGE_SIZE)
            _state.update {
                it.copy(
                    customers = nextVisible,
                    totalCount = filteredList.size,
                    loadingMore = false,
                    endReached = nextVisible.size >= filteredList.size,
                )
            }
        }
    }

    private fun applyAndPaginate() {
        page = 0
        val filteredList = filtered()
        _state.update {
            it.copy(
                customers = filteredList.take(PAGE_SIZE),
                totalCount = filteredList.size,
                endReached = filteredList.size <= PAGE_SIZE,
                loadingMore = false,
            )
        }
    }

    private fun filtered(): List<Customer> {
        val current = _state.value
        val q = current.query.trim().lowercase()
        return allCache.asSequence()
            .filter { c -> current.filters.countries.isEmpty() || c.country in current.filters.countries }
            .filter { c -> current.filters.sources.isEmpty() || c.source in current.filters.sources }
            .filter { c -> current.filters.owners.isEmpty() || c.ownerName in current.filters.owners }
            .filter { c -> current.filters.levels.isEmpty() || c.level in current.filters.levels }
            .filter { c ->
                q.isEmpty() ||
                    c.name.lowercase().contains(q) ||
                    c.companyName.lowercase().contains(q) ||
                    (c.email?.lowercase()?.contains(q) == true) ||
                    (c.phone?.contains(q) == true) ||
                    (c.whatsapp?.contains(q) == true)
            }
            .sortedWith(
                when (current.sort) {
                    CustomerSortOption.LAST_CONTACT_DESC ->
                        compareByDescending<Customer> { it.lastContactAt ?: 0L }
                    CustomerSortOption.CREATED_DESC -> compareByDescending { it.createdAt }
                    CustomerSortOption.LEVEL -> compareBy { it.level.ordinal }
                }
            )
            .toList()
    }

    companion object {
        const val PAGE_SIZE = 8
    }
}
