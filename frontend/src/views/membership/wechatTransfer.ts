type WeixinBridgeInvokeResult = {
  err_msg?: string
  errMsg?: string
}

type WeixinBridge = {
  invoke: (name: string, params: Record<string, string>, callback: (result?: WeixinBridgeInvokeResult) => void) => void
}

export type WechatMerchantTransferConfirmation = {
  mchId: string
  appId: string
  packageInfo: string
}

function getWeixinBridge() {
  return typeof window !== "undefined"
    ? (window as unknown as { WeixinJSBridge?: WeixinBridge }).WeixinJSBridge
    : undefined
}

async function waitForWeixinBridge(timeoutMs = 1500) {
  const existing = getWeixinBridge()
  if (existing?.invoke || typeof window === "undefined" || typeof document === "undefined") {
    return existing
  }
  return await new Promise<WeixinBridge | undefined>((resolve) => {
    const onReady = () => {
      cleanup()
      resolve(getWeixinBridge())
    }
    const cleanup = () => {
      window.clearTimeout(timer)
      document.removeEventListener("WeixinJSBridgeReady", onReady)
    }
    const timer = window.setTimeout(() => {
      cleanup()
      resolve(getWeixinBridge())
    }, timeoutMs)
    document.addEventListener("WeixinJSBridgeReady", onReady, false)
  })
}

function isSuccessfulInvokeResult(result: WeixinBridgeInvokeResult | undefined) {
  const raw = String(result?.err_msg ?? result?.errMsg ?? "").trim().toLowerCase()
  if (!raw) return true
  return raw === "ok" || raw.endsWith(":ok")
}

export async function requestWechatMerchantTransfer(confirmation: WechatMerchantTransferConfirmation) {
  const bridge = await waitForWeixinBridge()
  if (!bridge?.invoke) {
    return {
      ok: false,
      message: "当前浏览器不支持微信收款确认，请在微信客户端中打开后继续。",
    }
  }
  const result = await new Promise<WeixinBridgeInvokeResult | undefined>((resolve) => {
    bridge.invoke(
      "requestMerchantTransfer",
      {
        mchId: confirmation.mchId,
        appId: confirmation.appId,
        package: confirmation.packageInfo,
      },
      (payload) => resolve(payload),
    )
  })
  if (!isSuccessfulInvokeResult(result)) {
    return {
      ok: false,
      message: "微信收款确认没有完成，请在微信里确认后再返回。",
    }
  }
  return { ok: true, message: "" }
}

export function readWithdrawalConfirmationToken(confirmationUrl: string | null | undefined) {
  const raw = String(confirmationUrl || "").trim()
  if (!raw) return ""
  try {
    return new URL(raw, typeof window === "undefined" ? "https://example.invalid" : window.location.origin).searchParams.get("token") ?? ""
  } catch {
    return ""
  }
}
