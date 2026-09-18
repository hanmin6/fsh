package com.fusanhe.crm.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Forum
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.SpaceDashboard
import androidx.compose.material.icons.outlined.Forum
import androidx.compose.material.icons.outlined.People
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.SpaceDashboard
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.fusanhe.crm.domain.model.ThemeMode
import com.fusanhe.crm.ui.navigation.Routes
import com.fusanhe.crm.ui.screens.addcustomer.AddCustomerScreen
import com.fusanhe.crm.ui.screens.chat.ChatScreen
import com.fusanhe.crm.ui.screens.conversations.ConversationListScreen
import com.fusanhe.crm.ui.screens.customerdetail.CustomerDetailScreen
import com.fusanhe.crm.ui.screens.customersearch.CustomerSearchScreen
import com.fusanhe.crm.ui.screens.customers.CustomerListScreen
import com.fusanhe.crm.ui.screens.dashboard.DashboardScreen
import com.fusanhe.crm.ui.screens.login.LoginScreen
import com.fusanhe.crm.ui.screens.notifications.NotificationsScreen
import com.fusanhe.crm.ui.screens.profile.ProfileScreen
import com.fusanhe.crm.ui.screens.settings.SettingsScreen
import com.fusanhe.crm.ui.screens.splash.SplashScreen
import com.fusanhe.crm.ui.screens.settings.SettingsViewModel
import com.fusanhe.crm.ui.theme.FusanheTheme

private data class TopLevelDestination(
    val route: String,
    val label: String,
    val icon: ImageVector,
    val selectedIcon: ImageVector,
)

private val topLevelDestinations = listOf(
    TopLevelDestination(Routes.DASHBOARD, "工作台", Icons.Outlined.SpaceDashboard, Icons.Filled.SpaceDashboard),
    TopLevelDestination(Routes.CUSTOMERS, "客户", Icons.Outlined.People, Icons.Filled.People),
    TopLevelDestination(Routes.CONVERSATIONS, "询盘", Icons.Outlined.Forum, Icons.Filled.Forum),
    TopLevelDestination(Routes.PROFILE, "我的", Icons.Outlined.Person, Icons.Filled.Person),
)

fun NavHostController.navigateTopLevel(route: String) {
    navigate(route) {
        popUpTo(Routes.DASHBOARD) { saveState = true }
        launchSingleTop = true
        restoreState = true
    }
}

@Composable
fun FusanheApp(mainViewModel: MainViewModel = hiltViewModel()) {
    val settingsViewModel: SettingsViewModel = hiltViewModel()
    val themeMode by settingsViewModel.themeMode.collectAsStateWithLifecycle()
    val darkTheme = when (themeMode) {
        ThemeMode.SYSTEM -> isSystemInDarkTheme()
        ThemeMode.LIGHT -> false
        ThemeMode.DARK -> true
    }
    FusanheTheme(darkTheme = darkTheme) {
        val navController = rememberNavController()
        val backStackEntry by navController.currentBackStackEntryAsState()
        val currentRoute = backStackEntry?.destination?.route
        val showBottomBar = currentRoute in Routes.topLevel
        val unreadTotal by mainViewModel.unreadTotal.collectAsStateWithLifecycle()
        val isLoggedIn by mainViewModel.isLoggedIn.collectAsStateWithLifecycle()

        Scaffold(
            bottomBar = {
                if (showBottomBar) {
                    FusanheBottomBar(navController, currentRoute, unreadTotal)
                }
            },
        ) { padding ->
            NavHost(
                navController = navController,
                startDestination = Routes.SPLASH,
                modifier = Modifier.padding(padding),
            ) {
                composable(Routes.SPLASH) {
                    SplashScreen(isLoggedIn = isLoggedIn) { loggedIn ->
                        navController.navigate(if (loggedIn) Routes.DASHBOARD else Routes.LOGIN) {
                            popUpTo(0) { inclusive = true }
                        }
                    }
                }
                composable(Routes.LOGIN) {
                    LoginScreen(
                        onLoginSuccess = {
                            navController.navigate(Routes.DASHBOARD) {
                                popUpTo(0) { inclusive = true }
                            }
                        },
                    )
                }
                composable(Routes.DASHBOARD) {
                    DashboardScreen(
                        onAddCustomer = { navController.navigate(Routes.ADD_CUSTOMER) },
                        onCustomerClick = { id -> navController.navigate(Routes.customerDetail(id)) },
                        onConversationClick = { id -> navController.navigate(Routes.chat(id)) },
                        onConversationsTab = { navController.navigateTopLevel(Routes.CONVERSATIONS) },
                        onNotifications = { navController.navigate(Routes.NOTIFICATIONS) },
                    )
                }
                composable(Routes.CUSTOMERS) {
                    CustomerListScreen(
                        onAddCustomer = { navController.navigate(Routes.ADD_CUSTOMER) },
                        onCustomerClick = { id -> navController.navigate(Routes.customerDetail(id)) },
                        onOpenSearch = { navController.navigate(Routes.CUSTOMER_SEARCH) },
                    )
                }
                composable(Routes.ADD_CUSTOMER) {
                    AddCustomerScreen(
                        onSaved = { customerId ->
                            navController.navigate(Routes.customerDetail(customerId)) {
                                popUpTo(Routes.CUSTOMERS)
                            }
                        },
                        onBack = { navController.popBackStack() },
                    )
                }
                composable(Routes.CUSTOMER_DETAIL) {
                    CustomerDetailScreen(
                        onBack = { navController.popBackStack() },
                        onOpenConversation = { id -> navController.navigate(Routes.chat(id)) },
                    )
                }
                composable(Routes.CUSTOMER_SEARCH) {
                    CustomerSearchScreen(
                        onBack = { navController.popBackStack() },
                        onCustomerClick = { id -> navController.navigate(Routes.customerDetail(id)) },
                    )
                }
                composable(Routes.CONVERSATIONS) {
                    ConversationListScreen(
                        onConversationClick = { id -> navController.navigate(Routes.chat(id)) },
                    )
                }
                composable(Routes.CHAT) {
                    ChatScreen(
                        onBack = { navController.popBackStack() },
                        onCustomerDetail = { id -> navController.navigate(Routes.customerDetail(id)) },
                    )
                }
                composable(Routes.NOTIFICATIONS) {
                    NotificationsScreen(
                        onBack = { navController.popBackStack() },
                        onOpenConversation = { id -> navController.navigate(Routes.chat(id)) },
                        onOpenCustomer = { id -> navController.navigate(Routes.customerDetail(id)) },
                    )
                }
                composable(Routes.PROFILE) {
                    ProfileScreen(
                        onOpenSettings = { navController.navigate(Routes.SETTINGS) },
                        onOpenNotifications = { navController.navigate(Routes.NOTIFICATIONS) },
                        onLogout = {
                            navController.navigate(Routes.LOGIN) {
                                popUpTo(0) { inclusive = true }
                            }
                        },
                    )
                }
                composable(Routes.SETTINGS) {
                    SettingsScreen(onBack = { navController.popBackStack() })
                }
            }
        }
    }
}

@Composable
private fun FusanheBottomBar(
    navController: NavHostController,
    currentRoute: String?,
    unreadTotal: Int,
) {
    NavigationBar {
        topLevelDestinations.forEach { destination ->
            val selected = currentRoute == destination.route
            NavigationBarItem(
                selected = selected,
                onClick = { navController.navigateTopLevel(destination.route) },
                icon = {
                    if (destination.route == Routes.CONVERSATIONS && unreadTotal > 0) {
                        BadgedBox(badge = { Badge { Text("$unreadTotal") } }) {
                            Icon(
                                if (selected) destination.selectedIcon else destination.icon,
                                contentDescription = destination.label,
                            )
                        }
                    } else {
                        Icon(
                            if (selected) destination.selectedIcon else destination.icon,
                            contentDescription = destination.label,
                        )
                    }
                },
                label = {
                    Text(
                        destination.label,
                        fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal,
                    )
                },
            )
        }
    }
}
