import { describe, expect, it } from "vitest"
import { envSchema } from "@/lib/env"

describe("env schema", () => {
  it("defaults VITE_API_URL to an empty string", () => {
    const parsed = envSchema.parse({})
    expect(parsed.VITE_API_URL).toBe("")
  })

  it("parses a configured VITE_API_URL", () => {
    const parsed = envSchema.parse({ VITE_API_URL: "https://api.example.com" })
    expect(parsed.VITE_API_URL).toBe("https://api.example.com")
  })
})
