import { useEffect, useMemo, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"

import { Button } from "@/ui/components/ui/button"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useCompletePayoutBinding, useOpenMobilePayoutBinding } from "@/ui/queries/membership"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { formatMembershipApiError } from "@/views/membership/membershipUi"

export function WechatPayoutBindingPage() {
  const [searchParams] = useSearchParams()
  const bindingAttemptId = searchParams.get("attempt") ?? ""
  const state = searchParams.get("state") ?? ""
  const codeFromWechat = searchParams.get("code") ?? searchParams.get("authorizationCode") ?? ""
  const [authorizationCode, setAuthorizationCode] = useState(codeFromWechat)

  const openBinding = useOpenMobilePayoutBinding()
  const completeBinding = useCompletePayoutBinding()

  useEffect(() => {
    if (!bindingAttemptId || !state || openBinding.data || openBinding.isPending) return
    void openBinding.mutateAsync({ bindingAttemptId, state }).catch((err) => {
      showErrorFeedback("打开绑定失败", formatMembershipApiError(err))
    })
  }, [bindingAttemptId, state, openBinding])

  const payload = openBinding.data
  const accountLabel = useMemo(() => payload?.learningPyramidUserId ?? payload?.confirmedLearningPyramidUserId ?? "", [payload])

  async function confirmBinding() {
    if (!bindingAttemptId || !state || !authorizationCode.trim()) {
      showErrorFeedback("确认绑定失败", "缺少微信授权结果，请重新扫码。")
      return
    }
    try {
      await completeBinding.mutateAsync({
        bindingAttemptId,
        authorizationCode,
        state,
        confirmedLearningPyramidUserId: payload?.confirmedLearningPyramidUserId ?? accountLabel,
      })
      showSuccessFeedback("微信收款账号已绑定", "可以回到电脑页面继续提现。")
    } catch (err) {
      showErrorFeedback("确认绑定失败", formatMembershipApiError(err))
    }
  }

  return (
    <main className="min-h-screen bg-background px-5 py-10 text-foreground">
      <section className="mx-auto grid max-w-md gap-6">
        <div>
          <div className="text-sm text-muted-foreground">LearningPyramid</div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">绑定微信收款账号</h1>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">确认后，电脑端账号的邀请佣金会提现到当前微信。</p>
        </div>

        <div className="rounded-lg border bg-card p-5 shadow-sm">
          <div className="text-sm text-muted-foreground">将绑定到账号</div>
          <div className="mt-2 break-all text-base font-semibold">{accountLabel || "正在读取绑定信息..."}</div>
        </div>

        {!codeFromWechat && payload?.authorizationUrl && /^https?:\/\//i.test(payload.authorizationUrl) ? (
          <Button type="button" onClick={() => window.location.assign(payload.authorizationUrl ?? "")}>
            前往微信授权
          </Button>
        ) : null}

        {!codeFromWechat ? (
          <div className="grid gap-2">
            <Label htmlFor="wechat-binding-code">本地验收授权码</Label>
            <Input id="wechat-binding-code" value={authorizationCode} onChange={(event) => setAuthorizationCode(event.target.value)} />
          </div>
        ) : null}

        <Button type="button" onClick={() => void confirmBinding()} disabled={completeBinding.isPending || !payload}>
          {completeBinding.isPending ? "绑定中..." : "确认绑定"}
        </Button>

        <Link className="text-center text-sm text-muted-foreground hover:text-foreground" to="/membership">
          返回会员页面
        </Link>
      </section>
    </main>
  )
}
