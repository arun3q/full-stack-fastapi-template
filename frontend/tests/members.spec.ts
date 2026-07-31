import { expect, test } from "@playwright/test"
import { firstSuperuser, firstSuperuserPassword } from "./config.ts"
import { logInUser } from "./utils/user"

test("Members page shows invite form", async ({ page }) => {
  await logInUser(page, firstSuperuser, firstSuperuserPassword)
  await page.goto("/members")

  await expect(page.getByRole("heading", { name: "Members" })).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "Invite a member" }),
  ).toBeVisible()
  await expect(page.getByTestId("invite-email")).toBeVisible()
})

test("Members page lists the organization", async ({ page }) => {
  await logInUser(page, firstSuperuser, firstSuperuserPassword)
  await page.goto("/members")
  await expect(page.getByRole("heading", { name: /Members \(/ })).toBeVisible()
})
