import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/_marketing/terms")({
  component: TermsPage,
  head: () => ({
    meta: [{ title: "Terms of Service - FastAPI Template" }],
  }),
})

function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="text-3xl font-bold tracking-tight">Terms of Service</h1>
      <div className="mt-6 space-y-4 text-sm leading-7 text-muted-foreground">
        <p>
          These terms outline the rules and regulations for the use of this
          application. This is a template document — replace it with your own
          Terms of Service before launching.
        </p>
        <p>
          By accessing or using the service, you agree to be bound by these
          terms. If you disagree with any part of the terms, you may not access
          the service.
        </p>
        <p>
          Contact us at{" "}
          <span className="text-foreground">support@example.com</span> for any
          questions about these terms.
        </p>
      </div>
    </div>
  )
}
