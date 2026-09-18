package com.fusanhe.crm.data.mock

import com.fusanhe.crm.domain.model.Customer
import com.fusanhe.crm.domain.model.CustomerLevel
import com.fusanhe.crm.domain.model.CustomerSource

/** 演示用客户数据：12 个客户，覆盖不同国家、来源、等级、负责人 */
internal object MockCustomers {

    val all: List<Customer> by lazy { build() }

    private fun build(): List<Customer> = listOf(
        Customer(
            id = "cus01", name = "John Smith", companyName = "Summit Foods LLC", country = "美国",
            email = "john.smith@summitfoods.com", phone = "+1 415 555 0132", whatsapp = "+1 415 555 0132",
            alibabaId = "summitfoods", jobTitle = "采购总监",
            interestedProducts = listOf("冻结蓝莓", "冻干草莓"),
            source = CustomerSource.ALIBABA, level = CustomerLevel.A, ownerName = "张伟",
            tags = listOf("重点客户", "二次返单"),
            notes = "美国西部连锁超市供应商，每年 2 次大额采购，重视 BRC 认证。",
            lastContactAt = minutesAgo(35), createdAt = daysAgo(210),
        ),
        Customer(
            id = "cus02", name = "Anna Müller", companyName = "Bavaria Food Trading GmbH", country = "德国",
            email = "a.mueller@bavariafood.de", phone = "+49 89 555 2210",
            alibabaId = "bavariafood", jobTitle = "进口经理",
            interestedProducts = listOf("苹果脆片", "槐花蜂蜜"),
            source = CustomerSource.EMAIL, level = CustomerLevel.B, ownerName = "李娜",
            tags = listOf("认证关注"),
            notes = "对 HALAL / ISO22000 认证非常关注，习惯邮件沟通。",
            lastContactAt = hoursAgo(3), createdAt = daysAgo(160),
        ),
        Customer(
            id = "cus03", name = "Carlos García", companyName = "Distribuidora García S.A. de C.V.", country = "墨西哥",
            email = "carlos@garciadist.com.mx", phone = "+52 55 5555 3411", whatsapp = "+52 55 5555 3411",
            jobTitle = "总经理",
            interestedProducts = listOf("番茄酱 28-30%", "浓缩橙汁"),
            source = CustomerSource.ALIBABA, level = CustomerLevel.B, ownerName = "张伟",
            tags = listOf("价格敏感"),
            notes = "西班牙语客户，对价格敏感，需要西语沟通。",
            lastContactAt = minutesAgo(95), createdAt = daysAgo(88),
        ),
        Customer(
            id = "cus04", name = "María López", companyName = "Grupo Alimentario López", country = "西班牙",
            email = "maria.lopez@galopez.es", phone = "+34 91 555 7788",
            jobTitle = "采购经理",
            interestedProducts = listOf("浓缩橙汁", "速冻菠菜"),
            source = CustomerSource.EXHIBITION, level = CustomerLevel.A, ownerName = "李娜",
            tags = listOf("大客户", "展会线索"),
            notes = "2026 上海 FHC 展会认识，计划年度框架采购。",
            lastContactAt = hoursAgo(20), createdAt = daysAgo(120),
        ),
        Customer(
            id = "cus05", name = "James Wilson", companyName = "Wilson & Sons Trading", country = "英国",
            email = "james@wilsonsons.co.uk", phone = "+44 20 5555 6620",
            jobTitle = "合伙人",
            interestedProducts = listOf("槐花蜂蜜"),
            source = CustomerSource.MADE_IN_CHINA, level = CustomerLevel.C, ownerName = "王强",
            tags = listOf("新客户"),
            notes = "英国蜂蜜进口商，先要样品测试。",
            lastContactAt = daysAgo(2), createdAt = daysAgo(45),
        ),
        Customer(
            id = "cus06", name = "Sophie Bernard", companyName = "Bernard Import France", country = "法国",
            email = "sophie@bernardimport.fr", phone = "+33 1 5555 9012",
            jobTitle = "品类经理",
            interestedProducts = listOf("冻干草莓", "果蔬脆片"),
            source = CustomerSource.INDEPENDENT_SITE, level = CustomerLevel.B, ownerName = "张伟",
            tags = listOf(),
            notes = "官网表单询盘，客户语言为法语，可用英语沟通。",
            lastContactAt = hoursAgo(28), createdAt = daysAgo(60),
        ),
        Customer(
            id = "cus07", name = "Jack Thompson", companyName = "Outback Fresh Imports", country = "澳大利亚",
            email = "jack@outbackfresh.com.au", phone = "+61 2 5555 4477", whatsapp = "+61 412 555 447",
            jobTitle = "Director",
            interestedProducts = listOf("冻结蓝莓"),
            source = CustomerSource.WHATSAPP, level = CustomerLevel.C, ownerName = "王强",
            tags = listOf("价格敏感"),
            notes = "复购客户，经常通过 WhatsApp 直接催价。",
            lastContactAt = minutesAgo(25), createdAt = daysAgo(300),
        ),
        Customer(
            id = "cus08", name = "佐藤 健一", companyName = "Sato Trading Co., Ltd.", country = "日本",
            email = "sato@satorading.co.jp", phone = "+81 3 5555 8890",
            jobTitle = "海外采购课长",
            interestedProducts = listOf("脱水大蒜粉", "速冻菠菜"),
            source = CustomerSource.EXHIBITION, level = CustomerLevel.B, ownerName = "李娜",
            tags = listOf("认证关注"),
            notes = "对农残检测报告要求严格，需要日文或英文文件。",
            lastContactAt = hoursAgo(26), createdAt = daysAgo(150),
        ),
        Customer(
            id = "cus09", name = "Ahmed Al-Mansoori", companyName = "Gulf Foodstuff Trading LLC", country = "阿联酋",
            email = "ahmed@gulffood.ae", phone = "+971 4 555 3320", whatsapp = "+971 50 555 3320",
            alibabaId = "gulffood", jobTitle = "Owner",
            interestedProducts = listOf("槐花蜂蜜", "混合坚果"),
            source = CustomerSource.ALIBABA, level = CustomerLevel.A, ownerName = "张伟",
            tags = listOf("重点客户", "大客户"),
            notes = "迪拜经销商，关注 HALAL 认证与迪拜展会。",
            lastContactAt = minutesAgo(50), createdAt = daysAgo(180),
        ),
        Customer(
            id = "cus10", name = "Emily Carter", companyName = "Maple Import Foods", country = "加拿大",
            email = "emily@mapleimport.ca", phone = "+1 604 555 7781",
            jobTitle = "Procurement Specialist",
            interestedProducts = listOf("冻干草莓"),
            source = CustomerSource.EMAIL, level = CustomerLevel.C, ownerName = "李娜",
            tags = listOf(),
            notes = "零售小包装需求，量待确认。",
            lastContactAt = daysAgo(3), createdAt = daysAgo(30),
        ),
        Customer(
            id = "cus11", name = "Linda van Dijk", companyName = "Van Dijk Food Services B.V.", country = "荷兰",
            email = "linda@vandijkfoods.nl", phone = "+31 20 555 1123",
            jobTitle = "Inkoopadviseur",
            interestedProducts = listOf("番茄酱 28-30%", "速冻菠菜"),
            source = CustomerSource.INDEPENDENT_SITE, level = CustomerLevel.B, ownerName = "王强",
            tags = listOf("二次返单"),
            notes = "鹿特丹港提货，物流由客户指定货代。",
            lastContactAt = minutesAgo(40), createdAt = daysAgo(240),
        ),
        Customer(
            id = "cus12", name = "Oliver Brown", companyName = "Brown Brothers Wholesale", country = "英国",
            email = "oliver@brownbros.co.uk", phone = "+44 161 555 9021",
            jobTitle = "Buyer",
            interestedProducts = listOf("混合坚果"),
            source = CustomerSource.MANUAL, level = CustomerLevel.D, ownerName = "张伟",
            tags = listOf(),
            notes = "展会后电话跟进过一次，意向一般。",
            lastContactAt = daysAgo(6), createdAt = daysAgo(20),
        ),
    )
}
