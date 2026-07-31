import { expect, test } from "@playwright/test"
import { firstSuperuser, firstSuperuserPassword } from "./config.ts"
import { logInUser } from "./utils/user"

test("Billing page shows plans and subscription section", async ({ page }) => {
  await logInUser(page, firstSuperuser, firstSuperuserPassword)
  await page.goto("/billing")

  await expect(page.getByRole("heading", { name: "Billing" })).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "Current subscription" }),
  ).toBeVisible()
})

test("Billing page lists plans", async ({ page }) => {
  await logInUser(page, firstSuperuser, firstSuperuserPassword)
  await page.goto("/billing")

  // The seeded plans are listed (Free, Pro, Business, Enterprise)
  await expect(page.getByText("Free", { exact: true })).toBeVisible()
  await expect(page.getByText("Pro", { exact: true })).toBeVisible()
})
