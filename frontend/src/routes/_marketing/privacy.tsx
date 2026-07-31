import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/_marketing/privacy")({
  component: PrivacyPage,
  head: () => ({
    meta: [{ title: "Privacy Policy - FastAPI Template" }],
  }),
})

function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="text-3xl font-bold tracking-tight">Privacy Policy</h1>
      <div className="mt-6 space-y-4 text-sm leading-7 text-muted-foreground">
        <p>
          This privacy policy explains how data is collected, used and
          protected. This is a template document — replace it with your own
          Privacy Policy before launching.
        </p>
        <p>
          We only collect the information necessary to provide the service,
          including your account details and usage data. Your data is never sold
          to third parties.
        </p>
        <p>
          Contact us at{" "}
          <span className="text-foreground">support@example.com</span> for any
          privacy-related requests.
        </p>
      </div>
    </div>
  )
}
