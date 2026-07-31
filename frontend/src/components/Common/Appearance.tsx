import { Languages, Monitor, Moon, Sun } from "lucide-react"
import { useTranslation } from "react-i18next"

import {
  ACCENTS,
  type Accent,
  type Theme,
  useTheme,
} from "@/components/theme-provider"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

const ACCENT_SWATCHES: Record<Accent, string> = {
  default: "bg-primary",
  teal: "bg-teal-500",
  rose: "bg-rose-500",
  amber: "bg-amber-500",
  violet: "bg-violet-500",
}

type LucideIcon = React.FC<React.SVGProps<SVGSVGElement>>

const ICON_MAP: Record<Theme, LucideIcon> = {
  system: Monitor,
  light: Sun,
  dark: Moon,
}

function AccentPicker() {
  const { accent, setAccent } = useTheme()
  const { t } = useTranslation()

  return (
    <>
      <DropdownMenuSeparator />
      <DropdownMenuLabel className="text-xs text-muted-foreground">
        {t("appearance.accent")}
      </DropdownMenuLabel>
      <div className="flex gap-1.5 px-2 py-1.5">
        {ACCENTS.map((candidate) => (
          <button
            key={candidate}
            type="button"
            data-testid={`accent-${candidate}`}
            onClick={() => setAccent(candidate)}
            aria-label={`Accent ${candidate}`}
            className={`size-5 rounded-full border border-border ${ACCENT_SWATCHES[candidate]} ${
              accent === candidate
                ? "ring-2 ring-ring ring-offset-2 ring-offset-background"
                : ""
            }`}
          />
        ))}
      </div>
    </>
  )
}

function LanguagePicker() {
  const { t, i18n } = useTranslation()

  const switchTo = (lang: string) => {
    i18n.changeLanguage(lang)
  }

  return (
    <>
      <DropdownMenuSeparator />
      <DropdownMenuLabel className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Languages className="size-3.5" />
        {t("appearance.language")}
      </DropdownMenuLabel>
      <div className="grid grid-cols-2 gap-1 px-2 py-1.5">
        <button
          type="button"
          data-testid="lang-en"
          onClick={() => switchTo("en")}
          className={`rounded-md px-2 py-1 text-sm hover:bg-accent ${
            i18n.resolvedLanguage?.startsWith("en") ? "bg-accent" : ""
          }`}
        >
          English
        </button>
        <button
          type="button"
          data-testid="lang-es"
          onClick={() => switchTo("es")}
          className={`rounded-md px-2 py-1 text-sm hover:bg-accent ${
            i18n.resolvedLanguage?.startsWith("es") ? "bg-accent" : ""
          }`}
        >
          Español
        </button>
      </div>
    </>
  )
}

export const SidebarAppearance = () => {
  const { isMobile } = useSidebar()
  const { setTheme, theme } = useTheme()
  const { t } = useTranslation()
  const Icon = ICON_MAP[theme]

  return (
    <SidebarMenuItem>
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <SidebarMenuButton tooltip="Appearance" data-testid="theme-button">
            <Icon className="size-4 text-muted-foreground" />
            <span>{t("appearance.appearance")}</span>
            <span className="sr-only">Toggle theme</span>
          </SidebarMenuButton>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          side={isMobile ? "top" : "right"}
          align="end"
          className="w-(--radix-dropdown-menu-trigger-width) min-w-56"
        >
          <DropdownMenuItem
            data-testid="light-mode"
            onClick={() => setTheme("light")}
          >
            <Sun className="mr-2 h-4 w-4" />
            {t("appearance.light")}
          </DropdownMenuItem>
          <DropdownMenuItem
            data-testid="dark-mode"
            onClick={() => setTheme("dark")}
          >
            <Moon className="mr-2 h-4 w-4" />
            {t("appearance.dark")}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setTheme("system")}>
            <Monitor className="mr-2 h-4 w-4" />
            {t("appearance.system")}
          </DropdownMenuItem>
          <AccentPicker />
          <LanguagePicker />
        </DropdownMenuContent>
      </DropdownMenu>
    </SidebarMenuItem>
  )
}

export const Appearance = () => {
  const { setTheme } = useTheme()
  const { t } = useTranslation()

  return (
    <div className="flex items-center justify-center">
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <Button data-testid="theme-button" variant="outline" size="icon">
            <Sun className="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
            <Moon className="absolute h-[1.2rem] w-[1.2rem] rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
            <span className="sr-only">Toggle theme</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            data-testid="light-mode"
            onClick={() => setTheme("light")}
          >
            <Sun className="mr-2 h-4 w-4" />
            {t("appearance.light")}
          </DropdownMenuItem>
          <DropdownMenuItem
            data-testid="dark-mode"
            onClick={() => setTheme("dark")}
          >
            <Moon className="mr-2 h-4 w-4" />
            {t("appearance.dark")}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setTheme("system")}>
            <Monitor className="mr-2 h-4 w-4" />
            {t("appearance.system")}
          </DropdownMenuItem>
          <AccentPicker />
          <LanguagePicker />
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
