import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query"
import { createRouter, RouterProvider } from "@tanstack/react-router"
import { StrictMode } from "react"
import ReactDOM from "react-dom/client"
import { toast } from "sonner"
import { ApiError, OpenAPI } from "./client"
import { ThemeProvider } from "./components/theme-provider"
import { Toaster } from "./components/ui/sonner"
import { env } from "./lib/env"
import { clearTokens, configureOpenApi, refreshSession } from "./lib/featureApi"
import "./i18n"
import "./index.css"
import { routeTree } from "./routeTree.gen"

OpenAPI.BASE = env.VITE_API_URL
configureOpenApi()

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: handleApiError,
  }),
  mutationCache: new MutationCache({
    onError: handleApiError,
  }),
})

async function handleApiError(error: Error) {
  if (error instanceof ApiError && [401, 403].includes(error.status)) {
    // Silent recovery: try to rotate the refresh token before logging out.
    const refreshed = await refreshSession()
    if (refreshed) {
      queryClient.invalidateQueries()
      return
    }
    clearTokens()
    window.location.href = "/login"
    return
  }
  if (error instanceof ApiError) {
    const detail =
      typeof error.body === "object" &&
      error.body !== null &&
      "detail" in error.body
        ? String((error.body as { detail: unknown }).detail)
        : error.message
    toast.error(detail)
  }
}

const router = createRouter({ routeTree })
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
        <Toaster richColors closeButton />
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
)
