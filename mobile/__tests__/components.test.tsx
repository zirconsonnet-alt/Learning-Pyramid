import { AppButton } from "../src/components/AppButton"
import { EmptyState } from "../src/components/EmptyState"
import { LoadingState } from "../src/components/LoadingState"
import { renderWithProviders } from "../src/test/renderWithProviders"

describe("mobile base components", () => {
  it("renders concise loading and empty states", () => {
    const loading = renderWithProviders(<LoadingState label="加载中" />)
    expect(loading.getByText("加载中")).toBeTruthy()

    const empty = renderWithProviders(<EmptyState title="暂无内容" />)
    expect(empty.getByText("暂无内容")).toBeTruthy()
  })

  it("renders a button label without web-only elements", () => {
    const button = renderWithProviders(<AppButton label="进入" onPress={() => undefined} />)
    expect(button.getByText("进入")).toBeTruthy()
  })

  it("exposes disabled button state to accessibility", () => {
    const button = renderWithProviders(
      <AppButton disabled label="进入" onPress={() => undefined} />,
    )

    expect(button.toJSON()).toMatchObject({
      props: { accessibilityState: { disabled: true } },
    })
  })
})
