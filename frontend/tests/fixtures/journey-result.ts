import { test } from "@playwright/test"

export async function recordJourney<T>(journeyId: string, fn: () => Promise<T>): Promise<T> {
  return await test.step(`journey:${journeyId}`, fn)
}
