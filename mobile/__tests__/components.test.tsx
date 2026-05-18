import { render } from "@testing-library/react-native"

import { AppButton } from "../src/components/AppButton"
import { EmptyState } from "../src/components/EmptyState"
import { LoadingState } from "../src/components/LoadingState"

describe("mobile base components", () => {
  it("renders concise loading and empty states", () => {
    const loading = render(<LoadingState label="加载中" />)
    expect(loading.getByText("加载中")).toBeTruthy()

    const empty = render(<EmptyState title="暂无内容" />)
    expect(empty.getByText("暂无内容")).toBeTruthy()
  })

  it("renders a button label without web-only elements", () => {
    const button = render(<AppButton label="进入" onPress={() => undefined} />)
    expect(button.getByText("进入")).toBeTruthy()
  })
})
