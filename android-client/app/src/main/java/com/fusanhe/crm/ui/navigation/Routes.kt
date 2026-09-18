package com.fusanhe.crm.ui.navigation

/** 路由定义 */
object Routes {
    const val SPLASH = "splash"
    const val LOGIN = "login"
    const val DASHBOARD = "dashboard"
    const val CUSTOMERS = "customers"
    const val ADD_CUSTOMER = "add_customer"
    const val CUSTOMER_DETAIL = "customer/{customerId}"
    const val CUSTOMER_SEARCH = "customer_search"
    const val CONVERSATIONS = "conversations"
    const val CHAT = "chat/{conversationId}"
    const val NOTIFICATIONS = "notifications"
    const val PROFILE = "profile"
    const val SETTINGS = "settings"

    fun customerDetail(customerId: String) = "customer/$customerId"
    fun chat(conversationId: String) = "chat/$conversationId"

    /** 底部导航的四个主入口 */
    val topLevel = listOf(DASHBOARD, CUSTOMERS, CONVERSATIONS, PROFILE)
}
