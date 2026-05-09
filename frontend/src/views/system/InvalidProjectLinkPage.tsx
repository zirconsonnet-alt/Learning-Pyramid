import { Link } from "react-router-dom"

import { ErrorNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"

export function InvalidProjectLinkPage() {
  return (
    <ErrorNotice
      title="项目链接已失效"
      message="这个链接不再是有效项目入口。请从学科中心重新进入项目。"
      action={
        <Button asChild>
          <Link to="/projects">返回学科中心</Link>
        </Button>
      }
    />
  )
}
