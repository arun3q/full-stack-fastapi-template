import {
  Bot,
  Briefcase,
  Building2,
  CreditCard,
  Home,
  KeyRound,
  Rocket,
  ShieldCheck,
  Users,
  Webhook,
} from "lucide-react"
import { useTranslation } from "react-i18next"
import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { type Item, Main } from "./Main"
import { OrgSwitcher } from "./OrgSwitcher"
import { User } from "./User"

const baseItems: Item[] = [
  {
    icon: Home,
    titleKey: "app.dashboard",
    title: "Dashboard",
    path: "/dashboard",
  },
  {
    icon: Rocket,
    titleKey: "app.gettingStarted",
    title: "Getting started",
    path: "/onboarding",
  },
  { icon: Briefcase, titleKey: "app.items", title: "Items", path: "/items" },
  { icon: Users, titleKey: "app.members", title: "Members", path: "/members" },
  {
    icon: CreditCard,
    titleKey: "app.billing",
    title: "Billing",
    path: "/billing",
  },
  { icon: Bot, titleKey: "app.aiChat", title: "AI Chat", path: "/chat" },
  {
    icon: Building2,
    titleKey: "app.orgSettings",
    title: "Org settings",
    path: "/org-settings",
  },
  {
    icon: KeyRound,
    titleKey: "app.apiKeys",
    title: "API keys",
    path: "/api-keys",
  },
  {
    icon: Webhook,
    titleKey: "app.webhooks",
    title: "Webhooks",
    path: "/webhooks",
  },
  {
    icon: ShieldCheck,
    titleKey: "app.security",
    title: "Security",
    path: "/security",
  },
]

export function AppSidebar() {
  const { t } = useTranslation()
  const { user: currentUser } = useAuth()

  const translatedBase = baseItems.map((item) => ({
    ...item,
    title: t(item.titleKey ?? "app.dashboard"),
  }))
  const items = currentUser?.is_superuser
    ? [
        ...translatedBase,
        { icon: Users, title: t("app.admin"), path: "/admin" },
      ]
    : translatedBase

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-4 py-6 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
        <Logo variant="responsive" />
      </SidebarHeader>
      <SidebarContent>
        <OrgSwitcher />
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
