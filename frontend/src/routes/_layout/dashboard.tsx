import { createFileRoute } from "@tanstack/react-router"
import { useTranslation } from "react-i18next"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/dashboard")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: "Dashboard - FastAPI Template",
      },
    ],
  }),
})

function Dashboard() {
  const { t } = useTranslation()
  const { user: currentUser } = useAuth()

  return (
    <div>
      <div>
        <h1 className="text-2xl truncate max-w-sm">
          {t("dashboard.greeting", {
            name: currentUser?.full_name || currentUser?.email,
          })}
        </h1>
        <p className="text-muted-foreground">{t("dashboard.welcome")}</p>
      </div>
    </div>
  )
}
