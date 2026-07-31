import { Link } from "@tanstack/react-router"
import { Moon, Sun } from "lucide-react"
import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { Logo } from "@/components/Common/Logo"
import { useTheme } from "@/components/theme-provider"
import { Button } from "@/components/ui/button"
import { isLoggedIn } from "@/hooks/useAuth"
import { featureApi, type PublicConfig } from "@/lib/featureApi"

interface MarketingLayoutProps {
  children: React.ReactNode
}

export function MarketingLayout({ children }: MarketingLayoutProps) {
  const { resolvedTheme, setTheme } = useTheme()
  const { t } = useTranslation()
  const [config, setConfig] = useState<PublicConfig | null>(null)

  useEffect(() => {
    featureApi
      .publicConfig()
      .then(setConfig)
      .catch(() => setConfig(null))
  }, [])

  const projectName = config?.project_name ?? "FastAPI Template"
  const loggedIn = isLoggedIn()

  return (
    <div className="flex min-h-svh flex-col bg-background">
      <header className="sticky top-0 z-20 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
          <Link to="/" className="flex items-center gap-2">
            <Logo variant="responsive" asLink={false} className="h-6" />
          </Link>
          <nav className="hidden items-center gap-6 text-sm text-muted-foreground md:flex">
            <Link to="/" className="hover:text-foreground">
              {t("nav.features")}
            </Link>
            <Link to="/pricing" className="hover:text-foreground">
              {t("nav.pricing")}
            </Link>
            <Link to="/terms" className="hover:text-foreground">
              {t("nav.terms")}
            </Link>
            <Link to="/privacy" className="hover:text-foreground">
              {t("nav.privacy")}
            </Link>
          </nav>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              aria-label="Toggle theme"
              onClick={() =>
                setTheme(resolvedTheme === "dark" ? "light" : "dark")
              }
            >
              {resolvedTheme === "dark" ? (
                <Sun className="size-4" />
              ) : (
                <Moon className="size-4" />
              )}
            </Button>
            {loggedIn ? (
              <Button asChild>
                <Link to="/dashboard">{t("nav.openApp")}</Link>
              </Button>
            ) : (
              <>
                <Button variant="outline" asChild>
                  <Link to="/login">{t("nav.signIn")}</Link>
                </Button>
                <Button asChild>
                  <Link to="/signup">{t("nav.getStarted")}</Link>
                </Button>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1">{children}</main>

      <footer className="border-t py-10">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 text-sm text-muted-foreground md:flex-row">
          <p>
            © {new Date().getFullYear()} {projectName}. All rights reserved.
          </p>
          <div className="flex items-center gap-4">
            <Link to="/terms" className="hover:text-foreground">
              {t("nav.terms")}
            </Link>
            <Link to="/privacy" className="hover:text-foreground">
              {t("nav.privacy")}
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
