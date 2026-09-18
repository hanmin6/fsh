package com.fusanhe.crm.domain.model

/** 客户来源渠道 */
enum class CustomerSource(val label: String) {
    ALIBABA("Alibaba"),
    MADE_IN_CHINA("Made-in-China"),
    INDEPENDENT_SITE("独立站"),
    EMAIL("Email"),
    WHATSAPP("WhatsApp"),
    EXHIBITION("展会"),
    MANUAL("手工录入"),
    OTHER("其他"),
}

/** 客户等级 */
enum class CustomerLevel(val label: String) {
    A("A · 重点客户"),
    B("B · 普通客户"),
    C("C · 潜在客户"),
    D("D · 观察客户"),
}

/**
 * 客户领域模型。
 * 独立于 EspoCRM 的 Account/Contact 原始 JSON，由各 Repository 负责映射。
 */
data class Customer(
    val id: String,
    val name: String,
    val companyName: String,
    val country: String,
    val email: String? = null,
    val phone: String? = null,
    val whatsapp: String? = null,
    val alibabaId: String? = null,
    val madeInChinaId: String? = null,
    val jobTitle: String? = null,
    val interestedProducts: List<String> = emptyList(),
    val source: CustomerSource,
    val level: CustomerLevel,
    val ownerName: String,
    val tags: List<String> = emptyList(),
    val notes: String? = null,
    val lastContactAt: Long? = null,
    val createdAt: Long = 0L,
)

/** 新增客户表单输入 */
data class NewCustomerInput(
    val name: String = "",
    val companyName: String = "",
    val country: String = "",
    val source: CustomerSource? = null,
    val email: String = "",
    val phone: String = "",
    val whatsapp: String = "",
    val alibabaId: String = "",
    val madeInChinaId: String = "",
    val jobTitle: String = "",
    val interestedProducts: List<String> = emptyList(),
    val level: CustomerLevel = CustomerLevel.C,
    val ownerName: String = "",
    val tags: List<String> = emptyList(),
    val notes: String = "",
)

/** 表单可校验的字段 */
enum class CustomerField { NAME, COMPANY, COUNTRY, SOURCE, EMAIL, PHONE, WHATSAPP }

/** 客户列表筛选条件 */
data class CustomerFilters(
    val countries: Set<String> = emptySet(),
    val sources: Set<CustomerSource> = emptySet(),
    val owners: Set<String> = emptySet(),
    val levels: Set<CustomerLevel> = emptySet(),
) {
    val isDefault: Boolean
        get() = countries.isEmpty() && sources.isEmpty() && owners.isEmpty() && levels.isEmpty()
}

enum class CustomerSortOption(val label: String) {
    LAST_CONTACT_DESC("最近联系"),
    CREATED_DESC("创建时间"),
    LEVEL("客户等级"),
}
