import { render } from "@testing-library/react-native"

import { MineScreen } from "../src/screens/MineScreen"

describe("MineScreen", () => {
  it("groups account and system destinations without scoped settings", () => {
    const screen = render(<MineScreen openGlobalSettings={() => undefined} signOut={() => undefined} />)

    expect(screen.getByText("个人中心")).toBeTruthy()
    expect(screen.getByText("好友中心")).toBeTruthy()
    expect(screen.getByText("会员中心")).toBeTruthy()
    expect(screen.getByText("用户指南")).toBeTruthy()
    expect(screen.getByText("全局设置")).toBeTruthy()
    expect(screen.getByText("后台管理")).toBeTruthy()
    expect(screen.getByText("退出登录")).toBeTruthy()
    expect(screen.queryByText("学科设置")).toBeNull()
    expect(screen.queryByText("项目设置")).toBeNull()
  })
})
