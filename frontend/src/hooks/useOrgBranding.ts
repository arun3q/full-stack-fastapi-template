import { useQuery } from "@tanstack/react-query"
import { useEffect } from "react"

import type { Accent as ThemeAccent } from "@/components/theme-provider"
import { featureApi, getActiveOrgId } from "@/lib/featureApi"

type OrgBranding = {
  accent?: string
  logo_url?: string
}

function parseBranding(raw: string | null): OrgBranding | null {
  if (!raw) return null
  try {
    const parsed: unknown = JSON.parse(raw)
    return typeof parsed === "object" && parsed !== null
      ? (parsed as OrgBranding)
      : null
  } catch {
    return null
  }
}

export function useOrgBranding() {
  const { data } = useQuery({
    queryKey: ["organizations"],
    queryFn: featureApi.organizations,
  })

  const orgs = data?.data ?? []
  const orgId = getActiveOrgId() ?? orgs[0]?.id ?? null
  const active = orgs.find((org) => org.id === orgId) ?? orgs[0]
  const branding = parseBranding(active?.branding ?? null)

  useEffect(() => {
    const accent = branding?.accent
    const root = window.document.documentElement
    const valid = new Set<ThemeAccent>([
      "default",
      "teal",
      "rose",
      "amber",
      "violet",
    ])
    if (accent && valid.has(accent as ThemeAccent)) {
      root.dataset.accent = accent
    } else {
      delete root.dataset.accent
    }
  }, [branding?.accent])

  return { branding, organization: active }
}
