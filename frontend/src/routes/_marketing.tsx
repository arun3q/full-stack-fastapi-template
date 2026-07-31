import { createFileRoute, Outlet } from "@tanstack/react-router"

import { MarketingLayout } from "@/components/Marketing/MarketingLayout"

export const Route = createFileRoute("/_marketing")({
  component: MarketingRoute,
})

function MarketingRoute() {
  return (
    <MarketingLayout>
      <Outlet />
    </MarketingLayout>
  )
}
