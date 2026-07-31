import { z } from "zod"

const schema = z.object({
  VITE_API_URL: z.string().default(""),
})

export const env = schema.parse({
  VITE_API_URL: import.meta.env.VITE_API_URL ?? "",
})
