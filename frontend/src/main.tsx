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
  // 401: attempt a single-flight silent refresh before logging out.
  if (error instanceof ApiError && error.status === 401) {
    if (!refreshPromise) {
      refreshPromise = refreshSession().finally(() => {
        refreshPromise = null
      })
    }
    const refreshed = await refreshPromise
    if (refreshed) {
      queryClient.invalidateQueries()
      return
    }
    clearTokens()
    window.location.href = "/login"
    return
  }
  // 403: tenant/permission changed — refetch, don't enter a refresh loop.
  if (error instanceof ApiError && error.status === 403) {
    queryClient.invalidateQueries()
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

let refreshPromise: Promise<boolean> | null = null

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
