package com.fusanhe.crm.ui.screens.customersearch

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fusanhe.crm.data.mock.MockModeController
import com.fusanhe.crm.domain.model.Customer
import com.fusanhe.crm.domain.model.CustomerFilters
import com.fusanhe.crm.domain.model.CustomerLevel
import com.fusanhe.crm.domain.model.CustomerSortOption
import com.fusanhe.crm.domain.model.CustomerSource
import com.fusanhe.crm.domain.repository.CustomerRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class CustomerSearchUiState(
    val query: String = "",
    val filters: CustomerFilters = CustomerFilters(),
    val sort: CustomerSortOption = CustomerSortOption.LAST_CONTACT_DESC,
    val results: List<Customer> = emptyList(),
    val searching: Boolean = false,
    val error: String? = null,
)

@OptIn(FlowPreview::class)
@HiltViewModel
class CustomerSearchViewModel @Inject constructor(
    private val customerRepository: CustomerRepository,
    private val mode: MockModeController,
) : ViewModel() {

    private val _state = MutableStateFlow(CustomerSearchUiState())
    val state: StateFlow<CustomerSearchUiState> = _state.asStateFlow()

    private var searchJob: Job? = null

    init {
        runSearch()
    }

    fun onQueryChange(query: String) {
        _state.update { it.copy(query = query) }
        restartSearch()
    }

    fun toggleCountry(country: String) = _state.update {
        val set = it.filters.countries.toMutableSet()
        if (!set.remove(country)) set.add(country)
        it.copy(filters = it.filters.copy(countries = set))
    }.also { restartSearch() }

    fun toggleSource(source: CustomerSource) = _state.update {
        val set = it.filters.sources.toMutableSet()
        if (!set.remove(source)) set.add(source)
        it.copy(filters = it.filters.copy(sources = set))
    }.also { restartSearch() }

    fun toggleOwner(owner: String) = _state.update {
        val set = it.filters.owners.toMutableSet()
        if (!set.remove(owner)) set.add(owner)
        it.copy(filters = it.filters.copy(owners = set))
    }.also { restartSearch() }

    fun toggleLevel(level: CustomerLevel) = _state.update {
        val set = it.filters.levels.toMutableSet()
        if (!set.remove(level)) set.add(level)
        it.copy(filters = it.filters.copy(levels = set))
    }.also { restartSearch() }

    fun setSort(sort: CustomerSortOption) = _state.update {
        it.copy(sort = sort)
    }.also { restartSearch() }

    fun clearAll() = _state.update {
        it.copy(query = "", filters = CustomerFilters(), sort = CustomerSortOption.LAST_CONTACT_DESC)
    }.also { restartSearch() }

    fun retry() = runSearch()

    private fun restartSearch() {
        searchJob?.cancel()
        searchJob = viewModelScope.launch {
            delay(250)
            runSearch()
        }
    }

    private fun runSearch() {
        searchJob?.cancel()
        searchJob = viewModelScope.launch {
            _state.update { it.copy(searching = true, error = null) }
            val current = _state.value
            customerRepository.searchCustomers(current.query, current.filters, current.sort)
                .onSuccess { results ->
                    _state.update { it.copy(results = results, searching = false) }
                }
                .onFailure { e ->
                    _state.update {
                        it.copy(searching = false, error = e.message ?: "搜索失败", results = emptyList())
                    }
                }
        }
    }
}
